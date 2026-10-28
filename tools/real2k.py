"""Phase 2K - pipeline sugli shader REALI (DirectX-Graphics-Samples + FidelityFX SDK).

  probe     esegue ogni shader raccolto con risorse fittizie, in processo isolato con timeout
  split     divide in dev / REAL_VALIDATION, deterministico e dichiarato PRIMA di tutto
  variants  genera le varianti con trasformazioni meccaniche su HLSL reale, compila, deduplica
  measure   correttezza + confronto appaiato (protocollo 2I/2J, invariato)
  evaluate  memoria delle misure vs random vs solo-regole, a parita' di budget

    python tools/real2k.py <stage>
"""
import argparse, csv, hashlib, json, os, random, re, statistics, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import hlsl_tf
import ai_search as A

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "20_real")
BENCH = os.path.join(OUT, "bench2.exe")
CSO = os.path.join(OUT, "cso")
VC, VH = os.path.join(OUT, "vcso"), os.path.join(OUT, "vhlsl")
TMP = os.path.join(os.environ.get("TEMP", "."), "claude", "real2k")
DXC = A.DXC
TARGET_THREADS = 1 << 20

MIN_NS = 5000.0          # sotto questa soglia il tempo non e' misurabile in modo utile
RUNS = 5
REPS, DPM = 20, 4
WARM_MS = 250
CORRECT_DS = 1           # un solo set di risorse fittizie: il dataset e' fisso
TOL_STRICT, TOL_RMS = 1e-6, 1e-5
ACCEPT_PCT, ACCEPT_SIGMA = -1.0, 2.0
MAX_VARIANTS = 14
ATTRS = ["[unroll]", "[loop]", "[unroll(4)]"]


