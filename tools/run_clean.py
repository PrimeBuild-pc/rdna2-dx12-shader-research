"""Clean-room replication of Phase 2O's three decisive performance results.

The historical 2O measurements were taken with the user's ordinary desktop session running.
This cycle repeats only the results that carry a conclusion, on a verified-idle machine, using
the same executables, the same gates, the same sets and the same statistics:

    A  null / baseline        s_base alone, against the O2/O4/O5 baseline numbers
    B  sampler key comparison s_point vs s_base   (O4's texture-at-fixed-ALU arm)
    C  light-count comparison L32 vs L128         (O6's dose-response arm)

No build. The executables come from the O4 and O6 build records and their SHA-256 is verified
here and again at every run, so provenance is unchanged. Old and new numbers are never averaged
together: the criteria compare them.

    python -B tools/run_clean.py prepare
    python -B tools/run_clean.py run <variant> <set> [--samples N] [--rep R]
    python -B tools/run_clean.py analyse
"""
import argparse
import csv
from datetime import datetime
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G
import run_o4 as O4
import run_o5 as O5

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/32_clean_replication"
O4DIR = ROOT / "research/29_o4_sampler"
O6DIR = ROOT / "research/31_o6_lightcount"
SOURCE = {"s_base": O4DIR, "s_point": O4DIR, "L128": O6DIR, "L32": O6DIR}

# Historical values this cycle must reproduce, copied from the cycle reports before measuring.
HISTORICAL = dict(
    A=dict(ta_busy=88_700_482, gpu_busy_cycles=1_189_003, ps_tex=6_111_703,
           source="O5 tcp_ta / O4 resp / O5 stage_tex, s_base"),
    B=dict(d_ta_busy=-3.50, d_gpu_busy_cycles=-2.63,
           source="O5 tcp_ta + O4 resp, s_point vs s_base"),
    C=dict(d_ta_busy=-61.57, d_gpu_busy_cycles=-60.20, d_tex=-68.05,
           marginal_cycles_per_instr=13.13, source="O6, L32 vs L128"))

CRITERIA = dict(
    arm_A="aggregate work counters (TA_BUSY, SQ_PS INSTS_TEX_LOAD) within +-2 % of the historical "
          "baseline; GPUBusyCycles within +-5 %. Work counters are exact, timing is not.",
    arm_B="delta(s_point vs s_base) must keep its sign and land within max(1.0 percentage point, "
          "50 % of the historical effect) of the historical delta, on TA_BUSY and GPUBusyCycles.",
    arm_C="delta(L32 vs L128) must keep its sign and land within 5 percentage points of the "
          "historical delta on TA_BUSY, GPUBusyCycles and the texture instruction dose; and the "
          "implied marginal cost must stay inside O6's preregistered [10, 19] cycles band.",
    statistic="32 samples per run, 3 independent processes per variant per set, order interleaved "
              "then reversed then interleaved, exactly as in O4/O6.",
    verdict="CLEAN_REPLICATION = PASS only if all three arms meet their criterion. Old and new "
            "measurements are never pooled; a divergence is investigated, not averaged away.",
    environment="verified idle before measuring: no browser, no Discord, no game, no encoder; "
                "total GPU utilisation 1.69 % (desktop compositor only), live CPU under 0.5 %.")


def prepare():
    OUT.mkdir(exist_ok=True)
    m4 = json.loads((O4DIR / "experiment_manifest.json").read_text())
    (OUT / "sets").mkdir(exist_ok=True)
    for name, home in (("tcp_ta", O5.OUT), ("resp", O4DIR), ("sq_ps", O4DIR),
                       ("stage_tex", O5.OUT)):
        (OUT / "sets" / f"{name}.txt").write_bytes((home / "sets" / f"{name}.txt").read_bytes())
    for label, home in SOURCE.items():
        a = json.loads((home / f"build_{label}.json").read_text())
        G.require(G.sha(a["executable"]) == a["executable_sha256"],
                  f"{label}: executable changed since its verified build")
        G.require(a["custom_hash"] == "52CE6C5E64AB2E82", f"{label}: shader is not the baseline")
        here = OUT / f"build_{label}.json"
        if here.exists():   # prepare is re-runnable; an existing record must match, not be rewritten
            G.require(json.loads(here.read_text()) == a, f"{label}: build record changed")
        else:
            G.save_json(here, a)
    G.save_json(OUT / "experiment_manifest.json", dict(
        experiment_id="R_" + datetime.now().strftime("%Y%m%d_%H%M%S"), cycle="R",
        created_at=datetime.now().astimezone().isoformat(),
        purpose="clean-room replication of the three decisive Phase 2O performance results",
        reuses_builds_from={k: str(v.relative_to(ROOT)) for k, v in SOURCE.items()},
        workspace=m4["workspace"], expected_bytecode=m4["expected_bytecode"],
        expected_artifact=m4["expected_artifact"], first_frame=m4["first_frame"],
        historical_values=HISTORICAL, preregistered_criteria=CRITERIA))
    print("prepared", OUT, flush=True)


def run(label, setname, samples, rep):
    m = json.loads((OUT / "experiment_manifest.json").read_text())
    O4.OUT = OUT
    # The runner takes the executable from the build record and only uses the workspace for the
    # process working directory (the asset root), which is equivalent in both workspaces.
    O4.run(label, setname, samples, 0, rep)


