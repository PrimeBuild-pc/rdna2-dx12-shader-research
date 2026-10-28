"""Phase 2J - IR minimale di shader compute + trasformazioni MECCANICHE.

Il punto: in 2I le varianti le scrivevo a mano. Qui uno shader e' una struttura dati e
ogni trasformazione e' una funzione IR -> IR. Il proponente sceglie QUALI applicare; il
codice HLSL lo genera il programma. Cosi' "l'IA propone" e' verificabile.

Quattro forme di fase coprono il corpus:
  reduce      ciclo di riduzione su elementi caricati, con condizione opzionale
  chain       catena seriale (dipendenza loop-carried stretta)
  pipeline    array vivo fra le iterazioni: load -> mix -> riduzione
  ldsreduce   riduzione sequenziale su LDS

Import: `from ir2j import SHADERS, TRANSFORMS, apply_tf, emit, src_features`
"""
import copy, re

SRV_STRUCT = "StructuredBuffer<float4> In : register(t0);"
SRV_RAW = "ByteAddressBuffer In : register(t0);"

WRAP = """#define RS "RootFlags(0), UAV(u0), SRV(t0)"
%(SRV)s
RWStructuredBuffer<float4> Out : register(u0);
%(LDS)s
[RootSignature(RS)]
[numthreads(%(TG)d,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
%(BODY)s
  Out[t] = s;
}
"""


# =====================================================================
# Emissione
# =====================================================================
def _src(sh, ph, e):
    """Espressione di lettura dell'elemento con indice `e` (stringa)."""
    if ph.get("lds_stage"):
        # sh[gtid*trip + i] == In[(base + gtid*trip + i) & 65535] == In[(t*trip + i) & 65535]
        return f"shm[gtid.x*{ph['trip']}u + ({e})]"
    idx = ph["idx"].replace("{i}", f"({e})")
    if sh.get("raw"):
        return f"In.Load<float4>((({idx}) & 65535) << 4)"
    return f"In[({idx}) & 65535]"


def _stage_block(sh, ph):
    """Caricamento cooperativo coalescente del blocco del gruppo in LDS."""
    tot = sh["tg"] * ph["trip"]
    return (f"  uint base = gid.x * {tot}u;\n"
            f"  for (uint q0 = gtid.x; q0 < {tot}u; q0 += {sh['tg']}u)"
            f" shm[q0] = In[(base + q0) & 65535];\n"
            f"  GroupMemoryBarrierWithGroupSync();\n")


def _cond_val(ph, off):
    """Valore statico della condizione dentro un ramo sollevato, per l'offset `off`."""
    return None if ph.get("cond") is None else None  # risolto in emit_reduce


def emit_reduce(sh, ph):
    trip, per = ph["trip"], ph.get("per", 1)
    attr, K = ph.get("attr", ""), ph.get("acc", 1)
    c = ph.get("cond")
    out = []
    if ph.get("lds_stage"):
        out.append(_stage_block(sh, ph))
    names = [f"a{o}" for o in range(per)]
    accs = [f"r{k}" for k in range(K)] if K > 1 else ["s"]
    if K > 1:
        out.append("  float4 " + " = 0, ".join(accs) + " = 0;\n")

    def body(prefix, resolved):
        """resolved[o] = True/False/None (None = condizione dinamica)."""
        L = []
        if ph.get("load_first"):
            L += [f"{prefix}  float4 {names[o]} = pbuf[i + {o}];" for o in range(per)]
        else:
            L += [f"{prefix}  float4 {names[o]} = {_src(sh, ph, f'i + {o}')};" for o in range(per)]
        for o in range(per):
            acc = accs[o % K]
            th = ph["then"].replace("A", names[o])
            el = ph["else"].replace("A", names[o]) if ph.get("else") else None
            if c is None:
                L.append(f"{prefix}  {acc} += {th};")
            elif resolved is not None:
                L.append(f"{prefix}  {acc} += {th if resolved[o] else el};")
            else:
                cd = f"(({c['inv']} + i + {o}) & {c['mod']-1}u)"
                L.append(f"{prefix}  if ({cd}) {acc} += {th}; else {acc} += {el};")
        return "\n".join(L)

    if ph.get("load_first"):
        out.append(f"  float4 pbuf[{trip}];\n"
                   f"  [unroll] for (int q = 0; q < {trip}; ++q) pbuf[q] = {_src(sh, ph, 'q')};\n")
    if ph.get("hoist") and c is not None:
        # la condizione e' ((inv + i + o) & (mod-1)); con passo `per` multiplo di `mod`
        # il termine i sparisce, quindi basta ramificare sui `mod` residui di inv.
        mod = c["mod"]
        out.append(f"  uint hp = {c['inv']} & {mod-1}u;\n")
        for r in range(mod):
            out.append(("  if" if r == 0 else "  else if") + f" (hp == {r}u) {{\n")
            res = [((r + o) & (mod - 1)) != 0 for o in range(per)]
            out.append(f"  {attr} for (int i = 0; i < {trip}; i += {per}) {{\n"
                       f"{body('  ', res)}\n    }}\n  }}\n")
    else:
        out.append(f"  {attr} for (int i = 0; i < {trip}; i += {per}) {{\n"
                   f"{body('  ', None)}\n    }}\n")
    if K > 1:
        out.append("  s = " + " + ".join(f"({accs[k]})" for k in range(K)) + ";\n")
    return "".join(out)


