"""Phase 2J - confronto fra politiche di selezione, a parita' di budget.

Tutte le trasformazioni applicabili sono gia' state misurate (`run2j.py measure`), quindi
il confronto e' esatto: nessuna politica costa benchmark aggiuntivi.

  A  regole scritte a mano, prior statici dai DEV
  B  A + evidenza misurata dai soli shader DEV (nessuna fuga dalla validation)
  C  B + apprendimento online sulla validation: impara SOLO dai benchmark che ha speso,
     mediato su 200 ordini casuali degli shader
  R  random: 5 trasformazioni a caso fra le applicabili, media su 4000 estrazioni
  K  catalogo: le prime 5 applicabili in ordine fisso (brute force limitato)

    python tools/eval2j.py
"""
import csv, json, os, random, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir2j, pred2j, run2j

OUT = run2j.OUT
BUDGET = run2j.BUDGET


def stats(name, sel, T):
    d = T.get(name, {})
    means = [d[t]["mean"] for t in sel if d.get(t, {}).get("mean") is not None]
    return dict(hits=sum(1 for t in sel if d.get(t, {}).get("acc")),
                best=(min(means) if means else 0.0),
                regr=sum(1 for m in means if m > 1.0),
                first=next((i + 1 for i, t in enumerate(sel) if d.get(t, {}).get("acc")), None))


