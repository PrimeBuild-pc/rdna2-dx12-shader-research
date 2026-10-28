import pandas as pd, numpy as np, glob
for f in sorted(glob.glob("research/3DMark_SteelNomad_DX12/*/*.csv")):
    if f.endswith("-stats.csv"): continue
    d=pd.read_csv(f,low_memory=False)
    # 1-second bins of fps
    b=(d.TimeInSeconds//1).astype(int)
    fps=d.groupby(b).size()
    print(f"\n{f.split(chr(92))[-1]}  frames={len(d)} dur={d.TimeInSeconds.max():.2f}")
    print("  fps/s:", " ".join(f"{v:3d}" for v in fps.values))
    print("  maxFT:", f"{d.MsBetweenPresents.max():.1f}ms at t={d.TimeInSeconds[d.MsBetweenPresents.idxmax()]:.2f}")
    print("  swapchains:", d.SwapChainAddress.nunique(), "presentmodes:", d.PresentMode.unique(), "zeros MsBetweenDisplayChange:", (d.MsBetweenDisplayChange==0).sum())
