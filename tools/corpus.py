"""Phase 2H - corpus di shader sintetici e generalizzazione delle trasformazioni loop.

20 shader di classi diverse (ALU, pressione registri, memoria, branch, riduzioni,
dipendenze loop-carried, LDS, polinomi). Per ognuno: default DXC, [loop] ovunque,
[unroll] ovunque, [loop] solo sull'ultimo ciclo.

Misura tempo GPU reale, verifica l'output contro il proprio default, raccoglie metriche ISA.

    python tools/corpus.py --runs 3

Nessun driver/Registry/cache/gioco toccato.
"""
import argparse, csv, hashlib, os, re, shutil, statistics, subprocess, sys, tempfile
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.join(ROOT, "research", "12_d3d12_microbench")
BENCH = os.path.join(BENCH_DIR, "bench.exe")
OUT = os.path.join(ROOT, "research", "16_corpus")
DXC = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe"
RGA = os.path.join(ROOT, "RadeonDeveloperToolSuite-2026-05-28-1806",
                   "RadeonDeveloperToolSuite-2026-05-28-1806", "rga.exe")
TMP = os.path.join(os.environ.get("TEMP", "."), "claude", "corpus")

THREADS, TG = 262144, 64
REPS, DPM, DATASET = 25, 8, 0
TOL_REL = 1e-4

WRAP = """#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
%(LDS)s
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;
%(BODY)s
  Out[t] = s;
}
"""

# @1@ .. @9@ = punti dove si inserisce l'attributo di loop.
# Ogni shader legge da In[] con indice mascherato (& 65535) e scrive s in Out[t].
BODIES = {
 # --- ALU pura, nessuna memoria ---
 "alu_chain_dep": ("", """
  float4 a = float4(t & 255, (t >> 3) & 255, (t >> 6) & 255, 1) * 0.00390625 + 0.25;
  @1@ for (int i = 0; i < 64; ++i) a = a * 1.0009765625 + 0.0009765625;
  s = a;"""),
 "alu_ilp4": ("", """
  float4 a0 = float4(t & 255, 1, 2, 3) * 0.00390625 + 0.25, a1 = a0 + 0.125, a2 = a0 + 0.25, a3 = a0 + 0.5;
  @1@ for (int i = 0; i < 64; ++i) { a0 = a0*1.0009765625 + 0.001; a1 = a1*1.0009765625 + 0.002;
        a2 = a2*1.0009765625 + 0.003; a3 = a3*1.0009765625 + 0.004; }
  s = (a0 + a1) + (a2 + a3);"""),
 "trig_heavy": ("", """
  float4 a = float4(t & 511, (t >> 2) & 511, (t >> 4) & 511, 1) * 0.001953125;
  @1@ for (int i = 0; i < 32; ++i) a = sin(a) + cos(a * 1.5) * 0.5;
  s = a;"""),
 "transcend": ("", """
  float4 a = float4(t & 255, (t >> 3) & 255, (t >> 6) & 255, 7) * 0.00390625 + 0.5;
  @1@ for (int i = 0; i < 32; ++i) a = exp2(log2(a + 1.0) * 0.5) + rsqrt(a + 2.0);
  s = a;"""),
 "poly_horner": ("", """
  float4 x = float4(t & 255, (t >> 3) & 255, (t >> 6) & 255, 1) * 0.00390625;
  float4 a = 0;
  @1@ for (int i = 0; i < 40; ++i) a = a * x + float(40 - i) * 0.03125;
  s = a;"""),

 # --- pressione registri: stesso schema di s4_pressure, tre taglie ---
 "pressure8": ("", """
  float4 v[8];
  @1@ for (int i = 0; i < 8; ++i) v[i] = In[(t*8+i) & 65535] * (i+1);
  @2@ for (int k = 0; k < 8; ++k) v[k] = sin(v[k]) + v[(k*3)%8]*cos(v[(k*5)%8]);
  @3@ for (int j = 0; j < 8; ++j) s += v[j]*v[(j*3)%8];"""),
 "pressure24": ("", """
  float4 v[24];
  @1@ for (int i = 0; i < 24; ++i) v[i] = In[(t*24+i) & 65535] * (i+1);
  @2@ for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  @3@ for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),
 "pressure48": ("", """
  float4 v[48];
  @1@ for (int i = 0; i < 48; ++i) v[i] = In[(t*48+i) & 65535] * (i+1);
  @2@ for (int k = 0; k < 48; ++k) v[k] = sin(v[k]) + v[(k*7)%48]*cos(v[(k*13)%48]);
  @3@ for (int j = 0; j < 48; ++j) s += v[j]*v[(j*5)%48];"""),
 "pressure24_nomem": ("", """
  float4 v[24];
  @1@ for (int i = 0; i < 24; ++i) { float f = float(((t*24+i) & 65535) & 1023) * 0.0009765625 + 0.25;
        v[i] = float4(f, 1.0-f, f*0.5-0.25, 1.0) * (i+1); }
  @2@ for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  @3@ for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),

 # --- memoria ---
 "mem_seq": ("", """
  @1@ for (int i = 0; i < 32; ++i) s += In[(t*32+i) & 65535];"""),
 "mem_stride": ("", """
  @1@ for (int i = 0; i < 32; ++i) s += In[(t + i*1031) & 65535];"""),
 "mem_gather": ("", """
  uint h = t * 2654435761u;
  @1@ for (int i = 0; i < 32; ++i) { h = h * 1664525u + 1013904223u; s += In[(h >> 12) & 65535]; }"""),
 "mem_alu_mix": ("", """
  @1@ for (int i = 0; i < 24; ++i) { float4 a = In[(t*24+i) & 65535];
        s += sin(a) * cos(a * 1.25) + a * 0.5; }"""),

 # --- riduzioni ---
 "reduce_dot": ("", """
  float4 acc = 0;
  @1@ for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535]; acc += a * a; }
  s = acc;"""),
 "reduce_minmax": ("", """
  float4 mn = 1e30, mx = -1e30;
  @1@ for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535]; mn = min(mn, a); mx = max(mx, a); }
  s = mx - mn;"""),

 # --- controllo di flusso ---
 "branch_uniform": ("", """
  @1@ for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535];
        if (i < 16) s += a * a; else s += sin(a); }"""),
 "branch_divergent": ("", """
  @1@ for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535];
        if ((t + i) & 1) s += a * a; else s += sin(a) * cos(a); }"""),

 # --- dipendenza loop-carried stretta ---
 "loop_carried": ("", """
  float4 a = In[t & 65535] + 0.5;
  @1@ for (int i = 0; i < 48; ++i) a = sin(a) * 0.5 + a * 0.25 + 0.125;
  s = a;"""),

 # --- LDS ---
 "lds_reduce": ("groupshared float4 g[64];", """
  float4 a = In[t & 65535];
  @1@ for (int i = 0; i < 8; ++i) a += In[(t*8+i) & 65535] * (i+1);
  g[gtid.x] = a;
  GroupMemoryBarrierWithGroupSync();
  @2@ for (int i = 0; i < 64; ++i) s += g[i] * 0.015625;"""),
 "lds_shuffle": ("groupshared float4 g[64];", """
  g[gtid.x] = In[t & 65535];
  GroupMemoryBarrierWithGroupSync();
  @1@ for (int i = 0; i < 32; ++i) s += g[(gtid.x * 7 + i * 13) & 63] * sin(float(i) * 0.125);"""),
}

