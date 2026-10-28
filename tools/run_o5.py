"""Phase 2O cycle O5: stage attribution + cache/memory classification of `Render Color`.

O3 and O4 together said the cost of this pass is not filtering: removing the anisotropy
entirely, with the pixel shader bytecode byte-identical, moves it by at most ~3 %. Two things
stayed unmeasured and both are prerequisites for any bottleneck claim:

  (A) `TA_BUSY` was never attributed to a shader stage. Every texture ratio in O2/O3/O4 divided
      a whole-block timing counter by a *pixel-stage* work counter. If the vertex stage issues
      texture instructions in this scope, those ratios are biased.
  (B) The texture unit is 94 % busy - but busy doing what? `TCP_PERF_SEL_TCP_TA_REQ_STALL`
      counts the cycles the L0 vector cache holds the texture addresser back. That is the
      difference between "the addresser is working" and "the addresser is waiting on memory",
      and it has never been read.

No new build: this cycle reuses the five O4 executables, whose pixel shader bytecode is pinned
to the O1 baseline by the same fail-closed gate. Only the counter sets change, so the sampler
variants double as a memory-traffic lever at fixed bytecode.

    python -B tools/run_o5.py prepare
    python -B tools/run_o5.py run <variant> <set> [--samples N] [--passes N] [--rep R]
    python -B tools/run_o5.py analyse
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/30_o5_memory"
O4OUT = ROOT / "research/29_o4_sampler"
HW = ROOT / "research/26_gpa_hwcounters/counters_hardware.csv"
VARIANTS = ["s_base", "s_aniso1", "s_point", "s_bilinear"]


def hw_names():
    return [r["name"] for r in csv.DictReader(HW.open(encoding="utf-8"))]


def sets():
    """Every set is single-pass except `stage_tex`, whose 2 passes are forced by the hardware:
    the PS and VS shader masks of the same SQ event cannot share a pass. Pass counts were
    measured offline with gpaenum_hw.exe before any of this ran."""
    n = hw_names()
    p = lambda f: sorted(x for x in n if f(x))
    return {
        # (A) which stage issues the texture instructions in this scope
        "stage_tex": p(lambda x: x.startswith(("SQ_PS", "SQ_VS"))
                       and x.endswith(("PERF_SEL_INSTS_TEX_LOAD", "PERF_SEL_WAVES"))),
        # (A, control added mid-cycle) `SQ_VS*` read zero WAVES as well as zero texture loads,
        # which on its own cannot tell "the vertex stage issues no texture instruction" from
        # "the vertex stage does not run under the VS mask at all". RDNA2 maps a plain vertex
        # shader onto the NGG primitive-shader stage, so all eight shader masks are swept.
        # 7 passes, measured offline; aggregate work counters only, which O2 showed to be
        # reproducible across passes.
        "stage_all": p(lambda x: x.startswith("SQ_")
                       and x.endswith(("PERF_SEL_INSTS_TEX_LOAD", "PERF_SEL_WAVES"))),
        # (B) is the texture addresser held back by the L0 vector cache, and how often does it miss
        "tcp_ta": p(lambda x: (x.startswith("TCP") and x.endswith(
            ("PERF_SEL_REQ", "PERF_SEL_REQ_MISS", "PERF_SEL_TCP_TA_REQ_STALL")))
            or x.endswith("PERF_SEL_TA_BUSY")),
        # (C) hit rates further out: L1 (GL1C) and L2 (GL2C)
        "l1l2": p(lambda x: x.startswith("GL1C")
                  or (x.startswith("GL2C") and x.endswith(("PERF_SEL_REQ", "PERF_SEL_MISS")))),
        # (C) bytes actually read from memory, plus TA_BUSY in the same pass to normalise
        "dram": p(lambda x: (x.startswith("GL2C") and "EA_RDREQ" in x)
                  or x.endswith("PERF_SEL_TA_BUSY")),
    }


def prepare():
    OUT.mkdir(exist_ok=False)
    (OUT / "sets").mkdir()
    m4 = json.loads((O4OUT / "experiment_manifest.json").read_text())
    passes = {"stage_tex": 2, "tcp_ta": 1, "l1l2": 1, "dram": 1}
    counts = {}
    for name, counters in sets().items():
        (OUT / "sets" / f"{name}.txt").write_text("\n".join(counters) + "\n", encoding="utf-8")
        counts[name] = len(counters)

    # Reuse O4's verified builds. The executable hash is re-checked here and again at every run.
    for label in VARIANTS:
        a = json.loads((O4OUT / f"build_{label}.json").read_text())
        G.require(G.sha(a["executable"]) == a["executable_sha256"],
                  f"{label}: executable changed since the O4 build")
        G.require(a["bytecode_sha256"] == m4["expected_bytecode"],
                  f"{label}: shader is not the O1 baseline")
        G.save_json(OUT / f"build_{label}.json", a)

    G.save_json(OUT / "experiment_manifest.json", dict(
        experiment_id="O5_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
        created_at=datetime.now().astimezone().isoformat(), cycle="O5",
        workspace=m4["workspace"], original_source=m4["original_source"],
        dxc_selected=m4["dxc_selected"], configuration=m4["configuration"],
        first_frame=m4["first_frame"], patched_file=m4["patched_file"],
        reuses_builds_from="research/29_o4_sampler", variants={k: m4["variants"][k]
                                                               for k in VARIANTS},
        expected_bytecode=m4["expected_bytecode"], expected_artifact=m4["expected_artifact"],
        set_sizes=counts, set_passes_measured_offline=passes,
        ablation_kind="classification - no image claim, no accepted optimisation",
        preregistered_criteria=dict(
            A_question="what fraction of the texture instructions issued inside the Render "
                       "Color scope comes from the vertex stage rather than the pixel stage",
            A_prediction="< 1 %. ModelViewerVS.hlsl contains no Texture object and no Sample "
                         "call, so the vertex stage should issue zero texture instructions.",
            A_consequence="if the vertex share exceeds 5 %, every texture ratio in O2, O3 and "
                          "O4 that divided a whole-block TA counter by SQ_PS INSTS_TEX_LOAD is "
                          "biased and must be restated with the corrected denominator.",
            A_caveat="the PS and VS masks of one SQ event cannot share a hardware pass, so this "
                     "comparison is inherently cross-pass. O2 established that aggregate work "
                     "counters are reproducible across passes and that INSTS_TEX_LOAD carries "
                     "an emulation band of +-0.4 %; both are reported alongside the result.",
            B_question="is the texture addresser's busy time work, or waiting on the L0 cache",
            B_metric="sum over the 80 CUs of TCP_PERF_SEL_TCP_TA_REQ_STALL divided by the sum "
                     "of TA_PERF_SEL_TA_BUSY, both read in the same single pass",
            B_bands="stall/busy >= 30 % -> the addresser is predominantly held back by the L0 "
                    "vector cache, so the 94 % TexUnitBusy of 2N is a cache symptom; <= 10 % -> "
                    "the L0 cache is not what keeps the addresser busy; in between -> "
                    "inconclusive and O6 must discriminate. Bands fixed before any measurement.",
            B_unit_caveat="TCP and TA counters are cycle counters of two different blocks. "
                          "Their ratio is treated as an indicator, not an identity, unless the "
                          "sampler intervention moves it in the direction its meaning predicts.",
            C_question="where do the texture fetches land - L0, L1, L2 or DRAM",
            C_metrics="hit rate at each level (1 - miss/req), DRAM read bytes computed as "
                      "32*EA_RDREQ_32B + 64*EA_RDREQ_64B + 96*EA_RDREQ_96B + 128*EA_RDREQ_128B, "
                      "and misses per pixel-stage texture instruction",
            D_intervention="the four O4 sampler builds are a memory-traffic lever at byte-"
                           "identical bytecode: point filtering reads one texel per quad where "
                           "bilinear reads four. Dose = TCP REQ and L0 misses; response = "
                           "TA_BUSY and the stall ratio. A cache-bound pass must show the stall "
                           "ratio fall when the traffic falls.",
            statistic="median over >= 32 samples per run, >= 3 independent processes for the "
                      "baseline profile, order interleaved; work counters are reported with "
                      "their across-process spread and no single-run value is used alone",
            timing_source="GPUTime and GPUBusyCycles are NOT re-measured here. Mixing a derived "
                          "counter into a raw set costs an extra pass, and O4 already measured "
                          "them on these exact executables. O4's response table is the timing "
                          "reference and is cited as such.",
            o6_rule="O6 replicates or falsifies whichever cause O5 ranks first, with a fresh "
                    "fixed-bytecode intervention chosen to make that cause's prediction fail "
                    "if it is wrong. The intervention is written down before it is run."),
        workspace_budget_bytes=m4["workspace_budget_bytes"]))
    print("prepared", OUT, {k: (counts[k], passes[k]) for k in counts}, flush=True)


def run(label, setname, samples, passes, rep):
    O4.OUT = OUT          # same runner, same gate, this cycle's artifacts
    O4.run(label, setname, samples, passes, rep)


# ---------------------------------------------------------------- analysis

def load(tag):
    path = OUT / "runs" / tag / "gpa_results.csv"
    if not path.is_file():
        return None
    by = {}
    for r in csv.DictReader(path.open(encoding="utf-8")):
        by.setdefault(r["counter"], {})[int(r["sample"])] = float(r["value"])
    return {c: [v[i] for i in sorted(v)] for c, v in by.items()}


def tot(data, pattern):
    keys = [c for c in data if re.fullmatch(pattern, c)]
    if not keys:
        return None
    n = len(data[keys[0]])
    return statistics.median(sum(data[k][i] for k in keys) for i in range(n))


def reps(label, setname):
    out = {}
    for rep in (1, 2, 3):
        d = load(f"{label}_{setname}_r{rep}")
        if d:
            out[rep] = d
    return out


def spread(values):
    values = [v for v in values if v is not None]
    if len(values) < 2:
        return 0.0
    return (max(values) - min(values)) / (sum(values) / len(values)) * 100


def analyse():
    m = json.loads((OUT / "experiment_manifest.json").read_text())
    report = {"experiment_id": m["experiment_id"], "criteria": m["preregistered_criteria"]}
    line = "=" * 92

    print(line, "\nA. STAGE ATTRIBUTION  (stage_tex, 2 passes forced by the SQ shader mask)\n", line)
    a = {}
    for rep, d in reps("s_base", "stage_tex").items():
        a[rep] = dict(ps_tex=tot(d, r"SQ_PS\d_PERF_SEL_INSTS_TEX_LOAD"),
                      vs_tex=tot(d, r"SQ_VS\d_PERF_SEL_INSTS_TEX_LOAD"),
                      ps_waves=tot(d, r"SQ_PS\d_PERF_SEL_WAVES"),
                      vs_waves=tot(d, r"SQ_VS\d_PERF_SEL_WAVES"))
    for rep, x in a.items():
        share = x["vs_tex"] / (x["ps_tex"] + x["vs_tex"]) * 100 if (x["ps_tex"] + x["vs_tex"]) else 0
        print(f"   process {rep}: PS tex {x['ps_tex']:>14,.0f}   VS tex {x['vs_tex']:>12,.0f}"
              f"   VS share {share:6.3f} %   PS waves {x['ps_waves']:>10,.0f}"
              f"   VS waves {x['vs_waves']:>10,.0f}")
    if a:
        shares = [x["vs_tex"] / (x["ps_tex"] + x["vs_tex"]) * 100 for x in a.values()
                  if (x["ps_tex"] + x["vs_tex"])]
        verdict = ("PASS - prediction held" if max(shares) < 1 else
                   "RESTATE O2/O3/O4 ratios" if max(shares) > 5 else "between 1 % and 5 %")
        print(f"\n   across-process spread of PS tex: {spread([x['ps_tex'] for x in a.values()]):.3f} %"
              f"  (O2 emulation band +-0.4 %)")
        print(f"   preregistered prediction < 1 %  ->  {verdict}")
        report["A_vs_share_pct"] = shares
    report["A"] = a

    print("\n" + line, "\nB. IS THE ADDRESSER WAITING ON THE L0 CACHE  (tcp_ta, 1 pass)\n", line)
    b = {}
    for v in VARIANTS:
        per = {}
        for rep, d in reps(v, "tcp_ta").items():
            per[rep] = dict(stall=tot(d, r"TCP\d+_PERF_SEL_TCP_TA_REQ_STALL"),
                            req=tot(d, r"TCP\d+_PERF_SEL_REQ"),
                            miss=tot(d, r"TCP\d+_PERF_SEL_REQ_MISS"),
                            ta_busy=tot(d, r"TA\d+_PERF_SEL_TA_BUSY"))
        if per:
            b[v] = per
    print(f"{'variant':11s} {'TCP req':>16s} {'L0 miss':>14s} {'L0 hit%':>8s} {'TA stall':>16s}"
          f" {'TA_BUSY':>14s} {'stall/busy':>11s}")
    for v, per in b.items():
        med = {k: statistics.median(p[k] for p in per.values()) for k in
               ("stall", "req", "miss", "ta_busy")}
        b[v]["median"] = med
        print(f"{v:11s} {med['req']:16,.0f} {med['miss']:14,.0f}"
              f" {(1 - med['miss'] / med['req']) * 100 if med['req'] else 0:7.2f}%"
              f" {med['stall']:16,.0f} {med['ta_busy']:14,.0f}"
              f" {med['stall'] / med['ta_busy'] * 100 if med['ta_busy'] else 0:10.2f}%")
    if "s_base" in b:
        ratio = b["s_base"]["median"]["stall"] / b["s_base"]["median"]["ta_busy"] * 100
        band = ("CACHE-BOUND band (>=30 %)" if ratio >= 30 else
                "NOT the L0 cache (<=10 %)" if ratio <= 10 else "INCONCLUSIVE band (10-30 %)")
        print(f"\n   baseline stall/busy = {ratio:.2f} %  ->  {band}")
        report["B_stall_over_busy_pct"] = ratio
    if "s_base" in b and "s_point" in b:
        print("\n   intervention (dose at byte-identical bytecode), vs s_base:")
        for v in VARIANTS[1:]:
            if v not in b:
                continue
            d0, d1 = b["s_base"]["median"], b[v]["median"]
            f = lambda k: (d1[k] - d0[k]) / d0[k] * 100 if d0[k] else float("nan")
            r0 = d0["stall"] / d0["ta_busy"] * 100
            r1 = d1["stall"] / d1["ta_busy"] * 100
            print(f"   {v:11s} d TCP req {f('req'):7.2f} %  d L0 miss {f('miss'):7.2f} %"
                  f"  d TA stall {f('stall'):7.2f} %  d TA_BUSY {f('ta_busy'):7.2f} %"
                  f"  stall/busy {r0:.2f} -> {r1:.2f} %")
    report["B"] = {v: {str(k): p for k, p in per.items()} for v, per in b.items()}

    print("\n" + line, "\nC. WHERE THE FETCHES LAND  (l1l2 + dram, 1 pass each)\n", line)
    c = {}
    for v in VARIANTS:
        e = {}
        for rep, d in reps(v, "l1l2").items():
            e.setdefault("gl1c_req", []).append(tot(d, r"GL1C\d+_PERF_SEL_REQ"))
            e.setdefault("gl1c_miss", []).append(tot(d, r"GL1C\d+_PERF_SEL_REQ_MISS"))
            e.setdefault("gl2c_req", []).append(tot(d, r"GL2C\d+_PERF_SEL_REQ"))
            e.setdefault("gl2c_miss", []).append(tot(d, r"GL2C\d+_PERF_SEL_MISS"))
        for rep, d in reps(v, "dram").items():
            rd = sum(k * (tot(d, rf"GL2C\d+_PERF_SEL_EA_RDREQ_{k}B") or 0)
                     for k in (32, 64, 96, 128))
            e.setdefault("dram_read_bytes", []).append(rd)
            e.setdefault("ta_busy_dram", []).append(tot(d, r"TA\d+_PERF_SEL_TA_BUSY"))
        if e:
            c[v] = {k: statistics.median(vals) for k, vals in e.items()}
            c[v]["_spread"] = {k: spread(vals) for k, vals in e.items()}
    for v, x in c.items():
        print(f"{v:11s} L1 req {x.get('gl1c_req', 0):14,.0f} hit "
              f"{(1 - x['gl1c_miss'] / x['gl1c_req']) * 100 if x.get('gl1c_req') else 0:6.2f}%"
              f"   L2 req {x.get('gl2c_req', 0):14,.0f} hit "
              f"{(1 - x['gl2c_miss'] / x['gl2c_req']) * 100 if x.get('gl2c_req') else 0:6.2f}%"
              f"   DRAM read {x.get('dram_read_bytes', 0) / 1e6:9.2f} MB")
    report["C"] = c

    print("\n" + line, "\nD. DERIVED, AND A SELF-CONSISTENCY CHECK\n", line)
    # O4 measured GPUTime/GPUBusyCycles on these exact executables; see the manifest's
    # timing_source note. They are read from there rather than re-measured at an extra pass.
    o4 = json.loads((O4OUT / "o4_analysis.json").read_text())["response_median"]
    ps_tex = statistics.median(x["ps_tex"] for x in a.values()) if a else None
    d = {}
    if ps_tex and "s_base" in b and "s_base" in c:
        bb, cc = b["s_base"]["median"], c["s_base"]
        gput, gpub = o4["s_base"]["GPUTime"], o4["s_base"]["GPUBusyCycles"]
        d = dict(
            ps_tex_instructions=ps_tex,
            ta_busy_cycles_per_tex_instruction=bb["ta_busy"] / ps_tex,
            tcp_requests_per_tex_instruction=bb["req"] / ps_tex,
            l0_misses_per_tex_instruction=bb["miss"] / ps_tex,
            ta_busy_per_cu=bb["ta_busy"] / 80,
            ta_duty_cycle_pct=bb["ta_busy"] / 80 / gpub * 100,
            dram_read_MB=cc["dram_read_bytes"] / 1e6,
            dram_read_GB_per_s=cc["dram_read_bytes"] / (gput * 1e-9) / 1e9,
            l2_misses_x64B_MB=cc["gl2c_miss"] * 64 / 1e6)
        for k, v in d.items():
            print(f"   {k:44s} {v:>16,.2f}")
        agree = abs(d["l2_misses_x64B_MB"] - d["dram_read_MB"]) / d["dram_read_MB"] * 100
        print(f"\n   L2 misses x 64 B vs measured DRAM read bytes: {agree:.2f} % apart"
              f"  ({'consistent' if agree < 5 else 'INCONSISTENT - do not trust these counters'})")
    report["D"] = d

    (OUT / "o5_analysis.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nwrote", OUT / "o5_analysis.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "run", "analyse"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("setname", nargs="?", default="tcp_ta")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--passes", type=int, default=0)
    ap.add_argument("--rep", type=int, default=1)
    a = ap.parse_args()
    if a.action == "prepare":
        prepare()
    elif a.action == "run":
        run(a.name, a.setname, a.samples, a.passes, a.rep)
    else:
        analyse()
