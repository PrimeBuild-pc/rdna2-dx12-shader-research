"""Phase 2O cycle O6: replicate or falsify O5's conclusion by varying the texture instruction count.

O5 disposed of filtering (O4), L0 stalls (0.24 % of TA busy), L0 miss traffic (97.7 % hit) and
DRAM bandwidth (39.6 GB/s against 555-621 reached elsewhere in the same frame). What survived is:

    TA_BUSY in `Render Color` is set by the *count* of pixel-stage texture instructions -
    156 per wave, ~14.5 addresser cycles each - with the data essentially always in L0.

That is a claim about a coefficient, so it is falsifiable by moving the count. This cycle moves
it **without touching a single byte of shader code**: the number of lights that survive tile
culling is data, written by `Lighting::CreateRandomLights` in C++. Fewer lights means fewer
iterations of the light loop in `ShadeLights`, hence fewer shadow-map and light-buffer fetches
per wave, with the pixel shader bytecode still gated to the O1 baseline.

Lights are culled by index stride, so the type mix (sphere / cone / shadowed cone, laid out in
blocks of 32 by the original code) is thinned proportionally instead of being truncated to one
type. The random draws are untouched, so every surviving light is bit-identical to its
counterpart in the baseline.

The ALU falls together with the texture work - each removed light removes its shading maths too.
That confounder is measured here, not assumed, and the discriminating evidence against it is O4,
where TA_BUSY fell 3.5 % at *fixed* ALU and the pass time followed.

    python -B tools/run_o6.py prepare
    python -B tools/run_o6.py build <variant>
    python -B tools/run_o6.py run <variant> <set> [--samples N] [--rep R]
    python -B tools/run_o6.py analyse
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
OUT = ROOT / "research/31_o6_lightcount"

# The last statement of the per-light initialisation loop in CreateRandomLights. Unique in the
# file; the culling line is appended immediately after it, so every random draw above is
# untouched and the surviving lights keep exactly the parameters they have in the baseline.
ANCHOR = (b"        std::memcpy(m_LightData[n].shadowTextureMatrix, &shadowTextureMatrix, "
          b"sizeof(shadowTextureMatrix));")
STRIDE = {"L128": 1, "L64": 2, "L32": 4, "L16": 8}
VARIANTS = {k: ANCHOR if s == 1 else ANCHOR + b"\n        if (n %% %d != 0) m_LightData[n].radiusSq = 0.0f;" % s
            for k, s in STRIDE.items()}

O4.OUT = OUT
O4.CPP_REL = "MiniEngine/Model/LightManager.cpp"
O4.ANCHOR = ANCHOR
O4.VARIANTS = VARIANTS
O4.BASELINE_SNAPSHOT = "baseline_LightManager.cpp"
O4.PREFIX = "O6"

CRITERIA = dict(
    question="does TA_BUSY in Render Color follow the count of pixel-stage texture instructions, "
             "as O5 concluded, or not",
    lever="number of lights surviving tile culling, set in C++ data only. The pixel shader "
          "bytecode must stay 52CE6C5E64AB2E82 in every variant and the build gate enforces it, "
          "so instruction selection, register pressure and scheduling are fixed by construction.",
    dose="SQ_PS INSTS_TEX_LOAD per pixel-shader wave, measured, never inferred from the stride. "
         "Culling by radius is not assumed to be perfect - whatever it actually removes is what "
         "the dose reports.",
    confounder="SQ_PS INSTS_VALU and INST_CYCLES_VALU fall as well, since each removed light "
               "removes its shading arithmetic. Measured in the same single-pass session as the "
               "dose and reported beside it. This cycle cannot separate the two by itself; O4 "
               "already separated them in the other direction (TA_BUSY -3.5 % at fixed ALU).",
    response_mechanistic="sum of TA_PERF_SEL_TA_BUSY over the 80 CUs (set tcp_ta, 1 pass)",
    response_outcome="GPUTime and GPUBusyCycles of the Render Color sample (set resp)",
    replication_band="the model predicts d TA_BUSY / d (PS texture instructions) in [0.75, 1.25] "
                     "on every arm, and an implied marginal cost per removed instruction in "
                     "[10, 19] cycles, i.e. 14.5 +- 30 %. Bands fixed before measuring.",
    falsification="a ratio below 0.5 on the arms falsifies O5's conclusion: TA_BUSY would not be "
                  "following the instruction count. Above 1.5 the model is incomplete - something "
                  "else scales with the lights as well.",
    statistic="median over >= 32 samples per run, 3 independent processes per variant, order "
              "interleaved and reversed; threshold max(2 %, 3 x N95) per metric from the L128 "
              "A/A control measured here, as in O4",
    ablation_kind="diagnostic_only - fewer lights, so the image changes; no variant here is an "
                  "accepted optimisation",
    o5_numbers_under_test=dict(ta_busy_cycles_per_tex_instruction=14.51,
                               ps_tex_instructions_per_wave=156.0,
                               stall_over_busy_pct=0.24, l0_hit_pct=97.66))


def prepare():
    """Reuse O4's prepare - same fail-closed gate, same input hashing, its own workspace - but
    write O6's own preregistration into the manifest as it is created. `save_json` opens
    exclusively and never rewrites an artifact, so the criteria have to be injected on the way
    through rather than patched afterwards."""
    real = G.save_json

    def inject(path, obj):
        if Path(path).name == "experiment_manifest.json":
            obj = dict(obj, cycle="O6",
                       light_stride=STRIDE, ablation_kind=CRITERIA["ablation_kind"],
                       preregistered_criteria=CRITERIA,
                       reuses_analysis_from="research/30_o5_memory")
        return real(path, obj)

    G.save_json = inject
    try:
        O4.prepare()
    finally:
        G.save_json = real
    (OUT / "sets/tcp_ta.txt").write_bytes((O5.OUT / "sets/tcp_ta.txt").read_bytes())
    print("prepared O6:", OUT, flush=True)


# ---------------------------------------------------------------- analysis

def load(tag):
    p = OUT / "runs" / tag / "gpa_results.csv"
    if not p.is_file():
        return None
    by = {}
    for r in csv.DictReader(p.open(encoding="utf-8")):
        by.setdefault(r["counter"], {})[int(r["sample"])] = float(r["value"])
    return {c: [v[i] for i in sorted(v)] for c, v in by.items()}


def tot(d, pattern):
    keys = [c for c in d if re.fullmatch(pattern, c)]
    if not keys:
        return None
    n = len(d[keys[0]])
    return statistics.median(sum(d[k][i] for k in keys) for i in range(n))


def med_over_reps(label, setname, fields):
    vals = {}
    for rep in (1, 2, 3):
        d = load(f"{label}_{setname}_r{rep}")
        if not d:
            continue
        for k, pat in fields.items():
            vals.setdefault(k, []).append(tot(d, pat))
    return ({k: statistics.median(v) for k, v in vals.items()},
            {k: (max(v) - min(v)) / (sum(v) / len(v)) * 100 if len(v) > 1 and sum(v) else 0.0
             for k, v in vals.items()})


def analyse():
    m = json.loads((OUT / "experiment_manifest.json").read_text())
    order = ["L128", "L64", "L32", "L16"]
    line = "=" * 96
    dose_f = {"tex": r"SQ_PS\d_PERF_SEL_INSTS_TEX_LOAD", "valu": r"SQ_PS\d_PERF_SEL_INSTS_VALU",
              "valu_cyc": r"SQ_PS\d_PERF_SEL_INST_CYCLES_VALU", "waves": r"SQ_PS\d_PERF_SEL_WAVES"}
    resp_f = {"ta_busy": r"TA\d+_PERF_SEL_TA_BUSY",
              "stall": r"TCP\d+_PERF_SEL_TCP_TA_REQ_STALL", "tcp_req": r"TCP\d+_PERF_SEL_REQ"}
    time_f = {"GPUTime": r"GPUTime", "GPUBusyCycles": r"GPUBusyCycles"}

    dose, resp, time = {}, {}, {}
    for v in order:
        dose[v], _ = med_over_reps(v, "sq_ps", dose_f)
        resp[v], _ = med_over_reps(v, "tcp_ta", resp_f)
        time[v], time[v + "_spread"] = med_over_reps(v, "resp", time_f)
    dose = {k: v for k, v in dose.items() if v}
    report = {"experiment_id": m["experiment_id"], "criteria": m["preregistered_criteria"]}

    print(line, "\n1. DOSE  (sq_ps, 1 pass) - measured, not inferred from the stride\n", line)
    print(f"{'variant':8s} {'PS waves':>10s} {'tex instr':>16s} {'tex/wave':>9s} {'d tex':>8s}"
          f" {'VALU instr':>16s} {'d VALU':>8s}")
    for v in order:
        if v not in dose:
            continue
        x, b = dose[v], dose["L128"]
        print(f"{v:8s} {x['waves']:10,.0f} {x['tex']:16,.0f} {x['tex'] / x['waves']:9.2f}"
              f" {(x['tex'] - b['tex']) / b['tex'] * 100:7.2f}% {x['valu']:16,.0f}"
              f" {(x['valu'] - b['valu']) / b['valu'] * 100:7.2f}%")
    report["dose"] = dose

    print("\n" + line, "\n2. A/A CONTROL on L128 and thresholds\n", line)
    n95, thr = {}, {}
    for setname, fields in (("tcp_ta", resp_f), ("resp", time_f)):
        for k in fields:
            vals = []
            for rep in (1, 2, 3):
                d = load(f"L128_{setname}_r{rep}")
                if d:
                    vals.append(tot(d, fields[k]))
            if len(vals) > 1:
                pw = [abs(a - b) / ((a + b) / 2) * 100 for i, a in enumerate(vals)
                      for b in vals[i + 1:]]
                n95[k] = max(pw)
                thr[k] = max(2.0, 3 * max(pw))
                print(f"   {k:14s} pairwise " + ", ".join(f"{x:.2f}%" for x in pw)
                      + f"  -> N95 {n95[k]:.2f}%, threshold {thr[k]:.2f}%")
    report["n95"], report["threshold_pct"] = n95, thr

    print("\n" + line, "\n3. RESPONSE and the coefficient under test\n", line)
    print(f"{'variant':8s} {'TA_BUSY':>15s} {'d TA':>8s} {'GPUBusyCyc':>13s} {'d busy':>8s}"
          f" {'GPUTime':>11s} {'d time':>8s} {'dTA/dtex':>9s} {'cyc/instr':>10s}")
    rows = []
    for v in order:
        if v not in dose or not resp.get(v):
            continue
        d0, d1 = dose["L128"], dose[v]
        r0, r1 = resp["L128"], resp[v]
        t0, t1 = time["L128"], time[v]
        dtex = (d1["tex"] - d0["tex"]) / d0["tex"] * 100
        dta = (r1["ta_busy"] - r0["ta_busy"]) / r0["ta_busy"] * 100
        dbusy = (t1["GPUBusyCycles"] - t0["GPUBusyCycles"]) / t0["GPUBusyCycles"] * 100
        dtime = (t1["GPUTime"] - t0["GPUTime"]) / t0["GPUTime"] * 100
        ratio = dta / dtex if dtex else float("nan")
        marginal = ((r0["ta_busy"] - r1["ta_busy"]) / (d0["tex"] - d1["tex"])
                    if d0["tex"] != d1["tex"] else float("nan"))
        rows.append(dict(variant=v, d_tex=dtex, d_ta=dta, d_busy=dbusy, d_time=dtime,
                         ratio=ratio, marginal_cycles_per_instr=marginal))
        print(f"{v:8s} {r1['ta_busy']:15,.0f} {dta:7.2f}% {t1['GPUBusyCycles']:13,.0f}"
              f" {dbusy:7.2f}% {t1['GPUTime']:11,.0f} {dtime:7.2f}% {ratio:9.2f}"
              f" {marginal:10.2f}")
    report["rows"] = rows

    print("\n" + line, "\n4. PREREGISTERED VERDICT\n", line)
    arms = [r for r in rows if r["variant"] != "L128"]
    if arms:
        ratios = [r["ratio"] for r in arms]
        marg = [r["marginal_cycles_per_instr"] for r in arms]
        in_band = all(0.75 <= x <= 1.25 for x in ratios)
        cost_band = all(10 <= x <= 19 for x in marg)
        falsified = any(x < 0.5 for x in ratios)
        incomplete = any(x > 1.5 for x in ratios)
        print(f"   d TA_BUSY / d tex instructions: " + ", ".join(f"{x:.2f}" for x in ratios)
              + f"   band [0.75, 1.25] -> {'IN BAND' if in_band else 'OUT OF BAND'}")
        print(f"   marginal cycles per removed instruction: " + ", ".join(f"{x:.1f}" for x in marg)
              + f"   band [10, 19] -> {'IN BAND' if cost_band else 'OUT OF BAND'}")
        verdict = ("FALSIFIED - TA_BUSY does not follow the instruction count" if falsified else
                   "INCOMPLETE - something else scales with the lights too" if incomplete else
                   "REPLICATED" if in_band and cost_band else
                   "PARTIAL - direction confirmed, coefficient outside the preregistered band")
        print(f"\n   VERDICT: {verdict}")
        report["verdict"] = verdict

    print("\n" + line, "\n5. SATURATION AND THE PROPORTIONAL SHARE\n", line)
    print(f"{'variant':8s} {'TA duty':>9s} {'VALU duty':>10s} {'TA_BUSY/tex':>12s} {'VALUcyc/tex':>12s}")
    duty = {}
    for v in order:
        if v not in dose or not resp.get(v):
            continue
        duty[v] = dict(ta=resp[v]["ta_busy"] / 80 / time[v]["GPUBusyCycles"] * 100,
                       # INST_CYCLES_VALU is summed over the 4 shader engines = all 80 CUs.
                       # RDNA2 has 2 SIMD32 per CU, so 160 SIMDs, not 4 per CU as on GCN.
                       # Checked empirically: /80 would put the duty cycle at 193 %, which is
                       # impossible, and /160 gives 96.6 %, just under the 100 % ceiling.
                       valu=dose[v]["valu_cyc"] / 160 / time[v]["GPUBusyCycles"] * 100,
                       ta_per_tex=resp[v]["ta_busy"] / dose[v]["tex"],
                       valucyc_per_tex=dose[v]["valu_cyc"] / dose[v]["tex"])
        print(f"{v:8s} {duty[v]['ta']:8.2f}% {duty[v]['valu']:9.2f}%"
              f" {duty[v]['ta_per_tex']:12.2f} {duty[v]['valucyc_per_tex']:12.2f}")
    report["duty"] = duty

    have = [v for v in order if v in dose and resp.get(v) and time.get(v)]
    if len(have) >= 3:
        # Ordinary least squares on all arms, not just the two extremes. R^2 says the arms lie on
        # a line; it does NOT say the texture count *causes* the duration - the dose is collinear
        # with VALU work and with the loop trip count. With 4 points there are 2 dof, so the
        # interval is wide and quoted only to show the intercept is not zero.
        x = [dose[v]["tex"] for v in have]
        n, mx = len(x), sum(x) / len(x)
        sxx = sum((a - mx) ** 2 for a in x)
        fits = {}
        for name, y in (("TA_BUSY", [resp[v]["ta_busy"] for v in have]),
                        ("GPUBusyCycles", [time[v]["GPUBusyCycles"] for v in have])):
            my = sum(y) / n
            slope = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx
            b0 = my - slope * mx
            yh = [b0 + slope * a for a in x]
            ss_res = sum((b - c) ** 2 for b, c in zip(y, yh))
            r2 = 1 - ss_res / sum((b - my) ** 2 for b in y)
            se = (ss_res / (n - 2) * (1 / n + mx ** 2 / sxx)) ** 0.5
            ci = (b0 - 4.303 * se, b0 + 4.303 * se)   # t(0.975, df=2)
            fits[name] = dict(slope_per_tex_instruction=slope, intercept=b0, r_squared=r2,
                              intercept_ci95=ci, slope_share_at_baseline_pct=(1 - b0 / y[0]) * 100)
            print(f"\n   {name} = {slope:.6f} x tex + {b0:,.0f}   R2 {r2:.6f}"
                  f"   intercept CI95 [{ci[0]:,.0f}, {ci[1]:,.0f}]"
                  f"\n      -> {(1 - b0 / y[0]) * 100:.2f} % of the baseline lies on the sloped "
                  f"part; the rest is fixed cost")
        report["ols_all_arms"] = fits

    (OUT / "o6_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nwrote", OUT / "o6_analysis.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "build", "run", "analyse"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("setname", nargs="?", default="tcp_ta")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--passes", type=int, default=0)
    ap.add_argument("--rep", type=int, default=1)
    a = ap.parse_args()
    if a.action == "prepare":
        prepare()
    elif a.action == "build":
        O4.build(a.name)
    elif a.action == "run":
        O4.run(a.name, a.setname, a.samples, a.passes, a.rep)
    else:
        analyse()