def emit_chain(sh, ph):
    a = ph.get("attr", "")
    return (f"  float4 a = {ph['init']};\n"
            f"  {a} for (int i = 0; i < {ph['trip']}; ++i) {{ {ph['step']} }}\n"
            f"  s = a;\n")


def emit_pipeline(sh, ph):
    n, a1, a2, a3 = ph["n"], ph.get("a1", ""), ph.get("a2", ""), ph.get("a3", "")
    o = []
    if ph.get("lds_stage"):
        o.append(_stage_block(sh, dict(trip=n)))
        ld = f"shm[gtid.x*{n}u + i]"
    else:
        ld = _src(sh, dict(idx=ph["idx"], trip=n), "i") if False else None
        idx = ph["idx"].replace("{i}", "i")
        ld = (f"In.Load<float4>((({idx}) & 65535) << 4)" if sh.get("raw")
              else f"In[({idx}) & 65535]")
    o.append(f"  float4 v[{n}];\n")
    o.append(f"  {a1} for (int i = 0; i < {n}; ++i) v[i] = {ld} * (i+1);\n")
    o.append(f"  {a2} for (int k = 0; k < {n}; ++k)"
             f" v[k] = sin(v[k]) + v[(k*{ph['p1']})%{n}]*cos(v[(k*{ph['p2']})%{n}]);\n")
    if ph.get("split_reduce"):
        h = n // 2
        o.append(f"  float4 s0 = 0, s1 = 0;\n"
                 f"  {a3} for (int j = 0; j < {h}; ++j) s0 += v[j]*v[(j*{ph['p3']})%{n}];\n"
                 f"  {a3} for (int j2 = {h}; j2 < {n}; ++j2) s1 += v[j2]*v[(j2*{ph['p3']})%{n}];\n"
                 f"  s = s0 + s1;\n")
    else:
        o.append(f"  {a3} for (int j = 0; j < {n}; ++j) s += v[j]*v[(j*{ph['p3']})%{n}];\n")
    return "".join(o)


def emit_ldsreduce(sh, ph):
    tg, pre, a1, a2 = sh["tg"], ph["pre"], ph.get("a1", ""), ph.get("a2", "")
    inv = f"(1.0/{tg}.0)"
    o = [f"  float4 a = In[t & 65535];\n",
         f"  {a1} for (int i = 0; i < {pre}; ++i) a += In[(t*{pre}+i) & 65535] * (i+1);\n"]
    mode = ph.get("mode", "seq")
    if mode == "tree":
        o += [f"  g[gtid.x] = a * {inv};\n  GroupMemoryBarrierWithGroupSync();\n",
              f"  [unroll] for (uint st = {tg//2}u; st > 0u; st >>= 1) {{\n"
              f"    if (gtid.x < st) g[gtid.x] += g[gtid.x + st];\n"
              f"    GroupMemoryBarrierWithGroupSync(); }}\n  s = g[0];\n"]
    elif mode == "wave":
        o += [f"  float4 w = WaveActiveSum(a * {inv});\n",
              f"  uint lanes = WaveGetLaneCount(), wi = gtid.x / lanes;\n",
              f"  if (WaveGetLaneIndex() == 0) g[wi] = w;\n  GroupMemoryBarrierWithGroupSync();\n",
              f"  uint nw = {tg}u / lanes;\n  for (uint q = 0; q < nw; ++q) s += g[q];\n"]
    else:
        K = ph.get("acc", 1)
        o += [f"  g[gtid.x] = a;\n  GroupMemoryBarrierWithGroupSync();\n"]
        if K > 1:
            accs = [f"r{k}" for k in range(K)]
            o.append("  float4 " + " = 0, ".join(accs) + " = 0;\n")
            o.append(f"  {a2} for (int q = 0; q < {tg}; q += {K}) {{ " +
                     " ".join(f"{accs[k]} += g[q+{k}] * {inv};" for k in range(K)) + " }\n")
            o.append("  s = " + " + ".join(f"({x})" for x in accs) + ";\n")
        else:
            o.append(f"  {a2} for (int q = 0; q < {tg}; ++q) s += g[q] * {inv};\n")
    return "".join(o)


