"""Phase 2H - validazione forte delle varianti vincitrici di 2G.

Tre stadi indipendenti:
  correctness  20 dataset x 3 workload: dump completo dell'output, metriche d'errore
  datasets     20 dataset x 5 run: il guadagno dipende dall'input?
  scaling      workload x dispatch-per-measure x 5 run: il guadagno dipende dalla scala?

Ogni run e' un processo fresco. Nessun driver/Registry/cache/gioco toccato.

    python tools/robust.py correctness
    python tools/robust.py datasets
    python tools/robust.py scaling
"""
import argparse, csv, os, statistics, subprocess, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.join(ROOT, "research", "12_d3d12_microbench")
BENCH = os.path.join(BENCH_DIR, "bench.exe")
CSO = os.path.join(ROOT, "research", "14_optimizer", "cso")
OUT = os.path.join(ROOT, "research", "15_robustness")
TMP = os.path.join(os.environ.get("TEMP", "."), "claude", "dump2h")

DS_NAME = ["orig_0.25_1.25", "zeros", "ones", "small_1e-6", "large_1e6",
           "negatives", "alternating_pm1", "mixed_mag_1e-8_1e8", "rand_pm1", "rand_pm100",
           "near_pi_mult", "tiny_1e-30", "pow2_exact", "big_int", "const_0.5",
           "ramp_full", "half_pi_mult", "huge_1e30", "rand_sparse_zero", "rand_pm10000"]

# baseline + le 3 accettate in 2G + wave64 come controllo negativo noto
VARIANTS = ["baseline", "dxc_default", "L3_loop", "all_loop", "L2_loop", "wave64"]
TG = 64
TOL_REL = 1e-4     # tolleranza definita a priori sull'errore relativo massimo


def metrics(ref, var):
    a = np.fromfile(ref, dtype=np.float32)
    b = np.fromfile(var, dtype=np.float32)
    if a.shape != b.shape:
        return dict(status="size_mismatch")
    na, nb, ia, ib = np.isnan(a), np.isnan(b), np.isinf(a), np.isinf(b)
    nan_div = int(np.count_nonzero(na != nb))
    both_inf = ia & ib
    inf_div = int(np.count_nonzero(ia != ib)) + \
              int(np.count_nonzero(np.sign(a[both_inf]) != np.sign(b[both_inf])))
    m = np.isfinite(a) & np.isfinite(b)
    r = dict(status="ok", n=int(a.size), finite=int(m.sum()), nan_div=nan_div, inf_div=inf_div,
             max_abs=0.0, max_rel=0.0, rms=0.0, rms_rel=0.0)
    if m.any():
        x = a[m].astype(np.float64); y = b[m].astype(np.float64)
        d = np.abs(x - y)
        den = np.maximum(np.abs(x), np.abs(y))
        sig = den > 1e-30    # sotto questa scala il rapporto non significa nulla
        r["max_abs"] = float(d.max())
        r["max_rel"] = float(np.max(d[sig] / den[sig])) if sig.any() else 0.0
        r["rms"] = float(np.sqrt(np.mean(d * d)))
        rx = float(np.sqrt(np.mean(x * x)))
        r["rms_rel"] = r["rms"] / rx if rx > 0 else 0.0
    return r


def run_bench(csv_out, dataset, threads, dpm, reps, dumpdir):
    args = [BENCH, csv_out, str(reps), str(dpm), str(dataset), dumpdir]
    for v in VARIANTS:
        cp = os.path.relpath(os.path.join(CSO, v + ".cso"), BENCH_DIR)
        args.append(f"{v}:{cp}:{threads}:1:{TG}")
    p = subprocess.run(args, cwd=BENCH_DIR, capture_output=True, text=True, timeout=1800)
    rows = {}
    if os.path.exists(csv_out):
        for r in csv.DictReader(open(csv_out)):
            rows[r["variant"]] = r
        os.remove(csv_out)
    if not rows:
        print(f"  KO ds{dataset} th{threads} dpm{dpm}: rc={p.returncode}\n{(p.stdout+p.stderr)[-400:]}")
    return rows


