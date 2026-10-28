# Handoff — AMD RDNA2 / Cyberpunk 2077 research

> **English translation** of the original Italian handoff ([HANDOFF.it.md](HANDOFF.it.md)), last
> updated 2026-10-16. Where the two disagree, the Italian original and the phase reports win.
> Archived when the project was paused on 2026-10-28.

> **Note added at archive time (2026-10-28).** This handoff predates two final steps:
> - **Phase 68 did get its manual run** (PID 276, observe mode). The read-only back-buffer probe
>   found a full-screen pass writing straight to the real swap-chain back buffer: PSO serial 243,
>   pixel shader SHA-256 `1642c9e5…9d4c` (4995 bytes), 27,928 direct 3-vertex draws, blend/depth
>   off. That shader was matched to exactly one offset in the offline copy of
>   `staticshader_final.cache`. See
>   [phase 68 r1/candidate_mapping.json](research/68_c2077_backbuffer_catalog_20261016/r1/candidate_mapping.json).
> - **Phase 69 was preregistered but never built** —
>   [PREREGISTRATION.md](research/69_c2077_visible_canary_20261017/PREREGISTRATION.md). Its
>   `build/`, `offline/` and `payload/` folders are empty. That is where the work stopped.
>- The ReShade loader from phase 66 was **uninstalled from the game on 2026-10-28** with
>   `tools/c2077_shader_loader.py uninstall` (restore verified against its manifest). The original
>   workstation folder was then deleted. **Everything needed to rebuild the environment is in
>   [docs/REBUILD.md](docs/REBUILD.md) and [data/manifests/environment.json](data/manifests/environment.json).**
> - The game has since moved from 2.31 to **2.5** and the driver to 32.0.21045.16010: re-baseline
>   before comparing anything, and expect shader hashes (including `1642c9e5…`) to have changed.
>
> Raw binary artifacts (ETL, shader caches, extracted DXIL, build outputs) were **not published**.
> Their SHA-256 hashes are in [data/manifests/excluded_files.csv](data/manifests/excluded_files.csv).
> Large text data is in the GitHub Release archive; see [data/README.md](data/README.md).

**Updated: 2026-10-16, by Codex. Entry point for any agent or harness.**
This document summarises the state rebuilt from the files. It does not need access to the chat or
to Claude. The measurements date from 3–8 September; the WPR recovery from 26 September; the
offline analysis from 16 October. No new game captures.

## Immediate state and takeover

- Lorenzo said the Claude subscription had ended. **The work passed to Codex or the next
  available agent.** Do not start Claude, do not wait for it, and do not depend on the old Herdr
  panes.
- The sample PoC is finished and frozen. The five manual Cyberpunk runs and Steel Nomad runs are
  done. The fullscreen 1440p/1080p/720p/1440p scaling series is done too.
- **The Cyberpunk WPR capture already exists.** The old `STATUS.md` said to wait for the click,
  but it was written before the 22:28 capture on 8 September. On 26 September the ETL, metadata
  and native result were verified and benchmark alignment completed.
- **Offline WPR analysis done on 16 October, with no new benchmarks.** Clocks/window, CPU
  exclusive time, scheduler and GPU queues are now validated; current report:
  [OFFLINE_ATTRIBUTION_20261016.md](research/63_c2077_wpr_attribution/OFFLINE_ATTRIBUTION_20261016.md).
  Significant tracing perturbation observed; sampled CPU callers and the full critical path are
  not resolved. Do not carry the profiled run's regime over to the passive runs, and do not blame
  the whole drop on WPR.
- **Direction requested by Lorenzo: concrete, reversible shader experiments.** Real access in
  [phase 64](research/64_c2077_shader_access_20261016/STATUS.md); round trip and the `glass`
  canary validated in [phase 65](research/65_c2077_dxil_roundtrip_20261016/STATUS.md). The canary
  changes only four output operands; cache repacking only on research copies, never installed.
