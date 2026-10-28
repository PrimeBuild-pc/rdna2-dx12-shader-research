"""Cross-check pmparse against PresentMon's own -stats.csv on the UNTRIMMED capture."""
import glob, os, numpy as np, pandas as pd, sys
sys.path.insert(0, "tools")
from pmparse import load, FT, low_pct

rows = []
for f in sorted(glob.glob("research/**/*.csv", recursive=True)):
    if f.endswith("-stats.csv"):
        continue
    st = f[:-4] + "-stats.csv"
    if not os.path.exists(st):
        continue
    s = pd.read_csv(st).iloc[0]
    d = load(f)
    ft = d[FT].to_numpy()
    dur = d.TimeInSeconds.max() - d.TimeInSeconds.min()
    rows.append(dict(
        file=os.path.basename(f),
        pm_frames=int(s["Total Frames"]), my_frames=len(d),
        pm_dur=s["Duration"], my_dur=round(float(dur), 4),
        pm_avg_fps=s["Average FPS"], my_avg_fps=round(len(d) / dur, 4),
        pm_min_fps=s["Minimum FPS"], my_min_fps=round(1000 / ft.max(), 4),
        pm_p1_fps=s["1st Percentile FPS"], my_p1_fps=round(low_pct(ft, 0.01), 4),
        pm_p5_fps=s["5th Percentile FPS"], my_p5_fps=round(low_pct(ft, 0.05), 4),
        pm_max_fps=s["Maximum FPS"], my_max_fps=round(1000 / ft.min(), 4),
    ))
v = pd.DataFrame(rows)
for a, b in [("frames", "frames"), ("dur", "dur"), ("avg_fps", "avg_fps"), ("min_fps", "min_fps"),
             ("p1_fps", "p1_fps"), ("p5_fps", "p5_fps"), ("max_fps", "max_fps")]:
    v[f"d_{a}"] = (v[f"my_{b}"] - v[f"pm_{a}"]) / v[f"pm_{a}"].replace(0, np.nan) * 100
os.makedirs("research/04_benchmarks/analysis", exist_ok=True)
v.to_csv("research/04_benchmarks/analysis/parser_validation.csv", index=False)
pd.set_option("display.width", 250)
print(v[["file", "pm_frames", "my_frames", "d_dur", "d_avg_fps", "d_min_fps", "d_p1_fps", "d_p5_fps", "d_max_fps"]].to_string(index=False))
print("\nmax |delta%% | per metric:")
print(v[[c for c in v if c.startswith("d_")]].abs().max().round(4).to_string())
