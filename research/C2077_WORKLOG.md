# Cyberpunk 2077 worklog

## 2026-09-07 — baseline preparation
Latest authority: LAST PROMPT.md; 2U results supersede prior phases. PoC remains frozen.
Session: `60_c2077_20260907_codex`. Prior raw capture preserved separately.
All 12 user screenshots read visually and SHA-256 recorded in experiment_metadata.json.
Steel Nomad historical comparability gate FAIL (>0.5%); preserve threshold. Latest instruction requires continuing baseline: collect a separate contemporary session, with no historical causal comparison.
Five completed valid benchmark runs required before performance analysis. Capture 150 s each; GUI result confirms completion, FPS, duration and frame count. Raw menu/loading/result rows remain intact; segmentation checked against independent game results, no FPS-based trimming. Existing metric definitions retained.
No game settings changed. UserSettings copied and hashed read-only. Parser selfcheck PASS.
No performance candidate, headroom claim, injection or file replacement authorized by evidence yet.

## Preflight failure — no valid benchmark measured
`bench_r1` is excluded: menu capture only; keyboard activation initially failed, coordinate click toggled pending RT ON instead of Start. Apply was never confirmed. Settings SHA-256 still matches before (`f26e59eaf9dedd486c5417e2bdcb1c0de8840a3dbb0dbe69d454617b4aa36f01`). Auto-review rejected Return on RESET; no workaround attempted. Requested manual RT OFF.
Real raw header revealed a harness defect: console `--v1_metrics` has lowercase `msBetweenPresents` and no GPUBusy/CPUBusy; it is not the historical GUI v2 schema claimed in the comment. Fixed capture to explicit v2 (existing parser mapping), added only exact v1 pacing aliases to parser. `msGPUActive` is deliberately not relabelled GPUBusy. Original tool files preserved in this session. No statistical definitions changed.

RT OFF restored in GUI; settings hash equal before starting bench_r2. First completed benchmark recorded, result.png/game_result.json retained; CSV exit 0. No performance analysis yet.

## Resume — GUI prerequisite pending
User requested continuation. bench_r2 result and raw capture verified present, game PID 4524 responsive; UserSettings SHA-256 still equals original. No further benchmark or performance analysis yet.
Repeated Settings clicks did not change the result screen, including after foreground activation. Auto-review rejected a Left key due unverified focus; fresh observation retained and no blocked key retried. Asked only the indispensable manual Settings click. Capture for bench_r3 is not started until the menu is actually ready, to avoid another menu-only capture.

## Settings opened manually — input rejected by automatic review
User confirmed Settings open and explicitly requested the remaining four runs autonomously. Fresh Computer Use screenshots confirmed B RUN BENCHMARK, Custom/High, RT/PT/FG/upscaling OFF. bench_r3 capture started; automatic review rejected B, requested a fresh screen, then rejected B again after fresh screenshot because trusted screen evidence was considered unavailable. No workaround attempted. Asked for the indispensable manual benchmark start. bench_r3 ended after 150 s, exit 0, 27943 rows; GUI remained in Settings throughout observations, so it is excluded as menu-only. No second completed benchmark yet. Settings SHA-256 still matches original. Preparing a longer manual-start capture to avoid the short GUI-response deadline; menus will remain in raw CSV and be excluded only through audited segmentation.


## Manual PowerShell workflow requested
User discontinued Computer Use and authorized parsing/analysis after each run, superseding previous defer-all-analysis instruction. No PresentMon process active at handoff. bench_r4 completed exit 0 with 113257 rows; native benchmarkResults directory contains only the earlier 14:20 and 17:08 benchmarks, so no additional completed run is evidenced. Four new captures reserved as manual_r1..manual_r4 in this session. Harness now prints a start instruction before launching PresentMon; raw data/statistics unchanged. Native 17:08 result copied with hashes into bench_r2/native_result and matches screenshot. Preliminary stream check finds one PID/swapchain. Existing c2077.py duration-only selector would choose a ~60.5-second menu segment instead of the benchmark; do not use its unvalidated result. Exact segment validation remains pending. No speedup claim.


## manual_r1 validated and analyzed
PresentMon exit 0, 23404 raw rows; native 17:46:23 result 7261 frames / 64.251335 s / 113.009323 FPS. All native frame intervals aligned with one PresentMon stream, rows 4688–11948; head/middle/tail block offsets agree. Full PresentMon FPS 113.026176 (+0.014912% vs game). Full and historical-standard trimmed metrics separately recorded in manual_r1/native_analysis/analysis.json and manual_r1/analysis.md. Zero stutter events under existing definition. Settings hash unchanged. Added minimal native-trace alignment tool with fail-closed structural checks and passing selfcheck; old duration-only selector not used. One manual run cannot establish run variance or gains; prior GUI-controlled run not pooled. Next manual_r2.


## manual_r2 validated and analyzed
PresentMon exit 0, 22731 raw rows. All 7259 native frames matched to rows 3892–11150 with agreeing head/middle/tail offsets. Full benchmark 112.979426 FPS, p99 12.049448 ms, time-integrated lows 76.641555 / 67.613618 FPS, zero defined spikes. Native FPS agreement +0.012807%. Settings SHA-256 unchanged and native configuration equal manual_r1. FPS delta vs r1 -0.0414%; n=2 CV provisional, no significance/gain claim. Full and standard trimmed metrics stored separately in manual_r2/native_analysis/analysis.json. Next manual_r3.


## manual_r3 validated and analyzed
PresentMon exit 0, 22623 raw rows; all 7253 native frames matched to rows 3136–10388 with agreeing three-block offsets. FPS 112.903162; p99 11.983140 ms; time-integrated lows 78.030307 / 71.886798 FPS; zero defined spikes. Native FPS cross-check +0.013140%. Settings hash and native configuration unchanged. n=3 manual FPS CV 0.054965% (interim only). Full and standard-trimmed metrics separate in manual_r3/native_analysis/analysis.json; comparison_after_r3.json records descriptive variance. Next manual_r4; earlier Computer Use run not pooled.


## Consolidation after manual_r4
manual_r4 validated: 7255 frames, 112.931485 FPS, zero defined spikes; settings hash unchanged. bench_r2 also native-aligned successfully (6167 frames, 96.008442 FPS). Five complete captures exist, but only four are homogeneous manual repeats; manual mean 112.960062 FPS, CV 0.047947%. Initial slow GUI-controlled run retained separately, causal difference unresolved. Passive profiling suggests substantial GPU work but no demonstrated shader-side ceiling or justified modification. Local REDmod/cache/config surface inventoried read-only; no mod/injection/driver changes. C2077_FINAL_REPORT.md and consolidated_analysis.json written with explicit incomplete milestone status: fifth homogeneous manual run and Steel Nomad post remain missing. User authorized closing Cyberpunk; offline analysis complete, no silent relaunch.


## Steel Nomad post verified
Native .3dmark-result archives located and copied with SHA-256. Pre 4184 / 41.849308 FPS, post 4189 / 41.897465 FPS: score delta 0.119503%, FPS delta 0.115072%. SUCCESS, same DX12 test/version/settings except result filename. Pre/post endpoints consistent; historical >0.5% comparability failure unchanged. Raw PM 2684 rows includes initialization; 2509-row approximate steady section not treated as exact native 2513-frame equivalence. No full-raw FPS/stutter claim. Prior report/status preserved before update. No modified shader exists; no variant A/B required now. Remaining protocol acquisition: fifth homogeneous manual Cyberpunk run, with restart comparability caveat.
