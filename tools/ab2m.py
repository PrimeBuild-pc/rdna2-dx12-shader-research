"""Phase 2M - A/B end-to-end sullo shader realmente hot (ModelViewerPS via Lighting.hlsli).

Differenze rispetto a 2L, imposte dai difetti trovati allora:
  * il bersaglio esce dall'INVENTARIO runtime, non dal microbenchmark;
  * l'oracolo di correttezza non e' bit-exact (in 2L la build non modificata dava 2 hash
    su 6 run). Si misura la variabilita' di A contro se' stesso e la si usa come soglia.

    python tools/ab2m.py --target lighting --tf all_loop --runs 7
"""
import argparse, csv, hashlib, itertools, json, os, shutil, statistics, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import hlsl_tf
import run2l as L
import ab2l as AB

MODEL_SH = os.path.join(L.ME, "Model", "Shaders")
CORE_SH = os.path.join(L.ME, "Core", "Shaders")
BAK = os.path.join(L.TMP, "orig2m")

# bersagli scelti dall'inventario runtime, non dal microbenchmark
TARGETS = {
    # ModelViewerPS = 48.71% del GPU frame. I cicli veri stanno nell'header incluso,
    # che e' incluso SOLO da questo pixel shader.
    "lighting": (MODEL_SH, "Lighting.hlsli"),
}
SCOPES = ["Render Color", "Scene Render", "Z PrePass", "Main Render", "Temporal Resolve",
          "Generate SSAO", "Post Effects", "Render Shadow Map"]


def backup(path):
    os.makedirs(BAK, exist_ok=True)
    d = os.path.join(BAK, os.path.basename(path))
    if not os.path.exists(d):
        shutil.copy2(path, d)


def restore(path):
    d = os.path.join(BAK, os.path.basename(path))
    if os.path.exists(d):
        shutil.copy2(d, path)


def run_many(tag, runs, imgdir):
    """Ogni run scrive la propria immagine: serve a stimare la variabilita' interna."""
    os.makedirs(imgdir, exist_ok=True)
    out, imgs = [], []
    for i in range(runs):
        csvp = os.path.join(L.TMP, f"{tag}{i}.csv")
        img = os.path.join(imgdir, f"{tag}{i}.bin")
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
        if os.path.exists(img):
            imgs.append(img)
    return out, imgs


def pix_diff(a, b):
    """Frazione di pixel diversi fra due dump R11G11B10 (4 byte per pixel)."""
    x = np.fromfile(a, dtype=np.uint32); y = np.fromfile(b, dtype=np.uint32)
    if x.shape != y.shape:
        return 1.0
    return float(np.count_nonzero(x != y)) / max(1, x.size)