- **Loader/hooking authorisation received for Cyberpunk only;
  [phase 66](research/66_c2077_shader_loader_20261016/STATUS.md) installed, now in OBSERVE (no
  shader override).** Official ReShade 6.8.0 Full Add-on x64, SDK API 20; local add-on with a
  path/EXE-SHA guard and exact pixel bytecode match. It creates separate PSOs and redirects binds
  in memory, without replacing caches or original files. Five initial files added to `bin/x64`,
  plus the current observer; the phase-67 one is archived/removed. Restore on the real target
  verified: 84 original files, identical names and hashes; then the same package was reinstalled.
  **Control started manually, normal image confirmed by the user, game closed.** Last heartbeat
  PID 5396: 5 PSOs created, 1044 binds, zero clone errors;
  [control r1](research/66_c2077_shader_loader_20261016/runtime_control_r1/RESULT.md).
  **Canary r1 ended negative:** the user saw no pink surface, image unchanged. Last heartbeat
  PID 14612 then closed: 5 PSOs / 2033 binds, zero clone errors;
  [negative result](research/66_c2077_shader_loader_20261016/canary_r1/RESULT.md). Visual gate
  not passed, cause not established. Phase 67 finished: PID 11348 closed, zero target binds/draws
  observed even after a visual walk-around. Do not keep pushing the glass shader. Installed the
  [read-only phase 68 catalogue](research/68_c2077_backbuffer_catalog_20261016/STATUS.md),
  ShaderLab in observe, old probe archived/removed. Waiting for a manual start to identify the
  SHAs of shaders in draws to real back buffers, without changing shaders. A bind does not prove
  draws or visible fragments. Host WARNs about reference counts / add-ons still loaded at exit
  are kept; their cause and the exit code are not validated. No benchmark or speed-up.
- ReShade host is `NotSigned`; setup chain untrusted locally: limitation recorded, no
  certificates or protections changed. The driver currently reads **32.0.21045.11001**, unlike
  September's 32.0.21045.5002: do not reuse those baselines as a current performance comparison.

## Final goal and direction

Find a real, reproducible, correct optimisation of DX12 shader/pipeline work on the RX 6950 XT,
by understanding where the software wastes time. The folder name `driver mod` does not mean the
driver should be patched: the research moved from compiler levers to transformations of
application shaders, then to verification on a real game.

A positive result needs an identified expensive path, source → bytecode → executed-PSO
provenance, image correctness, and an A/B comparison against measured noise. A documented
negative result is valid; do not force an improvement by changing quality, thresholds or windows
after the fact.

The current direction, at Lorenzo's request after the WPR report, is concrete experiments on
application shaders: access to the real DXIL, round trip, verifiable reversible replacement, then
one transformation with an oracle/A-B. WPR remains a CPU/queue source already analysed, not a
prerequisite to reopen forever; on its own it does not identify optimisable shaders or the
ALU/texture/bandwidth limit.

## Operating rules and Lorenzo's preferences

- Keep going autonomously with reading, parsing, analysis, checks and authorised local work;
  stop only when a manual action is really needed. Do not stop at a report if useful work exists.
- Computer Use was dropped as unreliable. Lorenzo starts the game and benchmark by hand; the
  agent handles tools, capture and analysis. Parsing after each run is authorised and overrides
  the old instruction to wait for five runs.
- The benchmark lasts about **71 s as perceived by the operator**; the measured native sequence
  is about **64.24 s**. Captures include margin for menus/loading: do not trim data to 71 s
  arbitrarily.
- Do not modify installed drivers/signed packages, Registry, boot/security, Adrenalin settings or
  caches. No invasive interaction with Fortnite/Warzone/anti-cheat. Keep raw data, exclusions,
  backups and negative results.
- Any reversible intervention on the single-player game first needs a motivated candidate,
  provenance, backup/hash/manifest, verifiable restore and oracle/A-B. Autonomy is not an
  invitation to injection or speculative patches. Current authorised exception: the phase-66 DX12
  loader and add-on in Cyberpunk only, new files only, never anti-cheat. Mode changes/removal
  with the game closed, no hot-unload.
- Before the next measurements, check the current environment and processes: the PIDs, settings
  and admin state of 8 September are **historical**, not facts about the current session. Do not
  stop other people's WPR/PresentMon sessions.
