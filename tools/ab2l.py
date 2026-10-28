"""Phase 2L - integrazione A/B: applica le trasformazioni scelte dalla measurement memory
agli shader dell'applicazione reale, ricompila, e confronta A contro B.

Il verdetto viene dall'applicazione, non dal microbenchmark.
Correttezza: il frame finale e' bit-exact deterministico fra run (verificato), quindi il
confronto degli 8 MB del color buffer e' un oracolo esatto.

    python tools/ab2l.py --set bitonic --runs 7
"""
import argparse, csv, hashlib, json, os, shutil, statistics, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hlsl_tf
import run2l as L

SH = os.path.join(L.ME, "Core", "Shaders")
BAK = os.path.join(L.TMP, "orig")
MSBUILD = r"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe"

# Scelte dalla memoria delle misure di 2K. Solo attributi di ciclo: l'applicazione compila
# a shader model 6.2 e [WaveSize(N)] richiede 6.6.
SETS = {
    # misurati direttamente in 2K: Bitonic32PreSort -79.93%, Bitonic32InnerSort -51.18%.
    # I Bitonic64* sono la stessa famiglia di codice, non misurati: la trasformazione e'
    # proposta dalla memoria per analogia di feature, non da una misura diretta.
    "bitonic": {
        "Bitonic32PreSortCS.hlsl": "all_unroll4",
        "Bitonic32InnerSortCS.hlsl": "all_unroll4",
        "Bitonic64PreSortCS.hlsl": "all_unroll4",
        "Bitonic64InnerSortCS.hlsl": "all_unroll4",
    },
    "bitonic_measured_only": {
        "Bitonic32PreSortCS.hlsl": "all_unroll4",
        "Bitonic32InnerSortCS.hlsl": "all_unroll4",
    },
    # shader DAVVERO eseguiti dal pass "Culling & Sorting" (4.31% del frame).
    # In 2K erano stati scartati per correttezza, ma sono NON DETERMINISTICI di per se':
    # lo stesso binario eseguito due volte da' output diversi. Il gate numerico del
    # microbenchmark non e' applicabile; qui l oracolo e l immagine finale del frame.
    "culling": {
        "ParticleBinCullingCS.hlsl": "all_unroll4",
        "ParticleLargeBinCullingCS.hlsl": "all_unroll4",
    },
}


def apply_tf(path, tfname):
    src = open(path, encoding="utf-8", errors="replace").read()
    hlsl_tf.ATTRS = ["[unroll]", "[loop]", "[unroll(4)]"]
    cat = dict(hlsl_tf.catalogue(src, max_per_loop=2))
    if tfname not in cat:
        return None, f"trasformazione {tfname} non applicabile ({len(hlsl_tf.loops(src))} cicli)"
    out = cat[tfname](src)
    if out is None or out == src:
        return None, "nessun cambiamento"
    return out, ""


def backup(names):
    os.makedirs(BAK, exist_ok=True)
    for n in names:
        s = os.path.join(SH, n)
        d = os.path.join(BAK, n)
        if not os.path.exists(d):
            shutil.copy2(s, d)


def restore():
    if not os.path.isdir(BAK):
        return
    for n in os.listdir(BAK):
        shutil.copy2(os.path.join(BAK, n), os.path.join(SH, n))


def build():
    p = subprocess.run([MSBUILD, os.path.join(L.ME, "ModelViewer", "ModelViewer.vcxproj"),
                        "-p:Configuration=Profile", "-p:Platform=x64",
                        "-p:PlatformToolset=v145", "-v:m", "-m"],
                       cwd=L.ME, capture_output=True, text=True, timeout=3600)
    err = [l for l in (p.stdout + p.stderr).splitlines() if "error" in l.lower()]
    return (len(err) == 0), err[:5]


def run_set(tag, runs, img):
    out = []
    for i in range(runs):
        csvp = os.path.join(L.TMP, f"{tag}{i}.csv")
        env = dict(os.environ, ME_BENCH_FRAMES=str(L.FRAMES), ME_BENCH_WARM=str(L.WARM),
                   ME_BENCH_CSV=csvp, ME_BENCH_IMG=img)
        subprocess.run([L.EXE], cwd=L.CWD, env=env, capture_output=True, timeout=900)
        if not os.path.exists(csvp):
            continue
        rows = {}
        for r in csv.DictReader(open(csvp)):
            if r["scope"] != "__FRAMES__":
                rows[r["scope"]] = dict(depth=int(r["depth"]), gpu=float(r["gpu_ms_mean"]),
                                        cpu=float(r["cpu_ms_mean"]))
        os.remove(csvp)
        out.append(rows)
    return out


def frame(rs):
    return sum(v["gpu"] for v in rs.values() if v["depth"] == 1)


def cpu_frame(rs):
    return sum(v["cpu"] for v in rs.values() if v["depth"] == 1)


