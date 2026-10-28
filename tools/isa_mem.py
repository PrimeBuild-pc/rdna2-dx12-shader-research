"""Phase 2H - misura quanto l'ISA espone la latenza di memoria.

Per ogni load VMEM calcola la distanza (in istruzioni) fino all's_waitcnt che la copre.
Distanza corta = il wave si ferma subito dopo aver chiesto il dato; distanza lunga =
la latenza e' coperta da lavoro utile.

    python tools/isa_mem.py <shader.hlsl> [...]
"""
import os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RGA = os.path.join(ROOT, "RadeonDeveloperToolSuite-2026-05-28-1806",
                   "RadeonDeveloperToolSuite-2026-05-28-1806", "rga.exe")
VMEM = ("buffer_load", "global_load", "image_", "tbuffer_load", "buffer_store", "global_store")


def disasm(hlsl):
    hlsl = os.path.abspath(hlsl)   # RGA gira con cwd nella dir temporanea
    d = tempfile.mkdtemp(prefix="mem_")
    p = subprocess.run([RGA, "-s", "dx12", "-c", "gfx1030", "--cs", hlsl, "--cs-entry", "main",
                        "--cs-model", "cs_6_6", "--rs-macro", "RS",
                        "--isa", os.path.join(d, "isa.txt")], capture_output=True, text=True, cwd=d)
    f = [x for x in os.listdir(d) if "isa" in x and x.endswith(".txt")]
    t = open(os.path.join(d, f[0]), encoding="utf-8", errors="replace").read() if f else ""
    shutil.rmtree(d, ignore_errors=True)
    return t[t.find("Disassembly"):]


def analyse(hlsl):
    b = disasm(hlsl)
    ops = []
    for line in b.splitlines():
        m = re.match(r"\s{2,}([a-z][a-z0-9_]+)\s", line)
        if m:
            ops.append((m.group(1), line.strip()))
    loads = [i for i, (o, _) in enumerate(ops) if o.startswith("buffer_load") or o.startswith("global_load")]
    waits = [i for i, (o, _) in enumerate(ops) if o == "s_waitcnt"]
    dist = []
    for i in loads:
        nxt = next((w for w in waits if w > i), None)
        if nxt is not None:
            dist.append(nxt - i)
    dist.sort()
    # quante load consecutive vengono emesse prima del wait successivo (dimensione del gruppo)
    groups, cur = [], 0
    wset = set(waits)
    for i in range(len(ops)):
        if i in loads:
            cur += 1
        elif i in wset and cur:
            groups.append(cur); cur = 0
    if cur:
        groups.append(cur)
    n = len(ops)
    return dict(inst=n, loads=len(loads), waits=len(waits),
                clause=sum(1 for o, _ in ops if o == "s_clause"),
                d_min=dist[0] if dist else 0,
                d_med=dist[len(dist) // 2] if dist else 0,
                d_max=dist[-1] if dist else 0,
                d_mean=round(sum(dist) / len(dist), 1) if dist else 0,
                d_le2=sum(1 for x in dist if x <= 2),
                grp_max=max(groups) if groups else 0,
                grp_mean=round(sum(groups) / len(groups), 1) if groups else 0)


if __name__ == "__main__":
    print(f"{'shader':30s} {'inst':>5} {'load':>5} {'wait':>5} {'clau':>5} {'dist min/med/mean/max':>24} "
          f"{'d<=2':>5} {'grp mean/max':>13}")
    for h in sys.argv[1:]:
        r = analyse(h)
        print(f"{os.path.basename(h)[:30]:30s} {r['inst']:5d} {r['loads']:5d} {r['waits']:5d} "
              f"{r['clause']:5d} {r['d_min']:6d}/{r['d_med']:4d}/{r['d_mean']:6.1f}/{r['d_max']:5d} "
              f"{r['d_le2']:5d} {r['grp_mean']:6.1f}/{r['grp_max']:5d}")
