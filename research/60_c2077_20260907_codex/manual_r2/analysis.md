# Cyberpunk manual_r2 — passive capture analysis

Capture: 22731 raw rows, exit 0. Capture timestamps: 2026-09-07T17:52:56.369081+02:00 to 2026-09-07T17:55:33.026313+02:00. Native result 17:53:02. Settings hash unchanged: True; native configuration differences from manual_r1: {}.

All 7259 native frames matched to one PresentMon stream, zero-based rows 3892–11150. Independent head/middle/tail blocks have the same offset. Correlation 0.891455; FPS delta vs native +0.012807%; duration delta -0.008229 s. No hitch-based cuts within the benchmark.

| Metric | Full matched benchmark | Existing standard trim |
|---|---:|---:|
| avg_fps | 112.9794 | 113.1076 |
| ft_avg_ms | 8.8525 | 8.8425 |
| ft_median_ms | 8.8285 | 8.8074 |
| ft_p95_ms | 10.8139 | 10.8239 |
| ft_p99_ms | 12.0494 | 12.0716 |
| fps_1pct_low_time | 76.6416 | 76.4638 |
| fps_01pct_low_time | 67.6136 | 67.6136 |
| spikes | 0.0000 | 0.0000 |
| spikes_per_min | 0.0000 | 0.0000 |
| severe_spikes | 0.0000 | 0.0000 |

Full window 64.250636 s; historical-standard pmparse trim 7011 frames / 61.9852 s. Window metrics kept separate.

Versus manual_r1: FPS -0.0414%; 1% low -2.4931%; 0.1% low -1.5615%. Provisional n=2 FPS CV 0.0293%; insufficient runs for the planned baseline or a gain claim.

GPU busy mean 8.7196 ms, CPU busy mean 8.7187 ms. This does not independently classify the CPU/GPU bottleneck; neither clocks nor thermal/power telemetry are present. No settings or game file modifications.

Raw/native files and hashes retained in native_analysis. Next manual_r3.
