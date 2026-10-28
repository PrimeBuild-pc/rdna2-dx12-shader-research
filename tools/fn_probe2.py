import pandas as pd, numpy as np, glob
for f in sorted(glob.glob("research/fortnite_DX12_PerformanceMode/*.csv")):
    if f.endswith("-stats.csv"): continue
    d=pd.read_csv(f,low_memory=False)
    b=(d.TimeInSeconds//2).astype(int)
    fps=(d.groupby(b).size()/2).round(0).astype(int)
    print(f"\n{f.split(chr(92))[-1]} frames={len(d)} dur={d.TimeInSeconds.max():.2f} sc={d.SwapChainAddress.nunique()}")
    print("  fps/2s:", " ".join(f"{v}" for v in fps.values))
    print("  maxFT %.1fms @t=%.2f | ft>8ms: %d | ft>16ms: %d | vram MB %.0f-%.0f | gpuclk %.0f-%.0f | gpuutil %.0f-%.0f"%(
        d.MsBetweenPresents.max(), d.TimeInSeconds[d.MsBetweenPresents.idxmax()],
        (d.MsBetweenPresents>8).sum(), (d.MsBetweenPresents>16).sum(),
        d.GPUMemorySizeUsed.min()/1e6, d.GPUMemorySizeUsed.max()/1e6,
        d.GPUFrequency.min(), d.GPUFrequency.max(), d.GPUUtilization.min(), d.GPUUtilization.max()))