TRANSFORMS = {"default": None, "all_loop": "[loop]", "all_unroll": "[unroll]", "last_loop": "LAST"}


def apply_tf(body, tf):
    marks = sorted(set(re.findall(r"@(\d)@", body)))
    if tf is None:
        return re.sub(r"@\d@", "", body)
    if tf == "LAST":
        last = marks[-1] if marks else None
        return re.sub(r"@(\d)@", lambda m: "[loop]" if m.group(1) == last else "", body)
    return re.sub(r"@\d@", tf, body)


def sh(cmd, cwd=None, timeout=600):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def isa_metrics(hlsl):
    """Compila con il compilatore AMD installato e misura la forma dell'ISA."""
    d = tempfile.mkdtemp(prefix="cor_")
    rc, log = sh([RGA, "-s", "dx12", "-c", "gfx1030", "--cs", hlsl, "--cs-entry", "main",
                  "--cs-model", "cs_6_6", "--rs-macro", "RS",
                  "--isa", os.path.join(d, "isa.txt"), "-a", os.path.join(d, "st.txt")], cwd=d)
    r = {}
    isa = [f for f in os.listdir(d) if "isa" in f and f.endswith(".txt")]
    stf = [f for f in os.listdir(d) if "st" in f and f.endswith(".txt")]
    if "succeeded" in log and isa:
        t = open(os.path.join(d, isa[0]), encoding="utf-8", errors="replace").read()
        b = t[t.find("Disassembly"):]
        ops = re.findall(r"^\s{2,}([a-z][a-z0-9_]+)", b, re.M)
        cat = lambda p: sum(1 for o in ops if o.startswith(p))
        r = dict(inst=len(ops) - cat("s_code_end"),
                 valu=cat("v_"), salu=sum(1 for o in ops if o.startswith("s_") and not
                          o.startswith(("s_waitcnt", "s_clause", "s_branch", "s_cbranch", "s_code_end"))),
                 vmem=cat("buffer_") + cat("global_") + cat("image_") + cat("tbuffer_"),
                 lds=cat("ds_"), waitcnt=cat("s_waitcnt"), clause=cat("s_clause"),
                 branch=cat("s_cbranch") + cat("s_branch"),
                 trans=sum(1 for o in ops if o.startswith(("v_sin", "v_cos", "v_exp", "v_log",
                                                           "v_rcp", "v_rsq", "v_sqrt"))),
                 isa_sha=hashlib.sha256(re.sub(r"//.*", "", b).encode()).hexdigest()[:12])
        m = re.search(r"vgpr_count\((\d+)\)", t); r["vgpr_req"] = m.group(1) if m else ""
        m = re.search(r"wave_size\((\d+)\)", t); r["wave"] = m.group(1) if m else ""
    if stf:
        st = open(os.path.join(d, stf[0]), encoding="utf-8", errors="replace").read()
        g = lambda p: (re.search(p, st).group(1) if re.search(p, st) else "")
        r["vgpr_used"] = g(r"numUsedVgprs\s*=\s*(\d+)")
        r["sgpr_used"] = g(r"numUsedSgprs\s*=\s*(\d+)")
        r["lds_bytes"] = g(r"ldsUsageSizeInBytes\s*=\s*(\d+)")
        r["scratch"] = g(r"scratchMemUsageInBytes\s*=\s*(\d+)")
    shutil.rmtree(d, ignore_errors=True)
    return r


