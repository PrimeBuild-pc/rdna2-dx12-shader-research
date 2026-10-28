"""Phase 2J - corpus. Lo split e' dichiarato QUI, prima di scrivere le regole.

DEV        6 shader gia' misurati in 2H/2I: le regole del predittore nascono SOLO da questi.
VALIDATION 8 shader nuovi, mai usati per costruire regole. Tre sono trappole deliberate
           per le mie stesse regole (marcate `trap`).
"""

# ---------------------------------------------------------------- DEV
DEV = {
 # ramo divergente con parte invariante nel ciclo -> in 2I hoist ha dato -69.5%
 "d_bdiv": dict(tg=64, phases=[dict(k="reduce", trip=32, idx="t*32+{i}", coalescable=True,
      cond=dict(inv="t", mod=2, div="lane"), then="A*A", else_="sin(A)*cos(A)", accum="s")]),
 # riduzione memory-bound
 "d_dot": dict(tg=64, phases=[dict(k="reduce", trip=32, idx="t*32+{i}", coalescable=True,
      cond=None, then="A*A", accum="s")]),
 # memoria + trascendenti
 "d_mix": dict(tg=64, phases=[dict(k="reduce", trip=24, idx="t*24+{i}", coalescable=True,
      cond=None, then="sin(A)*cos(A*1.25) + A*0.5", accum="s")]),
 # array vivo fra le iterazioni, alimentato dalla memoria
 "d_p24": dict(tg=64, phases=[dict(k="pipeline", n=24, idx="t*24+{i}", coalescable=True,
      p1=7, p2=13, p3=5)]),
 # catena seriale senza memoria
 "d_trig": dict(tg=64, phases=[dict(k="chain", trip=32,
      init="float4(t & 511, (t >> 2) & 511, (t >> 4) & 511, 1) * 0.001953125",
      step="a = sin(a) + cos(a * 1.5) * 0.5;")]),
 # riduzione sequenziale su LDS
 "d_ldsred": dict(tg=64, phases=[dict(k="ldsreduce", pre=8)]),
}

# --------------------------------------------------------- VALIDATION
VALIDATION = {
 # TRAPPOLA 1: condizione invariante nel ciclo ma UNIFORME sul wave (gid.x).
 # Il default esegue gia' un solo lato: sollevare non dovrebbe servire.
 "v_cond_uniform": dict(tg=64, trap="hoist su condizione uniforme", phases=[dict(
      k="reduce", trip=32, idx="t*32+{i}", coalescable=True,
      cond=dict(inv="gid.x", mod=2, div="uniform"),
      then="A*A", else_="sin(A)*cos(A)", accum="s")]),
 # TRAPPOLA 2: ramo divergente ma con entrambi i lati economici: poco da saltare.
 "v_cond_cheap": dict(tg=64, trap="hoist con rami entrambi economici", phases=[dict(
      k="reduce", trip=32, idx="t*32+{i}", coalescable=True,
      cond=dict(inv="t", mod=2, div="lane"),
      then="A*A", else_="A*0.5", accum="s")]),
 # periodo 4 invece di 2: generalizzazione della regola su un modulo diverso
 "v_cond_mod4": dict(tg=64, phases=[dict(
      k="reduce", trip=32, idx="t*32+{i}", coalescable=True,
      cond=dict(inv="t", mod=4, div="lane"),
      then="A*A", else_="sin(A)*cos(A)", accum="s")]),
 # TRAPPOLA 3: pipeline piccola. La regola "array vivo -> niente unroll" potrebbe
 # essere sbagliata quando l'array e' piccolo.
 "v_pipe8": dict(tg=64, trap="array vivo ma piccolo", phases=[dict(
      k="pipeline", n=8, idx="t*8+{i}", coalescable=True, p1=3, p2=5, p3=3)]),
 # pipeline media
 "v_pipe16": dict(tg=64, phases=[dict(k="pipeline", n=16, idx="t*16+{i}", coalescable=True,
      p1=7, p2=11, p3=5)]),
 # riduzione LDS con gruppo da 128
 "v_lds128": dict(tg=128, phases=[dict(k="ldsreduce", pre=8)]),
 # catena seriale con trascendenti diversi
 "v_chain_exp": dict(tg=64, phases=[dict(k="chain", trip=40,
      init="float4(t & 255, (t >> 3) & 255, (t >> 6) & 255, 3) * 0.00390625 + 0.5",
      step="a = exp2(log2(a + 1.0) * 0.5) + rsqrt(a + 2.0);")]),
 # riduzione corta con ALU banale: puramente memory-bound
 "v_dot_light": dict(tg=64, phases=[dict(k="reduce", trip=16, idx="t*16+{i}",
      coalescable=True, cond=None, then="A*0.5", accum="s")]),
}


def _fix(d):
    """`else_` -> `else` (parola riservata in Python)."""
    for sh in d.values():
        for p in sh["phases"]:
            if "else_" in p:
                p["else"] = p.pop("else_")
    return d


DEV = _fix(DEV)
VALIDATION = _fix(VALIDATION)
ALL = dict(DEV, **VALIDATION)
SPLIT = {n: "dev" for n in DEV}
SPLIT.update({n: "validation" for n in VALIDATION})
