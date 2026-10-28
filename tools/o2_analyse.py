"""Analyse O2 counter runs: frame identity, cross-pass identity, aggregation, baseline.

Reads research/27_o2_counters/runs/*/gpa_results.csv. Applies the criteria preregistered in
experiment_manifest.json. Prints a report and writes o2_analysis.json.

    python -B tools/o2_analyse.py
"""
import csv
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/27_o2_counters"
IDENTITY_TOLERANCE = 0.001  # preregistered: 0.1%


def load(tag):
    """{counter: [value per sample]} in sample order."""
    path = OUT / "runs" / tag / "gpa_results.csv"
    if not path.is_file():
        return None
    by = {}
    for r in csv.DictReader(path.open(encoding="utf-8")):
        by.setdefault(r["counter"], {})[int(r["sample"])] = float(r["value"])
    return {c: [v[i] for i in sorted(v)] for c, v in by.items()}


def spread(values):
    """Relative spread; 0 when every sample is identical, including all-zero counters."""
    lo, hi = min(values), max(values)
    if lo == hi:
        return 0.0
    scale = max(abs(lo), abs(hi))
    return (hi - lo) / scale if scale else 0.0


def group(data, pattern):
    """Sum counters matching a regex, per sample."""
    keys = [c for c in data if re.fullmatch(pattern, c)]
    if not keys:
        return None, []
    n = len(data[keys[0]])
    return [sum(data[k][i] for k in keys) for i in range(n)], keys


def frame_identity(tag, data):
    per = {c: spread(v) for c, v in data.items()}
    # AMD marks these {nondeterministic} in their own descriptions; excluded from the claim.
    nondet = [c for c in per if re.search(r"SQC_PERF_SEL_(I|D)CACHE|WAIT_INST_LDS", c)]
    judged = {c: s for c, s in per.items() if c not in nondet}
    worst = max(judged.items(), key=lambda kv: kv[1]) if judged else ("-", 0.0)
    identical = sum(1 for s in judged.values() if s == 0.0)
    return dict(tag=tag, counters=len(per), judged=len(judged), excluded_nondeterministic=len(nondet),
                bit_identical_across_samples=identical, worst_counter=worst[0],
                worst_spread=worst[1], passes_criterion=worst[1] <= IDENTITY_TOLERANCE)


