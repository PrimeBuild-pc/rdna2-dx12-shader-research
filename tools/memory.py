"""Measurement memory: one row per measured variant, harvested from artefacts, never recalled.

Declared in the 2U preregistration before it was built. Its only sanctioned use is to rank
hypothesis kinds by measured median delta; it never proposes a transformation on its own, and a
hypothesis drawn from it is labelled `memory` in the manifest and counted separately.

Sources, all machine-readable, all produced by the runs themselves:
  research/*_2[tu]_*/           phases 2T and 2U: manifest, per-run summaries, isa_2u.json
  research/PHASE_2P_MEASUREMENT_MEMORY.csv
  research/PHASE_2R_MEASUREMENT_MEMORY.csv

A row whose source artefact cannot be found is not written. Diagnostics (candidate=False in the
manifest, or a name beginning with abl_/ablate_) are written with is_candidate=0 so they can be
excluded from any rate, because they are ceilings and not attempts.

    python -B tools/memory.py            # rebuild the csv and print the ranking
"""
import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
OUT = RESEARCH / "MEASUREMENT_MEMORY.csv"

FIELDS = ["phase", "workload", "shader", "variant", "kind", "is_candidate",
          "d_instructions", "d_valu", "d_image_instr", "d_transcendental", "d_vgpr",
          "predicted_low_pct", "predicted_high_pct", "measured_pct", "processes",
          "all_negative", "correctness_tier", "verdict", "note"]


def diagnostic(name, meta):
    if meta.get("candidate") is False:
        return True
    return name.startswith(("abl_", "ablate_"))


def latest_analysis(d):
    files = sorted(d.glob("analysis_*.json"))
    return json.loads(files[-1].read_text()) if files else None


def harvest_2tu(rows):
    for d in sorted(RESEARCH.glob("*_2[tu]_*")):
        if "SUPERSEDED" in d.name or "FAILED" in d.name:
            continue
        man = d / "experiment_manifest.json"
        if not man.is_file():
            continue
        m = json.loads(man.read_text())
        a = latest_analysis(d)
        if not a:
            continue
        isa = {}
        if (d / "isa_2u.json").is_file():
            isa = json.loads((d / "isa_2u.json").read_text())
        base_isa = isa.get("base", {})
        phase = "2U" if "_2u_" in d.name else "2T"
        shader = next(iter(m["expected_bytecode"].get("base", {})), "")
        for variant, v in sorted(a.get("verdicts", {}).items()):
            meta = m.get("transforms", {}).get(variant, {})
            vi = isa.get(variant, {})
            pred = meta.get("predicted_delta_pct") or [None, None]
            rows.append(dict(
                phase=phase, workload=m["workload_name"], shader=shader, variant=variant,
                kind=meta.get("kind", ""), is_candidate=0 if diagnostic(variant, meta) else 1,
                d_instructions=vi.get("instructions", "") and vi["instructions"] - base_isa.get("instructions", 0),
                d_valu=vi.get("valu", "") and vi["valu"] - base_isa.get("valu", 0),
                d_image_instr=vi.get("image", "") and vi["image"] - base_isa.get("image", 0),
                d_transcendental=vi.get("transcendental", "") and vi["transcendental"] - base_isa.get("transcendental", 0),
                d_vgpr=vi.get("vgpr", "") and vi["vgpr"] - base_isa.get("vgpr", 0),
                predicted_low_pct=pred[0], predicted_high_pct=pred[1],
                measured_pct=round(v["median_pct"], 3), processes=len(v["per_process"]),
                all_negative=int(all(p < 0 for p in v["per_process"])),
                correctness_tier=("A" if (v.get("correctness") or {}).get("identical")
                                  else "fail" if v.get("correctness") else ""),
                verdict=v["final"], note=meta.get("pattern_provenance", "")))


def harvest_csv(rows, path, phase, mapper):
    if not path.is_file():
        return
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            row = mapper(r)
            if row:
                row["phase"] = phase
                rows.append(row)


def map_2p(r):
    if (r["verdict"] in ("", "n/a (baseline)") or r["variant"] == "base"
            or "not a candidate" in r["verdict"] or "baseline" in r["verdict"]):
        return None
    return dict(workload="MiniEngine ModelViewer", shader="ModelViewerPS", variant=r["variant"],
                kind=r["kind"], is_candidate=1, d_instructions="", d_valu="", d_image_instr="",
                d_transcendental="", d_vgpr=r.get("vgpr", ""),
                predicted_low_pct="", predicted_high_pct="",
                # 2P recorded the pass response as the delta of GPUBusyCycles for the target
                # pass, which is the same quantity the later phases call the pass delta.
                measured_pct=float(r["d_gpubusycycles_pct"]) if r.get("d_gpubusycycles_pct") else "",
                processes=r.get("processes", ""),
                all_negative="", correctness_tier="A" if r.get("image_identical") == "True" else "fail",
                verdict=r["verdict"], note="pass delta measured as d_GPUBusyCycles")


def map_2r(r):
    if r["transform"] == "base":
        return None
    return dict(workload=r["workload"], shader=r["shader"], variant=r["transform"],
                kind="", is_candidate=1, d_instructions="", d_valu="", d_image_instr="",
                d_transcendental="", d_vgpr="",
                predicted_low_pct="", predicted_high_pct="",
                measured_pct=float(r["delta_pass_pct"]) if r.get("delta_pass_pct") else "",
                processes="",
                all_negative="", correctness_tier="",
                verdict=(r.get("accepted") or "").strip() or "REJECTED", note=r.get("cause", ""))


def main():
    rows = []
    harvest_2tu(rows)
    harvest_csv(rows, RESEARCH / "PHASE_2P_MEASUREMENT_MEMORY.csv", "2P", map_2p)
    harvest_csv(rows, RESEARCH / "PHASE_2R_MEASUREMENT_MEMORY.csv", "2R", map_2r)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows\n")

    cand = [r for r in rows if r["is_candidate"] == 1 and isinstance(r["measured_pct"], (int, float))]
    print("candidates only, ranked by measured median delta of the target region")
    print(f"{'phase':6s}{'workload':38s}{'variant':18s}{'kind':32s}{'meas':>8s}  {'corr':4s} verdict")
    for r in sorted(cand, key=lambda r: r["measured_pct"]):
        print(f"{r['phase']:6s}{r['workload'][:37]:38s}{r['variant'][:17]:18s}{r['kind'][:31]:32s}"
              f"{r['measured_pct']:>+8.2f}  {r['correctness_tier'] or '-':4s} {r['verdict']}")

    by_kind = {}
    for r in cand:
        by_kind.setdefault(r["kind"] or "(unlabelled)", []).append(r["measured_pct"])
    print("\nby transformation kind, the only sanctioned use of this file")
    print(f"{'kind':36s}{'n':>3s}{'median':>9s}{'best':>9s}")
    for k, v in sorted(by_kind.items(), key=lambda kv: statistics.median(kv[1])):
        print(f"{k[:35]:36s}{len(v):>3d}{statistics.median(v):>+9.2f}{min(v):>+9.2f}")

    ceilings = [r for r in rows if r["is_candidate"] == 0 and isinstance(r["measured_pct"], (int, float))]
    print("\nceilings and block probes, for reference - never attempts")
    for r in sorted(ceilings, key=lambda r: r["measured_pct"]):
        print(f"{r['phase']:6s}{r['workload'][:37]:38s}{r['variant'][:17]:18s}{r['measured_pct']:>+8.2f}")


if __name__ == "__main__":
    sys.exit(main())
