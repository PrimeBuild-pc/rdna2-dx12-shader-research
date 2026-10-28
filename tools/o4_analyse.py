"""Analyse O4 sampler runs: filtering dose vs Render Color response, shader bytecode fixed.

    python -B tools/o4_analyse.py

Dose comes from the `aniso` sessions (exact work counters), response from the `resp` sessions
(3 independent processes per variant, order interleaved). The threshold is derived here from
the s_base A/A control, as preregistered: max(2%, 3 x N95).
"""
import csv
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/29_o4_sampler"
VARIANTS = ["s_base", "s_aniso1", "s_aniso16", "s_point", "s_bilinear"]
ANISO_K = (1, 2, 4, 6, 8, 10, 12, 14, 16)


def load(tag):
    path = OUT / "runs" / tag / "gpa_results.csv"
    if not path.is_file():
        return None
    by = {}
    for r in csv.DictReader(path.open(encoding="utf-8")):
        by.setdefault(r["counter"], {})[int(r["sample"])] = float(r["value"])
    return {c: [v[i] for i in sorted(v)] for c, v in by.items()}


def total(data, pattern):
    """Median over samples of the per-sample sum of every counter matching the pattern."""
    keys = [c for c in data if re.fullmatch(pattern, c)]
    if not keys:
        return None
    n = len(data[keys[0]])
    return statistics.median(sum(data[k][i] for k in keys) for i in range(n))


def pct(new, ref):
    return (new - ref) / ref * 100 if ref else float("nan")


