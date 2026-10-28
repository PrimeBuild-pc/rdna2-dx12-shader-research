"""Match a complete native benchmark frame trace to passive PresentMon; never edit raw data."""
import argparse
import hashlib
import json
import shutil
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

from pmparse import FT, load, low_time, low_pct, spikes, summarize


def match(x, y):
    if len(y) < 2 or len(x) < len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Incomplete or nonfinite frame trace")
    n = len(y)
    s = np.r_[0, np.cumsum(x)]
    q = np.r_[0, np.cumsum(x * x)]
    variance = np.maximum(q[n:] - q[:-n] - (s[n:] - s[:-n]) ** 2 / n, 0)
    den = np.sqrt(variance * np.sum((y - y.mean()) ** 2))
    r = np.divide(np.correlate(x, y - y.mean(), mode="valid"), den,
                  out=np.full(len(x) - n + 1, -np.inf), where=den > 0)
    if not np.isfinite(r).any():
        raise ValueError("No identifiable frame pattern")
    a = int(np.argmax(r))
    return a, float(r[a])


def analyze(run, native):
    dest = run / "native_analysis"
    if dest.exists():
        raise FileExistsError(dest)
    metadata = json.loads((run / "metadata.json").read_text())
    if metadata["presentmon_returncode"] != 0:
        raise ValueError("PresentMon failed")
    game = json.loads((native / "summary.json").read_text())["Data"]
    g = pd.read_csv(native / "frames.csv", skipinitialspace=True)
    y = g["Frame time (ms)"].to_numpy(float)
    d = load(run / "presentmon.csv")
    if len(d.groupby(["ProcessID", "SwapChainAddress"])) != 1:
        raise ValueError("Multiple streams require explicit disambiguation")
    if len(y) != game["frameNumber"] or not np.array_equal(g["Frame index"], np.arange(len(y))):
        raise ValueError("Native frame count/index mismatch")
    x = d[FT].to_numpy(float)
    a, correlation = match(x, y)
    # ponytail: frame-for-frame matching requires a complete trace; dropped ETW events fail closed.
    checks = []
    size = min(1000, len(y) // 3)
    for offset in (0, len(y) // 2 - size // 2, len(y) - size):
        pos, score = match(x, y[offset:offset + size])
        checks.append(dict(native_offset=offset, presentmon_row=pos, correlation=score))
        if pos - offset != a:
            raise ValueError(f"Independent block alignment disagrees: {checks}")
    w = d.iloc[a:a + len(y)].copy().reset_index(drop=True)
    w["TimeInSeconds"] -= w.TimeInSeconds.iloc[0]
    ft = w[FT].to_numpy(float)
    dur = float(w.TimeInSeconds.iloc[-1])
    fps = len(w) / dur
    delta = 100 * (fps / game["averageFps"] - 1)
    # Existing Cyberpunk FPS cross-check tolerance; not a performance acceptance threshold.
    if abs(delta) > 1 or abs(dur - game["time"]) > 6:
        raise ValueError("Existing duration/FPS cross-check failed")
    sp, severe, med, excess = spikes(w)
    full = dict(frames=len(w), duration_s=dur, avg_fps=fps,
                ft_avg_ms=float(ft.mean()), ft_median_ms=float(np.median(ft)),
                ft_p95_ms=float(np.percentile(ft, 95)), ft_p99_ms=float(np.percentile(ft, 99)),
                fps_1pct_low_time=float(low_time(ft, .01)), fps_01pct_low_time=float(low_time(ft, .001)),
                fps_1pct_low_p99=float(low_pct(ft, .01)), fps_01pct_low_p999=float(low_pct(ft, .001)),
                spikes=int(sp.sum()), spikes_per_min=float(sp.sum() * 60 / dur),
                severe_spikes=int(severe.sum()), spike_time_lost_ms=float(excess[sp].sum()))
    standard, *_ = summarize(StringIO(w.to_csv(index=False)), "Cyberpunk native-matched", run.name)
    standard["file"] = "native_analysis/matched_frames.csv"
    signals = {c: dict(mean_ms=float(w[c].mean()), median_ms=float(w[c].median()),
                      populated=int(w[c].notna().sum()))
               for c in ("MsGPUBusy", "MsCPUBusy", "MsGPUWait", "MsCPUWait") if c in w}
    result = dict(run=str(run), native_source=str(native), game=game,
                  alignment=dict(first_row=a, last_row=a+len(y)-1, correlation=correlation,
                                 block_checks=checks, game_fps_delta_pct=delta,
                                 game_duration_delta_s=dur-game["time"]),
                  full_benchmark=full, standard_trimmed_window=standard, signals=signals,
                  window_policy="Full native-matched benchmark reported separately from existing pmparse 2s/head and partial-second/tail trim.",
                  limitations="No causal bottleneck claim from CPU/GPU busy timing alone. No run-to-run variance from one run.")
    dest.mkdir()
    hashes = {}
    for source in (run / "presentmon.csv", run / "metadata.json", native / "summary.json", native / "frames.csv", Path(__file__), Path(__file__).with_name("pmparse.py")):
        hashes[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
    for name in ("summary.json", "frames.csv"):
        shutil.copy2(native / name, dest / name)
    w.to_csv(dest / "matched_frames.csv", index=False)
    result["source_sha256"] = hashes
    (dest / "analysis.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(dict(full_benchmark=full, alignment=result["alignment"], signals=signals), indent=2))


def selfcheck():
    rng = np.random.default_rng(2077)
    x = rng.uniform(5, 15, 1000)
    assert match(x, x[173:773])[0] == 173
    assert match(x, x[173:773] + rng.normal(0, .01, 600))[0] == 173
    try:
        match(np.ones(100), np.ones(10))
    except ValueError:
        pass
    else:
        raise AssertionError("Constant trace must fail closed")
    print("native alignment selfcheck OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", type=Path)
    ap.add_argument("native", nargs="?", type=Path)
    args = ap.parse_args()
    if args.run and args.native:
        analyze(args.run, args.native)
    else:
        selfcheck()