- Use the requested CLIs directly (`codex`, `herdr`, etc.); do not search for them again unless
  they fail, do not create Agent-Launcher. Claude now excluded at the user's request. Herdr and
  sub-agents are optional tools, not prerequisites for resuming.

## Summary of the path so far

| Phase | Result that matters today |
|---|---|
| Inventory and driver analysis | Mapped package, components and the DX12 UMD `amdxc64.dll`. The 26.9.1 package in the root **does not match** the driver installed during measurements. Documented caches and configuration surfaces without patching signed files. |
| Early ETW and compiler | Historical Fortnite analysis and controlled RGA tests. The `AMD_SC_OPTIONS` parser is active, but the 272 `SCOption_*` cannot be set through the channels found: dump options are available, not a proven tuning lever. Do not reopen this branch without new evidence. |
| Shader lab, up to 2N | Built tools for compilation, ISA, microbenchmarks and runtime measurement. Several early conclusions were corrected: proxies/microbenchmarks do not prove a gain on the workload; old A/B tests without runtime provenance do not count as causal evidence. |
| Audit and 2O | Repaired and verified the build/bytecode/runtime/image chain. Corrected counter semantics: `TexUnitBusy` is a per-CU maximum, not a mean; two MRTs do not prove 2× overdraw; multipass allowed for aggregate work, not single timings. Falsified the filter-throughput-only thesis; ALU and texture are both critical in the studied sample. |
| 2P/2Q, MiniEngine/Sponza PoC | `stack3_scalar`, 68 lines of HLSL diff: **Render Color −41.43%; GPU frame −24.47% measured; −21.78% clock-corrected estimate**, not to be confused. Float32 correctness within 7 ULP on the verified case, one component bit-identical. Initial canary broken by the review and rebuilt with a positive control. Audit: 64 builds, 422 runs, 22 cycles with no discrepancies. |
| 2R and freeze | Transfer to nBody worked as a method, no transformation accepted. Phases 2P/2Q/2R frozen: do not touch them to raise the number. The PoC depends on scene/GPU/driver and proves no gains in games. |
| 2T | 0 hits on 4 workloads. Correct candidates below threshold or fast candidates not correct; fixed a time pairing that would otherwise have fabricated an acceptance. |
| 2U | 0 hits on 4; programme total about **1 hit in 9 distinct workloads**. Ceiling gate and decomposition avoid useless work. `shadow_tmax`, byte-identical and about −1.8/−2.2%, still rejected by the preregistered thresholds. The PoC's −41% is an outlier, not an expected yield. |
| Cyberpunk baseline | Five manual runs, machine checks, parsing/native alignment and mod-surface inventory. No mod applied. |
| Cyberpunk scaling | Initial borderless series unsuitable for resolution comparison because it changed the present path. Redone in fullscreen; v2 verdict final. |
| WPR CPU+GPU | Offline analysis 16 October: clock/5304 frames validated; 444,920 game CPU samples; running time of 34 threads matching xperf within 0.5 µs; real wait/signal; DMA FIFO/ownership/preemption rebuilt. Tracing materially present, no optimisation candidate; sampled callers/critical path and the cause of the drop versus passive runs remain open. |

Historical budgets (for example the 12 cycles of 2U, used up) belong to their phases: do not
treat them as a new available budget. Old checkboxes in `PLAN.md` are not all a backlog for today.

## Cyberpunk: results and limits

### Borderless baseline and controls, 7 September

Directory: [research/60_c2077_20260907_codex](research/60_c2077_20260907_codex).

- `manual_r1`…`manual_r5`: 113.0262 / 112.9794 / 112.9032 / 112.9315 / 113.0928 FPS. Mean
  **112.9866**, sample SD **0.07564**, CV **0.06695%**. Updated source:
  [manual_five_statistics.json](research/60_c2077_20260907_codex/manual_five_statistics.json).
- The fifth run follows a game restart; do not assume an identical tail distribution. Mean FPS is
  very stable, the 0.1% low is more variable. A descriptive/planning MDD is not an acceptance
  threshold for a future variant.
