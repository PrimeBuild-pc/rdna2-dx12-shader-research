"""Phase 2O cycle O3: controlled ablation of the material texture samples in Render Color.

Dose-response, not a single A/B. Each variant replaces one more material sample with a
type-preserving constant, so the removed texture work is a measured dose and the timing change
is the response. Diagnostic ablation: the image is expected to differ and is never treated as
an accepted variant.

    python -B tools/run_o3.py prepare
    python -B tools/run_o3.py build <variant>
    python -B tools/run_o3.py run <variant> <set> [--samples N] [--passes N] [--rep R]
    python -B tools/run_o3.py analyse
"""
import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G
import run_o1 as O1
import run_o2 as O2

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/28_o3_material_ablation"
FIRST_FRAME = 140

# Type-preserving replacements at the sample site. texNormal's value is used as *2-1, so
# float3(0.5,0.5,1.0) yields the flat tangent-space normal (0,0,1); texSpecular's .g is read,
# so the replacement must stay a float3.
ABLATIONS = {
    "spec":    (b"SAMPLE_TEX(texSpecular)", b"float3(0.5, 0.5, 0.5)"),
    "normal":  (b"SAMPLE_TEX(texNormal)",   b"float3(0.5, 0.5, 1.0)"),
    "diffuse": (b"SAMPLE_TEX(texDiffuse)",  b"float3(0.5, 0.5, 0.5)"),
}
VARIANTS = {
    "mat0": [],                                # baseline, unmodified shader
    "mat1": ["spec"],
    "mat2": ["spec", "normal"],
    "mat3": ["spec", "normal", "diffuse"],
}


def variant_source(names):
    src = (O1.ORIGINAL / O1.PS_REL).read_bytes()
    for n in names:
        old, new = ABLATIONS[n]
        G.require(src.count(old) == 1, f"ablation anchor not unique: {n}")
        src = src.replace(old, new)
    return src


def precompile_variants(stage):
    """Preregister the exact bytecode every variant must produce, before any build runs."""
    out = {}
    for label, names in VARIANTS.items():
        d = stage / label
        shutil.copytree((O1.ORIGINAL / O1.PS_REL).parent, d / "Shaders")
        (d / "Shaders/ModelViewerPS.hlsl").write_bytes(variant_source(names))
        (d / "Output/Model/CompiledShaders").mkdir(parents=True)
        G.run_checked([O1.DXC, "-nologo", "-E", "main", "-T", "ps_6_2", "-D", "_GAMING_DESKTOP=1",
                       "-Fh", d / "Output/Model/CompiledShaders/ModelViewerPS.h",
                       "-Vn", "g_pModelViewerPS", "-HV", "2021", d / "Shaders/ModelViewerPS.hlsl"],
                      d / "Shaders", stage / f"dxc_{label}.log", timeout=120)
        out[label] = G.shader_artifact(d)
    hashes = {k: v["bytecode_sha256"] for k, v in out.items()}
    G.require(len(set(hashes.values())) == len(hashes), "two variants compile to the same bytecode")
    G.require(out["mat0"]["custom_hash"] == "52CE6C5E64AB2E82",
              "mat0 is not the shader O1 and O2 verified")
    return out