def timing_writer(path):
    f = open(path, "w", newline="", encoding="utf-8")
    w = csv.writer(f)
    w.writerow(["dataset", "ds_name", "threads", "dpm", "variant", "run",
                "ns_median", "cv_pct", "pso_create_ms", "ns_cold", "ns_warm_median"])
    return f, w


def stage_correctness(a):
    path = os.path.join(OUT, "robust_correct.csv")
    f = open(path, "w", newline="", encoding="utf-8"); w = csv.writer(f)
    w.writerow(["dataset", "ds_name", "threads", "variant", "n_floats", "n_finite", "finite_pct",
                "max_abs_err", "max_rel_err", "rms_err", "rms_rel", "nan_div", "inf_div", "verdict"])
    for th in a.threads:
        for ds in range(20):
            run_bench(os.path.join(TMP, "c.csv"), ds, th, 4, 6, TMP)
            ref = os.path.join(TMP, "out_baseline.bin")
            for v in VARIANTS[1:]:
                vb = os.path.join(TMP, f"out_{v}.bin")
                if not (os.path.exists(ref) and os.path.exists(vb)):
                    w.writerow([ds, DS_NAME[ds], th, v] + [""] * 9 + ["dump_mancante"]); continue
                m = metrics(ref, vb)
                if m["status"] != "ok":
                    w.writerow([ds, DS_NAME[ds], th, v] + [""] * 9 + [m["status"]]); continue
                fp = 100.0 * m["finite"] / m["n"]
                bad = m["nan_div"] or m["inf_div"] or m["max_rel"] > TOL_REL
                verdict = "NO" if bad else ("SI" if fp >= 1.0 else "SI_degenere")
                w.writerow([ds, DS_NAME[ds], th, v, m["n"], m["finite"], f"{fp:.2f}",
                            f"{m['max_abs']:.6e}", f"{m['max_rel']:.6e}", f"{m['rms']:.6e}",
                            f"{m['rms_rel']:.6e}", m["nan_div"], m["inf_div"], verdict])
            for v in VARIANTS:
                p = os.path.join(TMP, f"out_{v}.bin")
                if os.path.exists(p):
                    os.remove(p)
            f.flush()
            print(f"  correctness th={th} ds={ds} ({DS_NAME[ds]})")
    f.close(); print("scritto", path)


def stage_datasets(a):
    f, w = timing_writer(os.path.join(OUT, "robust_datasets.csv"))
    for ds in range(20):
        for r in range(a.runs):
            rows = run_bench(os.path.join(TMP, "d.csv"), ds, 262144, 8, 25, "-")
            for v, row in rows.items():
                w.writerow([ds, DS_NAME[ds], 262144, 8, v, r, row["ns_median"], row["cv_pct"],
                            row["pso_create_ms"], row["ns_cold"], row["ns_warm_median"]])
        f.flush(); print(f"  datasets ds={ds} ({DS_NAME[ds]}) x{a.runs}")
    f.close()


def stage_scaling(a):
    f, w = timing_writer(os.path.join(OUT, "robust_scaling.csv"))
    for ds in (0, 8, 14):
        for th in a.threads:
            for dpm in (1, 2, 4, 8, 16):
                for r in range(a.runs):
                    rows = run_bench(os.path.join(TMP, "s.csv"), ds, th, dpm, 25, "-")
                    for v, row in rows.items():
                        w.writerow([ds, DS_NAME[ds], th, dpm, v, r, row["ns_median"], row["cv_pct"],
                                    row["pso_create_ms"], row["ns_cold"], row["ns_warm_median"]])
                f.flush(); print(f"  scaling ds={ds} th={th} dpm={dpm} x{a.runs}")
    f.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["correctness", "datasets", "scaling"])
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--threads", default="65536,262144,1048576")
    a = ap.parse_args()
    a.threads = [int(x) for x in a.threads.split(",")]
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
    {"correctness": stage_correctness, "datasets": stage_datasets, "scaling": stage_scaling}[a.stage](a)


if __name__ == "__main__":
    main()