- `bench_r2` at about 96 FPS is a separate full capture; the cause of the difference is not
  isolated. **96 → 113 is not an optimisation.** Preflight/menu-only and schema-probe captures
  remain excluded and kept.
- Superposition: five scores, mean 17138.4, CV 0.0954%; a machine check, not a primary DX12
  shader workload.
- Steel Nomad pre/post: **4184 → 4189**, FPS **41.849308 → 41.897465**. Score +0.1195%; gate
  against older references failed, so no historical pooling. These endpoints do not guarantee
  minute-by-minute stability nor cover the later run 5.
- The old full baseline metrics used N/(last−first timestamp). Scaling v2 uses N complete
  intervals: do not silently mix the formulas.

### Fullscreen scaling, 8 September — current verdict

Source: [VERDICT_V2.md](research/62_c2077_fullscreen_scaling/VERDICT_V2.md), with
[scaling_analysis_v2.json](research/62_c2077_fullscreen_scaling/scaling_analysis_v2.json).

| Run | FPS | Mean frame ms | GPU busy ms | GPU wait ms |
|---|---:|---:|---:|---:|
| fs1440_r1 | 112.368 | 8.8994 | 8.7747 | 0.0988 |
| fs1080_r1 | 163.965 | 6.0989 | 5.8543 | 0.1960 |
| fs720_r1 | 185.826 | 5.3814 | 4.1720 | 1.1069 |
| fs1440_r2 | 111.905 | 8.9361 | 8.8007 | 0.1076 |

- Identical PresentMode: Hardware Independent Flip, fullscreen `windowMode=2`; 1440p anchor drift
  **−0.411%**, within the historical 0.5% gate. A single run per low resolution: no CI or MDD
  transferred from the borderless baseline.
- **1440p mostly GPU-bound: strong. 720p limited mainly by non-GPU feeding/pacing, compatible
  with CPU/submission: probable.** CPUBusy includes pacing; it does not separate game CPU from
  driver. Busy/frame ratios are not measured hardware utilisation.
- At 720p the three blocks differ by one frame: window 6415–18356, declared ±1 tolerance and
  verified sensitivity. Do not present it as exact frame-by-frame identity. The other cases use
  strict agreement.
- v2 corrections: duration over N intervals; QPC used for continuity, not to find the window by
  duration alone; the duration-only locator was disproved. 33 historical hashes preserved.
- **Withdrawn**: the readings of the constant 4.81–5.38 ms term as CPU cost and of 186 FPS as a
  hard ceiling. The gain from lowering resolution is neither an achieved shader speed-up nor its
  upper bound.

## WPR: what is ready and what was picked up

Path: [research/63_c2077_wpr_attribution](research/63_c2077_wpr_attribution).

### Real capture recovered, not to be repeated pre-emptively

- ETL: `fs1440_r1/c2077_fs1440_attribution-run1-20260908-222856-633.etl`,
  **21,098,397,696 bytes**; log [capture_r1.log](research/63_c2077_wpr_attribution/capture_r1.log).
  *(Not published — too large. SHA-256 below and in the excluded-files manifest.)*
- Original metadata: `-meta.json` suffix; historical PID **16316**; PresentMon exit 0;
  **18,405 data rows** (18,406 with header); sampling kept at **1 ms**. WPR saved the trace
  correctly. Do not use that PID for actions on the current session.
- Original native result:
  `C:\Users\Lorenzo\Documents\CD Projekt Red\Cyberpunk 2077\benchmarkResults\benchmark_2026-09-08_22-29-31`.
- On 26 September normalised copies `metadata.json` and `presentmon.csv` were created to reuse
  the existing parser unchanged. Originals intact. Copies of native `frames.csv` and
  `summary.json` and source hashes are now kept in
  [native_analysis_v2](research/63_c2077_wpr_attribution/fs1440_r1/native_analysis_v2).
- **Strict alignment PASS:** 5304 frames, zero-based data rows **7745–13048**, three blocks
  agreeing, QPC continuity verified. **64.2440852 s / 82.56013 FPS**, versus 82.56697 native FPS;
  difference −0.00829%. Native 2560×1440, windowMode 2, RT/upscaling/FG off.