def dims_for(tg):
    tx, ty, tz = tg
    if ty > 1 or tz > 1:
        return (max(1, (1024 + tx - 1) // tx), max(1, (1024 + ty - 1) // ty), 1)
    return (max(1, min(65535, TARGET_THREADS // max(1, tx))), 1, 1)


def bindstr(bindings):
    toks = []
    for b in bindings:
        r, s, dim, fmt = b["reg"], b["slot"], b["dim"], b["fmt"]
        if s >= 16:
            continue
        if r == "cb":
            toks.append(f"b{s}")
        elif r == "s":
            toks.append(f"s{s}")
        elif r in ("t", "u"):
            d = {"2d": "2d", "2darray": "2darray", "r/o": "ro", "r/w": "rw",
                 "r/w+cnt": "rwcnt"}.get(dim, "ro" if r == "t" else "rw")
            toks.append(f"{r}{s}={d}.{fmt}")
    return ",".join(toks) if toks else "-"


def run_bench(tag, binds, dims, specs, reps, dpm, dumpdir, timeout=600, warm_ms=WARM_MS):
    out_csv = os.path.join(TMP, tag + ".csv")
    args = [BENCH, out_csv, str(reps), str(dpm), dumpdir, binds,
            str(dims[0]), str(dims[1]), str(dims[2])]
    for s in specs:
        n, p = s[0], s[1]
        d = s[2] if len(s) > 2 else None
        rel = os.path.relpath(p, OUT)
        args.append(f"{n}:{rel}" + (f":{d[0]}:{d[1]}:{d[2]}" if d else ""))
    env = dict(os.environ); env["BENCH_WARM_MS"] = str(warm_ms)
    try:
        p = subprocess.run(args, cwd=OUT, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None, "timeout_processo"
    rows = {}
    if os.path.exists(out_csv):
        for r in csv.DictReader(open(out_csv)):
            rows[r["variant"]] = float(r["ns_median"])
        os.remove(out_csv)
    if not rows:
        return None, (p.stdout + p.stderr)[-200:].replace("\n", " ")
    return rows, ""


# --------------------------------------------------------------------- probe
def probe():
    os.makedirs(TMP, exist_ok=True)
    H = json.load(open(os.path.join(OUT, "harvest.json")))
    ok, bad = [], []
    for i, r in enumerate(H):
        cso = os.path.join(CSO, r["name"] + ".cso")
        if not os.path.exists(cso):
            bad.append((r["name"], "cso mancante")); continue
        dims = dims_for(r["tg"])
        rows, err = run_bench("p", bindstr(r["bindings"]), dims, [(r["name"], cso)],
                              3, 1, "-", timeout=120, warm_ms=1)
        if rows is None:
            bad.append((r["name"], err))
            print(f"  [{i+1}/{len(H)}] KO {r['name'][:44]:44s} {err[:55]}")
        else:
            r2 = dict(r, dims=list(dims), binds=bindstr(r["bindings"]),
                      probe_ns=rows[r["name"]])
            ok.append(r2)
            print(f"  [{i+1}/{len(H)}] ok {r['name'][:44]:44s} {rows[r['name']]:10.0f} ns")
    json.dump(ok, open(os.path.join(OUT, "runnable.json"), "w"), indent=1)
    print(f"\neseguibili: {len(ok)} / {len(H)}")


# --------------------------------------------------------------------- split
def split():
    R = json.load(open(os.path.join(OUT, "runnable.json")))
    keep = [r for r in R if r["probe_ns"] >= MIN_NS]
    keep.sort(key=lambda r: r["name"])
    out = []
    for r in keep:
        h = int(hashlib.sha256(r["name"].encode()).hexdigest()[:8], 16)
        r["split"] = "dev" if h % 2 == 0 else "REAL_VALIDATION"
        out.append(r)
    json.dump(out, open(os.path.join(OUT, "corpus.json"), "w"), indent=1)
    nd = sum(1 for r in out if r["split"] == "dev")
    print(f"corpus: {len(out)} shader misurabili (scartati {len(R)-len(keep)} sotto {MIN_NS:.0f} ns)")
    print(f"  dev {nd} · REAL_VALIDATION {len(out)-nd}")
    with open(os.path.join(OUT, "corpus.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["name", "split", "path", "entry", "tg", "probe_ns", "binds"])
        for r in out:
            w.writerow([r["name"], r["split"], r["path"], r["entry"],
                        "x".join(map(str, r["tg"])), round(r["probe_ns"], 1), r["binds"]])


# ------------------------------------------------------------------ variants
def compile_one(src_path, entry, incs, cso):
    cmd = [DXC, "-T", "cs_6_6", "-E", entry, "-Fo", cso, "-HV", "2021", "-O3"]
    for i in incs:
        cmd += ["-I", i]
    cmd.append(src_path)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return os.path.exists(cso), (p.stdout + p.stderr)[-200:]


def variants():
    for d in (VC, VH, TMP):
        os.makedirs(d, exist_ok=True)
    C = json.load(open(os.path.join(OUT, "corpus.json")))
    hlsl_tf.ATTRS = ATTRS
    meta = {}
    for si, sh in enumerate(C):
        src = open(sh["path"], encoding="utf-8", errors="replace").read()
        incs = [os.path.dirname(sh["path"]), os.path.dirname(os.path.dirname(sh["path"]))]
        cat = hlsl_tf.catalogue(src, max_per_loop=2)[:MAX_VARIANTS]
        seen_h, seen_d = {}, {}
        base_cso = os.path.join(CSO, sh["name"] + ".cso")
        seen_d[hashlib.sha256(open(base_cso, "rb").read()).hexdigest()[:16]] = "default"
        seen_h[hashlib.sha256(re.sub(r"\s+", " ", src).encode()).hexdigest()[:16]] = "default"
        n_ok = n_dup = n_fail = 0
        for tf, fn in cat:
            vn = f"{sh['name']}__{tf}"
            try:
                s2 = fn(src)
            except Exception as e:
                n_fail += 1; meta[vn] = dict(shader=sh["name"], tf=tf, status="tf_error"); continue
            if s2 is None or s2 == src:
                n_dup += 1; meta[vn] = dict(shader=sh["name"], tf=tf, status="no_change"); continue
            hh = hashlib.sha256(re.sub(r"\s+", " ", s2).encode()).hexdigest()[:16]
            if hh in seen_h:
                n_dup += 1
                meta[vn] = dict(shader=sh["name"], tf=tf, status="dup_hlsl", dup_of=seen_h[hh]); continue
            seen_h[hh] = tf
            hp = os.path.join(VH, vn + ".hlsl"); open(hp, "w", encoding="utf-8").write(s2)
            cp = os.path.join(VC, vn + ".cso")
            ok, log = compile_one(hp, sh["entry"], incs, cp)
            if not ok:
                n_fail += 1
                meta[vn] = dict(shader=sh["name"], tf=tf, status="dxc_fail", log=log[:120]); continue
            dh = hashlib.sha256(open(cp, "rb").read()).hexdigest()[:16]
            if dh in seen_d:
                n_dup += 1
                meta[vn] = dict(shader=sh["name"], tf=tf, status="dup_dxil", dup_of=seen_d[dh])
                os.remove(cp); continue
            seen_d[dh] = tf
            # numthreads cambiato -> dispatch riscalato per coprire lo stesso dominio
            m = hlsl_tf.NUMTHREADS.search(s2)
            tg = [int(m.group(1)), int(m.group(2)), int(m.group(3))] if m else sh["tg"]
            meta[vn] = dict(shader=sh["name"], tf=tf, status="ok", dxil_sha=dh,
                            tg=tg, dims=list(dims_for(tg)))
            n_ok += 1
        print(f"  [{si+1}/{len(C)}] {sh['name'][:40]:40s} {len(cat):2d} proposte -> "
              f"{n_ok:2d} uniche, {n_dup:2d} dedup, {n_fail:2d} fallite")
    json.dump(meta, open(os.path.join(OUT, "variants.json"), "w"), indent=1)
    tot = sum(1 for v in meta.values() if v["status"] == "ok")
    print(f"\n{tot} varianti uniche da misurare")


# ---------------------------------------------------------------- features
def isa_features(sh):
    """ISA della sola BASELINE: e' cio' che il predittore puo' vedere."""
    src = open(sh["path"], encoding="utf-8", errors="replace").read()
    tmp = os.path.join(TMP, "f.hlsl")
    open(tmp, "w", encoding="utf-8").write(src)
    d = os.path.join(TMP, "rga"); os.makedirs(d, exist_ok=True)
    inc = os.path.dirname(sh["path"])
    inc2 = os.path.dirname(os.path.dirname(sh["path"]))
    base = [A.RGA, "-s", "dx12", "-c", "gfx1030", "--cs", os.path.abspath(sh["path"]),
            "--cs-entry", sh["entry"], "--cs-model", "cs_6_6",
            "-I", os.path.abspath(inc),
            "-I", os.path.abspath(inc2)]
    p = subprocess.run(base + ["--isa", os.path.join(d, "isa.txt")],
                       capture_output=True, text=True, cwd=d, timeout=300)
    r = {}
    fi = [x for x in os.listdir(d) if "isa" in x and x.endswith(".txt")]
    fs = [x for x in os.listdir(d) if x.startswith("gfx") and "st" in x and x.endswith(".txt")]
    if fi:
        t = open(os.path.join(d, fi[0]), encoding="utf-8", errors="replace").read()
        b = t[t.find("Disassembly"):]
        ops = re.findall(r"^\s{2,}([a-z][a-z0-9_]+)", b, re.M)
        cat = lambda *p: sum(1 for o in ops if o.startswith(p))
        loads = [i for i, o in enumerate(ops) if o.startswith(("buffer_load", "global_load", "image_"))]
        waits = [i for i, o in enumerate(ops) if o == "s_waitcnt"]
        dist = [min((w for w in waits if w > i), default=i) - i for i in loads]
        r = dict(inst=len(ops) - cat("s_code_end"), valu=cat("v_"),
                 salu=sum(1 for o in ops if o.startswith("s_") and not o.startswith(
                     ("s_waitcnt", "s_clause", "s_branch", "s_cbranch", "s_code_end"))),
                 vmem=cat("buffer_", "global_", "image_", "tbuffer_"), lds=cat("ds_"),
                 waitcnt=len(waits), clause=cat("s_clause"), branch=cat("s_cbranch", "s_branch"),
                 trans=cat("v_sin", "v_cos", "v_exp", "v_log", "v_rcp", "v_rsq", "v_sqrt"),
                 samp=cat("image_sample"),
                 load_use_med=(sorted(dist)[len(dist) // 2] if dist else 0))
    for x in os.listdir(d):
        os.remove(os.path.join(d, x))
    if fs:
        pass
    p2 = subprocess.run(base + ["-a", os.path.join(d, "st.txt")],
                        capture_output=True, text=True, cwd=d, timeout=300)
    fs = [x for x in os.listdir(d) if "st" in x and x.endswith(".txt")]
    if fs:
        st = open(os.path.join(d, fs[0]), encoding="utf-8", errors="replace").read()
        g = lambda pat: (re.search(pat, st).group(1) if re.search(pat, st) else "0")
        r["vgpr"] = int(g(r"numUsedVgprs\s*=\s*(\d+)"))
        r["sgpr"] = int(g(r"numUsedSgprs\s*=\s*(\d+)"))
        r["lds_bytes"] = int(g(r"ldsUsageSizeInBytes\s*=\s*(\d+)"))
        r["scratch"] = int(g(r"scratchMemUsageInBytes\s*=\s*(\d+)"))
    src_l = hlsl_tf.loops(src)
    r.update(n_loops=len(src_l), tg_total=sh["tg"][0] * sh["tg"][1] * sh["tg"][2],
             tg_x=sh["tg"][0], tg_y=sh["tg"][1], src_bytes=len(src),
             n_tex=src.count("Texture2D"), n_lds=src.count("groupshared"),
             wave_ops=len(re.findall(r"Wave[A-Z]\w*", src)),
             base_ns=sh["probe_ns"])
    if r.get("vmem"):
        r["wait_per_mem"] = round(r["waitcnt"] / max(1, r["vmem"] + r["lds"]), 3)
    else:
        r["wait_per_mem"] = 0.0
    return r


def features():
    C = json.load(open(os.path.join(OUT, "corpus.json")))
    F = {}
    for i, sh in enumerate(C):
        try:
            F[sh["name"]] = dict(isa_features(sh), split=sh["split"])
            print(f"  [{i+1}/{len(C)}] {sh['name'][:40]:40s} vgpr={F[sh['name']].get('vgpr','?'):>4} "
                  f"inst={F[sh['name']].get('inst',0):>5} loops={F[sh['name']]['n_loops']:>2}")
        except Exception as e:
            print(f"  [{i+1}/{len(C)}] KO {sh['name']}: {e}")
    json.dump(F, open(os.path.join(OUT, "features.json"), "w"), indent=1)
    keys = sorted({k for v in F.values() for k in v})
    with open(os.path.join(OUT, "shader_features.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["shader"] + keys); w.writeheader()
        for n, v in F.items():
            w.writerow(dict(shader=n, **{k: v.get(k, "") for k in keys}))
    print(f"\n{len(F)} shader con feature")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["probe", "split", "variants", "features"])
    a = ap.parse_args()
    os.makedirs(TMP, exist_ok=True)
    dict(probe=probe, split=split, variants=variants, features=features)[a.stage]()
