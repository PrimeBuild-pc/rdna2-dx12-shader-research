# Cyberpunk manual_r3 — passive capture analysis

Capture: 22623 raw rows, exit 0. Capture timestamps: 2026-09-07T18:00:05.612715+02:00 to 2026-09-07T18:02:42.232779+02:00. Native result 18:00:11. Settings SHA-256 unchanged: True; native configuration changes vs manual_r1: {}.

All 7253 native frames matched to one PresentMon stream, zero-based rows 3136–10388. Independent head/middle/tail offsets agree. Full correlation 0.888000; FPS cross-check +0.013140%; duration difference -0.008443 s. No hitch-based trimming inside the benchmark.

| Metric | Full matched benchmark | Existing standard trim |
|---|---:|---:|
| avg_fps | 112.9032 | 113.0571 |
| ft_avg_ms | 8.8585 | 8.8464 |
| ft_median_ms | 8.8238 | 8.7992 |
| ft_p95_ms | 10.9074 | 10.9179 |
| ft_p99_ms | 11.9831 | 11.9896 |
| fps_1pct_low_time | 78.0303 | 77.8931 |
| fps_01pct_low_time | 71.8868 | 71.8868 |
| spikes | 0.0000 | 0.0000 |
| spikes_per_min | 0.0000 | 0.0000 |
| severe_spikes | 0.0000 | 0.0000 |

Full window 64.240893 s. Existing pmparse standard trim: 7009 frames / 61.9952 s. Window metrics kept separate.

Three manual runs: mean FPS 112.969588, sample SD 0.062094, provisional CV 0.054965%. Run 3 vs run 1: -0.108836%. Zero defined stutters in all three. These are interim descriptive results, not a completed baseline or evidence of an optimization gain.

GPU busy mean 8.7232 ms. Similar CPU busy timing includes pacing and does not independently establish CPU limitation. No GPU clocks/temperature/power telemetry in these console captures. Prior Computer Use result remains separate.

Raw and native evidence hashes retained in native_analysis/analysis.json. Next manual_r4.