- PresentMode verified in the window: **Hardware: Independent Flip on all 5304 frames**. Also
  verified byte equality of the normalised copies and source hashes recorded by the parser.
- Window QPC: **32466592.8518 → 32530836.9370 ms**, exclusive end after the last interval. ETL
  conversion validated on 16 October: **[49.9097700, 114.1538552) s**; raw QPC origin
  324166830818, frequency 10 MHz. All 5304 DXGI stops matched in a contiguous sequence;
  online/ETL timestamps not bit-identical, residuals 0.2–12.9 µs, with no offset fitting.
- `xperf -a tracestats`: exit 0, **zero Lost Buffers / Lost Events**, check
  `etw_analyze.check_loss` PASS. Evidence
  [trace_validation.txt](research/63_c2077_wpr_attribution/fs1440_r1/trace_validation.txt).
  ETL span 177.2226409 s.
- The profiled run is much slower than the passive ones (~82.56 vs ~112 FPS).
  **Perturbation/conditions still to be quantified: do not automatically blame the whole
  difference on WPR, do not use this run as an A/B arm, and do not carry its regime over to the
  passive runs without verification.**

### Harness and checks already available

- [capture_etw.ps1](tools/capture_etw.ps1): v2 metrics, QPC ms, path quoting, verified
  timeout/exit, unique sessions/outputs, never stops other people's sessions; sampling kept by
  default, any explicit value restored; incomplete ETL saved on error.
- [c2077_native.py](tools/c2077_native.py): three-block alignment and validation, native
  FPS/duration cross-check, QPC check, ±1 uncertainty only if explicitly authorised and justified
  by the data.
- [etw_analyze.py](tools/etw_analyze.py): loss check and streaming CPU aggregation per module.
  **Does not complete the requested attribution on its own**: the native-window filter and the
  causal stack/queue reconstruction are missing.
- New analysis: [etl_extract.cpp](tools/etl_extract.cpp),
  [c2077_etw_offline.py](tools/c2077_etw_offline.py),
  [c2077_gpu_queue.py](tools/c2077_gpu_queue.py), [c2077_etw_check.py](tools/c2077_etw_check.py).
  Inputs/outputs and commands in
  [offline_20261016/README.md](research/63_c2077_wpr_attribution/fs1440_r1/offline_20261016/README.md);
  use only the canonical results, not the superseded attempts.
- Re-run on 16 October, all PASS: `pwsh -NoProfile -File tools/test_capture_etw.ps1`,
  `python -B tools/c2077_native.py`, `python -B tools/etw_analyze.py --selfcheck`; also PASS the
  self-checks of the new readers/parsers and real raw/xperf/PresentMon comparisons.
- The historical smoke test verified CPU stacks and DxgKrnl. Its statistics are not the
  benchmark's. WPA exports precise stacks/CSwitch, but the sampled export often stops at
  `[Root]`; GPU GUIDs without a preset do not produce a valid GPU export. Do not claim these
  limits are already solved.

### Results added on 16 October

- Game CPU exclusive: 48.80% executable, 28.40% ntoskrnl, 8.44% ntdll, 7.87% amdxc64, 1.23%
  D3D12Core. Percentages of process samples, not fractions of the critical frame. Kernel/DPC not
  equated with the UMD driver.
- Precise stacks: WaitForSingleObjectEx and ReleaseSemaphore observed in millions of events; no
  proof that the synchronisation can be removed. Historical TID 2700 is running for 61.518 s out
  of 64.244 s; not identified as the critical thread of the passive runs.
- GPU: union of the game's DMA FIFO **75.7717%** of the profiled window; 93,450 DMA starts, 2714
  preempted segments, no timeouts. This is not hardware occupancy. All 436,393 target
  QueuePacket Starts mapped agree on owner 16316; 18 separate DEVICE_COMMAND_BUFFER events not
  mapped.
- Correct layouts: **244 scalar WAIT=4**, **245 array SIGNAL=5**; 52,876 Unwaits validated. The
  initial replays with inverted enum / reused-pointer joins are kept but discarded.
