"""Phase 2G - Automated Shader Optimizer.

Ciclo: genera variante HLSL -> DXC -> compilatore AMD (RGA, ISA/stats) -> microbenchmark D3D12
-> verifica correttezza numerica -> conserva/scarta.

    python tools/opt_loop.py            # sweep completo
    python tools/opt_loop.py --runs 3   # numero di run indipendenti per variante

Non tocca driver, Registry, cache o giochi. Una variabile per variante.
Una variante entra nel ranking SOLO se: output corretto entro tolleranza, miglioramento
sopra il rumore misurato dello shader, e ripetibile in tutti i run indipendenti.
"""
import argparse, csv, hashlib, os, re, shutil, statistics, struct, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "research", "14_optimizer")
BENCH_DIR = os.path.join(ROOT, "research", "12_d3d12_microbench")
BENCH = os.path.join(BENCH_DIR, "bench.exe")
DXC = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe"
RGA = os.path.join(ROOT, "RadeonDeveloperToolSuite-2026-05-28-1806",
                   "RadeonDeveloperToolSuite-2026-05-28-1806", "rga.exe")

THREADS = 262144          # totale thread fisso: ogni variante scrive gli stessi elementi
REPS, DPM = 25, 8         # 25 misure, 8 dispatch ciascuna
TOL = 1e-4                # tolleranza relativa sull'output
NOISE_PCT = 2.32          # rumore misurato di s4_pressure (variance_report.md)

# --- template: {L1},{L2},{L3} attributi di loop; {TG} threadgroup; {WAVE} attributo wave ---
TPL = """#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]{WAVE}[numthreads({TG},1,1)]
void main(uint3 t : SV_DispatchThreadID){{
  float4 v[24];
  {L1} for (int i=0;i<24;++i) v[i] = In[(t.x*24+i) & 65535] * (i+1);
  {L2} for (int k=0;k<24;++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  {BODY3}
  Out[t.x] = s;
}}
"""
B3_BASE = "float4 s = 0;\n  {L3} for (int j=0;j<24;++j) s += v[j]*v[(j*5)%24];"
# 2 e 4 accumulatori: piu' ILP, l'ordine della somma float cambia -> entro tolleranza
B3_ACC2 = ("float4 s0=0, s1=0;\n  {L3} for (int j=0;j<24;j+=2) {{ s0 += v[j]*v[(j*5)%24];"
           " s1 += v[j+1]*v[((j+1)*5)%24]; }}\n  float4 s = s0+s1;")
B3_ACC4 = ("float4 s0=0,s1=0,s2=0,s3=0;\n  {L3} for (int j=0;j<24;j+=4) {{ s0 += v[j]*v[(j*5)%24];"
           " s1 += v[j+1]*v[((j+1)*5)%24]; s2 += v[j+2]*v[((j+2)*5)%24];"
           " s3 += v[j+3]*v[((j+3)*5)%24]; }}\n  float4 s = (s0+s1)+(s2+s3);")
# temporanei espliciti in L2 (stesso ordine, stesso risultato)
L2_TEMP = ("@L2@ for (int k=0;k<24;++k) { float4 a=v[(k*7)%24], b=v[(k*13)%24];"
           " v[k] = sin(v[k]) + a*cos(b); }")


def variants():
    """(nome, kind, tg, hlsl). Una sola variabile cambiata rispetto alla baseline."""
    def mk(l1="[unroll]", l2="[unroll]", l3="[unroll]", tg=64, wave="", body3=B3_BASE, l2body=None):
        b3 = body3.replace("{L3}", l3)
        body = TPL.replace("{BODY3}", b3).format(L1=l1, L2=l2, TG=tg, WAVE=wave)
        if l2body:
            old = f"  {l2} for (int k=0;k<24;++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);"
            body = body.replace(old, "  " + l2body.replace("@L2@", l2))
        return body

    V = [("baseline", "baseline", 64, mk())]
    for tg in (32, 128, 256):
        V.append((f"tg{tg}", "numthreads", tg, mk(tg=tg)))
    V += [("L1_loop", "loop_attr", 64, mk(l1="[loop]")),
          ("L2_loop", "loop_attr", 64, mk(l2="[loop]")),
          ("L3_loop", "loop_attr", 64, mk(l3="[loop]")),
          ("all_loop", "loop_attr", 64, mk(l1="[loop]", l2="[loop]", l3="[loop]"))]
    for n in (4, 8, 12):
        V.append((f"L2_unroll{n}", "unroll_factor", 64, mk(l2=f"[unroll({n})]")))
    V += [("L2_temps", "temporaries", 64, mk(l2body=L2_TEMP)),
          ("acc2", "ilp_accum", 64, mk(body3=B3_ACC2)),
          ("acc4", "ilp_accum", 64, mk(body3=B3_ACC4)),
          ("wave32", "wave", 64, mk(wave="[WaveSize(32)]")),
          ("wave64", "wave", 64, mk(wave="[WaveSize(64)]"))]
    return V