EMIT = dict(reduce=emit_reduce, chain=emit_chain, pipeline=emit_pipeline, ldsreduce=emit_ldsreduce)


def emit(sh):
    body = "".join(EMIT[p["k"]](sh, p) for p in sh["phases"])
    lds = []
    for p in sh["phases"]:
        if p["k"] == "ldsreduce":
            lds.append(f"groupshared float4 g[{sh['tg'] if p.get('mode') != 'wave' else 8}];")
        if p.get("lds_stage"):
            lds.append(f"groupshared float4 shm[{sh['tg'] * (p.get('trip') or p.get('n'))}];")
    return WRAP % dict(SRV=(SRV_RAW if sh.get("raw") else SRV_STRUCT), LDS="\n".join(lds),
                       TG=sh["tg"], BODY=body)


# =====================================================================
# Trasformazioni: IR -> IR (None se non applicabile)
# =====================================================================
def _ph(sh, kind):
    return [p for p in sh["phases"] if p["k"] == kind]


def _attrs(sh, a):
    d = copy.deepcopy(sh)
    for p in d["phases"]:
        for key in ("attr", "a1", "a2", "a3"):
            if key in p or key == "attr":
                p[key] = a
        if p["k"] == "pipeline":
            p["a1"] = p["a2"] = p["a3"] = a
        elif p["k"] == "ldsreduce":
            p["a1"] = p["a2"] = a
        else:
            p["attr"] = a
    return d


def tf_unroll_all(sh):   return _attrs(sh, "[unroll]")
def tf_loop_all(sh):     return _attrs(sh, "[loop]")


def tf_unroll_loads(sh):
    if not _ph(sh, "pipeline"):
        return None
    d = copy.deepcopy(sh)
    for p in _ph(d, "pipeline"):
        p["a1"] = "[unroll]"
    return d


def _widen(sh, P, hoist):
    R = _ph(sh, "reduce")
    if not R:
        return None
    d = copy.deepcopy(sh)
    for p in _ph(d, "reduce"):
        if p["trip"] % P:
            return None
        c = p.get("cond")
        if hoist:
            if not c or P % c["mod"]:
                return None
            p["hoist"] = True
        p["per"] = P
    return d


def tf_widen2(sh):        return _widen(sh, 2, False)
def tf_widen4(sh):        return _widen(sh, 4, False)
def tf_hoist_cond2(sh):   return _widen(sh, 2, True)
def tf_hoist_cond4(sh):   return _widen(sh, 4, True)


def _acc(sh, K):
    d, hit = copy.deepcopy(sh), False
    for p in d["phases"]:
        if p["k"] == "reduce":
            if p["trip"] % K:
                return None
            p["acc"] = K; p["per"] = max(p.get("per", 1), K); hit = True
        elif p["k"] == "ldsreduce" and p.get("mode", "seq") == "seq":
            if sh["tg"] % K:
                return None
            p["acc"] = K; hit = True
    return d if hit else None


def tf_acc2(sh):  return _acc(sh, 2)
def tf_acc4(sh):  return _acc(sh, 4)


def tf_load_first(sh):
    if not _ph(sh, "reduce"):
        return None
    d = copy.deepcopy(sh)
    for p in _ph(d, "reduce"):
        if p.get("lds_stage"):
            return None
        p["load_first"] = True
    return d


def tf_lds_stage(sh):
    d, hit = copy.deepcopy(sh), False
    for p in d["phases"]:
        if p["k"] in ("reduce", "pipeline") and p.get("coalescable"):
            n = p.get("trip") or p.get("n")
            if sh["tg"] * n * 16 > 32768:
                return None
            p["lds_stage"] = True; hit = True
    return d if hit else None


def tf_tree_reduce(sh):
    L = _ph(sh, "ldsreduce")
    if not L:
        return None
    d = copy.deepcopy(sh)
    for p in _ph(d, "ldsreduce"):
        p["mode"] = "tree"
    return d


def tf_wave_reduce(sh):
    L = _ph(sh, "ldsreduce")
    if not L:
        return None
    d = copy.deepcopy(sh)
    for p in _ph(d, "ldsreduce"):
        p["mode"] = "wave"
    return d


def _tg(sh, n):
    if sh["tg"] == n or _ph(sh, "ldsreduce"):
        return None                      # LDS dipende da tg: non lo tocco
    # se una condizione dipende da gid/gtid, cambiare tg cambia il RISULTATO, non solo
    # le prestazioni: la trasformazione non e' semanticamente valida su questo shader
    for p in sh["phases"]:
        c = p.get("cond")
        if c and ("gid" in c["inv"] or "gtid" in c["inv"]):
            return None
    d = copy.deepcopy(sh)
    d["tg"] = n
    for p in d["phases"]:
        if p.get("lds_stage") and n * (p.get("trip") or p.get("n")) * 16 > 32768:
            return None
    return d


