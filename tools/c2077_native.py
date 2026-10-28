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


def match(x, y, guard=50):
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
    rival = np.r_[r[:max(0, a - guard)], r[a + guard + 1:]]
    rival = rival[np.isfinite(rival)]
    margin = float(r[a] - rival.max()) if rival.size else None
    return a, float(r[a]), margin


def alignment(x, y, max_block_lag=0):
    if max_block_lag not in (0, 1) or len(y) < 6:
        raise ValueError("Need at least six frames and a block-lag allowance of 0 or 1")
    a, correlation, margin = match(x, y)
    # Diagnostic threshold, not a performance gate or a statistical confidence level.
    if margin is not None and margin < 0.05:
        raise ValueError(f"Ambiguous global alignment peak: margin={margin}")
    checks = []
    # Three full thirds, including the remainder: no fixed-frame short windows or gaps.
    for start, end in zip(np.linspace(0, len(y), 4, dtype=int)[:-1],
                          np.linspace(0, len(y), 4, dtype=int)[1:]):
        pos, score, block_margin = match(x, y[start:end])
        checks.append(dict(native_offset=int(start), frames=int(end-start),
                           presentmon_row=pos, lag_frames=int(pos-start-a),
                           correlation=score, peak_margin=block_margin))
    if any(abs(c["lag_frames"]) > max_block_lag or
           (c["peak_margin"] is not None and c["peak_margin"] < 0.05) for c in checks):
        raise ValueError(f"Independent block alignment disagrees or is ambiguous: {checks}")
    return dict(first_row=a, last_row=a+len(y)-1, correlation=correlation,
                peak_margin=margin, block_checks=checks, max_block_lag=max_block_lag,
                exact_block_agreement=all(c["lag_frames"] == 0 for c in checks),
                row_index_basis="zero-based data rows, CSV header excluded")


def qpc_check(d, metadata, a, y):
    """Check continuity at the matched position, NOT locate by non-unique total duration."""
    if "CPUStartQPCTime" not in d or "--qpc_time_ms" not in metadata.get("command", []):
        return None
    q = pd.to_numeric(d.CPUStartQPCTime, errors="coerce").to_numpy(float)
    ft = d[FT].to_numpy(float)
    if not np.isfinite(q).all() or not np.all(np.diff(q) > 0):
        raise ValueError("Nonfinite or nonmonotonic QPC timestamps")
    # Console v2 FrameTime belongs to the interval STARTING at this row's CPUStartQPCTime.
    error = float(np.max(np.abs(np.diff(q) - ft[:-1])))
    if error > 0.001:  # 1 us, above rounding of the four-decimal millisecond CSV fields
        raise ValueError(f"QPC/FrameTime discontinuity: {error} ms; possible missing CSV rows")
    n = len(y)
    elapsed = q[a:a+n] - q[a]
    native_elapsed = np.r_[0, np.cumsum(y[:-1])]
    return dict(first_ms=float(q[a]), last_ms=float(q[a+n-1]),
                end_ms=float(q[a+n-1]+ft[a+n-1]),
                interval_max_error_ms=error,
                native_span_delta_ms=float(elapsed[-1]-native_elapsed[-1]),
                native_elapsed_max_error_ms=float(np.max(np.abs(elapsed-native_elapsed))),
                duration_s=float((q[a+n-1]-q[a]+ft[a+n-1])/1000),
                policy="Continuity check only; cannot exclude upstream ETW loss or establish frame identity.")