def report(A, B, scopes, imgA, imgB):
    fa = [frame(r) for r in A]; fb = [frame(r) for r in B]
    ca = [cpu_frame(r) for r in A]; cb = [cpu_frame(r) for r in B]
    ma, mb = statistics.median(fa), statistics.median(fb)
    print(f"\n{'':38s} {'A (orig)':>10} {'B (ott.)':>10} {'delta':>9} {'spread A':>9} {'spread B':>9}")
    rows = []
    for s in scopes:
        a = [r[s]["gpu"] for r in A if s in r]
        b = [r[s]["gpu"] for r in B if s in r]
        if not a or not b:
            continue
        x, y = statistics.median(a), statistics.median(b)
        d = 100.0 * (y - x) / x if x else 0.0
        sa = 100.0 * (max(a) - min(a)) / x if x else 0
        sb = 100.0 * (max(b) - min(b)) / y if y else 0
        print(f"{s[:38]:38s} {x:10.5f} {y:10.5f} {d:+8.2f}% {sa:8.2f}% {sb:8.2f}%")
        rows.append(dict(scope=s, gpu_ms_A=round(x, 6), gpu_ms_B=round(y, 6),
                         delta_pct=round(d, 3), spread_A=round(sa, 2), spread_B=round(sb, 2)))
    print(f"{'GPU FRAME':38s} {ma:10.5f} {mb:10.5f} {100*(mb-ma)/ma:+8.2f}% "
          f"{100*(max(fa)-min(fa))/ma:8.2f}% {100*(max(fb)-min(fb))/mb:8.2f}%")
    print(f"{'CPU frame':38s} {statistics.median(ca):10.5f} {statistics.median(cb):10.5f} "
          f"{100*(statistics.median(cb)-statistics.median(ca))/statistics.median(ca):+8.2f}%")
    print(f"{'FPS equivalente (1/GPU frame)':38s} {1000/ma:10.1f} {1000/mb:10.1f} "
          f"{100*(ma-mb)/mb:+8.2f}%")
    ha = hashlib.sha256(open(imgA, "rb").read()).hexdigest()[:16] if os.path.exists(imgA) else "?"
    hb = hashlib.sha256(open(imgB, "rb").read()).hexdigest()[:16] if os.path.exists(imgB) else "?"
    print(f"\nimmagine finale: A {ha}  B {hb}  ->  "
          f"{'IDENTICA (bit-exact)' if ha == hb and ha != '?' else 'DIVERSA'}")
    return rows, dict(frame_A=ma, frame_B=mb, frame_delta=100 * (mb - ma) / ma,
                      cpu_A=statistics.median(ca), cpu_B=statistics.median(cb),
                      img_A=ha, img_B=hb, img_equal=(ha == hb and ha != "?"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="bitonic")
    ap.add_argument("--runs", type=int, default=7)
    a = ap.parse_args()
    os.makedirs(L.TMP, exist_ok=True); os.makedirs(L.OUT, exist_ok=True)
    files = SETS[a.set]
    backup(files.keys())
    restore()

    imgA = os.path.join(L.TMP, "imgA.bin"); imgB = os.path.join(L.TMP, "imgB.bin")
    print("=== A: applicazione originale ===")
    ok, err = build()
    if not ok:
        print("build A fallita:", err); return
    A = run_set("a", a.runs, imgA)

    print(f"\n=== applico le trasformazioni ({a.set}) ===")
    applied = []
    for n, tf in files.items():
        p = os.path.join(SH, n)
        s2, msg = apply_tf(p, tf)
        if s2 is None:
            print(f"  KO {n}: {msg}"); continue
        open(p, "w", encoding="utf-8").write(s2)
        print(f"  ok {n}: {tf} ({len(hlsl_tf.loops(open(p,encoding='utf-8').read()))} cicli)")
        applied.append(n)
    if not applied:
        print("nessuna trasformazione applicata"); restore(); return

    print("\n=== B: applicazione con shader ottimizzati ===")
    ok, err = build()
    if not ok:
        print("build B fallita:", err); restore(); build(); return
    B = run_set("b", a.runs, imgB)
    restore()

    scopes = ["Culling & Sorting", "Particle Render", "Particle Update", "Scene Render",
              "Render Color", "Temporal Resolve", "Post Effects"]
    rows, summ = report(A, B, scopes, imgA, imgB)
    with open(os.path.join(L.OUT, f"ab_{a.set}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["scope", "gpu_ms_A", "gpu_ms_B", "delta_pct",
                                       "spread_A_pct", "spread_B_pct"])
        for r in rows:
            w.writerow([r["scope"], r["gpu_ms_A"], r["gpu_ms_B"], r["delta_pct"],
                        r["spread_A"], r["spread_B"]])
        w.writerow(["__FRAME__", round(summ["frame_A"], 6), round(summ["frame_B"], 6),
                    round(summ["frame_delta"], 3), "", ""])
        w.writerow(["__IMG__", summ["img_A"], summ["img_B"],
                    "identica" if summ["img_equal"] else "DIVERSA", "", ""])
    json.dump(summ, open(os.path.join(L.OUT, f"ab_{a.set}.json"), "w"), indent=1)
    # ripristina il binario originale
    build()


if __name__ == "__main__":
    main()