- Whole ETL: 439 million events. In the window, 13.964 CPU-s sampled in Etw*/Etwp* symbols, plus
  27.277 CPU-s in two explicit StackWalk helpers. The causal contribution to the FPS drop is not
  quantified.
- **Sampled CPU callers not validated:** SampledProfile/SampleProf filters empty; even the
  historical smoke without a PID filter does not resolve them. The broad Profile filter is
  ambiguous and rejected as a source of CPU costs/callers. CSwitch/ReadyThread stacks are usable.
- PM/metadata/native hashes unchanged; ETL SHA-256
  `e2e4ae42ccb8bb1e41d8717513abe1bb469d6e4969ef1b8e363f229a5b21e739`. No changes to the system or
  the games.

## Next decision and concrete gaps

1. **Current priority: catalogue from real use in
   [phase 68](research/68_c2077_backbuffer_catalog_20261016/STATUS.md).** The phase-67 visual
   walk-around showed no target binds/draws; process 11348 closed. ShaderLab now in observe, zero
   shader overrides. Read-only catalogue installed, old probe removed/archived. Wait for a normal
   manual start and read the new `backbuffer` logs/PIDs with
   `python -B tools/c2077_shader_loader.py status`. Select by RTV0/back-buffer identity and
   draw/submission, then the exact SHA in the offline index (8340 unique / 19,950 occurrences),
   not by names. GPU completion/visibility/cost not proven by the counters; compute/copies/bundles
   are limits. No benchmark/cache clearing/new canaries before selection and oracle. Uninstall
   with the process closed covers the new add-on and its own logs.
   *(Done after this handoff — see the archive note at the top.)*
2. The current WPR report stands: do not redo alignment, scaling or benchmarks already done. Any
   further CPU work is secondary to the new direction; **sampled CPU callers** remain unvalidated,
   do not use the ambiguous `Profile` or `[Root]`. Full critical path and causal satisfaction of
   fences are not proven by the aggregates.
3. The profiled trace does not identify the passive-run regime nor optimisable shaders/PSOs. Any
   future measurement must perturb less and control for its effect; do not automatically repeat
   the same verbose profile. Only after approval for the new capture.
4. **No validated performance tuning.** The canary is diagnostic and alters the image on purpose:
   do not measure it as an optimisation. A future transformation needs a really-used shader/PSO,
   an oracle, preregistration, backup/restore and A/B. Do not reopen the frozen PoC or fabricate a
   speed-up.

RGP is a possible next route for GPU detail, not an existing Cyberpunk capture. Its
clock/profiling and synchronisation constraints must be assessed separately; do not run scripts
that change the Registry/groups as an automatic shortcut.

## Map of sources and superseded documents

Recommended reading order:

1. This file, [phase 68 — current catalogue](research/68_c2077_backbuffer_catalog_20261016/STATUS.md)
   and preregistration, [phase 67 — finished diagnosis](research/67_c2077_canary_probe_20261016/STATUS.md)
   and preregistration, then [phase 66 — loader](research/66_c2077_shader_loader_20261016/STATUS.md)
   and its README/preregistration, [phase 65 — offline canary](research/65_c2077_dxil_roundtrip_20261016/STATUS.md),
   [shader access 64](research/64_c2077_shader_access_20261016/STATUS.md), then
   [WPR report](research/63_c2077_wpr_attribution/OFFLINE_ATTRIBUTION_20261016.md) and
   [WPR STATUS](research/63_c2077_wpr_attribution/STATUS.md).
2. [Fullscreen verdict v2](research/62_c2077_fullscreen_scaling/VERDICT_V2.md).
3. [Frozen PoC](research/POC_FROZEN.md), [2T results](research/PHASE_2T_RESULTS.md),
   [2U results](research/PHASE_2U_RESULTS.md), [measurement memory](research/MEASUREMENT_MEMORY.csv).
4. [PLAN.md](PLAN.md), [C2077_WORKLOG.md](research/C2077_WORKLOG.md),
   [AUTONOMOUS_LOG.md](research/AUTONOMOUS_LOG.md) for the chronology;
   [metrics method](research/04_benchmarks/analysis/METHOD.md).

