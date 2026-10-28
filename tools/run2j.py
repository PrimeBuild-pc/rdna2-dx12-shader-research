"""Phase 2J - controller: brute force -> tabella di verita', poi confronto fra politiche.

La pipeline di valutazione e' quella congelata in 2I (compile -> dedup -> correctness ->
benchmark appaiato). Qui si misura TUTTO lo spazio applicabile una volta sola; predittore
e random vengono poi valutati come politiche di selezione sopra quella tabella, a parita'
di budget. Cosi' il confronto e' esatto e non dipende da quante volte si rilancia random.

    python tools/run2j.py build       genera, compila, deduplica, estrae feature
    python tools/run2j.py correct     correttezza su 5 dataset
    python tools/run2j.py measure     ground truth appaiata (tutte le trasformazioni)
    python tools/run2j.py evaluate    predittore vs random vs brute force
"""
import argparse, csv, hashlib, json, os, random, shutil, statistics, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import ir2j, corpus2j, pred2j
import ai_search as A

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "19_predictor")
TMP = os.path.join(os.environ.get("TEMP", "."), "claude", "pred2j")
HD, CD = os.path.join(OUT, "hlsl"), os.path.join(OUT, "cso")

BUDGET = 5
MEASURE_RUNS = 8
CORRECT_DS = [0, 5, 8, 12, 17]
THREADS, DATASET = 262144, 0
ACCEPT_PCT, ACCEPT_SIGMA = -1.0, 2.0


def dxil_features(cso, hlsl):
    """Disassembly DXIL: conteggi indipendenti da sorgente e ISA."""
    fc = os.path.join(TMP, "d.ll")
    rc, log = A.sh([A.DXC, "-T", "cs_6_6", "-E", "main", "-Fc", fc, hlsl])
    d = dict(dxil_bytes=os.path.getsize(cso) if os.path.exists(cso) else 0)
    if os.path.exists(fc):
        t = open(fc, encoding="utf-8", errors="replace").read()
        d.update(inst=t.count("\n  %"), br=t.count(" br "), phi=t.count(" phi "),
                 call=t.count(" call "), loads=t.count("bufferLoad") + t.count("rawBufferLoad"),
                 stores=t.count("bufferStore") + t.count("rawBufferStore"),
                 sincos=t.count("dx.op.unary.f32(i32 13") + t.count("dx.op.unary.f32(i32 12"),
                 blocks=t.count("\n; <label>"))
        os.remove(fc)
    return d


