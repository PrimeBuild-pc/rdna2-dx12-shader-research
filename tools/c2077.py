"""Analysis for the Cyberpunk 2077 built-in benchmark, captured passively with PresentMon.

A capture contains menu idle, the benchmark, and the result screen. The benchmark segment is
found from the capture itself and then **checked against a number the game reports on its own**:
if the segmentation is right, the average FPS over the segment has to match the game's result
screen. That cross-check is the point - it turns "I picked a window" into something falsifiable.

    python -B tools/c2077.py segment 60_c2077/bench_r1 --expect-fps 113.26 --expect-frames 7277
    python -B tools/c2077.py report 60_c2077
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G
from pmparse import load, low_time, low_pct, SPIKE_WIN, SPIKE_RATIO, SPIKE_ABS_MS

ROOT = Path(__file__).resolve().parents[1]
FT = "MsBetweenPresents"


def find_segment(d, target_s, tol_s=6.0):
    """The benchmark run inside a capture that also contains menu and result screen.

    The scene loads before the benchmark and again when it ends, and a load shows up as a frame
    interval far outside anything the running benchmark produces. So: cut the capture at every
    such frame, and keep the piece whose duration is closest to the length the game reports.
    """
    ft = d[FT].to_numpy(dtype=float)
    t = np.cumsum(ft) / 1000.0
    # A cut is a frame longer than 200 ms; the benchmark's own worst frames are ~10 ms.
    cuts = [0] + [i + 1 for i in np.nonzero(ft > 200.0)[0].tolist()] + [len(ft)]
    best = None
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 100:
            continue
        dur = float(t[b - 1] - t[a])
        score = abs(dur - target_s)
        if best is None or score < best[0]:
            best = (score, a, b, dur)
    G.require(best is not None, "no candidate segment found")
    score, a, b, dur = best
    return a, b, dur, score <= tol_s, len(cuts) - 2


def metrics(ft):
    med = pd.Series(ft).rolling(SPIKE_WIN, center=True, min_periods=1).median().to_numpy()
    spike = (ft > SPIKE_RATIO * med) & (ft - med >= SPIKE_ABS_MS)
    dur = ft.sum() / 1000.0
    return dict(
        frames=int(len(ft)), duration_s=round(dur, 3),
        avg_fps=round(len(ft) / dur, 3), median_fps=round(1000.0 / np.median(ft), 3),
        ft_avg_ms=round(float(ft.mean()), 4), ft_median_ms=round(float(np.median(ft)), 4),
        ft_p95_ms=round(float(np.percentile(ft, 95)), 4),
        ft_p99_ms=round(float(np.percentile(ft, 99)), 4),
        ft_p999_ms=round(float(np.percentile(ft, 99.9)), 4),
        ft_max_ms=round(float(ft.max()), 4),
        fps_1pct_low_time=round(float(low_time(ft, 0.01)), 3),
        fps_01pct_low_time=round(float(low_time(ft, 0.001)), 3),
        fps_1pct_low_p99=round(float(low_pct(ft, 0.01)), 3),
        spikes=int(spike.sum()), spikes_per_min=round(float(spike.sum() / dur * 60), 3),
    )


def segment(rel, expect_fps, expect_frames, target_s):
    run = ROOT / "research" / rel
    d = load(run / "presentmon.csv")
    a, b, dur, ok, n_cuts = find_segment(d, target_s)
    w = d.iloc[a:b].reset_index(drop=True)
    ft = w[FT].to_numpy(dtype=float)
    m = metrics(ft)

    # The cross-check. The game's own result screen is an independent measurement of the same
    # run, so agreement is evidence the window is the benchmark and not something else.
    check = {}
    if expect_fps:
        check["game_avg_fps"] = expect_fps
        check["delta_pct"] = round((m["avg_fps"] - expect_fps) / expect_fps * 100, 3)
        check["agrees_within_1pct"] = abs(check["delta_pct"]) <= 1.0
    if expect_frames:
        check["game_frames"] = expect_frames
        check["frame_delta"] = m["frames"] - expect_frames
        check["frame_delta_pct"] = round((m["frames"] - expect_frames) / expect_frames * 100, 3)

    for c, key in (("MsGPUBusy", "gpu_busy"), ("MsCPUBusy", "cpu_busy"),
                   ("MsGPUTime", "gpu_time"), ("MsGPUWait", "gpu_wait"),
                   ("MsCPUWait", "cpu_wait")):
        if c in w.columns:
            s = pd.to_numeric(w[c], errors="coerce")
            if s.notna().sum():
                m[f"{key}_mean_ms"] = round(float(s.mean()), 4)
                m[f"{key}_p99_ms"] = round(float(s.quantile(0.99)), 4)

    if "gpu_busy_mean_ms" in m and "cpu_busy_mean_ms" in m:
        m["bound"] = ("GPU" if m["gpu_busy_mean_ms"] > m["cpu_busy_mean_ms"] else "CPU")
        m["gpu_busy_share_of_frame_pct"] = round(
            m["gpu_busy_mean_ms"] / m["ft_avg_ms"] * 100, 2)

    out = dict(run=rel, segment=dict(first_row=a, last_row=b - 1, duration_s=round(dur, 3),
                                     duration_matches_expected=ok, load_breaks_in_capture=n_cuts,
                                     capture_rows=int(len(d))),
               cross_check=check, metrics=m)
    G.save_json_over(run / "segment.json", out)
    print(json.dumps(out, indent=2))
    return out


def report(session):
    base = ROOT / "research" / session
    runs = sorted(p for p in base.glob("bench_r*/segment.json"))
    G.require(runs, f"no analysed runs in {session}")
    rows = [json.loads(p.read_text()) for p in runs]
    keys = ["avg_fps", "ft_median_ms", "ft_p95_ms", "ft_p99_ms", "fps_1pct_low_time",
            "fps_01pct_low_time", "spikes_per_min", "gpu_busy_mean_ms", "cpu_busy_mean_ms"]
    print(f"{'run':10s}" + "".join(f"{k:>20s}" for k in keys))
    for r in rows:
        print(f"{r['run'].split('/')[-1]:10s}"
              + "".join(f"{r['metrics'].get(k, float('nan')):>20.3f}" for k in keys))
    print()
    print(f"{'':10s}" + "".join(f"{k:>20s}" for k in keys))
    for name, fn in (("mean", statistics.mean), ("sd", lambda v: statistics.stdev(v) if len(v) > 1 else 0.0)):
        print(f"{name:10s}" + "".join(
            f"{fn([r['metrics'][k] for r in rows if k in r['metrics']]):>20.4f}" for k in keys))
    cv = {}
    for k in keys:
        v = [r["metrics"][k] for r in rows if k in r["metrics"]]
        if len(v) > 1 and statistics.mean(v):
            cv[k] = statistics.stdev(v) / statistics.mean(v) * 100
    print(f"{'CV %':10s}" + "".join(f"{cv.get(k, float('nan')):>20.3f}" for k in keys))
    G.save_json_over(base / "session_summary.json",
                     dict(session=session, runs=[r["run"] for r in rows],
                          cv_pct={k: round(v, 4) for k, v in cv.items()},
                          per_run={r["run"]: r["metrics"] for r in rows},
                          cross_checks={r["run"]: r["cross_check"] for r in rows}))
    print("\nwrote session_summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["segment", "report"])
    ap.add_argument("target")
    ap.add_argument("--expect-fps", type=float)
    ap.add_argument("--expect-frames", type=int)
    ap.add_argument("--target-seconds", type=float, default=64.25)
    a = ap.parse_args()
    if a.action == "segment":
        segment(a.target, a.expect_fps, a.expect_frames, a.target_seconds)
    else:
        report(a.target)