def analyze(run, native, out_name="native_analysis", max_block_lag=0):
    if not out_name or Path(out_name).name != out_name or out_name in (".", ".."):
        raise ValueError("Output name must be one directory name inside the run")
    dest = run / out_name
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
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(x <= 0) or np.any(y <= 0):
        raise ValueError("Frame intervals must be finite and positive")
    aligned = alignment(x, y, max_block_lag)
    a = aligned["first_row"]
    qpc = qpc_check(d, metadata, a, y)
    if max_block_lag and qpc is None:
        raise ValueError("One-frame uncertainty requires verified millisecond QPC continuity")
    w = d.iloc[a:a + len(y)].copy().reset_index(drop=True)
    w["TimeInSeconds"] -= w.TimeInSeconds.iloc[0]
    ft = w[FT].to_numpy(float)
    # N FrameTime values cover N intervals; last-first timestamps cover only N-1.
    dur = float(ft.sum()) / 1000.0
    fps = len(w) / dur
    delta = 100 * (fps / game["averageFps"] - 1)
    if abs(delta) > 0.05 or abs(dur - game["time"]) > 0.5:
        raise ValueError(f"Duration/FPS cross-check failed: delta {delta:.4f}%, dur {dur:.4f}s")
    aligned.update(game_fps_delta_pct=delta, game_duration_delta_s=dur-game["time"],
                   duration_basis="sum of the window's N frame intervals", qpc=qpc)
    # ponytail: bounded +/-1-frame window uncertainty, not frame identity; use event-level
    # traces if causal per-frame attribution is needed. Never silently splice, shift or drop rows.
    sensitivity = []
    for pos in range(a-max_block_lag, a+max_block_lag+1):
        if pos < 0 or pos+len(y) > len(d):
            raise ValueError("Capture does not cover the alignment uncertainty bounds")
        candidate = d.iloc[pos:pos+len(y)]
        sensitivity.append(dict(first_row=pos, avg_fps=1000/candidate[FT].mean(),
                                **{c: float(candidate[c].mean()) for c in
                                   (FT, "MsGPUBusy", "MsCPUBusy", "MsGPUWait", "MsCPUWait")
                                   if c in candidate}))
    aligned["boundary_sensitivity"] = sensitivity
    sp, severe, med, excess = spikes(w)
    full = dict(frames=len(w), duration_s=dur, avg_fps=fps,
                ft_avg_ms=float(ft.mean()), ft_median_ms=float(np.median(ft)),
                ft_p95_ms=float(np.percentile(ft, 95)), ft_p99_ms=float(np.percentile(ft, 99)),
                fps_1pct_low_time=float(low_time(ft, .01)), fps_01pct_low_time=float(low_time(ft, .001)),
                fps_1pct_low_p99=float(low_pct(ft, .01)), fps_01pct_low_p999=float(low_pct(ft, .001)),
                spikes=int(sp.sum()), spikes_per_min=float(sp.sum() * 60 / dur),
                severe_spikes=int(severe.sum()), spike_time_lost_ms=float(excess[sp].sum()))
    standard, *_ = summarize(StringIO(w.to_csv(index=False)), "Cyberpunk native-matched", run.name)
    standard["file"] = f"{out_name}/matched_frames.csv"
    signals = {c: dict(mean_ms=float(w[c].mean()), median_ms=float(w[c].median()),
                      populated=int(w[c].notna().sum()))
               for c in ("MsGPUBusy", "MsCPUBusy", "MsGPUWait", "MsCPUWait") if c in w}
    result = dict(run=str(run), native_source=str(native), game=game,
                  alignment=aligned,
                  full_benchmark=full, standard_trimmed_window=standard, signals=signals,
                  window_policy="Full native-matched benchmark reported separately from existing pmparse 2s/head and partial-second/tail trim.",
                  limitations="No causal bottleneck claim from CPU/GPU busy timing alone. No run-to-run variance from one run. Block-lag allowance, when enabled, is explicit window uncertainty, not proof of exact frame identity or zero ETW loss.")
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
    return result


def selfcheck():
    rng = np.random.default_rng(2077)
    x = rng.uniform(5, 15, 1000)
    assert match(x, x[173:773])[0] == 173
    assert match(x, x[173:773] + rng.normal(0, .01, 600))[0] == 173
    assert match(x, x[173:773])[2] > 0.1
    assert alignment(x, x[173:773])["exact_block_agreement"]
    # A timing phase change is explicit uncertainty, never silently accepted as exact.
    shifted = np.r_[x[172:372], x[373:773]]
    assert not alignment(x, shifted, 1)["exact_block_agreement"]
    q = 1000 + np.r_[0, np.cumsum(x[:-1])]
    d = pd.DataFrame({FT: x, "CPUStartQPCTime": q})
    metadata = {"command": ["--qpc_time_ms"]}
    checked = qpc_check(d, metadata, 173, x[173:773])
    assert checked["interval_max_error_ms"] < 1e-8
    assert abs(checked["duration_s"] - x[173:773].sum()/1000) < 1e-10
    assert checked["native_elapsed_max_error_ms"] < 1e-8
    for operation in (
        lambda: match(np.ones(100), np.ones(10)),
        lambda: match(x[:10], x[:20]),
        lambda: match(x, np.array([1., np.nan])),
        lambda: alignment(np.tile(x, 2), x[173:773]),
        lambda: alignment(x, shifted),
        lambda: alignment(x, np.r_[x[170:370], x[373:773]], 1),
        lambda: qpc_check(d.drop(index=400), metadata, 173, x[173:773]),
    ):
        try:
            operation()
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid/ambiguous trace must fail closed")
    print("native alignment/duration/QPC selfcheck OK")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", type=Path)
    ap.add_argument("native", nargs="?", type=Path)
    ap.add_argument("--out-name", default="native_analysis")
    ap.add_argument("--max-block-lag", type=int, choices=(0, 1), default=0,
                    help="Explicit one-frame window uncertainty; strict agreement by default")
    args = ap.parse_args()
    if bool(args.run) != bool(args.native):
        ap.error("run and native must be supplied together")
    if args.run and args.native:
        analyze(args.run, args.native, args.out_name, args.max_block_lag)
    else:
        selfcheck()
