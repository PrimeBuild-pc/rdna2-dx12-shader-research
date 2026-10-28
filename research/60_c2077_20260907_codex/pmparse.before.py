"""PresentMon 2.5.1 capture parser -- Phase 1E baseline harness.

Reads raw PresentMon CSVs (never modifies them), trims a documented valid
window, and emits per-run metrics, frametime spikes and per-run correlations.

Metric definitions are in research/04_benchmarks/analysis/METHOD.md
"""
import numpy as np, pandas as pd

FT = "MsBetweenPresents"          # primary frametime signal (application present pacing)
FT_DISP = "MsBetweenDisplayChange"  # displayed-frame pacing (what the panel actually showed)

WARMUP_S = 2.0        # frames before this are capture/engine warm-up -> excluded
SPIKE_WIN = 21        # centered rolling-median window, frames
SPIKE_RATIO = 2.0     # ft > RATIO * local median
SPIKE_ABS_MS = 2.0    # ...and at least this many ms above local median
SEVERE_RATIO = 3.0
SEVERE_ABS_MS = 8.0

SIGNALS = ["MsCPUBusy", "MsCPUWait", "MsGPUTime", "MsGPUBusy", "MsGPUWait",
           "MsGPULatency", "MsInPresentAPI", "MsRenderPresentLatency",
           "GPUUtilization", "GPUFrequency", "GPUPower", "GPUVoltage",
           "GPUTemperature", "GPUMemoryFrequency", "GPUMemorySizeUsed",
           "CPUUtilization", "CPUFrequency"]


# PresentMon console --v2_metrics names, mapped onto the names the 2.x application writes and
# that this parser and every existing baseline in the project use.
V2_ALIASES = {
    "FrameTime": "MsBetweenPresents",
    "DisplayedTime": "MsBetweenDisplayChange",
    "CPUBusy": "MsCPUBusy",
    "CPUWait": "MsCPUWait",
    "GPULatency": "MsGPULatency",
    "GPUTime": "MsGPUTime",
    "GPUBusy": "MsGPUBusy",
    "GPUWait": "MsGPUWait",
    "DisplayLatency": "MsUntilDisplayed",
    "AnimationError": "MsAnimationError",
    "InPresentAPI": "MsInPresentAPI",
    "RenderPresentLatency": "MsRenderPresentLatency",
    "AllInputToPhotonLatency": "MsAllInputToPhotonLatency",
    "ClickToPhotonLatency": "MsClickToPhotonLatency",
}


def load(path):
    d = pd.read_csv(path, low_memory=False)
    d.columns = [c.lstrip("\ufeff") for c in d.columns]
    rename = {k: v for k, v in V2_ALIASES.items() if k in d.columns and v not in d.columns}
    if rename:
        d = d.rename(columns=rename)
    if "TimeInSeconds" not in d.columns and "MsBetweenPresents" in d.columns:
        # The v2 console CSV has no elapsed-time column. Rebuilt from the frame times, which is
        # what TimeInSeconds is: the first frame's interval is not elapsed time, so it starts at
        # zero and accumulates from the second frame on.
        d["TimeInSeconds"] = d["MsBetweenPresents"].fillna(0).cumsum().sub(
            d["MsBetweenPresents"].fillna(0).iloc[0]) / 1000.0
    return d


def valid_window(d, warmup=WARMUP_S):
    """Drop warm-up head and the trailing incomplete second. Raw file untouched."""
    t_end = np.floor(d.TimeInSeconds.max())
    w = d[(d.TimeInSeconds >= warmup) & (d.TimeInSeconds < t_end)].reset_index(drop=True)
    return w, float(warmup), float(t_end)


def low_time(ft, frac):
    """'GN-style' low: mean FPS of the slowest frames that make up `frac` of total frame time."""
    s = np.sort(ft)[::-1]
    k = min(int(np.searchsorted(np.cumsum(s), s.sum() * frac)) + 1, len(s))
    return k / (s[:k].sum() / 1000.0)


def low_pct(ft, frac):
    """Percentile low: reciprocal of the (1-frac) frametime percentile."""
    return 1000.0 / np.percentile(ft, 100.0 * (1.0 - frac))


def spikes(w):
    ft = w[FT].to_numpy()
    med = pd.Series(ft).rolling(SPIKE_WIN, center=True, min_periods=1).median().to_numpy()
    excess = ft - med
    is_spike = (ft > SPIKE_RATIO * med) & (excess >= SPIKE_ABS_MS)
    is_severe = (ft > SEVERE_RATIO * med) & (ft >= SEVERE_ABS_MS)
    return is_spike, is_severe, med, excess


