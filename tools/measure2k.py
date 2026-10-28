"""Phase 2K - misura sugli shader reali e costruzione della MEMORIA DELLE MISURE.

Protocollo invariato rispetto a 2I/2J: confronto appaiato con doppio riferimento
(default in prima e ultima posizione, media delle due) e ordine mescolato a ogni run.

    python tools/measure2k.py measure
    python tools/measure2k.py evaluate
"""
import argparse, csv, hashlib, json, os, random, shutil, statistics, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import real2k as R

OUT, TMP, CSO, VC = R.OUT, R.TMP, R.CSO, R.VC
MEM = os.path.join(OUT, "measurement_memory.csv")
BUDGETS = [1, 2, 3, 5, 8, 10]


def err_metrics(ref, var):
    a = np.fromfile(ref, dtype=np.float32); b = np.fromfile(var, dtype=np.float32)
    if a.shape != b.shape:
        return dict(bad=True, lvl="size_mismatch", max_rel=float("inf"), rms_rel=float("inf"), div=-1)
    div = int(np.count_nonzero(np.isnan(a) != np.isnan(b))) + \
          int(np.count_nonzero(np.isinf(a) != np.isinf(b)))
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return dict(bad=div > 0, lvl="degenere", max_rel=0.0, rms_rel=0.0, div=div)
    x = a[m].astype(np.float64); y = b[m].astype(np.float64)
    d = np.abs(x - y); den = np.maximum(np.abs(x), np.abs(y)); sig = den > 1e-30
    mr = float(np.max(d[sig] / den[sig])) if sig.any() else 0.0
    rms = float(np.sqrt(np.mean(d * d))); rx = float(np.sqrt(np.mean(x * x)))
    rr = rms / rx if rx else 0.0
    if div:
        return dict(bad=True, lvl="nan_inf_div", max_rel=mr, rms_rel=rr, div=div)
    if mr <= R.TOL_STRICT:
        return dict(bad=False, lvl="strict", max_rel=mr, rms_rel=rr, div=0)
    if rr <= R.TOL_RMS:
        return dict(bad=False, lvl="riassociazione", max_rel=mr, rms_rel=rr, div=0)
    return dict(bad=True, lvl="fuori_tolleranza", max_rel=mr, rms_rel=rr, div=0)