def tf_tg32(sh):   return _tg(sh, 32)
def tf_tg128(sh):  return _tg(sh, 128)


def tf_raw_buffer(sh):
    # solo le fasi che leggono In tramite _src sono parametrizzate sul tipo di buffer
    if not (_ph(sh, "reduce") or _ph(sh, "pipeline")):
        return None
    d = copy.deepcopy(sh); d["raw"] = True
    return d


def tf_split_reduce(sh):
    P = _ph(sh, "pipeline")
    if not P:
        return None
    d = copy.deepcopy(sh)
    for p in _ph(d, "pipeline"):
        if p["n"] % 2:
            return None
        p["split_reduce"] = True
    return d


TRANSFORMS = {
    "unroll_all": tf_unroll_all, "loop_all": tf_loop_all, "unroll_loads": tf_unroll_loads,
    "widen2": tf_widen2, "widen4": tf_widen4,
    "hoist_cond2": tf_hoist_cond2, "hoist_cond4": tf_hoist_cond4,
    "acc2": tf_acc2, "acc4": tf_acc4, "load_first": tf_load_first,
    "lds_stage": tf_lds_stage, "tree_reduce": tf_tree_reduce, "wave_reduce": tf_wave_reduce,
    "tg32": tf_tg32, "tg128": tf_tg128, "raw_buffer": tf_raw_buffer,
    "split_reduce": tf_split_reduce,
}


def apply_tf(sh, name):
    return TRANSFORMS[name](sh)


def applicable(sh):
    out = []
    for n, f in TRANSFORMS.items():
        try:
            if f(sh) is not None:
                out.append(n)
        except Exception:
            pass
    return out


# =====================================================================
# Feature di sorgente (dall'IR, non dal testo)
# =====================================================================
def src_features(sh):
    f = dict(tg=sh["tg"], n_phases=len(sh["phases"]), n_loops=0, max_trip=0, min_trip=0,
             n_branch=0, n_branch_divergent=0, branch_in_loop=0, cond_loop_invariant=0,
             cond_lane_dependent=0, n_loads=0, loads_per_iter=0, has_reduction=0,
             serial_reduction=0, loop_carried=0, array_live=0, array_size=0,
             lds_bytes_src=0, transcendental=0, mem_ops_dynamic=0, alu_per_load=0)
    trips = []
    for p in sh["phases"]:
        f["n_loops"] += 1
        if p["k"] == "reduce":
            trips.append(p["trip"])
            f["n_loads"] += p["trip"]; f["mem_ops_dynamic"] += p["trip"]
            f["loads_per_iter"] = max(f["loads_per_iter"], p.get("per", 1))
            f["has_reduction"] = 1; f["serial_reduction"] = 1
            body = (p["then"] or "") + (p.get("else") or "")
            f["transcendental"] += sum(body.count(x) for x in ("sin", "cos", "exp", "log", "rsqrt"))
            f["alu_per_load"] = len(re.findall(r"[*+\-/]", body))
            if p.get("cond"):
                f["n_branch"] += 1; f["branch_in_loop"] += 1
                if p["cond"]["div"] == "lane":
                    f["n_branch_divergent"] += 1; f["cond_lane_dependent"] = 1
                # la condizione ((inv + i) & m) ha una parte invariante nel ciclo
                f["cond_loop_invariant"] = 1
        elif p["k"] == "chain":
            trips.append(p["trip"]); f["loop_carried"] = 1
            f["transcendental"] += sum(p["step"].count(x) for x in ("sin", "cos", "exp", "log", "rsqrt"))
        elif p["k"] == "pipeline":
            trips += [p["n"]] * 3; f["n_loops"] += 2
            f["n_loads"] += p["n"]; f["mem_ops_dynamic"] += p["n"]
            f["array_live"] = 1; f["array_size"] = p["n"]
            f["has_reduction"] = 1; f["serial_reduction"] = 1
            f["loop_carried"] = 1; f["transcendental"] += 2 * p["n"]
        elif p["k"] == "ldsreduce":
            trips += [p["pre"], sh["tg"]]; f["n_loops"] += 1
            f["n_loads"] += p["pre"] + 1; f["mem_ops_dynamic"] += p["pre"] + 1
            f["has_reduction"] = 1; f["serial_reduction"] = 1
            f["lds_bytes_src"] = sh["tg"] * 16
    f["max_trip"] = max(trips) if trips else 0
    f["min_trip"] = min(trips) if trips else 0
    return f
