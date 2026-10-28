"""Phase 1E analysis: per-run metrics, run-to-run variance, spikes, correlations, charts."""
import glob, os, sys, json
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, "tools")
from pmparse import summarize, spikes, SIGNALS, FT

OUT = "research/04_benchmarks/analysis"
CH = os.path.join(OUT, "charts")
os.makedirs(CH, exist_ok=True)

WORKLOADS = {
    "fortnite": sorted(f for f in glob.glob("research/fortnite_DX12_PerformanceMode/*.csv")
                       if not f.endswith("-stats.csv")),
    "steelnomad": sorted(f for f in glob.glob("research/3DMark_SteelNomad_DX12/*/*.csv")
                         if not f.endswith("-stats.csv")),
}

summaries, outliers, corrs, windows = {}, [], [], {}

for wl, files in WORKLOADS.items():
    rows = []
    for i, f in enumerate(files, 1):
        rid = f"{wl}_r{i}"
        r, w, sp, sev, med, exc = summarize(f, wl, rid)
        rows.append(r)
        windows[rid] = w

        idx = np.where(sp)[0]
        for j in idx:
            rec = dict(run_id=rid, workload=wl, frame_index=int(j),
                       t_s=round(float(w.TimeInSeconds.iloc[j]), 4),
                       ft_ms=round(float(w[FT].iloc[j]), 4),
                       local_median_ms=round(float(med[j]), 4),
                       ratio=round(float(w[FT].iloc[j] / med[j]), 3),
                       excess_ms=round(float(exc[j]), 4),
                       severe=bool(sev[j]))
            for c in ["MsCPUBusy", "MsCPUWait", "MsGPUTime", "MsGPUBusy", "MsGPUWait",
                      "MsInPresentAPI", "GPUUtilization", "GPUFrequency", "GPUPower",
                      "GPUTemperature", "GPUMemorySizeUsed", "CPUUtilization", "CPUFrequency"]:
                s = pd.to_numeric(w[c], errors="coerce")
                rec[c] = round(float(s.iloc[j]), 4) if pd.notna(s.iloc[j]) else np.nan
                loc = s.iloc[max(0, j - 10):j + 11].median()
                rec[c + "_local_med"] = round(float(loc), 4) if pd.notna(loc) else np.nan
            outliers.append(rec)

        ft = w[FT]
        for c in SIGNALS:
            s = pd.to_numeric(w[c], errors="coerce")
            if s.notna().sum() < 100 or s.nunique() < 3:
                continue
            m = s.notna()
            rho, p = stats.spearmanr(ft[m], s[m])
            pear = ft[m].corr(s[m])
            spm = sp[m.to_numpy()]
            if spm.sum() >= 3 and (~spm).sum() >= 3:
                u, pu = stats.mannwhitneyu(s[m][spm], s[m][~spm], alternative="two-sided")
                d_med = float(s[m][spm].median() - s[m][~spm].median())
            else:
                pu, d_med = np.nan, np.nan
            corrs.append(dict(run_id=rid, workload=wl, signal=c,
                              spearman_rho=round(float(rho), 4), spearman_p=float(p),
                              pearson_r=round(float(pear), 4),
                              spike_median_delta=round(d_med, 4) if pd.notna(d_med) else np.nan,
                              spike_mwu_p=float(pu) if pd.notna(pu) else np.nan,
                              n=int(m.sum()), n_spikes=int(spm.sum())))
    summaries[wl] = pd.DataFrame(rows)

for wl, df in summaries.items():
    df.to_csv(os.path.join(OUT, wl + "_runs.csv"), index=False)
pd.DataFrame(outliers).to_csv(os.path.join(OUT, "frametime_outliers.csv"), index=False)
cdf = pd.DataFrame(corrs)
cdf.to_csv(os.path.join(OUT, "correlations.csv"), index=False)

VAR_METRICS = ["avg_fps", "median_fps", "fps_1pct_low_time", "fps_01pct_low_time",
               "fps_1pct_low_p99", "ft_avg_ms", "ft_median_ms", "ft_p95_ms", "ft_p99_ms",
               "ft_max_ms", "spikes", "GPUPower_mean", "GPUFrequency_mean",
               "GPUUtilization_mean", "GPUTemperature_max", "GPUMemorySizeUsed_max",
               "MsCPUBusy_mean", "MsGPUBusy_mean", "MsGPUWait_mean", "MsCPUWait_mean"]
var_rows = []
for wl, df in summaries.items():
    for m in VAR_METRICS:
        if m not in df:
            continue
        v = df[m].astype(float)
        mean, sd = v.mean(), v.std(ddof=1)
        mad = np.median(np.abs(v - v.median()))
        mz = 0.6745 * (v - v.median()) / mad if mad > 0 else v * 0
        var_rows.append(dict(workload=wl, metric=m, n=len(v), mean=mean, std=sd,
                             cv_pct=100 * sd / mean if mean else np.nan,
                             min=v.min(), max=v.max(),
                             range_pct=100 * (v.max() - v.min()) / mean if mean else np.nan,
                             ci95_halfwidth_pct=100 * 1.96 * sd / np.sqrt(len(v)) / mean if mean else np.nan,
                             outlier_runs="|".join(df.run_id[np.abs(mz) > 3.5]) if mad > 0 else ""))