def main():
    meta = json.load(open(os.path.join(OUT, "meta.json")))
    feats = json.load(open(os.path.join(OUT, "features.json")))
    hist = list(csv.DictReader(open(os.path.join(OUT, "search_history.csv"))))
    for r in hist:
        r["mean_pct"] = float(r["mean_pct"])
    T = run2j._truth(meta, hist)

    def ev_from(shaders):
        E = {}
        for sh in shaders:
            for tf, v in T.get(sh, {}).items():
                if v["mean"] is not None:
                    E.setdefault(tf, []).append((feats[sh], v["mean"]))
        return E

    DEV = [n for n, f in feats.items() if f["split"] == "dev"]
    VAL = [n for n, f in feats.items() if f["split"] == "validation"]
    dev_ev = ev_from(DEV)
    CAT = list(ir2j.TRANSFORMS.keys())

    prop, rows = [], []
    for name, f in feats.items():
        appl = f["applicable"].split(",")
        B = min(BUDGET, len(appl))
        isval = f["split"] == "validation"
        pA, _ = pred2j.propose(f, appl, B)
        pB, _ = pred2j.propose(f, appl, B, evidence=(dev_ev if isval else None))
        selA, selB = [t for t, _, _ in pA], [t for t, _, _ in pB]
        selK = [t for t in CAT if t in appl][:B]
        for rank, (tf, sc, why) in enumerate(pB if isval else pA, 1):
            g = T.get(name, {}).get(tf, {})
            prop.append(dict(shader=name, split=f["split"], rank=rank, tf=tf, score=sc,
                             reason=why, measured_pct=g.get("mean", ""),
                             accepted=("SI" if g.get("acc") else "no"), correct=g.get("corr", "")))
        sA, sB, sK = stats(name, selA, T), stats(name, selB, T), stats(name, selK, T)
        rnd = random.Random(7)
        R = [stats(name, rnd.sample(appl, B), T) for _ in range(4000)]
        allm = [v["mean"] for v in T.get(name, {}).values() if v["mean"] is not None]
        rows.append(dict(shader=name, split=f["split"], n_applicable=len(appl),
            n_accepted_total=sum(1 for v in T.get(name, {}).values() if v["acc"]),
            oracle_best_pct=round(min(allm) if allm else 0.0, 2),
            A_hits=sA["hits"], A_best_pct=round(sA["best"], 2), A_regr=sA["regr"],
            A_first=sA["first"] or "",
            B_hits=sB["hits"], B_best_pct=round(sB["best"], 2), B_regr=sB["regr"],
            B_first=sB["first"] or "",
            K_hits=sK["hits"], K_best_pct=round(sK["best"], 2),
            rand_hits=round(statistics.mean(x["hits"] for x in R), 3),
            rand_best_pct=round(statistics.mean(x["best"] for x in R), 2),
            rand_regr=round(statistics.mean(x["regr"] for x in R), 2),
            rand_first=(round(statistics.mean(x["first"] for x in R if x["first"]), 2)
                        if any(x["first"] for x in R) else ""),
            rand_p_no_hit=round(sum(1 for x in R if x["hits"] == 0) / len(R), 3)))

    # --- politica C: online, impara solo dai benchmark che ha effettivamente speso ---
    onl = {n: [] for n in VAL}
    rp = random.Random(99)
    for _ in range(200):
        order = VAL[:]; rp.shuffle(order)
        E = {k: list(v) for k, v in dev_ev.items()}
        for name in order:
            f = feats[name]; appl = f["applicable"].split(",")
            B = min(BUDGET, len(appl))
            picks, _ = pred2j.propose(f, appl, B, evidence=E)
            sel = [t for t, _, _ in picks]
            onl[name].append(stats(name, sel, T))
            for t in sel:
                m = T.get(name, {}).get(t, {}).get("mean")
                if m is not None:
                    E.setdefault(t, []).append((f, m))
    for r in rows:
        if r["split"] == "validation":
            o = onl[r["shader"]]
            r["C_hits"] = round(statistics.mean(x["hits"] for x in o), 2)
            r["C_best_pct"] = round(statistics.mean(x["best"] for x in o), 2)
            r["C_regr"] = round(statistics.mean(x["regr"] for x in o), 2)
        else:
            r["C_hits"] = r["C_best_pct"] = r["C_regr"] = ""

    with open(os.path.join(OUT, "transform_proposals.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(prop[0].keys())); w.writeheader(); w.writerows(prop)
    with open(os.path.join(OUT, "validation_results.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    for split in ("dev", "validation"):
        rs = [r for r in rows if r["split"] == split]
        print(f"\n=== {split.upper()} - budget {BUDGET} benchmark per shader ===")
        print(f"{'shader':16s} {'app':>3} {'acc':>3} {'oracolo':>8} | {'A':>5} {'A best':>8} "
              f"{'B':>5} {'B best':>8} {'C':>5} {'C best':>8} | {'rand':>5} {'rand best':>9} "
              f"{'cat':>4} {'P(0)':>5}")
        for r in rs:
            print(f"{r['shader']:16s} {r['n_applicable']:3d} {r['n_accepted_total']:3d} "
                  f"{r['oracle_best_pct']:+8.2f} | {r['A_hits']:5d} {r['A_best_pct']:+8.2f} "
                  f"{r['B_hits']:5d} {r['B_best_pct']:+8.2f} {str(r['C_hits']):>5} "
                  f"{str(r['C_best_pct']):>8} | {r['rand_hits']:5.2f} {r['rand_best_pct']:+9.2f} "
                  f"{r['K_hits']:4d} {r['rand_p_no_hit']:5.2f}")
        m = lambda k: statistics.mean(float(r[k]) for r in rs if r[k] != "")
        print(f"{'MEDIA':16s} {'':3} {'':3} {m('oracle_best_pct'):+8.2f} | "
              f"{m('A_hits'):5.2f} {m('A_best_pct'):+8.2f} {m('B_hits'):5.2f} {m('B_best_pct'):+8.2f} "
              f"{(m('C_hits') if split == 'validation' else 0):5.2f} "
              f"{(m('C_best_pct') if split == 'validation' else 0):+8.2f} | "
              f"{m('rand_hits'):5.2f} {m('rand_best_pct'):+9.2f} {m('K_hits'):4.2f}")
        if split == "validation":
            orc = m("oracle_best_pct")
            print("\n   frazione dell'oracolo catturata e hit rate (proposte utili / proposte):")
            for lbl, kb, kh in (("A  regole", "A_best_pct", "A_hits"),
                                ("B  +evidenza dev", "B_best_pct", "B_hits"),
                                ("C  online", "C_best_pct", "C_hits"),
                                ("R  random", "rand_best_pct", "rand_hits"),
                                ("K  catalogo", "K_best_pct", "K_hits")):
                print(f"     {lbl:18s} {100*m(kb)/orc:5.1f}%   hit rate {100*m(kh)/BUDGET:5.1f}%")


if __name__ == "__main__":
    main()