def image_oracle(imgsA, imgsB):
    """A-contro-A da' il rumore proprio dell'applicazione; A-contro-B va confrontato con quello."""
    aa = [pix_diff(p, q) for p, q in itertools.combinations(imgsA, 2)]
    ab = [pix_diff(p, q) for p in imgsA for q in imgsB]
    return aa, ab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="lighting")
    ap.add_argument("--tf", default="all_loop")
    ap.add_argument("--runs", type=int, default=7)
    a = ap.parse_args()
    os.makedirs(L.TMP, exist_ok=True); os.makedirs(L.OUT, exist_ok=True)
    d, fn = TARGETS[a.target]
    path = os.path.join(d, fn)
    backup(path); restore(path)

    imgdir = os.path.join(L.TMP, "img2m")
    shutil.rmtree(imgdir, ignore_errors=True)

    print("=== A: applicazione originale ===")
    ok, err = AB.build()
    if not ok:
        print("build A fallita:", err); return
    A, imgsA = run_many("a", a.runs, imgdir)

    src = open(path, encoding="utf-8", errors="replace").read()
    hlsl_tf.ATTRS = ["[unroll]", "[loop]", "[unroll(4)]", "[unroll(2)]"]
    cat = dict(hlsl_tf.catalogue(src, max_per_loop=4))
    if a.tf not in cat and a.tf != "AMDAHL_PROBE":
        print(f"trasformazione {a.tf} non applicabile. Disponibili: {sorted(cat)[:12]}")
        return
    if a.tf == "AMDAHL_PROBE":
        # NON e' una candidata: disattiva del tutto i cicli sulle luci per misurare
        # quanto di "Render Color" e' il light loop. Serve solo a fissare il tetto.
        i = src.find("{", src.find("void ShadeLights("))
        s2 = src[:i + 1] + "\n    return;   // AMDAHL PROBE: nessuna luce locale\n" + src[i + 1:]
    else:
        s2 = cat[a.tf](src)
    if s2 is None or s2 == src:
        print("nessun cambiamento"); return
    open(path, "w", encoding="utf-8").write(s2)
    print(f"\n=== applicata {a.tf} a {fn} ({len(hlsl_tf.loops(src))} cicli) ===")

    print("\n=== B: applicazione con shader ottimizzato ===")
    ok, err = AB.build()
    if not ok:
        print("build B fallita:", err[:3]); restore(path); AB.build(); return
    B, imgsB = run_many("b", a.runs, imgdir)
    restore(path)

    if not A or not B:
        print("misura fallita"); AB.build(); return

    fa = [AB.frame(r) for r in A]; fb = [AB.frame(r) for r in B]
    ma, mb = statistics.median(fa), statistics.median(fb)
    print(f"\n{'':30s} {'A (orig)':>10} {'B':>10} {'delta':>9} {'sprA':>7} {'sprB':>7}")
    rows = []
    for s in SCOPES:
        x = [r[s]["gpu"] for r in A if s in r]; y = [r[s]["gpu"] for r in B if s in r]
        if not x or not y:
            continue
        mx, my = statistics.median(x), statistics.median(y)
        dd = 100.0 * (my - mx) / mx if mx else 0.0
        sx = 100.0 * (max(x) - min(x)) / mx; sy = 100.0 * (max(y) - min(y)) / my
        print(f"{s[:30]:30s} {mx:10.5f} {my:10.5f} {dd:+8.2f}% {sx:6.2f}% {sy:6.2f}%")
        rows.append(dict(scope=s, gpu_ms_A=round(mx, 6), gpu_ms_B=round(my, 6),
                         delta_pct=round(dd, 3), spread_A=round(sx, 2), spread_B=round(sy, 2)))
    dfr = 100.0 * (mb - ma) / ma
    print(f"{'GPU FRAME':30s} {ma:10.5f} {mb:10.5f} {dfr:+8.2f}% "
          f"{100*(max(fa)-min(fa))/ma:6.2f}% {100*(max(fb)-min(fb))/mb:6.2f}%")
    ca = statistics.median(AB.cpu_frame(r) for r in A)
    cb = statistics.median(AB.cpu_frame(r) for r in B)
    print(f"{'CPU frame':30s} {ca:10.5f} {cb:10.5f} {100*(cb-ca)/ca:+8.2f}%")
    print(f"{'FPS equivalente':30s} {1000/ma:10.1f} {1000/mb:10.1f} {100*(ma-mb)/mb:+8.2f}%")

    aa, ab = image_oracle(imgsA, imgsB)
    print(f"\noracolo immagine (frazione di pixel diversi, {len(imgsA)}xA {len(imgsB)}xB):")
    print(f"  A vs A : min {min(aa):.3e}  mediana {statistics.median(aa):.3e}  max {max(aa):.3e}")
    print(f"  A vs B : min {min(ab):.3e}  mediana {statistics.median(ab):.3e}  max {max(ab):.3e}")
    verdict = ("indistinguibile dal rumore dell'app" if max(ab) <= max(aa) * 1.5
               else "DIVERSA oltre la variabilita' di A")
    print(f"  verdetto: {verdict}")

    out = dict(target=a.target, tf=a.tf, runs=a.runs, frame_A=ma, frame_B=mb,
               frame_delta_pct=dfr, cpu_A=ca, cpu_B=cb,
               img_AA_max=max(aa), img_AB_max=max(ab), img_verdict=verdict)
    tag = f"{a.target}_{a.tf}"
    json.dump(out, open(os.path.join(L.OUT, f"ab2m_{tag}.json"), "w"), indent=1)
    with open(os.path.join(L.OUT, f"ab2m_{tag}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["scope", "gpu_ms_A", "gpu_ms_B", "delta_pct",
                                       "spread_A_pct", "spread_B_pct"])
        for r in rows:
            w.writerow([r["scope"], r["gpu_ms_A"], r["gpu_ms_B"], r["delta_pct"],
                        r["spread_A"], r["spread_B"]])
        w.writerow(["__FRAME__", round(ma, 6), round(mb, 6), round(dfr, 3), "", ""])
    AB.build()   # ripristina il binario originale


if __name__ == "__main__":
    main()