def measure():
    C = json.load(open(os.path.join(OUT, "corpus.json")))
    V = json.load(open(os.path.join(OUT, "variants.json")))
    F = json.load(open(os.path.join(OUT, "features.json")))
    rows = []
    for si, sh in enumerate(C):
        name = sh["name"]
        if name not in F:
            continue
        base = os.path.join(CSO, name + ".cso")
        cand = [(vn, v) for vn, v in V.items()
                if v["shader"] == name and v["status"] == "ok"]
        if not cand:
            print(f"  [{si+1}/{len(C)}] {name[:38]:38s} nessuna variante"); continue
        dims = tuple(sh["dims"])
        specs_base = [("REF_A", base, dims)]
        # --- correttezza: un run con dump ---
        d = os.path.join(TMP, "d"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        sp = [("REF_A", base, dims)] + [(vn, os.path.join(VC, vn + ".cso"), tuple(v["dims"]))
                                        for vn, v in cand]
        got, err = R.run_bench("c", sh["binds"], dims, sp, 4, 1, d, timeout=900, warm_ms=1)
        corr = {}
        refb = os.path.join(d, "out_REF_A.bin")
        for vn, v in cand:
            vb = os.path.join(d, f"out_{vn}.bin")
            corr[vn] = (err_metrics(refb, vb) if os.path.exists(refb) and os.path.exists(vb)
                        else dict(bad=True, lvl="dump_mancante", max_rel=float("inf"),
                                  rms_rel=float("inf"), div=-1))
        shutil.rmtree(d, ignore_errors=True)
        # --- tempi appaiati ---
        diffs, basens = {}, []
        for r in range(R.RUNS):
            rnd = random.Random(r)
            order = cand[:]; rnd.shuffle(order)
            sp = ([("REF_A", base, dims)] +
                  [(vn, os.path.join(VC, vn + ".cso"), tuple(v["dims"])) for vn, v in order] +
                  [("REF_B", base, dims)])
            got, err = R.run_bench("m", sh["binds"], dims, sp, R.REPS, R.DPM, "-", timeout=900)
            if not got or "REF_A" not in got or "REF_B" not in got:
                continue
            b = 0.5 * (got["REF_A"] + got["REF_B"]); basens.append(b)
            for vn, v in order:
                if vn in got:
                    diffs.setdefault(vn, []).append(100.0 * (got[vn] - b) / b)
        if not basens:
            print(f"  [{si+1}/{len(C)}] {name[:38]:38s} MISURA FALLITA"); continue
        f = F[name]
        for vn, v in cand:
            dv = diffs.get(vn, [])
            if len(dv) < 2:
                continue
            mu, sd = statistics.mean(dv), statistics.stdev(dv)
            se = sd / len(dv) ** 0.5
            e = corr[vn]
            rows.append(dict(
                shader=name, split=sh["split"], transform=v["tf"], variant=vn,
                params="|".join(str(x) for x in v.get("tg", sh["tg"])),
                correctness=("SCARTATA:" + e["lvl"]) if e["bad"] else e["lvl"],
                max_rel=f"{e['max_rel']:.3e}", rms_rel=f"{e['rms_rel']:.3e}", nan_inf_div=e["div"],
                delta_pct=round(mu, 3), se_pct=round(se, 3),
                delta_plus_2se=round(mu + R.ACCEPT_SIGMA * se, 3), runs=len(dv),
                base_ns=round(statistics.median(basens), 1),
                workload="x".join(map(str, dims)), dataset="fixed_synth_v1",
                dxil_sha=v.get("dxil_sha", ""), isa_sha="",
                vgpr=f.get("vgpr", ""), sgpr=f.get("sgpr", ""), lds_bytes=f.get("lds_bytes", ""),
                branch=f.get("branch", ""), waitcnt=f.get("waitcnt", ""),
                wait_per_mem=f.get("wait_per_mem", ""), load_use_med=f.get("load_use_med", ""),
                clause=f.get("clause", ""), vmem=f.get("vmem", ""), n_loops=f.get("n_loops", ""),
                tg_total=f.get("tg_total", ""),
                accepted="SI" if (not e["bad"] and mu < R.ACCEPT_PCT
                                  and mu + R.ACCEPT_SIGMA * se < 0) else "no"))
        acc = sum(1 for r in rows if r["shader"] == name and r["accepted"] == "SI")
        print(f"  [{si+1}/{len(C)}] {name[:38]:38s} {len(cand):2d} varianti, base "
              f"{statistics.median(basens):9.0f} ns, {acc} accettate")
    with open(MEM, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    nacc = sum(1 for r in rows if r["accepted"] == "SI")
    nbad = sum(1 for r in rows if r["correctness"].startswith("SCARTATA"))
    print(f"\nmemoria: {len(rows)} misure, {nacc} accettate, {nbad} scartate per correttezza")


# ------------------------------------------------------------------ predittore
FEATKEYS = ["vgpr", "sgpr", "lds_bytes", "branch", "waitcnt", "wait_per_mem", "load_use_med",
            "clause", "vmem", "n_loops", "tg_total", "inst", "valu", "salu", "trans",
            "samp", "n_tex", "wave_ops", "base_ns"]


def vec(f, mu, sg):
    v = []
    for k in FEATKEYS:
        x = float(f.get(k, 0) or 0)
        v.append((x - mu[k]) / sg[k] if sg[k] > 0 else 0.0)
    return np.array(v)


def evaluate():
    F = json.load(open(os.path.join(OUT, "features.json")))
    M = list(csv.DictReader(open(MEM)))
    for r in M:
        r["delta_pct"] = float(r["delta_pct"])
    dev = [n for n, f in F.items() if f["split"] == "dev"]
    val = [n for n, f in F.items() if f["split"] == "REAL_VALIDATION"]
    mu = {k: statistics.mean(float(F[n].get(k, 0) or 0) for n in dev) for k in FEATKEYS}
    sg = {k: (statistics.pstdev(float(F[n].get(k, 0) or 0) for n in dev) or 1.0) for k in FEATKEYS}

    # le misure invalidate (la trasformazione cambia il numero totale di thread)
    # restano nel database ma non partecipano ne' al ranking ne' alla valutazione
    M = [r for r in M if r.get("valid", "si") == "si"]
    T = {}
    for r in M:
        T.setdefault(r["shader"], {})[r["transform"]] = r
    devmem = [r for r in M if r["split"] == "dev"]

    def memory_rank(name, appl, k=5):
        """kNN sui dev: per ogni trasformazione, media pesata dei Delta osservati
        sugli shader piu' simili. Fallback: media globale della trasformazione."""
        f = F[name]; v0 = vec(f, mu, sg)
        d = sorted(((float(np.linalg.norm(vec(F[n], mu, sg) - v0)), n) for n in dev))
        sc = {}
        for t in appl:
            near = [(dist, r["delta_pct"]) for dist, n in d
                    for r in [T.get(n, {}).get(t)] if r]
            if near:
                near = near[:k]
                w = [1.0 / (1.0 + x[0]) for x in near]
                sc[t] = (sum(wi * x[1] for wi, x in zip(w, near)) / sum(w), len(near))
            else:
                g = [r["delta_pct"] for r in devmem if r["transform"] == t]
                sc[t] = (statistics.mean(g) if g else 0.0, 0)
        return sorted(appl, key=lambda t: (sc[t][0], t)), sc

    def rules_rank(name, appl):
        """Solo-regole: ordine fisso derivato dalle euristiche di 2J, senza misure."""
        pri = {"all_unroll": 0, "L0_unroll": 1, "L1_unroll": 2, "all_unroll4": 3,
               "L0_unroll4": 4, "L1_unroll4": 5, "wave32": 6, "all_loop": 7,
               "L0_loop": 8, "L1_loop": 9, "wave64": 10}
        return sorted(appl, key=lambda t: (pri.get(t, 20), t)), {}

    def stats(name, sel):
        d = T.get(name, {})
        ds = [d[t]["delta_pct"] for t in sel if t in d]
        hits = sum(1 for t in sel if d.get(t, {}).get("accepted") == "SI")
        rej = sum(1 for t in sel if str(d.get(t, {}).get("correctness", "")).startswith("SCARTATA"))
        first = next((i + 1 for i, t in enumerate(sel) if d.get(t, {}).get("accepted") == "SI"), None)
        return dict(hits=hits, best=(min(ds) if ds else 0.0),
                    regr=sum(1 for x in ds if x > 1.0), rej=rej, first=first)

    rows, prop = [], []
    for name in val:
        appl = sorted(T.get(name, {}).keys())
        if not appl:
            continue
        mem_order, sc = memory_rank(name, appl)
        rule_order, _ = rules_rank(name, appl)
        allv = [T[name][t]["delta_pct"] for t in appl]
        oracle = min(allv) if allv else 0.0
        nacc = sum(1 for t in appl if T[name][t]["accepted"] == "SI")
        for rank, t in enumerate(mem_order[:max(BUDGETS)], 1):
            prop.append(dict(shader=name, rank=rank, transform=t,
                             predicted_pct=round(sc[t][0], 3), neighbours=sc[t][1],
                             measured_pct=T[name][t]["delta_pct"],
                             accepted=T[name][t]["accepted"],
                             correctness=T[name][t]["correctness"]))
        row = dict(shader=name, n_applicable=len(appl), n_accepted=nacc,
                   oracle_pct=round(oracle, 2))
        for B in BUDGETS:
            b = min(B, len(appl))
            sm = stats(name, mem_order[:b]); sr = stats(name, rule_order[:b])
            rnd = random.Random(1234)
            RR = [stats(name, rnd.sample(appl, b)) for _ in range(3000)]
            row[f"mem_best_B{B}"] = round(sm["best"], 2)
            row[f"mem_hits_B{B}"] = sm["hits"]
            row[f"rule_best_B{B}"] = round(sr["best"], 2)
            row[f"rand_best_B{B}"] = round(statistics.mean(x["best"] for x in RR), 2)
            row[f"rand_hits_B{B}"] = round(statistics.mean(x["hits"] for x in RR), 3)
            row[f"rand_pfail_B{B}"] = round(sum(1 for x in RR if x["hits"] == 0) / len(RR), 3)
        row["mem_first_hit"] = stats(name, mem_order)["first"] or ""
        rows.append(row)

    with open(os.path.join(OUT, "transform_proposals.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(prop[0].keys())); w.writeheader(); w.writerows(prop)
    with open(os.path.join(OUT, "validation_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    print(f"\nREAL_VALIDATION: {len(rows)} shader mai usati per costruire il ranking")
    print(f"spazio: {statistics.mean(r['n_applicable'] for r in rows):.1f} trasformazioni/shader, "
          f"{sum(r['n_accepted'] for r in rows)} varianti accettate in totale")
    print(f"\n{'budget':>6} | {'memoria':>9} {'hit':>5} | {'regole':>9} | {'random':>9} {'hit':>5} "
          f"{'P(0 hit)':>9} | {'oracolo':>8}")
    orc = statistics.mean(r["oracle_pct"] for r in rows)
    for B in BUDGETS:
        m = lambda k: statistics.mean(r[k] for r in rows)
        print(f"{B:6d} | {m(f'mem_best_B{B}'):+9.2f} {m(f'mem_hits_B{B}'):5.2f} | "
              f"{m(f'rule_best_B{B}'):+9.2f} | {m(f'rand_best_B{B}'):+9.2f} "
              f"{m(f'rand_hits_B{B}'):5.2f} {m(f'rand_pfail_B{B}'):9.3f} | {orc:+8.2f}")
    m2 = statistics.mean(r["mem_best_B2"] for r in rows)
    need = next((B for B in BUDGETS if statistics.mean(r[f"rand_best_B{B}"] for r in rows) <= m2), None)
    print(f"\nmemoria con budget 2 = {m2:+.2f}%; random lo raggiunge con budget "
          f"{need}" if need else
          f"\nmemoria con budget 2 = {m2:+.2f}%; random NON lo raggiunge nemmeno con budget {max(BUDGETS)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["measure", "evaluate"])
    a = ap.parse_args()
    os.makedirs(TMP, exist_ok=True)
    dict(measure=measure, evaluate=evaluate)[a.stage]()
