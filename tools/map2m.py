"""Phase 2M - mappa hash di shader -> file sorgente, per HASH e non per nome.

In 2L e nella prima parte di 2M ho sbagliato due volte associando uno shader al sorgente
in base al nome del PSO o a un'ipotesi sul renderer usato. L'unico legame affidabile e'
l'hash del bytecode registrato a runtime dall'inventario.

Gli header generati dalla build (`CompiledShaders/<Nome>.h`) contengono l'array di byte
del DXIL: se ne calcola lo stesso FNV-1a usato in PipelineState.h e si confronta.

    python tools/map2m.py <inventory.csv>
"""
import csv, glob, os, re, sys

ME = r"C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine"
BUILD = os.path.join(ME, "Build", "x64", "Profile", "Output")
SRCDIRS = [os.path.join(ME, "Core", "Shaders"), os.path.join(ME, "Model", "Shaders")]

BYTES_RE = re.compile(r"0x([0-9a-fA-F]{2})")


def fnv1a(data):
    h = 1469598103934665603
    for b in data:
        h ^= b
        h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return h


def compiled_shaders():
    """{hash: (nome, byte)} per ogni header generato dalla build."""
    out = {}
    for h in glob.glob(os.path.join(BUILD, "*", "CompiledShaders", "*.h")):
        try:
            t = open(h, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        # SOLO l'inizializzatore dell'array: gli header DXC contengono anche un blocco
        # di disassembly commentato pieno di numeri esadecimali, che falsava l'hash.
        m = re.search(r"g_p\w+\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;", t, re.S)
        if not m:
            continue
        data = bytes(int(x, 16) for x in BYTES_RE.findall(m.group(1)))
        if not data:
            continue
        out[fnv1a(data)] = (os.path.splitext(os.path.basename(h))[0], len(data))
    return out


def find_source(name):
    for d in SRCDIRS:
        p = os.path.join(d, name + ".hlsl")
        if os.path.exists(p):
            return p
    return ""


def main():
    inv = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:\Users\Lorenzo\AppData\Local\Temp\claude\l2\inventory2.csv"
    CS = compiled_shaders()
    print(f"{len(CS)} shader compilati trovati nella build\n")
    rows = list(csv.DictReader(open(inv)))
    seen = set()
    print(f"{'scope':24s} {'stage':5s} {'hash':>16s} {'sorgente':34s} {'byte':>7s} {'call/f':>7s}")
    out = []
    for r in sorted(rows, key=lambda x: (x["scope"], x["pso"])):
        for stage, col in (("VS", "vs_hash"), ("PS", "ps_hash"), ("CS", "cs_hash")):
            hx = r[col]
            if not hx or int(hx, 16) == 0:
                continue
            h = int(hx, 16)
            nm, nb = CS.get(h, ("(NON TROVATO)", 0))
            src = find_source(nm) if nb else ""
            key = (r["scope"], stage, hx)
            if key in seen:
                continue
            seen.add(key)
            print(f"{r['scope'][:24]:24s} {stage:5s} {hx:>16s} {nm[:34]:34s} {nb:7d} "
                  f"{float(r['calls_per_frame']):7.2f}")
            out.append(dict(scope=r["scope"], stage=stage, hash=hx, shader=nm,
                            bytes=nb, source=src.replace("\\", "/"),
                            calls_per_frame=r["calls_per_frame"], pso_name=r["pso"]))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                           "research", "22_runtime", "shader_map.csv"),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    miss = sum(1 for r in out if r["bytes"] == 0)
    print(f"\n{len(out)} associazioni, {miss} non risolte")


if __name__ == "__main__":
    main()
