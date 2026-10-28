# Cyberpunk manual_r1 — passive capture analysis

Capture: 23404 raw rows, PresentMon exit 0. Native result: benchmark_2026-09-07_17-46-23. Settings hash unchanged: True.

Matched all 7261 native frames to PresentMon rows 4688–11948 (zero-based), with identical offset from three independent 1000-frame blocks. Full-trace correlation 0.891991. FPS cross-check difference +0.014912%; duration difference -0.009579 s. Menu/loading/result rows excluded; no hitch-based cuts within benchmark.

| Metric | Full matched benchmark | Existing standard trim |
|---|---:|---:|
| avg_fps | 113.0262 | 113.1597 |
| ft_avg_ms | 8.8489 | 8.8384 |
| ft_median_ms | 8.8178 | 8.7923 |
| ft_p95_ms | 10.7516 | 10.7615 |
| ft_p99_ms | 11.7872 | 11.8624 |
| fps_1pct_low_time | 78.6011 | 78.4371 |
| fps_01pct_low_time | 68.6861 | 68.6861 |
| spikes | 0.0000 | 0.0000 |
| spikes_per_min | 0.0000 | 0.0000 |
| severe_spikes | 0.0000 | 0.0000 |

Full window: 64.241756 s. Standard pmparse window: relative 2 s to floor(end), 7015 frames, 61.992 s. These windows are reported separately, never pooled. Both use existing project FPS/low/stutter definitions.

GPU busy mean 8.7241 ms / mean frametime 8.8489 ms (98.59%): consistent with substantial GPU work, not proof of shader-side optimization headroom. CPU busy also includes pacing; no CPU/GPU bottleneck decision from comparing those columns. No GPU clocks/temperature/power telemetry in this capture.

Only one completed manual run so far: no run-to-run variance, significance or gain claim. Earlier Computer Use run had a different observed performance level and is not silently pooled with manual runs.

Raw files retained. Native summary/frames copied and SHA-256 provenance stored in native_analysis/analysis.json. Reusable parser: tools/c2077_native.py; synthetic known-offset/noisy-offset/constant-trace selfcheck PASS.

Next: manual_r2 with identical settings and capture workflow.