def prepare():
    OUT.mkdir(exist_ok=False)
    eid = "O3_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(os.environ["TEMP"]) / "claude" / eid
    work.mkdir(exist_ok=False)
    expected = precompile_variants(OUT / "preregistered")
    (OUT / "sets").mkdir()
    for name in ["sq_ps", "resp"]:
        names = O2.sets()["sq_ps"] if name == "sq_ps" else (
            [f"TA{i}_PERF_SEL_TA_BUSY" for i in range(80)]
            + [f"TA{i}_PERF_SEL_ANISO_1_CYCLE_QUADS" for i in range(80)]
            + ["GPUTime", "GPUBusyCycles"])
        (OUT / "sets" / f"{name}.txt").write_text("\n".join(sorted(set(names))) + "\n",
                                                  encoding="utf-8")
    G.save_json(OUT / "experiment_manifest.json", dict(
        experiment_id=eid, created_at=datetime.now().astimezone().isoformat(), cycle="O3",
        workspace=str(work), original_source=str(O1.ORIGINAL), dxc_selected=str(O1.DXC),
        configuration="Profile/x64/v145", first_frame=FIRST_FRAME,
        variants={k: v for k, v in VARIANTS.items()},
        expected_bytecode={k: v["bytecode_sha256"] for k, v in expected.items()},
        expected_artifacts=expected,
        ablation_kind="diagnostic_only - the rendered image is expected to differ; no variant "
                      "here is ever an accepted optimisation",
        preregistered_criteria=dict(
            dose="PS INSTS_TEX_LOAD and the aniso-1 quad total, both relative to mat0. The "
                 "emulated SQ counters carry +-0.4% (measured in O2); the TA quad counters "
                 "are exact.",
            response_mechanistic="sum of TA_BUSY over the 80 CUs",
            response_outcome="GPUTime of the Render Color sample",
            statistic="median over >=32 samples per run, >=3 independent processes per variant, "
                      "process order interleaved across variants",
            threshold="a GPUTime change counts only if |delta| > max(2%, 3 x N95), with N95 the "
                      "95th percentile of |delta| between independent mat0 runs (A/A control)",
            confounder="delta INSTS_VALU and INST_CYCLES_VALU are recorded, not assumed: "
                       "replacing a sample with a constant also removes dependent ALU",
            conclusion_rule="material texture sampling is on the critical path of Render Color "
                            "if GPUTime falls monotonically with dose AND the largest dose "
                            "exceeds the threshold AND that is replicated with reversed order. "
                            "Otherwise it is not the limiter, and the measured effect bounds how "
                            "much it could contribute."),
        workspace_budget_bytes=8_000_000_000))

    with (OUT / "input_hashes.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "copy", "bytes", "sha256"])
        total = 0
        for area in ["MiniEngine", "Packages", "vcpkg", "vcpkg_installed"]:
            for source in sorted((O1.ORIGINAL / area).rglob("*")):
                if not source.is_file() or (area == "MiniEngine" and
                        source.relative_to(O1.ORIGINAL / area).parts[0] == "Build"):
                    continue
                if area == "vcpkg_installed" and any(x in source.parts for x in ["debug", "tools"]):
                    continue
                target = work / source.relative_to(O1.ORIGINAL)
                h = G.sha(source)
                total += source.stat().st_size
                G.require(total < 3_000_000_000, "input copy budget exceeded")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                G.require(G.sha(target) == h, "copy integrity failure")
                w.writerow([str(source), str(target), source.stat().st_size, h])
        shutil.copy2(O1.ORIGINAL / "vcpkg.json", work / "vcpkg.json")
        for p in [ROOT / "tools/buildv.py", ROOT / "tools/run_o1.py", ROOT / "tools/run_o2.py",
                  ROOT / "tools/run_o3.py", ROOT / "tools/o1_probe.h", ROOT / "tools/o2_gpa.h"]:
            w.writerow([str(p), "", p.stat().st_size, G.sha(p)])

    O1.instrument(work, OUT, o2=True)
    O1.finish_prepare(work, OUT)
    shutil.copy2(Path(os.environ["TEMP"]) / "claude/gpa/4_4/bin/GPUPerfAPIDX12-x64.dll",
                 work / "MiniEngine/ModelViewer/GPUPerfAPIDX12-x64.dll")
    print("Prepared", work, flush=True)


def manifest():
    return json.loads((OUT / "experiment_manifest.json").read_text())


def build(label):
    m = manifest()
    G.require(label in VARIANTS, f"unknown variant {label}")
    work = Path(m["workspace"]).resolve(strict=True)
    G.require(work.name == m["experiment_id"]
              and work.parent == (Path(os.environ["TEMP"]) / "claude").resolve()
              and O1.ORIGINAL.resolve() not in [work, *work.parents],
              "workspace path is not this experiment's own copy")
    source = work / O1.PS_REL
    baseline = (OUT / "baseline_ModelViewerPS.hlsl").read_bytes()
    G.require(source.read_bytes() == baseline, "workspace source not restored")
    with (OUT / "instrumented_source_hashes.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if Path(row["path"]) != source:
                G.require(G.sha(row["path"]) == row["sha256"],
                          f"instrumented source changed since prepare: {row['path']}")
    try:
        source.write_bytes(variant_source(VARIANTS[label]))
        snap = OUT / "source_revisions" / f"{label}_ModelViewerPS.hlsl"
        if snap.exists():
            G.require(snap.read_bytes() == source.read_bytes(), "variant source changed")
        else:
            snap.write_bytes(source.read_bytes())
        attempt = 1
        while (work / "build" / f"{label}.{attempt}").exists() or \
              (OUT / "build_logs" / f"{label}.{attempt}").exists():
            attempt += 1
        artifact = G.build(work / "MiniEngine", work / "build" / f"{label}.{attempt}",
                           OUT / "build_logs" / f"{label}.{attempt}", Path(m["dxc_selected"]),
                           expected=m["expected_bytecode"][label])
        G.save_json(OUT / f"build_{label}.json", artifact)
        print(json.dumps(artifact, indent=2), flush=True)
    finally:
        source.write_bytes(baseline)
        G.require(source.read_bytes() == baseline, "baseline source restoration failed")


def run(label, setname, samples, passes, rep):
    m = manifest()
    artifact = json.loads((OUT / f"build_{label}.json").read_text())
    G.require(G.sha(artifact["executable"]) == artifact["executable_sha256"],
              "executable changed since the verified build")
    G.require(artifact["bytecode_sha256"] == m["expected_bytecode"][label],
              "artifact is not this variant's preregistered bytecode")
    setfile = OUT / "sets" / f"{setname}.txt"
    G.require(setfile.is_file(), f"unknown set {setname}")
    tag = f"{label}_{setname}_r{rep}"
    folder = OUT / "runs" / tag
    folder.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ME_", "AMD_", "SC_"))}
    env.update(ME_O2_DIR=str(folder), ME_O2_SET=str(setfile),
               ME_O2_FIRST=str(m["first_frame"]), ME_O2_SAMPLES=str(samples))
    if passes:
        env["ME_O2_PASSES"] = str(passes)
    proc = G.run_checked([artifact["executable"]], Path(m["workspace"]) / "MiniEngine/ModelViewer",
                         folder / "process.log", env=env, timeout=900)
    G.require(not (folder / "gpa_failure.txt").exists(), "GPA reported a failure")
    G.require((folder / "gpa_results.csv").is_file(), "no GPA results")
    G.save_json(folder / "run.json", dict(variant=label, set=setname, rep=rep, pid=proc["pid"],
                                          samples=samples,
                                          bytecode_sha256=artifact["bytecode_sha256"],
                                          executable_sha256=artifact["executable_sha256"]))
    print(f"{tag}: ok (pid {proc['pid']})", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "build", "run"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("setname", nargs="?", default="resp")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--passes", type=int, default=0)
    ap.add_argument("--rep", type=int, default=1)
    a = ap.parse_args()
    if a.action == "prepare":
        prepare()
    elif a.action == "build":
        build(a.name)
    else:
        run(a.name, a.setname, a.samples, a.passes, a.rep)