def main():
    m = json.loads((OUT / "experiment_manifest.json").read_text())
    runs = {t: load(t) for t in ["sq_ps", "ta_busy", "crosspass", "aniso"]}
    runs = {k: v for k, v in runs.items() if v}
    report = {"experiment_id": m["experiment_id"], "criteria": m["preregistered_criteria"]}

    print("=" * 78)
    print("1. FRAME-TO-FRAME IDENTITY  (same binary, consecutive frames, one pass)")
    print("=" * 78)
    report["frame_identity"] = []
    for tag, data in runs.items():
        r = frame_identity(tag, data)
        report["frame_identity"].append(r)
        print(f"  {tag:10s} {r['judged']:4d} counters judged, {r['excluded_nondeterministic']:3d} excluded "
              f"(AMD: nondeterministic)")
        print(f"             {r['bit_identical_across_samples']:4d} bit-identical across all samples; "
              f"worst spread {r['worst_spread']*100:.5f}%  ({r['worst_counter']})")
        print(f"             criterion (<= {IDENTITY_TOLERANCE*100}%): "
              f"{'PASS' if r['passes_criterion'] else 'FAIL'}\n")

    print("=" * 78)
    print("2. CROSS-PASS IDENTITY  (does a counter measured across N passes match 1 pass?)")
    print("=" * 78)
    if "ta_busy" in runs and "crosspass" in runs:
        one, _ = group(runs["ta_busy"], r"TA\d+_PERF_SEL_TA_BUSY")
        many, _ = group(runs["crosspass"], r"TA\d+_PERF_SEL_TA_BUSY")
        a, b = statistics.median(one), statistics.median(many)
        rel = abs(a - b) / max(a, b) if max(a, b) else 0.0
        noise = max(spread(one), spread(many))
        ok = rel <= max(noise, IDENTITY_TOLERANCE)
        report["cross_pass"] = dict(one_pass_median=a, multi_pass_median=b, relative_difference=rel,
                                    frame_noise=noise, passes_criterion=ok)
        print(f"  sum(TA_BUSY) 1 pass  : {a:,.0f}")
        print(f"  sum(TA_BUSY) 2 passes: {b:,.0f}")
        print(f"  relative difference  : {rel*100:.5f}%   frame-to-frame noise: {noise*100:.5f}%")
        print(f"  criterion: {'PASS - passes see the same workload' if ok else 'FAIL - passes differ'}\n")
    else:
        print("  (runs missing)\n")

    print("=" * 78)
    print("3. AGGREGATION  (does the SDK's own derived counter equal my sum of the raw ones?)")
    print("=" * 78)
    report["aggregation"] = {}
    if "crosspass" in runs:
        d = runs["crosspass"]
        tot, keys = group(d, r"TA\d+_PERF_SEL_TA_BUSY")
        checks = []
        if tot and "TexUnitBusyCycles" in d:
            checks.append(("sum(TA_i_BUSY) vs TexUnitBusyCycles", tot, d["TexUnitBusyCycles"], len(keys)))
        if "CPF_PERF_SEL_CPF_STAT_BUSY" in d and "GPUBusyCycles" in d:
            checks.append(("CPF_STAT_BUSY vs GPUBusyCycles",
                           d["CPF_PERF_SEL_CPF_STAT_BUSY"], d["GPUBusyCycles"], 1))
        for label, mine, theirs, n in checks:
            diffs = [abs(x - y) / max(abs(x), abs(y), 1) for x, y in zip(mine, theirs)]
            exact = all(x == y for x, y in zip(mine, theirs))
            report["aggregation"][label] = dict(exact=exact, max_relative=max(diffs),
                                                mine=statistics.median(mine),
                                                sdk=statistics.median(theirs), raw_counters=n)
            print(f"  {label}")
            print(f"    mine  {statistics.median(mine):>20,.2f}   (sum over {n} raw counters)")
            print(f"    SDK   {statistics.median(theirs):>20,.2f}")
            print(f"    {'EXACT MATCH' if exact else f'max relative difference {max(diffs)*100:.6f}%'}\n")
        # TexUnitBusy is a percentage; find which normalisation the SDK actually uses.
        if tot and "TexUnitBusy" in d and "GPUBusyCycles" in d:
            print("  TexUnitBusy% - candidate formulas against the SDK value:")
            gb = d["GPUBusyCycles"]
            inst = len(keys)
            cands = {
                "sum(TA_BUSY)/GPUBusyCycles*100": [t / g * 100 for t, g in zip(tot, gb)],
                f"mean over {inst} CUs / GPUBusyCycles*100": [t / inst / g * 100 for t, g in zip(tot, gb)],
                "max(TA_BUSY)/GPUBusyCycles*100":
                    [max(d[k][i] for k in keys) / gb[i] * 100 for i in range(len(gb))],
            }
            got = statistics.median(d["TexUnitBusy"])
            report["aggregation"]["TexUnitBusy_formula"] = {"sdk_value": got}
            for name, vals in cands.items():
                v = statistics.median(vals)
                rel = abs(v - got) / max(abs(v), abs(got), 1e-12)
                report["aggregation"]["TexUnitBusy_formula"][name] = dict(value=v, relative=rel)
                print(f"    {name:44s} {v:12.6f}   {'MATCH' if rel < 1e-6 else f'off by {rel*100:.3f}%'}")
            print(f"    {'SDK TexUnitBusy':44s} {got:12.6f}\n")

    print("=" * 78)
    print("4. RENDER COLOR BASELINE  (unmodified shader, no ablation)")
    print("=" * 78)
    report["baseline"] = {}
    if "sq_ps" in runs:
        d = runs["sq_ps"]
        print("  Pixel-stage SQ counters, summed over the 4 shader engines (median of samples):")
        for ev in ["PERF_SEL_WAVES", "PERF_SEL_WAVES_32", "PERF_SEL_INSTS_VALU",
                   "PERF_SEL_INST_CYCLES_VALU", "PERF_SEL_ITEM_CYCLES_VALU",
                   "PERF_SEL_INSTS_SALU", "PERF_SEL_INSTS_TEX_LOAD", "PERF_SEL_INSTS_TEX_STORE"]:
            tot, keys = group(d, rf"SQ_PS\d+_{re.escape(ev)}")
            if not tot:
                continue
            v = statistics.median(tot)
            report["baseline"][ev] = v
            print(f"    {ev:32s} {v:>18,.0f}")
    if "ta_busy" in runs:
        d = runs["ta_busy"]
        tot, keys = group(d, r"TA\d+_PERF_SEL_TA_BUSY")
        per = [statistics.median([d[k][i] for i in range(len(d[k]))]) for k in keys]
        report["baseline"]["TA_BUSY_sum"] = statistics.median(tot)
        report["baseline"]["TA_BUSY_per_cu_mean"] = statistics.mean(per)
        report["baseline"]["TA_BUSY_per_cu_min"] = min(per)
        report["baseline"]["TA_BUSY_per_cu_max"] = max(per)
        print(f"\n  TA_BUSY over {len(keys)} CUs: sum {statistics.median(tot):>16,.0f}")
        print(f"    per-CU mean {statistics.mean(per):,.0f}   min {min(per):,.0f}   "
              f"max {max(per):,.0f}   imbalance max/mean {max(per)/statistics.mean(per):.3f}")
    if "sq_ps" in runs and "ta_busy" in runs:
        tex, _ = group(runs["sq_ps"], r"SQ_PS\d+_PERF_SEL_INSTS_TEX_LOAD")
        ta, _ = group(runs["ta_busy"], r"TA\d+_PERF_SEL_TA_BUSY")
        if tex and ta and statistics.median(tex):
            r = statistics.median(ta) / statistics.median(tex)
            report["baseline"]["ta_busy_cycles_per_ps_tex_instruction"] = r
            print(f"\n  TA busy cycles per pixel-stage texture instruction: {r:.3f}")
            print("    (both from single-pass sessions; a ratio across two sessions, so it "
                  "inherits\n     the cross-pass result above - not yet a bottleneck claim)")
    if "aniso" in runs:
        d = runs["aniso"]
        print("\n  Aniso sample histogram (quads requiring N aniso samples, all 80 CUs):")
        tot_q = 0.0
        weighted = 0.0
        for k in (1, 2, 4, 6, 8, 10, 12, 14, 16):
            tot, _ = group(d, rf"TA\d+_PERF_SEL_ANISO_{k}_CYCLE_QUADS")
            if not tot:
                continue
            v = statistics.median(tot)
            tot_q += v
            weighted += k * v
            report["baseline"][f"aniso_{k}_quads"] = v
            print(f"    {k:2d} samples {v:>18,.0f}")
        if tot_q:
            print(f"    total quads {tot_q:>16,.0f}   mean aniso samples/quad "
                  f"{weighted/tot_q:.4f}")
            report["baseline"]["aniso_mean_samples_per_quad"] = weighted / tot_q
            if "TexAveAnisotropy" in d:
                got = statistics.median(d["TexAveAnisotropy"])
                report["baseline"]["TexAveAnisotropy_sdk"] = got
                print(f"    SDK TexAveAnisotropy {got:.4f}  -> "
                      f"{'matches the weighted mean' if abs(got-weighted/tot_q) < 1e-6 else 'differs'}")

    (OUT / "o2_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT/'o2_analysis.json'}")


if __name__ == "__main__":
    main()