def summarize(path, label, run_id):
    d = load(path)
    w, t0, t1 = valid_window(d)
    ft = w[FT].to_numpy()
    dur = float(w.TimeInSeconds.max() - w.TimeInSeconds.min())
    n = len(w)
    sp, sev, med, exc = spikes(w)

    # dropped frames: no explicit Dropped column in this loadout; a frame that never
    # reached the display leaves MsBetweenDisplayChange NaN or 0.
    dc = w[FT_DISP]
    dropped = int(dc.isna().sum() + (dc == 0).sum())

    r = dict(
        run_id=run_id, workload=label, file=path,
        frames_raw=len(d), duration_raw_s=round(float(d.TimeInSeconds.max()), 4),
        window_start_s=t0, window_end_s=t1,
        frames_valid=n, duration_valid_s=round(dur, 4),
        avg_fps=n / dur,
        median_fps=1000.0 / np.median(ft),
        fps_1pct_low_time=low_time(ft, 0.01),
        fps_01pct_low_time=low_time(ft, 0.001),
        fps_1pct_low_p99=low_pct(ft, 0.01),
        fps_01pct_low_p999=low_pct(ft, 0.001),
        frames_in_01pct=max(1, int(round(n * 0.001))),
        ft_avg_ms=ft.mean(), ft_median_ms=np.median(ft),
        ft_p95_ms=np.percentile(ft, 95), ft_p99_ms=np.percentile(ft, 99),
        ft_p999_ms=np.percentile(ft, 99.9), ft_max_ms=ft.max(),
        ft_std_ms=ft.std(ddof=1),
        ft_disp_avg_ms=dc.mean(), ft_disp_p99_ms=dc.quantile(0.99),
        spikes=int(sp.sum()), spikes_per_min=sp.sum() / dur * 60,
        severe_spikes=int(sev.sum()),
        spike_time_lost_ms=float(exc[sp].sum()),
        dropped_frames=dropped,
        present_mode="|".join(f"{k}:{v}" for k, v in w.PresentMode.value_counts().items()),
        present_runtime=("|".join(w.PresentRuntime.unique())
                         if "PresentRuntime" in w.columns else ""),
        frame_type=("|".join(f"{k}:{v}" for k, v in w.FrameType.value_counts().items())
                    if "FrameType" in w.columns else ""),
        sync_interval=int(w.SyncInterval.iloc[0]), allows_tearing=int(w.AllowsTearing.iloc[0]),
    )
    for c in SIGNALS:
        # Which telemetry columns exist depends on the capture tool: the console CSV carries
        # fewer than the application's. A signal that is not in the file is simply not reported.
        if c not in w.columns:
            continue
        s = pd.to_numeric(w[c], errors="coerce")
        if s.notna().sum() == 0:
            continue
        r[f"{c}_mean"] = s.mean()
        r[f"{c}_median"] = s.median()
        r[f"{c}_p99"] = s.quantile(0.99)
        r[f"{c}_min"] = s.min()
        r[f"{c}_max"] = s.max()
    return r, w, sp, sev, med, exc


def _selfcheck():
    """Known distributions -> known answers."""
    # 950 frames @10ms + 50 @100ms: both low methods must land on the 100ms frames.
    ft = np.r_[np.full(950, 10.0), np.full(50, 100.0)]
    assert abs(low_time(ft, 0.01) - 10.0) < 0.01, low_time(ft, 0.01)
    assert abs(low_pct(ft, 0.01) - 10.0) < 0.01, low_pct(ft, 0.01)
    # 999 @10ms + one 1000ms hitch: the percentile method hides it, the
    # time-integrated method does not. This is why both are reported.
    ft2 = np.r_[np.full(999, 10.0), [1000.0]]
    assert abs(low_pct(ft2, 0.01) - 100.0) < 1.0, low_pct(ft2, 0.01)
    assert abs(low_time(ft2, 0.01) - 1.0) < 0.01, low_time(ft2, 0.01)

    # spike detector: 10 isolated 100ms hitches in a 1000-frame 10ms stream
    ftl = np.full(1010, 10.0); ftl[100::100][:10] = 100.0
    d = pd.DataFrame({"TimeInSeconds": np.r_[0, np.cumsum(ftl)[:-1]] / 1000.0, FT: ftl,
                      FT_DISP: ftl, "SyncInterval": 0, "AllowsTearing": 1,
                      "PresentMode": "x", "PresentRuntime": "DXGI", "FrameType": "Application"})
    sp, sev, med, exc = spikes(d)
    assert sp.sum() == 10 and sev.sum() == 10, (sp.sum(), sev.sum())
    assert 890 < exc[sp].sum() < 910, exc[sp].sum()
    # a sustained regime change (10 slow frames in a row at the tail) is NOT a spike
    ftr = np.r_[np.full(1000, 10.0), np.full(10, 100.0)]
    assert spikes(d.assign(**{FT: ftr}))[0].sum() == 0
    flat = np.full(500, 1.65)  # steady 600 FPS -> no spikes
    d2 = pd.DataFrame({"TimeInSeconds": np.cumsum(flat) / 1000.0, FT: flat, FT_DISP: flat,
                       "SyncInterval": 0, "AllowsTearing": 1, "PresentMode": "x",
                       "PresentRuntime": "DXGI", "FrameType": "Application"})
    assert spikes(d2)[0].sum() == 0
    n = flat.copy(); n[250] = 3.3   # 2x local median but only +1.65ms -> under the floor
    assert spikes(d2.assign(**{FT: n}))[0].sum() == 0
    n2 = flat.copy(); n2[250] = 12.0  # real hitch at 600 FPS -> caught
    assert spikes(d2.assign(**{FT: n2}))[0].sum() == 1

    # valid_window trims warm-up head and trailing partial second
    d3 = pd.DataFrame({"TimeInSeconds": np.arange(0, 10, 0.1), FT: 100.0, FT_DISP: 100.0})
    w, t0, t1 = valid_window(d3, warmup=2.0)
    assert w.TimeInSeconds.min() == 2.0 and w.TimeInSeconds.max() < 9.0, (t0, t1)
    print("pmparse selfcheck OK")


if __name__ == "__main__":
    _selfcheck()