def err_metrics(ref, var):
    a = np.fromfile(ref, dtype=np.float32); b = np.fromfile(var, dtype=np.float32)
    if a.shape != b.shape:
        return dict(bad=True, max_rel=float("inf"), rms_rel=float("inf"), div=-1)
    div = int(np.count_nonzero(np.isnan(a) != np.isnan(b))) + \
          int(np.count_nonzero(np.isinf(a) != np.isinf(b)))
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return dict(bad=div > 0, max_rel=0.0, rms_rel=0.0, div=div, degenerate=True)
    x = a[m].astype(np.float64); y = b[m].astype(np.float64)
    d = np.abs(x - y); den = np.maximum(np.abs(x), np.abs(y)); sig = den > 1e-30
    mr = float(np.max(d[sig] / den[sig])) if sig.any() else 0.0
    rms = float(np.sqrt(np.mean(d * d))); rx = float(np.sqrt(np.mean(x * x)))
    return dict(bad=(div > 0 or mr > TOL_REL), max_rel=mr, rms_rel=(rms / rx if rx else 0.0), div=div)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
    hd = os.path.join(OUT, "hlsl"); cd = os.path.join(OUT, "cso")
    os.makedirs(hd, exist_ok=True); os.makedirs(cd, exist_ok=True)

    specs, meta = [], {}
    for sname, (lds, body) in BODIES.items():
        seen = {}
        for tf, val in TRANSFORMS.items():
            src = WRAP % dict(LDS=lds, BODY=apply_tf(body, val))
            h = hashlib.sha256(src.encode()).hexdigest()[:12]
            name = f"{sname}__{tf}"
            if h in seen:
                meta[name] = dict(shader=sname, tf=tf, dup_of=seen[h], src_sha=h)
                print(f"  = {name}: sorgente identico a {seen[h]}")
                continue
            seen[h] = name
            hp = os.path.join(hd, name + ".hlsl"); open(hp, "w").write(src)
            cp = os.path.join(cd, name + ".cso")
            rc, log = sh([DXC, "-T", "cs_6_6", "-E", "main", "-Fo", cp, hp])
            if not os.path.exists(cp):
                print(f"  KO {name}: DXC\n{log[-300:]}"); meta[name] = dict(shader=sname, tf=tf, err="dxc"); continue
            im = isa_metrics(hp)
            if not im:
                print(f"  KO {name}: RGA"); meta[name] = dict(shader=sname, tf=tf, err="rga"); continue
            meta[name] = dict(shader=sname, tf=tf, src_sha=h, **im)
            specs.append((name, cp))
            print(f"  ok {name:34s} vgpr={im.get('vgpr_used',''):>4} inst={im.get('inst',0):>5} "
                  f"vmem={im.get('vmem',0):>3} wait={im.get('waitcnt',0):>3} clause={im.get('clause',0):>3} "
                  f"br={im.get('branch',0):>3}")

    # --- benchmark: run indipendenti, dump solo al primo per la verifica ---
    allruns = []
    for r in range(a.runs):
        dump = TMP if r == 0 else "-"
        args = [BENCH, os.path.join(TMP, f"c{r}.csv"), str(REPS), str(DPM), str(DATASET), dump]
        args += [f"{n}:{os.path.relpath(cp, BENCH_DIR)}:{THREADS}:1:{TG}" for n, cp in specs]
        rc, log = sh(args, cwd=BENCH_DIR, timeout=7200)
        d = {}
        p = os.path.join(TMP, f"c{r}.csv")
        if os.path.exists(p):
            for row in csv.DictReader(open(p)):
                d[row["variant"]] = float(row["ns_median"])
        allruns.append(d)
        print(f"  run {r+1}/{a.runs}: {len(d)} varianti")
        if not d:
            print(log[-800:])

    rows = []
    for name, cp in specs:
        m = meta[name]
        meds = [d[name] for d in allruns if name in d]
        if not meds:
            continue
        med = statistics.median(meds)
        spread = 100 * (max(meds) - min(meds)) / med if med else 0
        ref = os.path.join(TMP, f"out_{m['shader']}__default.bin")
        vb = os.path.join(TMP, f"out_{name}.bin")
        if m["tf"] == "default":
            e = dict(bad=False, max_rel=0.0, rms_rel=0.0, div=0)
        elif os.path.exists(ref) and os.path.exists(vb):
            e = err_metrics(ref, vb)
        else:
            e = dict(bad=True, max_rel=float("inf"), rms_rel=float("inf"), div=-1)
        rows.append(dict(name=name, shader=m["shader"], tf=m["tf"], ns_median=round(med, 1),
                         runs=len(meds), spread_pct=round(spread, 3),
                         correct="no" if e["bad"] else "SI",
                         max_rel_err=f"{e['max_rel']:.3e}", rms_rel=f"{e['rms_rel']:.3e}",
                         nan_inf_div=e["div"],
                         **{k: m.get(k, "") for k in ("vgpr_used", "sgpr_used", "inst", "valu",
                            "salu", "vmem", "lds", "waitcnt", "clause", "branch", "trans",
                            "scratch", "wave", "isa_sha")}))

    base = {r["shader"]: r for r in rows if r["tf"] == "default"}
    for r in rows:
        b = base.get(r["shader"])
        if b:
            r["d_pct"] = round(100 * (r["ns_median"] - b["ns_median"]) / b["ns_median"], 2)
            r["threshold_pct"] = round(max(2.0, r["spread_pct"], b["spread_pct"]), 3)
            r["verdict"] = ("meglio" if (r["correct"] == "SI" and r["d_pct"] < -r["threshold_pct"])
                            else "peggio" if r["d_pct"] > r["threshold_pct"]
                            else "uguale")
            if r["tf"] == "default":
                r["verdict"] = "-"
            r["d_waitcnt"] = (int(r["waitcnt"]) - int(b["waitcnt"])) if r["waitcnt"] != "" and b["waitcnt"] != "" else ""
            r["d_clause"] = (int(r["clause"]) - int(b["clause"])) if r["clause"] != "" and b["clause"] != "" else ""

    keys = ["shader", "tf", "name", "correct", "max_rel_err", "rms_rel", "nan_inf_div", "ns_median",
            "d_pct", "verdict", "threshold_pct", "runs", "spread_pct", "vgpr_used", "sgpr_used",
            "inst", "valu", "salu", "vmem", "lds", "waitcnt", "d_waitcnt", "clause", "d_clause",
            "branch", "trans", "scratch", "wave", "isa_sha"]
    with open(os.path.join(OUT, "corpus_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader()
        for r in sorted(rows, key=lambda r: (r["shader"], r["tf"])):
            w.writerow({k: r.get(k, "") for k in keys})

    print(f"\n{'shader':22s} {'tf':11s} {'ns':>9} {'d%':>8} {'corr':5s} {'wait':>5} {'clau':>5} esito")
    for r in sorted(rows, key=lambda r: (r["shader"], r["tf"])):
        print(f"{r['shader']:22s} {r['tf']:11s} {r['ns_median']:9.0f} {r.get('d_pct',0):+8.2f} "
              f"{r['correct']:5s} {r['waitcnt']:>5} {r['clause']:>5} {r.get('verdict','')}")
    for v in ("meglio", "peggio", "uguale"):
        n = sum(1 for r in rows if r.get("verdict") == v)
        print(f"{v}: {n}")


if __name__ == "__main__":
    main()