def sh(cmd, cwd=None, timeout=300):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "timeout"


def compile_dxil(hlsl_path, cso_path):
    rc, log = sh([DXC, "-T", "cs_6_6", "-E", "main", "-Fo", cso_path, hlsl_path])
    return os.path.exists(cso_path), log


def isa_stats(hlsl_path):
    out = tempfile.mkdtemp(prefix="opt_")
    rc, log = sh([RGA, "-s", "dx12", "-c", "gfx1030", "--cs", hlsl_path, "--cs-entry", "main",
                  "--cs-model", "cs_6_6", "--rs-macro", "RS", "--isa", os.path.join(out, "isa.txt")],
                 cwd=out)
    r = {}
    iso = [x for x in os.listdir(out) if "isa" in x and x.endswith(".txt")]
    if "succeeded" in log and iso:
        t = open(os.path.join(out, iso[0]), encoding="utf-8", errors="replace").read()
        g = lambda p: (re.search(p, t).group(1) if re.search(p, t) else "")
        b = t[t.find("Disassembly"):]
        ins = [l for l in b.splitlines() if re.match(r"\s{2}[a-z][a-z0-9_]+\s", l) and "//" in l]
        r = dict(vgpr=g(r"vgpr_count\((\d+)\)"), sgpr=g(r"sgpr_count\((\d+)\)"),
                 wave=g(r"wave_size\((\d+)\)"), inst=len(ins),
                 scratch="0" if "scratch" not in t.lower() else "?",
                 isa_sha=hashlib.sha256(re.sub(r"//.*", "", b).encode()).hexdigest()[:12])
    shutil.rmtree(out, ignore_errors=True)
    return r


