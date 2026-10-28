"""Phase 2O cycle O4: sampler-only ablation - texture filtering cost with the shader unchanged.

O3 could not fully separate texture work from ALU: removing a sample also removes the ALU that
consumed it. Here nothing in the shader changes. Only the static sampler that the material
textures are read through is altered, in C++. The pixel shader bytecode must come out
byte-identical to the O1/O2/O3 baseline, and the build gate enforces exactly that, so any
change in Render Color time is attributable to the cost of filtering and not to instruction
count, register pressure or scheduling.

    python -B tools/run_o4.py prepare
    python -B tools/run_o4.py build <variant>
    python -B tools/run_o4.py run <variant> <set> [--samples N] [--passes N] [--rep R]
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
OUT = ROOT / "research/29_o4_sampler"
FIRST_FRAME = 140
CPP_REL = "MiniEngine/Model/Renderer.cpp"
# Name of the pristine copy of the patched file. A later cycle that reuses this runner against a
# different source file overrides it, so the snapshot is named after what it actually holds.
BASELINE_SNAPSHOT = "baseline_Renderer.cpp"
# Experiment-id prefix, so a later cycle reusing this runner names its own workspace.
PREFIX = "O4"
ANCHOR = b"    SamplerDesc DefaultSamplerDesc;\n    DefaultSamplerDesc.MaxAnisotropy = 8;"

# Only the material sampler changes. Shadow and cube-map samplers are left alone, so the light
# and shadow sampling that dominates this shader's texture instruction count is untouched.
VARIANTS = {
    "s_base":    ANCHOR,
    "s_aniso1":  b"    SamplerDesc DefaultSamplerDesc;\n    DefaultSamplerDesc.MaxAnisotropy = 1;",
    "s_aniso16": b"    SamplerDesc DefaultSamplerDesc;\n    DefaultSamplerDesc.MaxAnisotropy = 16;",
    "s_point":   b"    SamplerDesc DefaultSamplerDesc;\n    DefaultSamplerDesc.MaxAnisotropy = 1;\n"
                 b"    DefaultSamplerDesc.Filter = D3D12_FILTER_MIN_MAG_MIP_POINT;",
    "s_bilinear": b"    SamplerDesc DefaultSamplerDesc;\n    DefaultSamplerDesc.MaxAnisotropy = 1;\n"
                  b"    DefaultSamplerDesc.Filter = D3D12_FILTER_MIN_MAG_LINEAR_MIP_POINT;",
}


def variant_cpp(work, label):
    src = (O1.ORIGINAL / CPP_REL).read_bytes()
    old, new = ANCHOR, VARIANTS[label]
    if b"\r\n" in src:  # Renderer.cpp is CRLF; match and insert in the file's own ending
        old, new = old.replace(b"\n", b"\r\n"), new.replace(b"\n", b"\r\n")
    G.require(src.count(old) == 1, "sampler anchor not unique")
    return src.replace(old, new)


def prepare():
    OUT.mkdir(exist_ok=False)
    eid = PREFIX + "_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(os.environ["TEMP"]) / "claude" / eid
    work.mkdir(exist_ok=False)
    expected = O1.precompile(O1.DXC, OUT / "preregistered")
    G.require(expected["A"]["custom_hash"] == "52CE6C5E64AB2E82",
              "baseline shader is not the one O1 verified")
    (OUT / "sets").mkdir()
    (OUT / "sets/resp.txt").write_text("\n".join(sorted(set(
        [f"TA{i}_PERF_SEL_TA_BUSY" for i in range(80)]
        + [f"TA{i}_PERF_SEL_ANISO_1_CYCLE_QUADS" for i in range(80)]
        + ["GPUTime", "GPUBusyCycles"]))) + "\n", encoding="utf-8")
    (OUT / "sets/aniso.txt").write_text("\n".join(sorted(set(
        [f"TA{i}_PERF_SEL_ANISO_{k}_CYCLE_QUADS" for i in range(80)
         for k in (1, 2, 4, 6, 8, 10, 12, 14, 16)]
        + [f"TA{i}_PERF_SEL_MIP_{k}_CYCLE_QUADS" for i in range(80) for k in (1, 2)]
        + ["TexAveAnisotropy"]))) + "\n", encoding="utf-8")
    (OUT / "sets/sq_ps.txt").write_text("\n".join(sorted(set(O2.sets()["sq_ps"]))) + "\n",
                                        encoding="utf-8")
    G.save_json(OUT / "experiment_manifest.json", dict(
        experiment_id=eid, created_at=datetime.now().astimezone().isoformat(), cycle="O4",
        workspace=str(work), original_source=str(O1.ORIGINAL), dxc_selected=str(O1.DXC),
        configuration="Profile/x64/v145", first_frame=FIRST_FRAME,
        patched_file=CPP_REL,
        variants={k: v.decode() for k, v in VARIANTS.items()},
        expected_bytecode=expected["A"]["bytecode_sha256"],
        expected_artifact=expected["A"],
        ablation_kind="diagnostic_only - filtering quality changes, so the image changes; no "
                      "variant here is an accepted optimisation",
        preregistered_criteria=dict(
            invariant="every variant must produce the SAME pixel shader bytecode as the O1 "
                      "baseline (52CE6C5E64AB2E82). The build gate rejects anything else, so "
                      "instruction count, ALU and scheduling are held fixed by construction.",
            dose="the aniso sample histogram and TexAveAnisotropy, which are exact work counters",
            response_mechanistic="sum of TA_BUSY over the 80 CUs",
            response_outcome="GPUTime and GPUBusyCycles of the Render Color sample",
            statistic="median over >=32 samples per run, >=3 independent processes per variant, "
                      "order interleaved and reversed between repetitions",
            threshold="max(2%, 3 x N95) with N95 from the s_base A/A control measured here",
            conclusion_rule="if Render Color time moves with filtering cost while the shader "
                            "bytecode is unchanged, texture filtering is on its critical path, "
                            "and the slope quantifies by how much. A null result with a verified "
                            "filtering dose falsifies the filtering-throughput hypothesis.",
            bidirectional="the dose goes both down (aniso1, bilinear, point) and up (aniso16), "
                          "so a one-sided artefact cannot mimic the effect"),
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
                  ROOT / "tools/run_o4.py", ROOT / f"tools/run_{PREFIX.lower()}.py",
                  ROOT / "tools/o1_probe.h", ROOT / "tools/o2_gpa.h"]:
            if p.is_file():
                w.writerow([str(p), "", p.stat().st_size, G.sha(p)])

    O1.instrument(work, OUT, o2=True)
    O1.finish_prepare(work, OUT)
    (OUT / BASELINE_SNAPSHOT).write_bytes((work / CPP_REL).read_bytes())
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
    target = work / CPP_REL
    baseline_cpp = (OUT / BASELINE_SNAPSHOT).read_bytes()
    G.require(target.read_bytes() == baseline_cpp, "workspace Renderer.cpp not restored")
    with (OUT / "instrumented_source_hashes.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if Path(row["path"]) != target:
                G.require(G.sha(row["path"]) == row["sha256"],
                          f"instrumented source changed since prepare: {row['path']}")
    try:
        target.write_bytes(variant_cpp(work, label))
        snap = OUT / "source_revisions" / f"{label}_Renderer.cpp"
        if snap.exists():
            G.require(snap.read_bytes() == target.read_bytes(), "variant source changed")
        else:
            snap.write_bytes(target.read_bytes())
        attempt = 1
        while (work / "build" / f"{label}.{attempt}").exists() or \
              (OUT / "build_logs" / f"{label}.{attempt}").exists():
            attempt += 1
        # expected == the baseline bytecode for EVERY variant: that is the whole point.
        artifact = G.build(work / "MiniEngine", work / "build" / f"{label}.{attempt}",
                           OUT / "build_logs" / f"{label}.{attempt}", Path(m["dxc_selected"]),
                           expected=m["expected_bytecode"])
        G.require(artifact["custom_hash"] == "52CE6C5E64AB2E82", "shader changed - invalid for O4")
        G.save_json(OUT / f"build_{label}.json", artifact)
        print(f"{label}: shader unchanged ({artifact['custom_hash']}), "
              f"exe {artifact['executable_sha256'][:12]}", flush=True)
    finally:
        target.write_bytes(baseline_cpp)
        G.require(target.read_bytes() == baseline_cpp, "baseline restoration failed")


def run(label, setname, samples, passes, rep):
    m = manifest()
    artifact = json.loads((OUT / f"build_{label}.json").read_text())
    G.require(G.sha(artifact["executable"]) == artifact["executable_sha256"],
              "executable changed since the verified build")
    G.require(artifact["bytecode_sha256"] == m["expected_bytecode"], "shader is not the baseline")
    setfile = OUT / "sets" / f"{setname}.txt"
    G.require(setfile.is_file(), f"unknown set {setname}")
    folder = OUT / "runs" / f"{label}_{setname}_r{rep}"
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
    print(f"{label}_{setname}_r{rep}: ok", flush=True)


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
