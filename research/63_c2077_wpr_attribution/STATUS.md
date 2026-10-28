# WPR Cyberpunk attribution — offline analysis, current evidence limits

## Current update, 2026-10-16 — no new benchmark

Canonical report: [OFFLINE_ATTRIBUTION_20261016.md](OFFLINE_ATTRIBUTION_20261016.md). Portable entry point: [../../HANDOFF.md](../../HANDOFF.md).

Completed on the existing September capture:

- Raw-QPC/ETL alignment and 5304 contiguous DXGI presents validated. Native window [49.9097700, 114.1538552) s ETL; cross-session timestamps differ by 0.2–12.9 us, with no fitted offset.
- Exclusive CPU samples and loaded-image attribution; scheduler running for 34 target threads agrees with native xperf within 0.5 us. Actual wait/signal stacks show frequent WaitForSingleObjectEx / ReleaseSemaphore, not proof of removable work.
- Device/context/node ownership and classic DMA FIFO replay; target union 75.7717%, 2714 preempted segments, zero queue timeout. This is scheduler evidence, not shader duration/hardware occupancy.
- Queue schemas validated: 178 normal DMA, **244 scalar WAIT=4**, **245 array SIGNAL=5**. Initial wrong enum/pointer joins are quarantined, not results.
- Significant tracing/stack collection observed in exclusive CPU samples. Do not attribute the entire ~112→82.56 FPS difference to WPR, or transfer the profiled bottleneck to passive runs.
- Tests/crosschecks and source hashes PASS; ETL SHA-256 `e2e4ae42ccb8bb1e41d8717513abe1bb469d6e4969ef1b8e363f229a5b21e739`. Artifact map and exclusions: [offline_20261016/README.md](fs1440_r1/offline_20261016/README.md).

**Unresolved:** validated sampled CPU caller stacks and a complete causal critical path; fence observations are not automatically satisfaction chains. Shader/PSO provenance and ALU/texture/bandwidth attribution are absent. Exact sampled-stack filters are empty even on the historical smoke without PID filtering; broad `Profile` output is ambiguous and rejected for CPU cost/caller attribution.

**Decision:** no justified driver/game/shader change and no demonstrated optimization. No new capture requested or started. Further measures, if later authorized, must address these specific gaps and profiling perturbation instead of repeating the verbose profile blindly.

Everything below is historical state. In particular, the waiting-for-click state and capture command are **not current instructions**.

## Superseding update, 2026-09-26 — Codex takeover

Claude is unavailable per the user. Current portable entry point: [../../HANDOFF.md](../../HANDOFF.md).
The historical waiting-for-click state below was superseded by a capture later on September 8:
`fs1440_r1/c2077_fs1440_attribution-run1-20260908-222856-633.etl` (21,098,397,696 bytes),
with successful stop logged in `capture_r1.log`. Do not request another benchmark before analyzing it.

Verified offline on September 26:

- PresentMon exit 0, 18,405 data rows, historical target PID 16316, sampling preserved at 1 ms.
- Added byte-for-byte normalized copies `fs1440_r1/metadata.json` and `presentmon.csv` for the existing parser; originals preserved.
- Native result `benchmark_2026-09-08_22-29-31` matched strictly: 5304 frames, rows 7745–13048 (zero-based), all three blocks agree. Native files and source hashes saved in `fs1440_r1/native_analysis_v2/`.
- Full window 64.2440852 s, 82.56013 FPS; native 82.56697 FPS, delta −0.00829%; native 2560×1440, windowMode 2. QPC continuity PASS, window [32466592.8518, 32530836.9370) ms.
- `xperf -a tracestats` exit 0 and `etw_analyze.check_loss` PASS: zero lost buffers/events. Evidence `fs1440_r1/trace_validation.txt`.
- Harness pure test, native alignment selfcheck and ETW validation selfcheck all PASS.
- Matched-window PresentMode: Hardware: Independent Flip on all 5304 frames. Normalized copies are byte-identical to originals; all source hashes recorded by the parser verified.

Still pending: independent QPC/ETL clock alignment, actual CPU caller/wait stacks, GPU ownership/queue attribution, coverage and profiling perturbation assessment. The profiled run is substantially slower than passive runs; do not assume all of the difference is caused by WPR or transfer its bottleneck to passive runs. No causal attribution or shader optimization claim yet. The next capture command below is historical reference, not the next action. Current process/admin/session state has not been rechecked.

## Historical state before acquisition, 2026-09-08

- Cyberpunk launched normally (PID 16316 at preflight), executable `E:\GOG\Cyberpunk 2077\bin\x64\Cyberpunk2077.exe`. Launcher also open. Do not relaunch a second instance.
- Saved settings verified before launch: Fullscreen, 2560x1440, VSync off, FPS cap off, resolution scaling off. Snapshot `UserSettings.before.json`; SHA256 e996a4183f5cdde530f4fb463e2356e11a8fc26fb81723a867782ab518806fce. No agent edits to settings/game/driver/cache/registry.
- Admin access verified. WPR idle after smoke, original/current sampling interval 10000 x100ns = 1 ms. PresentMonService is unrelated and must not be stopped.
- Actual benchmark attribution NOT captured yet. User must reach the benchmark menu and confirm ready; then agent starts the timed capture and signals the manual benchmark click. No PowerShell command required from user.