def build():
    for p in (OUT, HD, CD, TMP):
        os.makedirs(p, exist_ok=True)
    meta, feats, dedup = {}, {}, []
    for name, base in corpus2j.ALL.items():
        sh0 = dict(base, name=name)
        appl = ir2j.applicable(sh0)
        seen_src, seen_dxil, seen_isa = {}, {}, {}
        variants = [("default", sh0)] + [(t, ir2j.apply_tf(sh0, t)) for t in appl]
        for tf, sh in variants:
            vn = f"{name}__{tf}"
            src = ir2j.emit(sh)
            hs = ir2j.re.sub(r"\s+", " ", src).strip()
            hs = hashlib.sha256(hs.encode()).hexdigest()[:16]
            rec = dict(name=vn, shader=name, tf=tf, split=corpus2j.SPLIT[name],
                       tg=sh["tg"], hlsl_sha=hs)
            if hs in seen_src:
                rec.update(status="dup_hlsl", dup_of=seen_src[hs]); meta[vn] = rec
                dedup.append(rec); continue
            seen_src[hs] = vn
            hp = os.path.join(HD, vn + ".hlsl"); open(hp, "w").write(src)
            cp = os.path.join(CD, vn + ".cso")
            rc, log = A.sh([A.DXC, "-T", "cs_6_6", "-E", "main", "-Fo", cp, hp])
            if not os.path.exists(cp):
                rec.update(status="dxc_fail", log=log[-200:]); meta[vn] = rec
                print(f"  KO {vn}: DXC {log[-200:]}"); continue
            ds = hashlib.sha256(open(cp, "rb").read()).hexdigest()[:16]
            rec["dxil_sha"] = ds
            if ds in seen_dxil:
                rec.update(status="dup_dxil", dup_of=seen_dxil[ds]); meta[vn] = rec
                dedup.append(rec); continue
            seen_dxil[ds] = vn
            im = A.isa_of(hp)
            if not im:
                rec.update(status="rga_fail"); meta[vn] = rec
                print(f"  KO {vn}: RGA"); continue
            rec.update(im)
            if im["isa_sha"] in seen_isa:
                rec.update(status="dup_isa", dup_of=seen_isa[im["isa_sha"]]); meta[vn] = rec
                dedup.append(rec); continue
            seen_isa[im["isa_sha"]] = vn
            rec["status"] = "ok"
            meta[vn] = rec
            if tf == "default":
                srcf = ir2j.src_features(sh0)
                stage = ir2j.apply_tf(sh0, "lds_stage") if "lds_stage" in appl else None
                sb = 0
                if stage:
                    for ph in stage["phases"]:
                        if ph.get("lds_stage"):
                            sb = stage["tg"] * (ph.get("trip") or ph.get("n")) * 16
                feats[name] = pred2j.merge_features(srcf, im, dxil_features(cp, hp), sb)
                feats[name]["split"] = corpus2j.SPLIT[name]
                feats[name]["applicable"] = ",".join(appl)
        print(f"  {name:16s} [{corpus2j.SPLIT[name]:10s}] {len(appl)} trasformazioni, "
              f"{sum(1 for v in meta.values() if v['shader']==name and v.get('status')=='ok')} uniche, "
              f"{sum(1 for v in meta.values() if v['shader']==name and str(v.get('status','')).startswith('dup'))} dedup")
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
    json.dump(feats, open(os.path.join(OUT, "features.json"), "w"), indent=1)
    keys = sorted({k for v in feats.values() for k in v})
    with open(os.path.join(OUT, "shader_features.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["shader"] + keys); w.writeheader()
        for n, v in feats.items():
            w.writerow(dict(shader=n, **{k: v.get(k, "") for k in keys}))
    with open(os.path.join(OUT, "dedup.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["name", "shader", "tf", "status", "dup_of"])
        for r in meta.values():
            w.writerow([r["name"], r["shader"], r["tf"], r.get("status", ""), r.get("dup_of", "")])
    ok = sum(1 for v in meta.values() if v.get("status") == "ok")
    print(f"\n{ok} varianti uniche, {len(dedup)} deduplicate su {len(meta)} generate")


def live(meta, shader):
    return [(n, os.path.join(CD, n + ".cso"), r["tg"])
            for n, r in meta.items() if r["shader"] == shader and r.get("status") == "ok"]


def correct():
    meta = json.load(open(os.path.join(OUT, "meta.json")))
    rows, verdict = [], {}
    for name in corpus2j.ALL:
        specs = live(meta, name)
        ref_name = f"{name}__default"
        for ds in CORRECT_DS:
            d = os.path.join(TMP, "c"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
            A.bench(specs, ds, THREADS, d, "c")
            ref = os.path.join(d, f"out_{ref_name}.bin")
            for n, p, tg in specs:
                if n == ref_name:
                    continue
                vb = os.path.join(d, f"out_{n}.bin")
                e = (A.err_metrics(ref, vb) if os.path.exists(ref) and os.path.exists(vb)
                     else dict(bad=True, lvl="dump_mancante", max_rel=float("inf"),
                               rms_rel=float("inf"), div=-1))
                rows.append(dict(name=n, shader=name, dataset=ds, livello=e["lvl"],
                                 max_rel=f"{e['max_rel']:.3e}", rms_rel=f"{e['rms_rel']:.3e}",
                                 div=e["div"], bad=int(e["bad"])))
                v = verdict.setdefault(n, dict(bad=0, lvls=set()))
                v["bad"] += int(e["bad"]); v["lvls"].add(e["lvl"])
            shutil.rmtree(d, ignore_errors=True)
        print(f"  correttezza {name}")
    with open(os.path.join(OUT, "correctness.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "shader", "dataset", "livello", "max_rel",
                                          "rms_rel", "div", "bad"])
        w.writeheader(); w.writerows(rows)
    ok = {n: ("strict" if v["lvls"] == {"strict"} else "riassociazione")
          for n, v in verdict.items() if v["bad"] == 0}
    json.dump(ok, open(os.path.join(OUT, "correct.json"), "w"), indent=1)
    bad = [n for n, v in verdict.items() if v["bad"]]
    print(f"\ncorrette: {len(ok)} / {len(verdict)}; scartate: {bad}")


def measure():
    meta = json.load(open(os.path.join(OUT, "meta.json")))
    ok = json.load(open(os.path.join(OUT, "correct.json")))
    hist = []
    for name in corpus2j.ALL:
        specs = live(meta, name)
        ref = next((x for x in specs if x[0] == f"{name}__default"), None)
        cand = [x for x in specs if x[0] != ref[0]]
        diffs = {}
        for r in range(MEASURE_RUNS):
            rnd = random.Random(r)
            order = cand[:]; rnd.shuffle(order)
            lst = [("REF_A", ref[1], ref[2])] + order + [("REF_B", ref[1], ref[2])]
            m = A.bench(lst, DATASET, THREADS, "-", "m")
            if "REF_A" not in m or "REF_B" not in m:
                continue
            base = 0.5 * (m["REF_A"] + m["REF_B"])
            diffs.setdefault("__base__", []).append(base)
            for n, _, _ in order:
                if n in m:
                    diffs.setdefault(n, []).append(100.0 * (m[n] - base) / base)
        for n, v in diffs.items():
            if n == "__base__" or len(v) < 2:
                continue
            mu, sd = statistics.mean(v), statistics.stdev(v)
            se = sd / len(v) ** 0.5
            hist.append(dict(shader=name, split=corpus2j.SPLIT[name],
                             tf=meta[n]["tf"], name=n, runs=len(v),
                             mean_pct=round(mu, 3), se_pct=round(se, 3),
                             mean_plus_2se=round(mu + ACCEPT_SIGMA * se, 3),
                             correct=ok.get(n, "SCARTATA"),
                             accepted="SI" if (n in ok and mu < ACCEPT_PCT
                                               and mu + ACCEPT_SIGMA * se < 0) else "no"))
        print(f"  misurato {name}: {len(cand)} varianti x {MEASURE_RUNS} processi, "
              f"base {statistics.median(diffs['__base__']):.0f} ns")
    hist.sort(key=lambda r: (r["shader"], r["mean_pct"]))
    with open(os.path.join(OUT, "search_history.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(hist[0].keys())); w.writeheader(); w.writerows(hist)
    print(f"\n{sum(1 for r in hist if r['accepted']=='SI')} varianti accettate su {len(hist)}")


def _truth(meta, hist):
    """{shader: {tf: (mean_pct, accepted, correct)}} includendo i duplicati,
    che costano comunque una compilazione ma non un benchmark."""
    T = {}
    byname = {r["name"]: r for r in hist}
    for vn, r in meta.items():
        if r["tf"] == "default":
            continue
        sh, tf = r["shader"], r["tf"]
        d = T.setdefault(sh, {})
        if r.get("status") == "ok":
            h = byname.get(vn)
            d[tf] = dict(mean=(h["mean_pct"] if h else None),
                         acc=(h["accepted"] == "SI" if h else False),
                         corr=(h["correct"] if h else "SCARTATA"), dup=None)
        elif str(r.get("status", "")).startswith("dup"):
            d[tf] = dict(mean=None, acc=False, corr="dup", dup=r.get("dup_of"))
        else:
            d[tf] = dict(mean=None, acc=False, corr="fail", dup=None)
    # un duplicato eredita il risultato dell'originale: costa 0 benchmark
    for sh, d in T.items():
        for tf, v in d.items():
            if v["dup"]:
                o = next((x for k, x in d.items()
                          if meta.get(v["dup"], {}).get("tf") == k), None)
                if o:
                    v["mean"], v["acc"], v["corr"] = o["mean"], o["acc"], "dup:" + str(o["corr"])
    return T


def evaluate():
    meta = json.load(open(os.path.join(OUT, "meta.json")))
    feats = json.load(open(os.path.join(OUT, "features.json")))
    hist = list(csv.DictReader(open(os.path.join(OUT, "search_history.csv"))))
    for r in hist:
        r["mean_pct"] = float(r["mean_pct"])
    T = _truth(meta, hist)

    prop_rows, val_rows = [], []
    for name, f in feats.items():
        appl = f["applicable"].split(",")
        picks, sc = pred2j.propose(f, appl, BUDGET)
        for rank, (tf, s, why) in enumerate(picks, 1):
            g = T.get(name, {}).get(tf, {})
            prop_rows.append(dict(shader=name, split=f["split"], rank=rank, tf=tf,
                                  score=s, reason=why,
                                  measured_pct=(g.get("mean") if g else ""),
                                  accepted=("SI" if g.get("acc") else "no"),
                                  correct=g.get("corr", "")))

        def stats(sel):
            hits = sum(1 for t in sel if T.get(name, {}).get(t, {}).get("acc"))
            means = [T[name][t]["mean"] for t in sel
                     if T.get(name, {}).get(t, {}).get("mean") is not None]
            regr = sum(1 for m in means if m > 1.0)
            rej = sum(1 for t in sel if T.get(name, {}).get(t, {}).get("corr") == "SCARTATA")
            best = min(means) if means else 0.0
            first = next((i + 1 for i, t in enumerate(sel)
                          if T.get(name, {}).get(t, {}).get("acc")), None)
            return hits, best, regr, rej, first

        ph, pbest, pregr, prej, pfirst = stats([t for t, _, _ in picks])
        rnd = random.Random(12345)
        R = [stats(rnd.sample(appl, min(BUDGET, len(appl)))) for _ in range(4000)]
        rh = statistics.mean(x[0] for x in R)
        rbest = statistics.mean(x[1] for x in R)
        rregr = statistics.mean(x[2] for x in R)
        rrej = statistics.mean(x[3] for x in R)
        rfirst = [x[4] for x in R if x[4]]
        allmeans = [v["mean"] for v in T.get(name, {}).values() if v["mean"] is not None]
        oracle = min(allmeans) if allmeans else 0.0
        nacc = sum(1 for v in T.get(name, {}).values() if v["acc"])
        val_rows.append(dict(
            shader=name, split=f["split"], n_applicable=len(appl), n_accepted_total=nacc,
            oracle_best_pct=round(oracle, 2),
            pred_hits=ph, pred_best_pct=round(pbest, 2), pred_regressions=pregr,
            pred_rejected=prej, pred_first_hit=(pfirst or ""),
            rand_hits=round(rh, 3), rand_best_pct=round(rbest, 2),
            rand_regressions=round(rregr, 2), rand_rejected=round(rrej, 2),
            rand_first_hit=(round(statistics.mean(rfirst), 2) if rfirst else ""),
            rand_prob_no_hit=round(sum(1 for x in R if x[0] == 0) / len(R), 3)))

    with open(os.path.join(OUT, "transform_proposals.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(prop_rows[0].keys())); w.writeheader(); w.writerows(prop_rows)
    with open(os.path.join(OUT, "validation_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(val_rows[0].keys())); w.writeheader(); w.writerows(val_rows)

    for split in ("dev", "validation"):
        rows = [r for r in val_rows if r["split"] == split]
        print(f"\n=== {split.upper()} ({len(rows)} shader) ===")
        print(f"{'shader':16s} {'appl':>4} {'acc':>4} {'oracolo':>8} | "
              f"{'pred hit':>8} {'pred best':>9} {'1o hit':>6} | "
              f"{'rand hit':>8} {'rand best':>9} {'1o hit':>6} {'P(0 hit)':>8}")
        for r in rows:
            print(f"{r['shader']:16s} {r['n_applicable']:4d} {r['n_accepted_total']:4d} "
                  f"{r['oracle_best_pct']:+8.2f} | {r['pred_hits']:8d} {r['pred_best_pct']:+9.2f} "
                  f"{str(r['pred_first_hit']):>6} | {r['rand_hits']:8.2f} {r['rand_best_pct']:+9.2f} "
                  f"{str(r['rand_first_hit']):>6} {r['rand_prob_no_hit']:8.3f}")
        n = len(rows)
        print(f"{'MEDIA':16s} {'':4} {'':4} "
              f"{statistics.mean(r['oracle_best_pct'] for r in rows):+8.2f} | "
              f"{statistics.mean(r['pred_hits'] for r in rows):8.2f} "
              f"{statistics.mean(r['pred_best_pct'] for r in rows):+9.2f} {'':>6} | "
              f"{statistics.mean(r['rand_hits'] for r in rows):8.2f} "
              f"{statistics.mean(r['rand_best_pct'] for r in rows):+9.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build", "correct", "measure", "evaluate"])
    a = ap.parse_args()
    os.makedirs(TMP, exist_ok=True)
    A.OUT = OUT
    dict(build=build, correct=correct, measure=measure, evaluate=evaluate)[a.stage]()
