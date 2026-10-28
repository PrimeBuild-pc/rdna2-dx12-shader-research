"""Phase 2O cycle O2: raw-counter semantics, workload identity, and a Render Color baseline.

No ablation. Nothing here changes a shader; the only source edits are the shared O1/O2
instrumentation, and the pixel shader stays byte-identical to the O1 baseline.

    python -B tools/run_o2.py prepare
    python -B tools/run_o2.py build
    python -B tools/run_o2.py run <set> [--samples N] [--passes N] [--tag T]
    python -B tools/run_o2.py analyse
"""
import argparse
import csv
from datetime import datetime
import json
import os
import re
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G
import run_o1 as O1

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/27_o2_counters"
FIRST_FRAME = 140  # same rationale as O1: after all 128 light shadow slices

# Counter sets. Names come from the verified live enumeration in research/26_gpa_hwcounters.
SQ_PS_EVENTS = ["PERF_SEL_INSTS_VALU", "PERF_SEL_INST_CYCLES_VALU", "PERF_SEL_ITEM_CYCLES_VALU",
                "PERF_SEL_INSTS_SALU", "PERF_SEL_INSTS_TEX_LOAD", "PERF_SEL_INSTS_TEX_STORE",
                "PERF_SEL_WAVES", "PERF_SEL_WAVES_32"]
ANISO = [f"PERF_SEL_ANISO_{k}_CYCLE_QUADS" for k in (1, 2, 4, 6, 8, 10, 12, 14, 16)]


def sets():
    sq = [f"SQ_PS{i}_{e}" for i in range(4) for e in SQ_PS_EVENTS]
    ta = [f"TA{i}_PERF_SEL_TA_BUSY" for i in range(80)]
    return {
        # Single pass each: frame-to-frame identity is measurable without any pass confound.
        "sq_ps": sq,
        "ta_busy": ta,
        # Multi-pass on purpose. TA_BUSY appears here AND in ta_busy, so comparing the two
        # measures directly whether passes running on different frames agree.
        "crosspass": ta + ["TexUnitBusyCycles", "TexUnitBusy", "GPUBusyCycles", "GPUTime",
                           "CPF_PERF_SEL_CPF_STAT_BUSY"],
        # Aniso histogram plus the derived counter built from it, for the aggregation check.
        "aniso": [f"TA{i}_{e}" for i in range(80) for e in ANISO] + ["TexAveAnisotropy"],
        # Which shader stage issues the texture work in this scope. SQ<n>_ (no mask) is the
        # unmasked total, so ALL minus PS is exactly the non-pixel share.
        # MEASURED: mixing shader masks across passes corrupts individual SQ counters (see
        # runs/stage_tex). One mask per session, one pass each, is the only form that is trusted.
        "tex_all": [f"SQ{i}_PERF_SEL_{e}" for i in range(4)
                    for e in ("INSTS_TEX_LOAD", "WAVES")],
        "tex_vs": [f"SQ_VS{i}_PERF_SEL_{e}" for i in range(4)
                   for e in ("INSTS_TEX_LOAD", "WAVES")],
        "tex_cs": [f"SQ_CS{i}_PERF_SEL_{e}" for i in range(4)
                   for e in ("INSTS_TEX_LOAD", "WAVES")],
        **{f"tex_{m.lower()}": [f"SQ_{m}{i}_PERF_SEL_{e}" for i in range(4)
                                for e in ("INSTS_TEX_LOAD", "WAVES")]
           for m in ("GS", "ES", "HS", "LS")},
        # Timing plus the exact work dose, for dose-response ablation measurements.
        "timing": [f"TA{i}_PERF_SEL_TA_BUSY" for i in range(80)]
                + [f"TA{i}_PERF_SEL_ANISO_1_CYCLE_QUADS" for i in range(80)]
                + ["GPUTime", "GPUBusyCycles"],
    }