## Harness changes completed

`tools/capture_etw.ps1`: console v2 + QPC milliseconds + terminate-on-process-exit; unique session and output names; no stop-existing-session; current sample interval preserved by default and explicit opt-in interval restored to the actual original value; one target instance; WPR existing-recording refusal; free-space check; process snapshot after target validation; PM timeouts/return codes retained/checked; metadata includes PID, command, clock interval and attribution-only purpose; WPR markers; own incomplete recording saved instead of canceled on error.

Persistent pure test: `pwsh -NoProfile -File tools/test_capture_etw.ps1` PASS.
Live preflight on DWM PASS. Live CPU+GPU smoke `smoke/c2077_v2_smoke-run1-20260908-221444-485.etl`: 8.3139337 s, 1,559,232,512 bytes, lost buffers/events 0/0; PM exit 0, 235 data rows. No WPR left active, sampling still 1 ms. Game was running during this smoke but this is NOT the requested benchmark window. Do not use it as gameplay attribution.

## Next capture — agent executes after user ready

Run from project root (not a user command):

```powershell
pwsh -NoProfile -File tools/capture_etw.ps1 -Process Cyberpunk2077.exe -Tag c2077_fs1440_attribution -Run 1 -Seconds 150 -PreRoll 20 -ValidateSeconds 3 -PreserveSamplingInterval -PresentMonSession c2077_fs1440_attribution_r1 -OutDir research/63_c2077_wpr_attribution/fs1440_r1
```

Start hidden/background with stdout/stderr redirected to a session log so the assistant can notify the user to start the benchmark after readiness. Poll until completion; do not leave a recording without follow-up. User keeps focus on the game during the benchmark. All settings stay unchanged; verify native summary render 2560x1440/windowMode 2 and PresentMode in the matched window. Capture purpose is attribution, never performance A/B against passive data.

## Offline route verified / limitations to address

- `xperf -i <etl> -a tracestats` and `tools/etw_analyze.check_loss` pass. Do this first on the real trace, no -tle/-tti bypasses.
- `xperf -a dumper` emits SampledProfile, full Stack rows (timestamp + TID + frame index + address + Image!Function), CSwitch and ReadyThread. CPU IP/module counts alone are insufficient: join stack rows to sample/switch events and inspect actual caller paths, or use native `xperf -a stack -butterfly -pid <pid> -event SampledProfile -range <lo_us> <hi_us>` (CLI help verified). Native xperf profile/cswitch actions also accept microsecond range filters. Public symbols may be loaded with a process-local symbol path and project-local cache; never invent private game/AMD function names.
- GPU Device DC_Start includes hProcessId/hDevice; Context DC_Start includes hDevice/hContext/NodeOrdinal. DmaPacket Start/Stop use hContext + submission/completion ID + queue sequence. QueuePacket Start/Info/Stop and CPU/GPU fence events are present. IMPORTANT: QueuePacket Start has MULTIPLE different header layouts (normal DMA, signal, wait); cannot key schemas by name alone. Validate layout or use native decoder. Event execution PID on completion/DPC is NOT context ownership; map device/context owner first. See `smoke/event_examples.txt` for exact headers and example records.
- Independent clock alignment is still to implement for the real benchmark. PresentMon offline `--etl_file` supports QPC and default relative CPUStartTime; two exports of the same ETL can establish the trace-time/QPC translation and validate against online PM. Avoid pmparse's legacy cumulative TimeInSeconds as the ETL clock. Native matching uses `tools/c2077_native.py` with exact blocks by default; if data do not pass, diagnose explicitly, do not silently select a favorable window.
- WPA exporter exists and runs. `cpu_stacks.wpaProfile` and `attribution.wpaProfile` derive from the installed AppLaunch profile, preserving Sessions and ModifiedGraphs. Initial stripped XML failed to load; preserving the native structure worked.
- `smoke/wpa_expanded` exports actual CPU Precise context-switch/ready stacks (181727 rows on OLD desktop smoke). Sampled export currently expands only to `[Root]` for many records: NOT yet a usable full sampled-call-tree export. Prefer xperf stack/dumper or fix stack expansion before attributing callers.
- Added GPU Graph GUIDs without Preset are ignored by WPA: NO GPU CSV was produced. Do not claim GPU export validation; raw DxgKrnl events are the verified route so far. Registered tables: GPU Utilization (FM) b859d131-dfb5-4605-be19-810b298b6975; GPU Work 59915b43-429b-4d83-9b37-a2b0c6565592.
- WPA warnings about missing user MyPresets and wpaexporter.deps.json occurred; stock export may return exit 0 even on table errors. Verify actual files/columns/data, not exit code alone.

## Required attribution report

Native-matched benchmark time range only; CPU exclusive sample cost by game/amdxc64/d3d runtime/dxgkrnl/kernel/other, inclusive caller stacks separately (no double counting); hot-thread running vs ready vs waiting, actual wait/signal paths; mapped GPU context/node submission-to-execution and execution spans, outstanding work vs starvation/preemption/synchronization. Distinguish GPU scheduler CPU work executed in System/DPC from game-attributed driver CPU work. Include event/stack coverage, symbol limitations, uncertainty and any missing providers. No game/shader changes until a causal hot path is identified; aggregate CPU utilization does not establish critical path.
