"""Phase 2J - predittore interpretabile: feature -> proposte di trasformazione.

Regole scritte a mano, ognuna con l'evidenza dev che la giustifica. Il predittore
PROPONE soltanto: non puo' dichiarare vincente niente senza benchmark.

Le feature usate dal predittore sono quelle della BASELINE (sorgente + DXIL + ISA).
Non vede l'ISA delle varianti: sarebbe come vederne il risultato.
"""

# Prior statici: media dei d% osservati sui DEV shader in 2H/2I, in punti percentuali.
# Servono solo a ordinare a parita' di regole, non a decidere.
DEV_PRIOR = {
    "unroll_all":  -3.0,    # 9 meglio / 3 peggio / 8 uguale sul corpus 2H
    "loop_all":    +0.0,    # 2H: no-op su 20 shader su 20
    "unroll_loads": -0.5,
    "widen2":      -1.0, "widen4": -0.5,
    "hoist_cond2": -20.0, "hoist_cond4": -18.0,   # 2I: -69.5% / -67.5% su d_bdiv
    "acc2":        -1.0, "acc4": -2.0,            # 2I: dot__acc4 -5.8%
    "load_first":  +12.0,                          # 2I: +24.9% / +28.3%
    "lds_stage":   +90.0,                          # 2I: +93% / +100% / +110%
    "tree_reduce": -14.0, "wave_reduce": -14.5,   # 2I
    "tg32":        -0.5, "tg128": +5.0,           # 2I
    "raw_buffer":  +0.2,                           # 2I: neutro su 2 shader
    "split_reduce": -0.1,
}

# (nome, predicato sulle feature, {trasformazione: delta di punteggio}, evidenza dev)
RULES = [
 ("R1_hoist_divergente",
  lambda f: f["cond_loop_invariant"] and f["cond_lane_dependent"] and f["isa_cbranch"] >= 8,
  {"hoist_cond2": +3.0, "hoist_cond4": +2.2, "widen2": +0.8},
  "d_bdiv: 32 regioni divergenti nell'ISA + condizione con parte invariante -> -69.5%"),

 ("R2_hoist_inutile_se_uniforme",
  lambda f: f["cond_loop_invariant"] and not f["cond_lane_dependent"],
  {"hoist_cond2": -2.5, "hoist_cond4": -2.5},
  "una condizione uniforme sul wave e' gia' gestita con branch scalare: niente da sollevare"),

 ("R3_latenza_memoria_esposta",
  lambda f: f["isa_wait_per_mem"] >= 0.8 and f["isa_load_use_med"] <= 8 and not f["array_live"],
  {"unroll_all": +1.5, "acc4": +1.5, "acc2": +1.0, "widen2": +1.0},
  "d_dot / d_mix: waitcnt per operazione di memoria alto e load->use corto -> -6%"),

 ("R4_lds_costoso",
  lambda f: f["lds_stage_bytes"] >= 8192,
  {"lds_stage": -4.0},
  "2I: staging LDS +93% / +100% / +110% con 24-32 KB per gruppo"),

 ("R5_array_vivo_no_unroll",
  lambda f: f["array_live"] and f["mem_ops_dynamic"] > 0,
  {"unroll_all": -2.5, "unroll_loads": +0.8, "split_reduce": +0.3},
  "2H: pressure24 +34.5%, pressure48 +31.0% con [unroll]"),

 ("R6_catena_seriale_senza_memoria",
  lambda f: f["loop_carried"] and f["mem_ops_dynamic"] <= 2,
  {"unroll_all": +2.0, "loop_all": -0.5},
  "d_trig: catena di trascendenti senza memoria -> [unroll] -25.4%"),

 ("R7_riduzione_lds_sequenziale",
  lambda f: f["lds_bytes_src"] > 0,
  {"wave_reduce": +2.5, "tree_reduce": +2.4, "acc4": -2.0, "acc2": -1.5, "unroll_all": -2.0},
  "d_ldsred: wave -14.5%, tree -14.4%, acc4 +43.8%, unroll +40.7%"),

 ("R8_pressione_registri",
  lambda f: f["isa_vgpr"] >= 30 and f["max_trip"] >= 24,
  {"load_first": -2.0, "widen4": -0.8, "acc4": -0.3},
  "2I: load_first +24.9% / +28.3% con array di 24-32 float4"),

 ("R9_loop_corto_indipendente",
  lambda f: f["max_trip"] <= 16 and not f["array_live"] and not f["loop_carried"],
  {"unroll_all": +1.0, "widen2": +0.5},
  "corpo piccolo e iterazioni indipendenti: srotolare espone piu' operazioni in volo"),

 ("R10_costo_senza_beneficio_noto",
  lambda f: True,
  {"raw_buffer": -1.0, "loop_all": -1.0, "tg128": -0.8, "tg32": -0.4},
  "2H/2I: [loop] no-op su 20/20; raw_buffer neutro; tg128 +5.1%"),
]