def load(tag):
    p = OUT / "runs" / tag / "gpa_results.csv"
    if not p.is_file():
        return None
    by = {}
    for r in csv.DictReader(p.open(encoding="utf-8")):
        by.setdefault(r["counter"], {})[int(r["sample"])] = float(r["value"])
    return {c: [v[i] for i in sorted(v)] for c, v in by.items()}


def tot(d, pat):
    keys = [c for c in d if re.fullmatch(pat, c)]
    if not keys:
        return None
    n = len(d[keys[0]])
    return statistics.median(sum(d[k][i] for k in keys) for i in range(n))


def med(label, setname, pat):
    vals = [tot(load(f"{label}_{setname}_r{r}"), pat) for r in (1, 2, 3)
            if load(f"{label}_{setname}_r{r}")]
    return statistics.median(vals), vals


def analyse():
    h, ok = HISTORICAL, {}
    line = "=" * 92
    print(line)
    print("ARM A - null / baseline on a clean machine")
    print(line)
    ta, _ = med("s_base", "tcp_ta", r"TA\d+_PERF_SEL_TA_BUSY")
    gb, _ = med("s_base", "resp", r"GPUBusyCycles")
    gt, gt_v = med("s_base", "resp", r"GPUTime")
    tx, _ = med("s_base", "stage_tex", r"SQ_PS\d_PERF_SEL_INSTS_TEX_LOAD")
    for name, new, old, tol in (("TA_BUSY", ta, h["A"]["ta_busy"], 2.0),
                                ("PS tex instructions", tx, h["A"]["ps_tex"], 2.0),
                                ("GPUBusyCycles", gb, h["A"]["gpu_busy_cycles"], 5.0)):
        d = (new - old) / old * 100
        print(f"   {name:22s} clean {new:16,.0f}   historical {old:16,.0f}   "
              f"delta {d:+6.2f} %   tol +-{tol:.0f} %  {'OK' if abs(d) <= tol else 'FAIL'}")
        ok[name] = abs(d) <= tol
    print(f"   {'GPUTime':22s} clean {gt:16,.0f}   per process "
          + ", ".join(f"{v:,.0f}" for v in gt_v))

    print("\n" + line)
    print("ARM B - sampler at byte-identical bytecode (s_point vs s_base)")
    print(line)
    for key, setname, pat, oldd in (
            ("d_ta_busy", "tcp_ta", r"TA\d+_PERF_SEL_TA_BUSY", h["B"]["d_ta_busy"]),
            ("d_gpu_busy_cycles", "resp", r"GPUBusyCycles", h["B"]["d_gpu_busy_cycles"])):
        b, _ = med("s_base", setname, pat)
        p, _ = med("s_point", setname, pat)
        new = (p - b) / b * 100
        tol = max(1.0, abs(oldd) * 0.5)
        good = (new < 0) == (oldd < 0) and abs(new - oldd) <= tol
        print(f"   {key:22s} clean {new:+7.2f} %   historical {oldd:+7.2f} %   "
              f"|diff| {abs(new - oldd):.2f} pt   tol {tol:.2f} pt  {'OK' if good else 'FAIL'}")
        ok["B_" + key] = good

    print("\n" + line)
    print("ARM C - light-count dose-response (L32 vs L128)")
    print(line)
    dose = {}
    for key, setname, pat, oldd, tol in (
            ("d_tex", "sq_ps", r"SQ_PS\d_PERF_SEL_INSTS_TEX_LOAD", h["C"]["d_tex"], 5.0),
            ("d_ta_busy", "tcp_ta", r"TA\d+_PERF_SEL_TA_BUSY", h["C"]["d_ta_busy"], 5.0),
            ("d_gpu_busy_cycles", "resp", r"GPUBusyCycles", h["C"]["d_gpu_busy_cycles"], 5.0)):
        a, _ = med("L128", setname, pat)
        b, _ = med("L32", setname, pat)
        dose[key] = (a, b)
        new = (b - a) / a * 100
        good = (new < 0) == (oldd < 0) and abs(new - oldd) <= tol
        print(f"   {key:22s} clean {new:+7.2f} %   historical {oldd:+7.2f} %   "
              f"|diff| {abs(new - oldd):.2f} pt   tol {tol:.1f} pt  {'OK' if good else 'FAIL'}")
        ok["C_" + key] = good
    marg = (dose["d_ta_busy"][0] - dose["d_ta_busy"][1]) / (dose["d_tex"][0] - dose["d_tex"][1])
    good = 10 <= marg <= 19
    print(f"   {'marginal cycles/instr':22s} clean {marg:7.2f}     historical "
          f"{h['C']['marginal_cycles_per_instr']:7.2f}     band [10, 19]  {'OK' if good else 'FAIL'}")
    ok["C_marginal"] = good

    verdict = "PASS" if all(ok.values()) else "FAIL"
    print("\n" + line)
    print(f"CLEAN_REPLICATION = {verdict}")
    print(line)
    for k, v in ok.items():
        if not v:
            print("   failed:", k)
    G.save_json(OUT / "clean_replication.json",
                dict(verdict=verdict, checks=ok, historical=h, criteria=CRITERIA,
                     measured=dict(ta_busy=ta, ps_tex=tx, gpu_busy_cycles=gb, gpu_time=gt,
                                   gpu_time_per_process=gt_v)))
    print("\nwrote", OUT / "clean_replication.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "run", "analyse"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("setname", nargs="?", default="tcp_ta")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--rep", type=int, default=1)
    a = ap.parse_args()
    if a.action == "prepare":
        prepare()
    elif a.action == "run":
        run(a.name, a.setname, a.samples, a.rep)
    else:
        analyse()