def prepare():
    OUT.mkdir(exist_ok=False)
    eid = "O2_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(os.environ["TEMP"]) / "claude" / eid
    work.mkdir(exist_ok=False)
    expected = O1.precompile(O1.DXC, OUT / "preregistered")
    G.require(expected["A"]["custom_hash"] == "52CE6C5E64AB2E82",
              "baseline shader is not the one O1 verified")
    (OUT / "sets").mkdir()
    for name, names in sets().items():
        (OUT / "sets" / f"{name}.txt").write_text("\n".join(sorted(set(names))) + "\n",
                                                  encoding="utf-8")
    G.save_json(OUT / "experiment_manifest.json", dict(
        experiment_id=eid, created_at=datetime.now().astimezone().isoformat(),
        cycle="O2", workspace=str(work), original_source=str(O1.ORIGINAL),
        dxc_selected=str(O1.DXC), configuration="Profile/x64/v145",
        expected_bytecode=expected["A"]["bytecode_sha256"],
        expected_artifact=expected["A"], first_frame=FIRST_FRAME,
        counter_sets={k: len(set(v)) for k, v in sets().items()},
        gpa_context_flags="kGpaOpenContextEnableHardwareCountersBit",
        shader_modification="none - O2 measures the unmodified baseline",
        workload=f"Sponza 1920x1080, frozen camera, TAA/motion blur/adaptation off, "
                 f"fixed 1/60 timestep, sampling from frame {FIRST_FRAME}",
        preregistered_criteria=dict(
            frame_identity="a single-pass set must give identical values on every sampled frame; "
                           "any counter varying by more than 0.1% fails the identity claim",
            cross_pass="TA_BUSY totals from the 1-pass set and the multi-pass set must agree "
                       "within the frame-to-frame spread measured above",
            aggregation="sum(TA_i_BUSY) == TexUnitBusyCycles exactly, and "
                        "CPF_PERF_SEL_CPF_STAT_BUSY == GPUBusyCycles exactly",
            note="no ablation, no performance verdict, no shader change in this cycle"),
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
        for p in [O1.ORIGINAL / "vcpkg.json", ROOT / "tools/buildv.py", ROOT / "tools/run_o1.py",
                  ROOT / "tools/run_o2.py", ROOT / "tools/o1_probe.h", ROOT / "tools/o2_gpa.h"]:
            w.writerow([str(p), "", p.stat().st_size, G.sha(p)])

    O1.instrument(work, OUT, o2=True)
    O1.finish_prepare(work, OUT)
    # The GPA DLL is loaded by name from the working directory of the run.
    shutil.copy2(Path(os.environ["TEMP"]) / "claude/gpa/4_4/bin/GPUPerfAPIDX12-x64.dll",
                 work / "MiniEngine/ModelViewer/GPUPerfAPIDX12-x64.dll")
    print("Prepared", work, flush=True)


def manifest():
    return json.loads((OUT / "experiment_manifest.json").read_text())


def build():
    m = manifest()
    work = Path(m["workspace"]).resolve(strict=True)
    G.require(work.name == m["experiment_id"]
              and work.parent == (Path(os.environ["TEMP"]) / "claude").resolve()
              and O1.ORIGINAL.resolve() not in [work, *work.parents],
              "workspace path is not this experiment's own copy")
    with (OUT / "instrumented_source_hashes.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            G.require(G.sha(row["path"]) == row["sha256"],
                      f"instrumented source changed since prepare: {row['path']}")
    attempt = 1
    while (work / "build" / f"O2.{attempt}").exists() or (OUT / "build_logs" / f"O2.{attempt}").exists():
        attempt += 1
    artifact = G.build(work / "MiniEngine", work / "build" / f"O2.{attempt}",
                       OUT / "build_logs" / f"O2.{attempt}", Path(m["dxc_selected"]),
                       expected=m["expected_bytecode"])
    G.require(artifact["custom_hash"] == "52CE6C5E64AB2E82", "not the O1-verified baseline shader")
    G.save_json(OUT / "build_result.json", artifact)
    print(json.dumps(artifact, indent=2), flush=True)


def run(name, samples, passes, tag):
    m = manifest()
    work = Path(m["workspace"])
    artifact = json.loads((OUT / "build_result.json").read_text())
    G.require(G.sha(artifact["executable"]) == artifact["executable_sha256"],
              "executable changed since the verified build")
    setfile = OUT / "sets" / f"{name}.txt"
    if not setfile.is_file():  # sets() stays the single source of truth for set contents
        G.require(name in sets(), f"unknown counter set: {name}")
        setfile.write_text("\n".join(sorted(set(sets()[name]))) + "\n", encoding="utf-8")
    folder = OUT / "runs" / (tag or name)
    folder.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ME_", "AMD_", "SC_"))}
    env.update(ME_O2_DIR=str(folder), ME_O2_SET=str(setfile),
               ME_O2_FIRST=str(m["first_frame"]), ME_O2_SAMPLES=str(samples))
    if passes:
        env["ME_O2_PASSES"] = str(passes)
    proc = G.run_checked([artifact["executable"]], work / "MiniEngine/ModelViewer",
                         folder / "process.log", env=env, timeout=600)
    G.require(not (folder / "gpa_failure.txt").exists(),
              (folder / "gpa_failure.txt").read_text() if (folder / "gpa_failure.txt").exists() else "")
    G.require((folder / "gpa_results.csv").is_file(), "no GPA results were written")
    session = dict(l.split("=", 1) for l in
                   (folder / "gpa_session.txt").read_text().strip().splitlines())
    # MEASURED in runs/stage_tex: with several SQ shader masks spread over multiple passes,
    # individual SQ counters come back corrupted (SQ0_INSTS_TEX_LOAD 1.25e9 against a true
    # ~1.5e6) while their siblings stay correct. Never accept that combination silently.
    masks = {(re.match(r"SQ_([A-Z]{2})\d+_", n) or [None, "ALL"])[1]
             for n in setfile.read_text().split() if n.startswith("SQ")}
    G.require(len(masks) <= 1 or int(session["passes"]) == 1,
              f"multi-pass session mixing SQ shader masks {sorted(masks)} is not trusted")
    rows = list(csv.DictReader((folder / "gpa_results.csv").open(encoding="utf-8")))
    G.require(len(rows) == int(session["counters"]) * samples, "unexpected result row count")
    result = dict(set=name, tag=tag or name, pid=proc["pid"], samples=samples,
                  session=session, rows=len(rows),
                  executable_sha256=artifact["executable_sha256"],
                  shader_custom_hash=artifact["custom_hash"])
    G.save_json(folder / "run.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "build", "run", "sets"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--passes", type=int, default=0)
    ap.add_argument("--tag")
    a = ap.parse_args()
    if a.action == "prepare":
        prepare()
    elif a.action == "build":
        build()
    elif a.action == "sets":
        for k, v in sets().items():
            print(f"{k:12s} {len(set(v)):5d} counters")
    else:
        run(a.name, a.samples, a.passes, a.tag)
