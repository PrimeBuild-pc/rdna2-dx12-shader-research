import pandas as pd, glob, os
files = sorted(f for f in glob.glob("research/**/*.csv", recursive=True) if not f.endswith("-stats.csv"))
for f in files:
    d = pd.read_csv(f, low_memory=False)
    print(f"\n### {f}  rows={len(d)}  dur={d.TimeInSeconds.max():.2f}s")
    if f is files[0] or True:
        pass
# column population summary across all
import collections
pop = collections.defaultdict(list)
for f in files:
    d = pd.read_csv(f, low_memory=False)
    for c in d.columns:
        pop[c].append(1 - d[c].isna().mean())
print("\n=== column population (mean non-NA fraction across 14 files) ===")
for c, v in pop.items():
    m = sum(v)/len(v)
    print(f"{m:6.3f}  {c}")