def compare(a, b, tol=TOL):
    """Errore relativo massimo fra due dump binari di float."""
    A = open(a, "rb").read(); B = open(b, "rb").read()
    if len(A) != len(B):
        return False, float("inf"), "dimensioni diverse"
    n = len(A) // 4
    fa = struct.unpack(f"<{n}f", A); fb = struct.unpack(f"<{n}f", B)
    worst, nan = 0.0, 0
    for x, y in zip(fa, fb):
        if x != x or y != y:
            nan += 1; continue
        d = abs(x - y) / max(abs(x), abs(y), 1.0)
        if d > worst:
            worst = d
    if nan:
        return False, worst, f"{nan} NaN"
    return worst <= tol, worst, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(LAB, exist_ok=True)
    hd = os.path.join(LAB, "hlsl"); cd = os.path.join(LAB, "cso")
    os.makedirs(hd, exist_ok=True); os.makedirs(cd, exist_ok=True)

    V = variants()
    seen, rows, specs = {}, [], []
    for name, kind, tg, src in V:
        h = hashlib.sha256(src.encode()).hexdigest()[:12]
        if h in seen:
            print(f"  skip {name}: sorgente identico a {seen[h]}")
            continue
        seen[h] = name
        hp = os.path.join(hd, name + ".hlsl"); open(hp, "w").write(src)
        cp = os.path.join(cd, name + ".cso")
        ok, log = compile_dxil(hp, cp)
        if not ok:
            print(f"  KO  {name}: DXC fallito"); rows.append(dict(name=name, kind=kind, src_sha=h, status="dxc_fail")); continue
        st = isa_stats(hp)
        if not st:
            print(f"  KO  {name}: RGA fallito"); rows.append(dict(name=name, kind=kind, src_sha=h, status="rga_fail")); continue
        specs.append((name, kind, tg, h, cp, st))
        print(f"  ok  {name:14s} vgpr={st['vgpr']:>3} sgpr={st['sgpr']:>3} inst={st['inst']:>4} "
              f"wave={st['wave']} isa={st['isa_sha']}")

    # --- benchmark: `runs` esecuzioni indipendenti del processo ---
    allruns = []
    for r in range(a.runs):
        args = [BENCH, os.path.join(LAB, f"bench_run{r}.csv"), str(REPS), str(DPM)]
        args += [f"{n}:{os.path.relpath(cp, BENCH_DIR)}:{THREADS}:1:{tg}" for n, k, tg, h, cp, st in specs]  # relativo: il parser del bench splitta su ':'
        rc, log = sh(args, cwd=BENCH_DIR, timeout=3600)
        d = {}
        p = os.path.join(LAB, f"bench_run{r}.csv")
        if os.path.exists(p):
            for row in csv.DictReader(open(p)):
                d[row["variant"]] = float(row["ns_median"])
        allruns.append(d)
        print(f"  run {r+1}/{a.runs}: {len(d)} varianti misurate")

    base_bin = os.path.join(BENCH_DIR, "out_baseline.bin")
    for name, kind, tg, h, cp, st in specs:
        meds = [d[name] for d in allruns if name in d]
        if not meds:
            continue
        med = statistics.median(meds)
        spread = 100 * (max(meds) - min(meds)) / med if med else 0
        ob = os.path.join(BENCH_DIR, f"out_{name}.bin")
        if name == "baseline" or not os.path.exists(base_bin) or not os.path.exists(ob):
            corr, err, note = (True, 0.0, "riferimento") if name == "baseline" else (False, float("inf"), "output mancante")
        else:
            corr, err, note = compare(base_bin, ob)
        rows.append(dict(name=name, kind=kind, src_sha=h, status="ok",
                         correct="SI" if corr else "NO", max_rel_err=f"{err:.3e}", note=note,
                         ns_median=round(med, 1), runs=len(meds), run_spread_pct=round(spread, 3),
                         **{k: st.get(k, "") for k in ("vgpr", "sgpr", "wave", "inst", "isa_sha")}))

    base = next((r for r in rows if r["name"] == "baseline" and r.get("status") == "ok"), None)
    for r in rows:
        if r.get("status") == "ok" and base:
            r["d_pct"] = round(100 * (r["ns_median"] - base["ns_median"]) / base["ns_median"], 2)
            # il miglioramento deve superare SIA il rumore globale dello shader SIA lo
            # spread run-to-run della variante stessa: altrimenti non e' distinguibile
            thr = max(NOISE_PCT, r["run_spread_pct"], base["run_spread_pct"])
            r["threshold_pct"] = round(thr, 3)
            r["accepted"] = ("SI" if (r["correct"] == "SI" and r["d_pct"] < -thr
                                      and r["name"] != "baseline") else "no")
    keys = ["name", "kind", "status", "correct", "max_rel_err", "note", "ns_median", "d_pct",
            "accepted", "threshold_pct", "runs", "run_spread_pct", "vgpr", "sgpr", "wave", "inst", "isa_sha", "src_sha"]
    with open(os.path.join(LAB, "optimizer_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})

    ok = [r for r in rows if r.get("status") == "ok"]
    ok.sort(key=lambda r: r.get("ns_median", 9e9))
    print(f"\n{'variante':14s} {'corr':5s} {'ns':>9} {'d%':>7} {'vgpr':>5} {'inst':>5} {'wave':>5} {'acc':>4}")
    for r in ok[:15]:
        print(f"{r['name']:14s} {r['correct']:5s} {r['ns_median']:9.0f} {r.get('d_pct',0):+7.2f} "
              f"{r['vgpr']:>5} {r['inst']:>5} {r['wave']:>5} {r.get('accepted',''):>4}")
    acc = [r for r in ok if r.get("accepted") == "SI"]
    print(f"\nvarianti ACCETTATE (corrette e sopra il rumore {NOISE_PCT}%): {len(acc)}")
    for r in acc:
        print(f"   {r['name']}: {r['d_pct']:+.2f}%")


if __name__ == "__main__":
    main()