def main():
    report = {}

    # ---------- dose ----------
    dose = {}
    for v in VARIANTS:
        d = load(f"{v}_aniso_r1")
        if not d:
            continue
        buckets = {k: total(d, rf"TA\d+_PERF_SEL_ANISO_{k}_CYCLE_QUADS") for k in ANISO_K}
        quads = sum(buckets.values())
        cycles = sum(k * b for k, b in buckets.items())
        dose[v] = dict(buckets=buckets, quads=quads, aniso_cycles=cycles,
                       mean_aniso=cycles / quads if quads else 0,
                       tex_ave_anisotropy=statistics.median(d["TexAveAnisotropy"]),
                       mip1=total(d, r"TA\d+_PERF_SEL_MIP_1_CYCLE_QUADS"),
                       mip2=total(d, r"TA\d+_PERF_SEL_MIP_2_CYCLE_QUADS"))
        dose[v]["mip_cycles"] = dose[v]["mip1"] + 2 * dose[v]["mip2"]
    base = dose["s_base"]
    print("=" * 92)
    print("1. DOSE  (aniso session, 8 samples, exact work counters)")
    print("=" * 92)
    print(f"{'variant':11s} {'quads':>12s} {'aniso-cycles':>14s} {'mean':>7s} {'TexAveAniso':>12s}"
          f" {'d quads':>9s} {'d cycles':>9s}")
    for v in VARIANTS:
        if v not in dose:
            continue
        x = dose[v]
        print(f"{v:11s} {x['quads']:12,.0f} {x['aniso_cycles']:14,.0f} {x['mean_aniso']:7.4f}"
              f" {x['tex_ave_anisotropy']:12.4f} {pct(x['quads'], base['quads']):8.2f}%"
              f" {pct(x['aniso_cycles'], base['aniso_cycles']):8.2f}%")
    print("\n   aniso bucket histogram (quads per cycle-count bucket)")
    print(f"   {'k':>3s} " + " ".join(f"{v:>14s}" for v in VARIANTS if v in dose))
    for k in ANISO_K:
        print(f"   {k:3d} " + " ".join(f"{dose[v]['buckets'][k]:14,.0f}"
                                      for v in VARIANTS if v in dose))
    print(f"   {'mip1':>3s} " + " ".join(f"{dose[v]['mip1']:14,.0f}" for v in VARIANTS if v in dose))
    print(f"   {'mip2':>3s} " + " ".join(f"{dose[v]['mip2']:14,.0f}" for v in VARIANTS if v in dose))
    print(f"   {'MIP cycles':>3s} " + " ".join(f"{dose[v]['mip_cycles']:14,.0f}"
                                              for v in VARIANTS if v in dose))
    print(f"   {'d MIP':>3s} " + " ".join(f"{pct(dose[v]['mip_cycles'], base['mip_cycles']):13.2f}%"
                                         for v in VARIANTS if v in dose))
    report["dose"] = dose

    # ---------- response ----------
    metrics = {"TA_BUSY": r"TA\d+_PERF_SEL_TA_BUSY",
               "ANISO_1_QUADS": r"TA\d+_PERF_SEL_ANISO_1_CYCLE_QUADS",
               "GPUTime": r"GPUTime", "GPUBusyCycles": r"GPUBusyCycles"}
    resp = {}
    for v in VARIANTS:
        for rep in (1, 2, 3):
            d = load(f"{v}_resp_r{rep}")
            if not d:
                continue
            resp.setdefault(v, {})[rep] = {m: total(d, p) for m, p in metrics.items()}

    print("\n" + "=" * 92)
    print("2. A/A CONTROL on s_base  (3 independent processes, same binary)")
    print("=" * 92)
    n95 = {}
    for m in metrics:
        vals = [resp["s_base"][r][m] for r in sorted(resp["s_base"])]
        # symmetric: relative to the pair's mean, so N95 does not depend on pair order
        pw = [abs(a - b) / ((a + b) / 2) * 100 for i, a in enumerate(vals) for b in vals[i + 1:]]
        n95[m] = max(pw)
        print(f"   {m:14s} pairwise |diff| " + ", ".join(f"{x:.2f}%" for x in pw)
              + f"  -> N95 {max(pw):.2f}%")
    # The preregistration names GPUTime AND GPUBusyCycles as response outcomes but never says
    # which one feeds N95. So the formula is applied to each outcome with its own A/A control,
    # and the conservative co-primary verdict (both must pass) is what gets reported.
    thr = {m: max(2.0, 3 * n95[m]) for m in metrics}
    print()
    for m in metrics:
        print(f"   threshold[{m}] = max(2%, 3 x {n95[m]:.2f}%) = {thr[m]:.2f}%")
    report["n95"] = n95
    report["threshold_pct"] = thr

    print("\n" + "=" * 92)
    print("3. RESPONSE  (median of 3 processes, 32 samples each)")
    print("=" * 92)
    print(f"{'variant':11s} " + " ".join(f"{m:>16s}" for m in metrics))
    med = {}
    for v in VARIANTS:
        if v not in resp:
            continue
        med[v] = {m: statistics.median(resp[v][r][m] for r in resp[v]) for m in metrics}
        print(f"{v:11s} " + " ".join(f"{med[v][m]:16,.0f}" for m in metrics))
    print()
    print(f"{'variant':11s} " + " ".join(f"{'d ' + m:>16s}" for m in metrics) + "  verdict")
    for v in VARIANTS:
        if v == "s_base" or v not in med:
            continue
        deltas = {m: pct(med[v][m], med["s_base"][m]) for m in metrics}
        passed = [m for m in ("GPUTime", "GPUBusyCycles") if abs(deltas[m]) > thr[m]]
        verdict = ("co-primary PASS" if len(passed) == 2 else
                   "no effect" if not passed else f"split: only {passed[0]} above its threshold")
        print(f"{v:11s} " + " ".join(f"{deltas[m]:15.2f}%" for m in metrics) + "  " + verdict)
    report["response_median"] = med
    report["response_per_rep"] = resp

    # ---------- slope ----------
    print("\n" + "=" * 92)
    print("4. SLOPE  d GPUTime / d TA_BUSY   and   d TA_BUSY / d aniso-cycles")
    print("=" * 92)
    for v in VARIANTS:
        if v == "s_base" or v not in med or v not in dose:
            continue
        dta = pct(med[v]["TA_BUSY"], med["s_base"]["TA_BUSY"])
        dt = pct(med[v]["GPUTime"], med["s_base"]["GPUTime"])
        dc = pct(dose[v]["aniso_cycles"], base["aniso_cycles"])
        print(f"   {v:11s} d aniso-cycles {dc:7.2f}%  d TA_BUSY {dta:7.2f}%  d GPUTime {dt:7.2f}%"
              f"   time/TA {dt / dta if dta else float('nan'):6.2f}"
              f"   TA/dose {dta / dc if dc else float('nan'):6.2f}")

    (OUT / "o4_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nwrote", OUT / "o4_analysis.json")


if __name__ == "__main__":
    main()