Beware of historical sources:

- `LAST PROMPT.md` (now [docs/history/LAST_PROMPT.md](docs/history/LAST_PROMPT.md)) currently
  holds the request to redo scaling in fullscreen: done. It no longer holds all earlier
  operational prompts.
- `CLAUDE.md` (now [docs/history/CLAUDE.md](docs/history/CLAUDE.md)) holds initial context and
  constraints, but some phase/install/dependency notes are old. The file name does not require
  using Claude.
- `research/CODEX_HANDOFF_AUDIT.md` is the 5 September audit, not this handoff: its corrections
  matter, but several blockers were later resolved by 2O and later phases.
- The body of `research/C2077_FINAL_REPORT.md` and parts of the worklogs still say run 5 is
  missing. **This is superseded** by `manual_five_statistics.json` and the `manual_r5` data. The
  borderless baseline must not be mixed with fullscreen.
- The WPR note "waiting for the click" was superseded by the 22:28 artifacts. No second capture
  should be requested just because that sentence stayed in the old status.

## Portability and resuming on another harness

Original root: `C:\Users\Lorenzo\Downloads\driver mod`. The links in this file are relative.
Carry over **at least `HANDOFF.md`, `PLAN.md`, `CLAUDE.md`, `LAST PROMPT.md`, `tools/` and
`research/`**, keeping raw data, JSON, hashes, backups and the ETL/PDB needed. Markdown alone gives
context; it does not replace the artifacts needed to reproduce the measurements.

Historical local dependencies to recheck when changing machine:

- PresentMon installed, verified on 16 October:
  `C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication\PresentMon-2.6.0-x64.exe`; the
  historical measurements used 2.5.1. An official Intel-signed 2.5.1 copy was recovered only for
  offline replay in the `offline_20261016` directory.
- WPR/WPT: `C:\Windows\System32\wpr.exe`,
  `C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\` (`xperf`, WPA,
  WPAExporter).
- Python with numpy/pandas/scipy; PowerShell `pwsh`; AMD tools in the RadeonDeveloperToolSuite
  folder at the root.
- Cyberpunk GOG: `E:\GOG\Cyberpunk 2077`; native results in Documents/CD Projekt Red; settings in
  `%LOCALAPPDATA%\CD Projekt Red\Cyberpunk 2077\UserSettings.json`.
- Some historical samples/builds lived in `%TEMP%\claude\src\...`: do not assume they are
  versioned or carried over just because `research/` exists. Check dependencies and provenance
  before reproducing frozen builds. (Part of that tree was preserved in
  [preserved_temp_claude_20260909/](preserved_temp_claude_20260909/README.md).)
- Hardware for the measurements: RX 6950 XT, Ryzen 7 5800X3D, 32 GB, Windows 11 build 26200;
  driver 32.0.21045.5002 / Radeon 26.8.1. Do not infer the current driver from the 26.9.1
  installer in the root.

Minimal prompt to resume (historical, before the phase-68 run):

> Read HANDOFF.md and research/68_c2077_backbuffer_catalog_20261016/STATUS.md. Control normal,
> canary without marker; phase 67 without target binds/draws even after the walk-around, PID 11348
> closed. Do not keep pushing that glass. Now ShaderLab observe and new read-only catalogue
> installed (old probe archived/removed). Wait for a normal manual start and new backbuffer
> logs/PIDs, identify shaders from draws to swap-chain resources and the exact SHA offline; do not
> choose by names first. No active shader mod, no benchmark/WPR/cache clearing/driver
> patch/anti-cheat. CPU counters do not prove GPU completion/visibility/FPS. Manifest-owned
> uninstall includes the new add-on/log. Do not start Claude; keep raw data and update
> HANDOFF/PLAN.

## Maintenance rule

Update this same file at every milestone or change of direction: date, artifacts produced, checks
actually run, conclusions/limits, what remains and the next action. Keep details in the phase
reports and link them; avoid new competing handoffs. Do not mark an analysis complete just because
the capture or smoke test succeeded.
