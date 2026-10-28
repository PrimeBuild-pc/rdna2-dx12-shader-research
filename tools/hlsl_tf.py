"""Phase 2K - trasformazioni meccaniche su HLSL REALE.

Vincolo dichiarato: niente trasformazione che richieda di fidarsi di un modello sulla
correttezza. Quindi su sorgente arbitrario si applica solo cio' che e' verificabile
meccanicamente:

  attributi di ciclo   [unroll] / [loop] / [unroll(N)] su un ciclo o su tutti.
                       Sono hint di codegen: non cambiano la semantica per costruzione.
  [WaveSize(N)]        SM 6.6. Puo' cambiare il risultato se lo shader usa wave ops:
                       lo decide il gate di correttezza, non un'euristica.
  numthreads           valida solo se lo shader NON legge gtid/gid/groupshared/wave ops
                       e il dispatch viene riscalato per coprire lo stesso dominio.
                       Il guard e' testuale e conservativo.

Trasformazioni strutturali (hoisting di condizioni, split di accumulatori, tree reduction)
NON sono incluse: su HLSL arbitrario servirebbe un AST vero, e senza quello sarebbero
"fidarsi del modello". E' un limite dichiarato, non un'omissione.
"""
import re

ATTRS = ["[unroll]", "[loop]", "[unroll(2)]", "[unroll(4)]", "[unroll(8)]"]
# lo shader non puo' cambiare threadgroup se osserva la propria posizione nel gruppo
TG_UNSAFE = re.compile(r"SV_GroupThreadID|SV_GroupIndex|SV_GroupID|groupshared|"
                       r"GroupMemoryBarrier|AllMemoryBarrierWithGroupSync|Wave[A-Z]\w*|"
                       r"QuadRead|SV_GroupThreadId", re.I)


def _mask(src):
    """Posizioni dentro commenti o stringhe: da ignorare quando si cerca un `for`."""
    m = bytearray(len(src))
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                m[k] = 1
            i = j
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                m[k] = 1
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            j = min(n, j + 1)
            for k in range(i, j):
                m[k] = 1
            i = j
        else:
            i += 1
    return m


LOOP = re.compile(r"\b(for|while)\s*\(")
ATTR_BEFORE = re.compile(r"\]\s*$")


def loops(src):
    """Offset di inizio di ogni ciclo, e l'attributo eventualmente gia' presente."""
    m = _mask(src)
    out = []
    for mo in LOOP.finditer(src):
        i = mo.start()
        if m[i]:
            continue
        # attributo gia' presente subito prima?
        pre = src[:i].rstrip()
        a0, a1 = i, i
        if pre.endswith("]"):
            d, j = 0, len(pre) - 1
            while j >= 0:
                if pre[j] == "]":
                    d += 1
                elif pre[j] == "[":
                    d -= 1
                    if d == 0:
                        break
                j -= 1
            if j >= 0:
                a0, a1 = j, len(pre)
        out.append(dict(start=i, attr_start=a0, attr_end=a1,
                        kind=mo.group(1), existing=src[a0:a1] if a0 != a1 else ""))
    return out


def set_attr(src, idx_list, attr):
    """Sostituisce/inserisce `attr` sui cicli indicati. Lavora a ritroso sugli offset."""
    L = loops(src)
    out = src
    for i in sorted(idx_list, reverse=True):
        if i >= len(L):
            continue
        e = L[i]
        out = out[:e["attr_start"]] + attr + " " + out[e["attr_end"]:]
    return out


NUMTHREADS = re.compile(r"\[\s*numthreads\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*\]")


def tg_safe(src):
    return TG_UNSAFE.search(src) is None


def set_numthreads(src, tg):
    if not tg_safe(src):
        return None
    m = NUMTHREADS.search(src)
    if not m:
        return None
    return src[:m.start()] + f"[numthreads({tg[0]},{tg[1]},{tg[2]})]" + src[m.end():]


WAVESIZE = re.compile(r"\[\s*WaveSize\s*\([^)]*\)\s*\]")


def set_wavesize(src, n):
    m = NUMTHREADS.search(src)
    if not m:
        return None
    s = WAVESIZE.sub("", src)
    m = NUMTHREADS.search(s)
    return s[:m.start()] + f"[WaveSize({n})]\n" + s[m.start():]


def catalogue(src, max_per_loop=4):
    """Trasformazioni applicabili a questo sorgente, con nome stabile.
    Restituisce [(nome, funzione(src)->src|None)]."""
    L = loops(src)
    out = []
    for a in ATTRS:
        tag = a.strip("[]").replace("(", "").replace(")", "")
        if L:
            out.append((f"all_{tag}", (lambda a=a, n=len(L): (lambda s: set_attr(s, range(n), a)))()))
        for i in range(min(len(L), max_per_loop)):
            out.append((f"L{i}_{tag}", (lambda a=a, i=i: (lambda s: set_attr(s, [i], a)))()))
    for n in (32, 64):
        out.append((f"wave{n}", (lambda n=n: (lambda s: set_wavesize(s, n)))()))
    m = NUMTHREADS.search(src)
    if m and tg_safe(src):
        tx, ty, tz = int(m.group(1)), int(m.group(2)), int(m.group(3))
        cands = []
        if ty > 1:
            cands = [(16, 16, 1), (32, 8, 1), (8, 8, 1)]
        else:
            cands = [(32, 1, 1), (128, 1, 1), (256, 1, 1)]
        for c in cands:
            if c != (tx, ty, tz):
                out.append((f"tg{c[0]}x{c[1]}",
                            (lambda c=c: (lambda s: set_numthreads(s, c)))()))
    return out