vdf = pd.DataFrame(var_rows)
vdf.to_csv(os.path.join(OUT, "run_to_run_variance.csv"), index=False)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(CH, name), dpi=110)
    plt.close(fig)


for wl in WORKLOADS:
    ids = [r for r in windows if r.startswith(wl)]

    fig, ax = plt.subplots(figsize=(13, 5))
    for rid in ids:
        w = windows[rid]
        ax.plot(w.TimeInSeconds, w[FT], lw=0.4, alpha=0.65, label=rid)
    ax.set_yscale("log"); ax.set_xlabel("t (s)"); ax.set_ylabel("frametime (ms, log)")
    ax.set_title(wl + " - frametime over time (valid window)"); ax.legend(fontsize=7, ncol=4)
    save(fig, wl + "_frametime_over_time.png")

    fig, ax = plt.subplots(figsize=(11, 5))
    allft = np.concatenate([windows[r][FT].to_numpy() for r in ids])
    hi = np.percentile(allft, 99.9)
    for rid in ids:
        ax.hist(windows[rid][FT], bins=200, range=(allft.min(), hi), histtype="step", lw=1, label=rid)
    ax.set_xlabel("frametime (ms)"); ax.set_ylabel("frames")
    ax.set_title(wl + " - frametime distribution (up to 99.9th pct)"); ax.legend(fontsize=7, ncol=4)
    save(fig, wl + "_frametime_distribution.png")

    fig, ax = plt.subplots(figsize=(11, 5))
    q = np.concatenate([np.linspace(0, 99, 200), np.linspace(99, 100, 100)])
    for rid in ids:
        ax.plot(q, np.percentile(windows[rid][FT], q), lw=1.2, label=rid)
    ax.set_yscale("log"); ax.set_xlabel("percentile"); ax.set_ylabel("frametime (ms, log)")
    ax.set_title(wl + " - frametime percentile curve"); ax.legend(fontsize=7, ncol=4)
    save(fig, wl + "_percentile_curve.png")

    df = summaries[wl]
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(df))
    ax.bar(x - 0.25, df.avg_fps, 0.25, label="avg FPS")
    ax.bar(x, df.fps_1pct_low_time, 0.25, label="1% low (time-int)")
    ax.bar(x + 0.25, df.fps_01pct_low_time, 0.25, label="0.1% low (time-int)")
    ax.set_xticks(x); ax.set_xticklabels(df.run_id, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("FPS"); ax.set_title(wl + " - FPS per run"); ax.legend()
    ax.axhline(df.avg_fps.mean(), color="k", ls="--", lw=0.8)
    save(fig, wl + "_fps_per_run.png")

    for sig, fname in [("MsGPUBusy", "gpubusy"), ("MsCPUBusy", "cpubusy"),
                       ("GPUFrequency", "gpuclock"), ("GPUPower", "gpupower")]:
        fig, ax = plt.subplots(figsize=(9, 5))
        for rid in ids:
            w = windows[rid]
            s = pd.to_numeric(w[sig], errors="coerce")
            k = max(1, len(w) // 4000)
            ax.scatter(s[::k], w[FT][::k], s=2, alpha=0.25, label=rid)
        ax.set_yscale("log"); ax.set_xlabel(sig); ax.set_ylabel("frametime (ms, log)")
        ax.set_title(wl + " - " + sig + " vs frametime"); ax.legend(fontsize=7, ncol=4, markerscale=4)
        save(fig, wl + "_" + fname + "_vs_frametime.png")

    fig, ax = plt.subplots(figsize=(13, 5))
    for rid in ids:
        w = windows[rid]
        b = (w.TimeInSeconds // 1).astype(int)
        g = w.groupby(b).size()
        ax.plot(g.index, g.values, lw=1, label=rid)
    ax.set_xlabel("t (s)"); ax.set_ylabel("frames in 1s bin (= FPS)")
    ax.set_title(wl + " - per-second FPS, run alignment"); ax.legend(fontsize=7, ncol=4)
    save(fig, wl + "_fps_timeline.png")

print("=== per-run headline ===")
pd.set_option("display.width", 250)
for wl, d in summaries.items():
    print("\n--- " + wl + " ---")
    print(d[["run_id", "duration_valid_s", "frames_valid", "avg_fps", "median_fps",
             "fps_1pct_low_time", "fps_01pct_low_time", "ft_avg_ms", "ft_p99_ms", "ft_max_ms",
             "spikes", "severe_spikes", "dropped_frames"]].round(3).to_string(index=False))
print("\n=== variance ===")
print(vdf.round(4).to_string(index=False))
