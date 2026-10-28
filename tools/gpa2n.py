"""Phase 2N - raccolta di counter hardware su uno scope, con controlli sperimentali.

I controlli servono a CLASSIFICARE il collo di bottiglia, non sono ottimizzazioni:
  base        applicazione originale
  ps_black    pixel shader ridotto a colore costante
  no_tex      texture fetch sostituiti da costanti (albedo/normal/specular)
  one_rt      un solo render target scritto invece di MRT

    python tools/gpa2n.py --scope "Render Color" --variant base
"""
import argparse, csv, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run2l as L
import ab2l as AB

SH = os.path.join(L.ME, "Model", "Shaders")
PS = os.path.join(SH, "ModelViewerPS.hlsl")
BAK = os.path.join(L.TMP, "orig2n")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "research", "23_bottleneck")


def backup():
    os.makedirs(BAK, exist_ok=True)
    d = os.path.join(BAK, "ModelViewerPS.hlsl")
    if not os.path.exists(d):
        shutil.copy2(PS, d)


def restore():
    d = os.path.join(BAK, "ModelViewerPS.hlsl")
    if os.path.exists(d):
        shutil.copy2(d, PS)


def patch(variant):
    src = open(PS, encoding="utf-8", errors="replace").read()
    if variant == "base":
        return src
    if variant == "ps_black":
        return src.replace("mrt.Color = colorSum;", "mrt.Color = float3(0,0,0);")
    if variant == "no_tex":
        # stessa struttura e stesso flusso, ma senza campionare le texture:
        # la macro SAMPLE_TEX diventa una costante
        return src.replace(
            "# define SAMPLE_TEX(texName) texName.Sample(defaultSampler, vsOutput.uv)",
            "# define SAMPLE_TEX(texName) float4(0.5, 0.5, 0.5, 1.0)")
    if variant == "one_rt":
        # scrive un solo render target invece di due: dimezza il traffico verso i ROP
        import re as _re
        s = _re.sub(r"[ \t]*float3 Normal : SV_Target1;[ \t]*\r?\n", "", src)
        s = _re.sub(r"[ \t]*mrt\.Normal = normal;[ \t]*\r?\n", "", s)
        return s
    raise SystemExit("variante sconosciuta: " + variant)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="Render Color")
    ap.add_argument("--variant", default="base")
    ap.add_argument("--frames", type=int, default=200)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True); os.makedirs(L.TMP, exist_ok=True)
    backup(); restore()

    src = open(PS, encoding="utf-8", errors="replace").read()
    new = patch(a.variant)
    if a.variant != "base":
        if new == src:
            print(f"ATTENZIONE: la variante {a.variant} non ha cambiato il sorgente")
        open(PS, "w", encoding="utf-8").write(new)
    ok, err = AB.build()
    if not ok:
        print("build fallita:", err[:3]); restore(); AB.build(); return

    tag = f"{a.scope.replace(' ', '_')}_{a.variant}"
    csvp = os.path.join(OUT, f"gpa_{tag}.csv")
    logp = os.path.join(L.TMP, "gpa.log")
    for f in (csvp, logp):
        if os.path.exists(f):
            os.remove(f)
    env = dict(os.environ, ME_BENCH_FRAMES=str(a.frames), ME_BENCH_WARM="60",
               ME_BENCH_CSV=os.path.join(L.TMP, "g.csv"),
               ME_GPA_SCOPE=a.scope, ME_GPA_CSV=csvp, ME_GPA_LOG=logp)
    subprocess.run([L.EXE], cwd=L.CWD, env=env, capture_output=True, timeout=900)
    restore()
    if a.variant != "base":
        AB.build()

    if not os.path.exists(csvp):
        print("nessun risultato GPA. log:")
        if os.path.exists(logp):
            print(open(logp).read()[-500:])
        return
    rows = {r["counter"]: float(r["value"]) for r in csv.DictReader(open(csvp))}
    print(f"\n=== {a.scope} / {a.variant} ===")
    for k in ("GPUTime", "PSBusy", "VsGsBusy", "TexUnitBusy", "MemUnitBusy", "MemUnitStalled",
              "PSExportStalls", "WriteUnitStalled", "PrimitiveAssemblyBusy",
              "PAStalledOnRasterizer", "DepthStencilTestBusy", "ZUnitStalled",
              "PSPixelsOut", "CBMemWritten", "FetchSize", "WriteSize",
              "L0CacheHit", "L1CacheHit", "L2CacheHit", "LocalVidMemBytes"):
        if k in rows:
            print(f"  {k:24s} {rows[k]:16.2f}")


if __name__ == "__main__":
    main()
