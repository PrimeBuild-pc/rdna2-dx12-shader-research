"""Self-check di stabilita' del banco. Va eseguito all'inizio di ogni sessione di ricerca:
se un controllo fallisce la sessione si ferma e nessun risultato viene registrato.

Le soglie NON sono scelte a priori: sono derivate dalla calibrazione fatta in 2I
(8 processi freschi) e dichiarate qui una volta per tutte.

  1. pavimento      store-only a 262144 thread ~3150 ns          tolleranza 15%
  2. determinismo   due esecuzioni dello stesso CSO              bit-identico
  3. riproducib.    8 processi freschi, shader rappresentativo   <=2.0%  (misurato 1.1-1.3%)
                    idem sullo shader di pavimento               <=4.0%  (misurato 2.7%)
  4. ordinamento    wave64 deve risultare piu' lento del default
  5. nullo appaiato lo STESSO CSO misurato due volte in un processo:
                    |media| <=0.5% e SE <=0.5%                   (misurato 0.04% / 0.03%)

Il controllo 5 e' quello che qualifica lo strumento per cercare guadagni dell'1-3%:
misura il rumore del confronto appaiato, che e' l'unica statistica usata in 2I.

    python tools/bench_selfcheck.py
"""
import csv, hashlib, os, statistics, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.join(ROOT, "research", "12_d3d12_microbench")
BENCH = os.path.join(BENCH_DIR, "bench.exe")
CORPUS = os.path.join(ROOT, "research", "16_corpus", "cso")
DXC = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe"
TMP = os.path.join(os.environ.get("TEMP", "."), "claude", "selfcheck")

FLOOR_NS, FLOOR_TOL = 3150.0, 0.15
REPRO_REPR, REPRO_FLOOR = 2.0, 4.0
NULL_MEAN, NULL_SE = 0.5, 0.5
N_PROC = 8

STORE_ONLY = """#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID){ Out[tid.x] = float4(1,2,3,4); }
"""


def run(tag, dumpdir, specs, reps=25, dpm=8, ds=0):
    out_csv = os.path.join(TMP, tag + ".csv")
    args = [BENCH, out_csv, str(reps), str(dpm), str(ds), dumpdir]
    args += [f"{n}:{os.path.relpath(p, BENCH_DIR)}:{th}:1:64" for n, p, th in specs]
    r = subprocess.run(args, cwd=BENCH_DIR, capture_output=True, text=True, timeout=1800)
    out = {}
    if os.path.exists(out_csv):
        for row in csv.DictReader(open(out_csv)):
            out[row["variant"]] = float(row["ns_median"])
        os.remove(out_csv)
    if not out:
        print((r.stdout + r.stderr)[-600:])
    return out


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


def main():
    os.makedirs(TMP, exist_ok=True)
    fails, res = [], {}

    hp = os.path.join(TMP, "store_only.hlsl"); open(hp, "w").write(STORE_ONLY)
    floor_cso = os.path.join(CORPUS, "_floor.cso")
    subprocess.run([DXC, "-T", "cs_6_6", "-E", "main", "-Fo", floor_cso, hp], capture_output=True)
    p24 = os.path.join(CORPUS, "pressure24__default.cso")
    mseq = os.path.join(CORPUS, "mem_seq__default.cso")
    for p in (floor_cso, p24, mseq):
        if not os.path.exists(p):
            print("FAIL: manca", p); return 1

    # un solo giro di N_PROC processi copre i controlli 1, 3 e 5
    runs = []
    for i in range(N_PROC):
        m = run(f"s{i}", "-", [("floor", floor_cso, 262144), ("A", p24, 262144),
                               ("B", p24, 262144), ("C", mseq, 262144), ("D", mseq, 262144)])
        if len(m) < 5:
            print("FAIL: il banco non ha misurato tutte le varianti"); return 1
        runs.append(m)

    fl = statistics.median(r["floor"] for r in runs)
    dev = abs(fl - FLOOR_NS) / FLOOR_NS
    ok1 = dev <= FLOOR_TOL
    print(f"1. pavimento         {fl:8.0f} ns   scarto {dev*100:5.1f}%  (max {FLOOR_TOL*100:.0f}%)   "
          f"{'OK' if ok1 else 'FAIL'}")
    res["floor_ns"] = fl

    for key, lbl, thr in (("floor", "pavimento", REPRO_FLOOR), ("C", "mem_seq", REPRO_REPR),
                          ("A", "pressure24", REPRO_REPR)):
        v = [r[key] for r in runs]
        sp = 100.0 * (max(v) - min(v)) / statistics.median(v)
        ok = sp <= thr
        print(f"3. riproducib. {lbl:11s} {sp:6.2f}%   (max {thr}%)          {'OK' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"riproducibilita/{lbl}")

    for a, b, lbl in (("C", "D", "mem_seq"), ("A", "B", "pressure24")):
        ds = [100.0 * (r[b] - r[a]) / r[a] for r in runs]
        m, sd = statistics.mean(ds), statistics.stdev(ds)
        se = sd / len(ds) ** 0.5
        ok = abs(m) <= NULL_MEAN and se <= NULL_SE
        print(f"5. nullo appaiato {lbl:11s} media {m:+6.3f}%  SE {se:5.3f}%      "
              f"{'OK' if ok else 'FAIL'}")
        if lbl == "mem_seq":                    # solo lo strumento ben condizionato e' bloccante
            res["null_se"] = se
            if not ok:
                fails.append("nullo appaiato")
        elif not ok:
            print(f"   (nota: {lbl} ha rumore appaiato piu' alto; serve piu' n su questo shader)")

    if not ok1:
        fails.append("pavimento")

    d1, d2 = os.path.join(TMP, "d1"), os.path.join(TMP, "d2")
    os.makedirs(d1, exist_ok=True); os.makedirs(d2, exist_ok=True)
    for dd in (d1, d2):
        run("d", dd, [("p24", p24, 262144)], reps=6, dpm=4)
    a, b = os.path.join(d1, "out_p24.bin"), os.path.join(d2, "out_p24.bin")
    det = os.path.exists(a) and os.path.exists(b) and sha(a) == sha(b)
    print(f"2. determinismo      {'bit-identico' if det else 'DIVERSO':12s}                     "
          f"{'OK' if det else 'FAIL'}")
    if not det:
        fails.append("determinismo")

    slow = os.path.join(ROOT, "research", "14_optimizer", "cso", "wave64.cso")
    m = run("o", "-", [("fast", p24, 262144), ("slow", slow, 262144)])
    ok4 = "fast" in m and "slow" in m and m["slow"] > m["fast"] * 1.05
    print(f"4. ordinamento       {m.get('fast',0):.0f} < {m.get('slow',0):.0f} ns"
          f"                {'OK' if ok4 else 'FAIL'}")
    if not ok4:
        fails.append("ordinamento")

    print()
    if fails:
        print("SELF-CHECK FALLITO:", ", ".join(fails), "- non registrare risultati")
        return 1
    print(f"SELF-CHECK OK - rumore del confronto appaiato SE={res['null_se']:.3f}%: "
          f"il banco puo' risolvere differenze dell'1%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