def merge_features(src, isa, dxil, lds_stage_bytes):
    f = dict(src)
    f["lds_stage_bytes"] = lds_stage_bytes
    for k, v in isa.items():
        f["isa_" + k] = v
    for k, v in dxil.items():
        f["dxil_" + k] = v
    mem = max(1, int(isa.get("vmem", 0)) + int(isa.get("lds", 0)))
    f["isa_wait_per_mem"] = round(int(isa.get("waitcnt", 0)) / mem, 3)
    f["isa_load_use_med"] = int(isa.get("load_use_med", 0))
    f["isa_cbranch"] = int(isa.get("branch", 0))
    f["isa_vgpr"] = int(isa.get("vgpr") or 0)
    # occupancy stimata (wave32 gfx1030: 1024 VGPR/SIMD, granularita' 8, max 16 wave)
    v = max(8, ((f["isa_vgpr"] + 7) // 8) * 8)
    f["occ_waves_vgpr"] = min(16, 1024 // v)
    lb = int(isa.get("lds_bytes") or 0)
    f["occ_groups_lds"] = (65536 // lb) if lb else 99
    return f


# --------------------------------------------------------------------------
# Parte adattiva: impara dai risultati misurati, comprese le regressioni.
# Ogni trasformazione ha una chiave ordinata (o nessuna). Con evidenza nello
# stesso punto della chiave, l'evidenza SOSTITUISCE la regola scritta a mano:
# una misura batte un'euristica. Senza evidenza restano le regole.
# --------------------------------------------------------------------------
KEY = {
    "unroll_all":  lambda f: f["array_size"] if f["array_live"] else -1,
    "unroll_loads": lambda f: f["array_size"] if f["array_live"] else -1,
    "split_reduce": lambda f: f["array_size"] if f["array_live"] else -1,
    "lds_stage":   lambda f: f["lds_stage_bytes"] / 1024.0,
    "hoist_cond2": lambda f: f["cond_lane_dependent"],
    "hoist_cond4": lambda f: f["cond_lane_dependent"],
}


def evidence_prior(tf, f, history, k=2):
    """history = [(features, d%)] osservati per QUESTA trasformazione.
    Restituisce (stima, n_usati) o (None, 0)."""
    if not history:
        return None, 0
    kf = KEY.get(tf)
    if kf is None:
        return sum(d for _, d in history) / len(history), len(history)
    try:
        x0 = float(kf(f))
    except Exception:
        return sum(d for _, d in history) / len(history), len(history)
    pts = []
    for hf, d in history:
        try:
            pts.append((abs(float(kf(hf)) - x0), d))
        except Exception:
            pass
    if not pts:
        return None, 0
    pts.sort()
    sel = pts[:k]
    w = [1.0 / (1.0 + p[0]) for p in sel]
    return sum(wi * p[1] for wi, p in zip(w, sel)) / sum(w), len(sel)


def score(f, applicable, prior_scale=0.04, extra_prior=None, evidence=None,
          ev_scale=0.09, ev_clip=4.0):
    """Restituisce (punteggi, motivazioni). Punteggio = regole + prior smorzato."""
    sc = {t: 0.0 for t in applicable}
    why = {t: [] for t in applicable}
    ev = {}
    if evidence:
        for t in applicable:
            est, n = evidence_prior(t, f, evidence.get(t, []))
            if est is not None:
                ev[t] = (est, n)
    for t, (est, n) in ev.items():
        v = max(-ev_clip, min(ev_clip, -est * ev_scale))
        sc[t] += v
        why[t].append(f"evidenza[{n}]={est:+.1f}%{v:+.2f}")
    for name, pred, deltas, _ev in RULES:
        try:
            hit = bool(pred(f))
        except Exception:
            hit = False
        if not hit:
            continue
        for t, d in deltas.items():
            if t in sc and t not in ev:      # con evidenza misurata la regola tace
                sc[t] += d
                why[t].append(f"{name}{d:+.1f}")
    pri = dict(DEV_PRIOR)
    if extra_prior:
        pri.update(extra_prior)
    for t in sc:
        if t in ev:
            continue
        # un prior negativo (miglioramento osservato) alza il punteggio, smorzato
        p = -pri.get(t, 0.0) * prior_scale
        p = max(-2.0, min(2.0, p))
        sc[t] += p
        if abs(p) >= 0.05:
            why[t].append(f"prior{p:+.2f}")
    return sc, why


def propose(f, applicable, budget, extra_prior=None, evidence=None):
    sc, why = score(f, applicable, extra_prior=extra_prior, evidence=evidence)
    order = sorted(applicable, key=lambda t: (-sc[t], t))
    return [(t, round(sc[t], 3), " ".join(why[t]) or "-") for t in order[:budget]], sc
