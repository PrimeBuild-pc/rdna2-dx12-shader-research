"""Phase 2K - raccolta di compute shader REALI da repo open source.

Cerca gli entry point compute ([numthreads]) nei sorgenti, prova a compilarli standalone
con DXC e tiene solo quelli che compilano. Per ognuno estrae il binding delle risorse dal
disassembly DXIL, che serve al banco generico per creare risorse fittizie.

    python tools/harvest2k.py <src_root> [<src_root> ...]
"""
import argparse, collections, hashlib, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "20_real")
DXC = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe"
TMP = os.path.join(os.environ.get("TEMP", "."), "claude", "harvest")

ENTRY = re.compile(r"\[\s*numthreads\s*\(([^)]*)\)\s*\]\s*(?:\[[^\]]*\]\s*)*"
                   r"(?:void|[A-Za-z_][\w:<>, ]*)\s+([A-Za-z_]\w*)\s*\(", re.S)
# tabella "Resource Bindings" nel disassembly DXIL
RESLINE = re.compile(r"^;\s+(\S+)\s+(\w+)\s+(\w+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*$")


def entries(text):
    out = []
    for m in ENTRY.finditer(text):
        tg = m.group(1)
        nums = re.findall(r"(\d+)", tg)
        if len(nums) == 3:
            out.append((m.group(2), tuple(int(x) for x in nums)))
    return out


def parse_bindings(dis):
    """Legge il blocco '; Resource Bindings:' del disassembly DXIL."""
    res = []
    lines = dis.splitlines()
    try:
        i = next(k for k, l in enumerate(lines) if "Resource Bindings:" in l)
    except StopIteration:
        return res
    for l in lines[i + 1:]:
        if not l.startswith(";"):
            break
        s = l.strip("; ").strip()
        if not s or s.startswith("---") or s.startswith("Name "):
            continue
        parts = s.split()
        if len(parts) < 6:
            continue
        name, typ, fmt, dim = parts[0], parts[1], parts[2], parts[3]
        bind = parts[-2] if len(parts) >= 6 else ""
        m = re.match(r"([a-z]+)(\d+)", bind)
        if not m:
            continue
        res.append(dict(name=name, type=typ, fmt=fmt, dim=dim,
                        reg=m.group(1), slot=int(m.group(2)),
                        count=parts[-1]))
    return res


def try_compile(path, entry, incs, defines, model="cs_6_6"):
    cso = os.path.join(TMP, "h.cso"); dis = os.path.join(TMP, "h.ll")
    for f in (cso, dis):
        if os.path.exists(f):
            os.remove(f)
    cmd = [DXC, "-T", model, "-E", entry, "-Fo", cso, "-Fc", dis,
           "-HV", "2021", "-O3"]
    for i in incs:
        cmd += ["-I", i]
    for d in defines:
        cmd += ["-D", d]
    cmd.append(path)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not os.path.exists(cso):
        return None, (p.stdout + p.stderr)[-300:]
    d = open(dis, encoding="utf-8", errors="replace").read() if os.path.exists(dis) else ""
    return dict(cso=open(cso, "rb").read(), dis=d), ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(TMP, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    csod = os.path.join(OUT, "cso"); os.makedirs(csod, exist_ok=True)

    files = []
    for r in a.roots:
        for dp, _dn, fn in os.walk(r):
            for f in fn:
                if f.lower().endswith((".hlsl",)):
                    files.append(os.path.join(dp, f))
    print(f"{len(files)} file HLSL trovati")

    ok, fail = [], collections.Counter()
    for path in files:
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        es = entries(txt)
        if not es:
            continue
        incs = [os.path.dirname(path), os.path.dirname(os.path.dirname(path))]
        for entry, tg in es:
            r, err = try_compile(path, entry, incs, [])
            if r is None:
                fail[err.split("\n")[0][:70] or "?"] += 1
                continue
            sha = hashlib.sha256(r["cso"]).hexdigest()[:16]
            name = f"{os.path.splitext(os.path.basename(path))[0]}_{entry}"
            name = re.sub(r"[^A-Za-z0-9_]", "_", name)[:48]
            binds = parse_bindings(r["dis"])
            open(os.path.join(csod, name + ".cso"), "wb").write(r["cso"])
            ok.append(dict(name=name, path=path.replace("\\", "/"), entry=entry,
                           tg=list(tg), tg_total=tg[0] * tg[1] * tg[2],
                           dxil_sha=sha, bindings=binds,
                           src_bytes=len(txt)))
            if a.limit and len(ok) >= a.limit:
                break
        if a.limit and len(ok) >= a.limit:
            break

    # deduplica per DXIL identico
    seen, uniq = {}, []
    for r in ok:
        if r["dxil_sha"] in seen:
            continue
        seen[r["dxil_sha"]] = r["name"]; uniq.append(r)
    json.dump(uniq, open(os.path.join(OUT, "harvest.json"), "w"), indent=1)
    print(f"\ncompilati: {len(ok)} entry point, {len(uniq)} unici per DXIL")
    print("\nprime cause di fallimento:")
    for e, n in fail.most_common(8):
        print(f"  {n:5d}  {e}")
    kinds = collections.Counter()
    for r in uniq:
        for b in r["bindings"]:
            kinds[b["reg"] + ":" + b["dim"]] += 1
    print("\nrisorse richieste:", dict(kinds.most_common(15)))


if __name__ == "__main__":
    main()
