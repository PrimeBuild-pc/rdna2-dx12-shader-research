"""Phase 2L - profiling e A/B end-to-end su MiniEngine ModelViewer (Sponza).

  baseline   N esecuzioni indipendenti dell'app, profilo GPU per pass, varianza
  rank       tabella di costo: us/chiamata, chiamate/frame, us/frame, % del GPU frame
  ab         confronto A/B fra applicazione originale e applicazione con shader sostituito

    python tools/run2l.py baseline --runs 7
"""
import argparse, csv, os, shutil, statistics, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "21_workload")
ME = r"C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine"
EXE = os.path.join(ME, "Build", "x64", "Profile", "Output", "ModelViewer", "ModelViewer.exe")
CWD = os.path.join(ME, "ModelViewer")
TMP = os.path.join(os.environ.get("TEMP", "."), "claude", "l2")

FRAMES, WARM = 2000, 400


def run_once(tag, frames=FRAMES, warm=WARM, timeout=600):
    csvp = os.path.join(TMP, tag + ".csv")
    if os.path.exists(csvp):
        os.remove(csvp)
    env = dict(os.environ, ME_BENCH_FRAMES=str(frames), ME_BENCH_WARM=str(warm),
               ME_BENCH_CSV=csvp)
    try:
        subprocess.run([EXE], cwd=CWD, env=env, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if not os.path.exists(csvp):
        return None
    rows = {}
    for r in csv.DictReader(open(csvp)):
        if r["scope"] == "__FRAMES__":
            continue
        rows[r["scope"]] = dict(depth=int(r["depth"]), gpu=float(r["gpu_ms_mean"]),
                                cpu=float(r["cpu_ms_mean"]), samples=int(r["samples"]))
    os.remove(csvp)
    return rows


def collect(runs, tag="b"):
    out = []
    for i in range(runs):
        r = run_once(f"{tag}{i}")
        if r is None:
            print(f"  run {i}: FALLITO"); continue
        out.append(r)
        tot = sum(v["gpu"] for v in r.values() if v["depth"] == 1)
        print(f"  run {i}: {len(r)} scope, GPU frame {tot:.4f} ms")
    return out


def summarize(runs):
    """Media e spread per scope, su run indipendenti."""
    keys = sorted({k for r in runs for k in r})
    S = {}
    for k in keys:
        g = [r[k]["gpu"] for r in runs if k in r]
        c = [r[k]["cpu"] for r in runs if k in r]
        if not g:
            continue
        med = statistics.median(g)
        S[k] = dict(depth=runs[0].get(k, {}).get("depth", 1), gpu=med,
                    cpu=statistics.median(c), n=len(g),
                    spread=(100.0 * (max(g) - min(g)) / med if med else 0.0),
                    sd=(statistics.stdev(g) if len(g) > 1 else 0.0))
    return S


def frame_total(S):
    """Il profiler e' annidato: la somma dei nodi di livello 1 e' il frame GPU."""
    return sum(v["gpu"] for v in S.values() if v["depth"] == 1)


def baseline(a):
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
    runs = collect(a.runs)
    if not runs:
        print("nessun run valido"); return
    S = summarize(runs)
    tot = frame_total(S)
    tots = [sum(v["gpu"] for k, v in r.items() if v["depth"] == 1) for r in runs]
    with open(os.path.join(OUT, "baseline_profile.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scope", "depth", "gpu_ms", "cpu_ms", "pct_frame_gpu", "spread_pct", "runs"])
        for k, v in sorted(S.items(), key=lambda x: -x[1]["gpu"]):
            w.writerow([k, v["depth"], round(v["gpu"], 5), round(v["cpu"], 5),
                        round(100.0 * v["gpu"] / tot, 3), round(v["spread"], 2), v["n"]])
    print(f"\nGPU frame: {tot:.4f} ms (mediana su {len(runs)} run)")
    print(f"  spread run-to-run del frame: {100*(max(tots)-min(tots))/statistics.median(tots):.2f}%")
    print(f"\n{'scope':32s} {'liv':>3} {'GPU ms':>9} {'% frame':>8} {'spread':>7}")
    for k, v in sorted(S.items(), key=lambda x: -x[1]["gpu"])[:24]:
        print(f"{k[:32]:32s} {v['depth']:3d} {v['gpu']:9.4f} {100*v['gpu']/tot:7.2f}% "
              f"{v['spread']:6.2f}%")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["baseline"])
    ap.add_argument("--runs", type=int, default=7)
    a = ap.parse_args()
    dict(baseline=baseline)[a.stage](a)
