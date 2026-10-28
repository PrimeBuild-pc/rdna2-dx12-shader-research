# PLAN — Phase 1 roadmap

> **English translation** of the original Italian plan ([PLAN.it.md](PLAN.it.md)). Where the two
> disagree, the Italian original and the phase reports win. A few characters that were mangled in
> the original file (Windows paths with `\a` / `\u` sequences) are restored here.
> For the current state start from [HANDOFF.md](HANDOFF.md) and the [README](README.md).

> **Current state 2026-09-26:** start from [HANDOFF.md](HANDOFF.md). Claude unavailable; Codex took over. Baseline and fullscreen scaling done. Recovered the real WPR capture already made on 8 September: native alignment and loss check PASS; the offline CPU/driver/GPU-queue attribution remains. The historical summaries below are not the current backlog.

Updated: **2026-09-07 — 2U CLOSED: hit rate 0 of 4 (2T was 0 of 4); 1 hit in 9 workloads across the whole programme**. Cyberpunk milestone prepared and ready, waiting for the game to be installed.
> **2U in one line:** three changes to the pipeline — **ceiling gate**, **ceiling decomposition**, **two-tier correctness rule** — all worked and **none produced a hit**. Two workloads closed by the gate before any hypothesis (ceiling −0.38% and +0.22%). The best candidate, `shadow_tmax` on a DXR workload, is **byte-identical, replicated, with full separation at −1.8/−2.2%** — and the preregistered threshold rejects it. **The bottleneck is not generating ideas: it is exactness and the threshold.** Report: [`research/PHASE_2U_RESULTS.md`](research/PHASE_2U_RESULTS.md) · Cyberpunk procedure: [`research/C2077_OPERATOR_PROCEDURE.md`](research/C2077_OPERATOR_PROCEDURE.md).
> 2T: hit rate of the method measured, 0 of 4 workloads. 2O, 2P, 2Q, 2R complete; adversarial review done; PoC FROZEN.
> **2T in one line:** the frozen pipeline, run on 4 D3D12 workloads declared before looking at them, produced **zero accepted transformations out of 5 attempted**. Two workloads closed before any hypothesis because the pass cannot be improved (5.76 µs dispatch, 480 ns draw). W4 has **16.6% of the frame inside the pixel shader** — the ceiling is there — and the pipeline got nothing out of it: the fast candidate was not exact, the exact one was not fast. Counting 2P and 2R, the method stands at **1 hit in 6 workloads**. Report: [`research/PHASE_2T_RESULTS.md`](research/PHASE_2T_RESULTS.md). Status: **build gate validated; O1 PASS (1/6);
O2 PASS (2/6): semantics and aggregation of raw counters validated against the SDK, workload
identity measured, `Render Color` baseline acquired without ablations; O3 PASS (3/6): dose-response
on material samples, 2.1% of texture instructions = 13.9% of TA cycles; O4 PASS (4/6):
sampler-only ablation with unchanged bytecode — **2N's "texture-filter-throughput bound" hypothesis
is falsified**; O5 PASS (5/6): stage attribution closed (99.53% pixel) and cache/memory
eliminated by measurement (L0 stall 0.24%, hit 97.66%, 39.6 GB/s); O6 PASS (6/6): **replicated** that
88% of the pass's cycles scale with the texture instruction count, at 13.1 cycles each, but the
SIMD-divisor correction shows the pass is **co-saturated** VALU 96.6% / TA 93.6%, so the two
units **cannot be ranked** at baseline. **2P: first real end-to-end gain** — `stack3_scalar` takes `Render Color` to −41.4% and the GPU frame to −24.5% measured, in 68 lines of application HLSL. **2Q: float32 equivalence verified** (≤7 ULP, `SCALAR_BRANCH` bit-identical, `fresnel5` proven more accurate over its whole domain, data contract measured). **2R: method carried to a second D3D12 workload, no transformation accepted**. **Adversarial review done: it broke the data-contract canary, which was rebuilt and given a positive control**; 2P/2Q/2R are now **frozen** as a validated PoC (`research/POC_FROZEN.md`). Next proposed phase, just one: **2T, measure the hit rate of the method** on 3–5 D3D12 workloads declared before looking at them**.
Phases 1A, 1B, 1E, 1.5, 2A–2N have historical reports; "complete" does not certify all of their conclusions.

> **CURRENT ERRATA — overrides the historical entries below.**
> Audit: [`research/CODEX_HANDOFF_AUDIT.md`](research/CODEX_HANDOFF_AUDIT.md).
> **RESOLVED** — the chain `source → bytecode → linked binary → executed PSO → image` is now
> shown to be fail-closed and reversible:
> [`research/24_phase2o_build_gate/PHASE_2O_O1_RESULTS.md`](research/24_phase2o_build_gate/PHASE_2O_O1_RESULTS.md).
> **RESOLVED NEGATIVELY (O4)** — "Render Color texture-**filter**-throughput bound" is now
> **falsified by measurement**: switching anisotropic filtering off entirely (−17.9% aniso cycles) or
> going down to point filtering, with the pixel-shader bytecode **byte-identical** and ALU verified
> unchanged within 0.07%, moves the pass **by at most ~3%** while `TexUnitBusy` stays ~94%.
> → [`research/29_o4_sampler/PHASE_2O_O4_RESULTS.md`](research/29_o4_sampler/PHASE_2O_O4_RESULTS.md).
> It remained true that with 2N's instrumentation the thesis **was not obtainable**. Among the 145 derived counters there is no
> VALU/SALU/occupancy counter for the pixel stage, and `TexUnitBusy` by documentation includes
> cache and memory effects. 2N's 31-counter set needs **13 passes** (measured offline).
> → [`research/25_gpa_validity/GPA_VALIDITY.md`](research/25_gpa_validity/GPA_VALIDITY.md).
> **PARTLY RESOLVED** — `kGpaOpenContextEnableHardwareCountersBit` exposes **4001 counters instead
> of 145** (verified offline **and on a live DX12 context**, identical sets). There are `SQ`
> counters masked `PS` for pixel-shader ALU (`INSTS_VALU`, `INST_CYCLES_VALU`,
> `INSTS_TEX_LOAD`, waves) — **1 pass** for all 36 — and `TA` counters for filtering cost
> (`TA_BUSY`, `ANISO_*_CYCLE_QUADS`) — `TA_BUSY` over 80 CUs in **1 pass**.
> → [`research/26_gpa_hwcounters/GPA_HW_COUNTERS.md`](research/26_gpa_hwcounters/GPA_HW_COUNTERS.md).
> **O5 becomes executable again**, with raw counters.
> **MEASURED CORRECTION (O2)** — `TexUnitBusy` is the **maximum over 80 CUs**, not a mean or a
> sum: `TexUnitBusy% = max(TA_BUSY)/GPUBusyCycles·100`, verified exact against the SDK. 2N's
> 94.6% refers to *the busiest CU*, not to the texture units as a whole (here the measured
> imbalance is only 1.013). `TexAveAnisotropy` and `GPUBusyCycles` validated exact.
> **Workload identity (O2)** — **aggregate-work** counters are bit-identical even over a
> 5-pass session; **per-instance** and **timing** counters are not
> (`GPUTime` varies by 19.9% between frames). Multipass is therefore admissible for aggregate
> work, never for single timing values.
> → [`research/27_o2_counters/PHASE_2O_O2_RESULTS.md`](research/27_o2_counters/PHASE_2O_O2_RESULTS.md).
> `PSPixelsOut ≈ 2× screen` counts two MRTs; it does not prove 2× overdraw.
> The 2L–2M A/B tests without runtime provenance remain invalid for causal conclusions.
> Image oracle: **now exists and works**, but only for O1's capture point
> (`g_SceneColorBuffer` after `Render Color`, before particles and post-effects).
> 2M's 28.90 draws/frame are **one** of the two components of the scope: at runtime
> **34** are observed across 2 native PSOs.
> 2K's 2.5× figure needs recalculation: best/oracle include variants discarded for correctness.
See [`research/PHASE_1_STATUS.md`](research/PHASE_1_STATUS.md) and
[`research/PHASE_1_5_DECISION_GATE.md`](research/PHASE_1_5_DECISION_GATE.md).
Legend: `[ ]` to do · `[~]` in progress · `[x]` done · `[!]` blocked

---

## Blockers before starting

- [!] **Black Myth: Wukong Benchmark not installed** → blocks 1F. Download it.
- [x] `pip install pefile lief capstone` — done (pefile 2024.8.26, lief 1.0.0, capstone 5.0.7).
- [~] Repeatable Fortnite scenario: the 7 runs follow the same route but are **not aligned
  frame-by-frame** (FPS/s trace correlation 0.55) and the CSV has no scene markers. Background
  processes must also be recorded (see the r4 anomaly).

---

## 1A — Inventory → `research/00_inventory/` ✔ COMPLETE
- [x] `project_tree.txt`, `software_versions.md`, `hardware_info.json`, `windows_info.json`, `gpu_info.json`
- Found: **HAGS on** (`HwSchMode=2`), Defender real-time on, Win 11 25H2 26200.9168,
  display 2560x1440, GPU `DEV_73A5` (Navi 21).
- **The package in the project (v…9003, INF u0203729) is NOT the installed driver (v…5002, INF u0203303).**

## 1B — Driver package map → `research/01_driver_map/` ✔ COMPLETE
- [x] Walk + SHA-256 + PE metadata + sigcheck on all 724 files (219 PE, 322 signed)
- [x] Parsing of the 41 INFs → **a single Display-class INF**, `u0203729.inf`
- [x] `driver_files.csv`, `driver_map.json`, `component_analysis.md`, `dependency_graph.json`
- [x] Shortlist of 12 binaries backed by evidence (INF + exports + version info), none by filename
- Key results:
  - **`amdxc64.dll` = DX12 UMD** (INF `UserModeDriverName[3]` + export `OpenAdapter12`); it also
    exports `D3D12OpenCompilerDDI`, `GetSettingsBlobsAll`, `GetSettingsBlobsAllDecoded`.
  - **The shader compiler is statically linked inside the UMD**: 6 imports, all Windows, zero
    AMD dependencies. Exports = Boost/XML serialisers of `_SC_COMPILE_FLAGS`,
    `_E_SC_SI_OPT_MINIMIZE_VGPRS_STRATEGY`, `_SC_CACHE_POLICY`…
  - **`HKR,Parameters,DXCTuningsFileName = amdxc64z.dll`** declared by the INF but **the file is
    not in the package**. Potential tuning surface outside the signed catalogue — *to verify*.
  - `C:\Windows\System32\amdxc64.dll` is the **stub** (143 KB), not the UMD.
- [ ] Not done: extraction of `amdvlk_nexus.cab`; no runtime evidence (→ 1K).

## 1C — Shader cache forensics → `research/02_shader_cache/`
- [ ] Hash+size+mtime baseline of `DxCache`/`DxcCache` (**before** any run)
- [ ] Procmon on Fortnite: closed → start → menu → gameplay → exit
- [ ] `cache_before.csv`, `cache_after.csv`, `file_activity.csv`, `cache_diff.md`
- [ ] Answer: which files are read/written/created, by which process, when, how many bytes
- [ ] Check stability between two identical starts and whether the filename correlates with content
- Hypothesis to test: `DxcCache` (515 MB) is the real store; `DxCache` (1.9 MB) is index/metadata.

## 1D — Controlled cache rebuild → `research/03_cache_rebuild/`
- [ ] Full cache backup (copy, not move)
- [ ] Written **manual** procedure; deletion is performed by the human operator
- [ ] Cold-cache vs warm-cache runs: timestamps, file creation order, size, CPU/GPU, frametime

## 1E — Benchmark harness → `research/04_benchmarks/analysis/` ✔ COMPLETE (analysis)
- [x] Parser `tools/pmparse.py` with an executable self-check; `analyze.py` produces metrics,
  variance, spikes, correlations and 18 charts
- [x] Validated against PresentMon's `-stats.csv` on 14/14 files (max 0.053% on avg FPS) and
  against the 3DMark GUI (41.38 vs 41.385)
- [x] Definitions written in `METHOD.md`: 1% / 0.1% low **time-integrated** (primary) and
  **percentile** (secondary), spike = `ft > 2x rolling median (21 frames) AND +>=2 ms`
- [x] **Baseline noise: Steel Nomad ±0.11% (MDD 0.17%) · Fortnite ±1.3% (MDD 2.17%)**
- [x] Fortnite is **CPU-bound** (CPUBusy 1.53 > GPUBusy 1.37 ms, GPU util 74%);
  Steel Nomad is **99.9% GPU-bound**
- [ ] To do: PresentMon *launch* wrapper + `experiment_metadata.json` for future runs
  (so far the operator launched runs by hand)

## 1F — Wukong: controlled profiling → `research/05_rgp/`
- [!] blocked by the benchmark installation
- Note: Steel Nomad covers the role of *measuring instrument* (CV 0.11%) but is closed and runs with
  an already-warm cache: it does not expose the shader compilation path. Wukong is still needed.
- [ ] Fixed graphics config + N baseline runs → standard deviation → threshold for a "real" difference
- [ ] RGP capture; if it works: event timing, occupancy, VGPR/SGPR/LDS, expensive shaders, hashes
- [ ] `expensive_shaders.csv`, `pipeline_notes.md`, `shader_analysis/`
- [ ] Check RGP → RGA interoperability on extracted pipelines

## 1G — Windows scheduling → `research/06_etw/`
- [ ] WPR trace around the controlled benchmark; WPA/GPUView analysis
- [ ] Classify the limit: GPU exec / CPU submission / sync / shader / memory / present / unknown

## 1H — Fortnite baseline
- [ ] ≥5 comparable runs, non-invasive tools only
- [ ] Run-to-run variance **before** any claim; cold vs warm cache kept separate

## 1I — Warzone shader investigation
- [ ] Procmon on the shader preloading phase
- [ ] Classify the data found: text, DXIL/DXBC, AMD driver cache, metadata, archive, unknown
- Note: `E:\Call of Duty\_retail_\cod25` — the `.ff` files are game archives, not shaders.

## 1J — Correlation → `research/07_correlation/shader_cache_map.json`
- [ ] Chain: shader/pipeline → hash → cache activity → blob → render event → frametime cost
- [ ] Each relation labelled confirmed / strong / probable / speculative; gaps = "unknown"

## 1K — Driver analysis candidates
- [ ] List of UMDs actually loaded in the controlled workload (runtime evidence, not filenames)
- [ ] Per candidate: path, version, signature, process, exports/imports, probable role, shader/PSO/cache relevance
- [ ] Only after the shortlist: targeted Ghidra. No blanket decompilation.

## Phase 1.5 — CPU attribution + UMD settings (at the decision gate)

### 1.5A — ETW/WPR attribution on Fortnite → `research/08_etw_fortnite/`
- [x] Capture harness `tools/capture_etw.ps1` (WPR CPU+GPU file mode + PresentMon + background snapshot)
- [x] 8 kHz sampling verified: `xperf -setprofint 1221` → 16,300 samples/s versus 1,677 by default
- [x] Streaming analyser `tools/etw_analyze.py` (no 1.45 GB dump), validated on a dry run:
  per-module attribution without symbols, correct RVAs, loaded module path resolved
- [x] Decision threshold fixed **before** the data: >=15% of samples in `amdxc64.dll` = strong branch, <3% = branch closed
- [x] **3 Fortnite captures made** (2026-09-04, 3 x 13.5 GB) and analysed: 8.4 M samples,
  2.9 billion event rows → `research/08_etw_fortnite/RESULTS.md`
- [x] `cpu_module_attribution.csv`, `hot_threads.csv`, `amdxc64_hot_offsets.csv`, `summary_3runs.csv`
- [x] **`amdxc64.dll` = 0.151 core-equivalents = ~151 ms CPU/s ≈ 0.24 ms/frame**, CV 1.95% over 3 runs;
  81% on a single submission thread (TID 15168, 26.9% of the thread)
- [x] **UMD hot code in only 204 pages of 4 KB**; top-10 (40 KB) = 29.4% of the cost
- [x] **Run 4 with valid PresentMon** (24,695 frames): critical-path thread identified
  quantitatively → `amdxc64.dll` = **2.1%** ≈ 0.03 ms/frame, identical over 4 runs and 2 sessions
- [x] **BRANCH A CLOSED**: below the preregistered 3% threshold. The critical path is 84%
  `ntoskrnl.exe` (3 pages = 50% of kernel time), not the AMD driver
- [x] Script bug found and fixed: `Start-Process -ArgumentList` does not quote the space in
  "driver mod" → PresentMon exited with code 1. It was **not** PresentMonService or WPR (both
  verified innocent). Added fail-fast pre-flight, try/finally, `-ValidateOnly`
- [x] ETLs deleted after analysis (~50 GB freed); derived CSVs kept

### 1.5B — UMD settings/tunings → `research/09_umd_settings/` ✔ COMPLETE
- [x] Real instance identified from the registry: `...\u0203303.inf_amd64_...\B026363\amdxc64.dll`,
  sha256 `6aaade81…`; analysis on a copy
- [x] **`GetSettingsBlobsAllDecoded` = empty stub** (`xor eax,eax; ret`) → no standalone probe
- [x] `GetSettingsBlobsAll` = `uint32_t f(void* buf, uint32_t size)`, query-size-then-fill, depends on
  a global populated only by driver init → useless from a host that only does LoadLibrary
- [x] **`DXCTuningsFileName` belongs to the KMD**: string only in `amdkmdag.sys`, live key under
  `Services\amduw23g-203303-6af680f4\Parameters`, files do not exist → **dead end**
- [x] **Found the real interface**: `AMD_SC_OPTIONS`, `AMD_SC_CFG_FILE`/`amdsc.ini`,
  `AMD_DXCP_TEST_OPTIONS`, `AMD_CONFIG_DIR`, `EnableGlobalSettingsDumping`/`GlobalSettingsDumpFile`,
  boost::program_options parser, **272 `SCOption_*` options** + ISA dump options per shader hash
- [ ] To clarify: whether they are active in retail, the syntax, and the `cmp eax,1` guarding the dump

## Phase 2 — shader compiler / codegen (workload: Steel Nomad)

### 2A/2B/2C — SC parser → `research/10_sc_probe/` ✔ PARSER ACTIVE
- [x] **`AMD_SC_OPTIONS` and `AMD_SC_CFG_FILE` are consumed by the retail build** (confirmed):
  valid name -> OK, one-letter typo -> DX12 backend fails
- [x] File syntax reconstructed: `#` comment (not `;`), `key=value` without `--`,
  spaces allowed, names validated, no sections. boost::program_options::parse_config_file
- [x] **First successful dump**: `dump-prefix` + `dump-all=true` produces `SC_INPUT` XML per
  shader hash + a text dump with ISA, Shader Stats (VGPR/SGPR/spill), Optimization Report,
  SCML Model Decision Stats, Scheduler stats
- [x] Chain obtained: `shader hash -> SC_INPUT XML -> RDNA2 ISA -> statistics`, without
  touching signed files, registry or caches, or injecting anything
- Tool: **RGA in DX12 mode** (uses the installed driver, headless, a few seconds).
  3DMark not usable for the canary: Epic build on JVM, does not start when launched from a script;
  ProcMon without filters is unusable (2.1 GB in 8 min). `tools/sc_probe.ps1` removed,
  replaced by `tools/sc_canary.sh`
- [ ] **Not done**: no optimisation option enabled; no dump on Steel Nomad
  (the Epic launcher must inherit the environment)

### 2D — catalogue of the 272 SCOptions ✔ (partial)
- [x] Contiguous pointer table at RVA `0x2722060`, stride 8: **the index is the option ID**
  (`SCOption_MINIMIZE_VGPRS` = #20). 62 RDNA2 candidates
- [ ] datatype/default/range not determined

### 2E — Compiler Optimization Lab → `research/11_compiler_experiments/` ✔ CLOSED (negative)
- [x] Baseline of 6 controlled shaders (VGPR 8..144, inst 80..1994, up to 40 branches): `baseline.csv`
- [x] **The 272 `SCOption_*` CANNOT be set**: the only `options_description` in the binary are
  "CompilerControl options" and "Dump options" (8 dump options). `u32SCOptions[0] = 0x%08X` shows
  that the name table serves *reporting* of a bitmask, not input
- [x] 12 naming variants tested with the oracle: all fail
- [x] `AMD_DXCP_TEST_OPTIONS` discarded: it accepts arbitrary names but the known settings are
  Adrenalin features (Chill/Boost/RIS/Anti-Lag/FSR), not codegen
- [x] Negative control: 24 compilations with the available options, **0 change the ISA**
- [x] **Empty ranking**: no accessible codegen lever. No candidates invented
- Corrections: `AMD_SC_OPTIONS` works (it splits on **spaces**, my path with "driver mod" was
  being split); default `dump-prefix` = `amdsc` in the CWD; the dump-* are `typed_value<bool>`
  (they need `=value`); a per-shader syntax `<hash>.<options>` exists

### 2F — D3D12 bench with timestamp queries → `research/12_d3d12_microbench/` ✔ WORKING
- [x] `bench.cpp` (MSVC/O2): native D3D12, timestamp queries @100 MHz, warm-up 10, 25 measurements,
  8 dispatches/measurement, median/mean/p95/sd/CV. No rendering, no VSync
- [x] **Correctness bug found and fixed**: uninitialised SRV buffer -> shaders were reading
  denormals/NaN. `s3_mem` CV **68.7% -> 0.09%**
- [x] **Bench variance measured first** (3 independent runs, medians):
  s2 ±0.02%, s3 ±0.28%, s5 ±0.22%, **s4 ±2.32%** (the noisiest)
- [x] **Wave32 vs Wave64 on 4 shaders**: `[WaveSize(32)]` produces ISA **byte-identical** to the
  baseline (the driver already picks wave32); **wave64 always slower**: +7.6% (s4), +14.6%
  (s5), +16.3% (s2), +18.4% (s3)
- [x] **Important counter-example**: `s4_pressure` w64 has VGPR 144->116 and inst 691->678, and is
  **+7.6% slower**. Fewer registers and fewer instructions != faster. (wave64 VGPRs cost
  double in the register file: 116 w64 ~ 232 w32-equivalent -> worse occupancy)
- [x] **Ranking: no variant faster than the baseline.** No candidates invented
- [x] Chain closed: HLSL -> DXC -> DXIL -> AMD compiler -> ISA -> **real GPU time in ns**
- [ ] Not done (stop requested): numthreads, unroll/loop, rewrites of s4, numerical
  correctness check of output across variants

### `AmdExtD3DCreateInterface` / AGS reconnaissance ✔ (static only)
- [x] The stub in System32 is a **pure forwarder**: 2 exports, no GUID, no strings
- [x] 59 `AmdExt*` symbols in the UMD: **intrinsics** (32/64/float atomics, wave ops
  ballot/scan/reduce, constant load, thread id) via `AmdExtD3DShaderIntrinsicsUAV`
- [x] **No compiler control**: no flags, optimisations, register allocation, scheduling.
  It does not reopen the levers closed in 2E

### 2G — Automated Shader Optimizer → `research/14_optimizer/` ✔ WORKING
- [x] **Numerical correctness check** added to the bench (readback of 65,536 float4,
  relative tolerance 1e-4); validated: two runs of the same shader give bit-identical output
- [x] Automatic loop: generate HLSL -> DXC -> RGA (ISA/VGPR/inst) -> bench 3 runs -> verify ->
  keep/discard. 16 one-variable-at-a-time variants, dedup by source SHA
- [x] **The check rejected 3 false positives**: `L2_unroll4/8/12` were the fastest
  (-57%, -61%) but with **relative error 1.5-2.0** = semantically different result
- [x] Acceptance criterion **corrected along the way**: threshold = max(shader noise, variant
  spread, baseline spread). From 5 "accepted" to **3 really valid**
- [x] **Top 3** (correct, spread <0.3% over 3 runs):
  `L3_loop` **-30.03%**, `all_loop` -29.87%, `L2_loop` -14.54%
- [x] New counter-examples to static metrics: `L2_loop` has **more VGPRs** (152 vs 144) and is
  -14.5%; `L3_loop` has **more instructions** (719 vs 691) and is -30%
- [ ] Not done (stop requested): exploration with the best ones as parents; access patterns
  (they change the data read -> different output, would need a different correctness criterion)

### Static `u32SCOptions` branch → `research/13_scoptions_static/` ✔ CLOSED
- [x] No reverse engineering needed: **the dump lists the active flags per shader**
  (`//!option SCOption_X = 1`)
- [x] On Navi 21: **34 active out of 272** (22 always active, 12 shader-dependent, 238 never active)
- [x] Of the 12 shader-dependent ones, **11 are hardware workarounds** (NSA, prefetch, LDS+VMEM,
  FP atomic denorm): the input triggers them, but for **correctness**, not performance
- [x] `MINIMIZE_VGPRS`, `PBQP`, `LIVENESS_BASED_SCHEDULING`, `FORCE_WAVE32/64`, `SUBVECTOR`,
  `ML_MODEL_FOR_PS_WAVESIZE`: **never seen active** and not reachable
- Conclusion: the hypothesis "I can induce the heuristic from the input" is true as a mechanism but
  **useless as an optimisation lever**

### 2H — Robustness and cause → `research/15_robustness/`, `16_corpus/`, `17_rgp/` ✔ COMPLETE
- [x] **Corrects 2G at the root**: 2G's "baseline" had an explicit `[unroll]` written by me.
  **DXC's default** (no attribute) already produces the fast code: `dxc_default` and
  `L3_loop` agree within 0.5% on all 20 datasets and all 15 scales.
  **Against the compiler the gain is zero.** 2G's sentence "DXC's default (full
  unroll) is a wrong choice" is **false** and must be struck
- [x] **Two bench measurement defects found and fixed**: warm-up by iterations instead of by
  time (up to **5.2x** error on short shaders) and low duty cycle (one submission+fence per
  measurement -> GPU clock drops). Now all `reps` measurements are in **a single command list**.
  Cross-process repeatability: 0.3-0.6% (previously up to 419%)
- [x] 2G set remeasured: `L3_loop` **-16.31%** (not -30%), `all_loop` -16.65%,
  **`L2_loop` -1.63% -> REJECTED**. The `[unroll]` baseline has 12.7% spread and is **bimodal**
- [x] **Strong correctness**: 20 deterministic datasets x 3 workloads, **full** output
  (1,048,576 floats), max abs/max rel/RMS/RMS rel/diverging NaN-Inf. The variants **exceed
  1e-4 on 7 datasets of 20** — but **`dxc_default` fails on the same 7 with the same
  errors**: the shader is ill-conditioned, not the transformation. RMS rel 1e-7 everywhere.
  `wave64` is the only bit-identical one, and it is the slowest
- [x] **CPU reference** in float32 on the same bits read by the GPU: RMS rel 1e-5 on ds0. The
  GPU-CPU gap (4.6e-01) is 3 orders of magnitude larger than between GPU variants (1.2e-03)
- [x] **Scale**: gain between -12.2% and -32.0% over 45 combinations (3 datasets x 3 workloads x
  5 dpm x 5 runs). Larger on small workloads
- [x] **Cause (confidence: strong)**. **Identical** occupancy (144 VGPR both), scratch 0,
  no branches: `[loop]` does not prevent unrolling in the ISA. What changes is **load
  scheduling**: `s_waitcnt` 23 vs 14, `s_clause` 1 vs 3, median load->wait distance 3 vs 8,
  **12 loads of 24 stall within 2 instructions** versus 1 of 24, load groups 1.5 vs 6.0
- [x] **Three controls**: (null) `pressure24_nomem`, same arithmetic without loads -> the penalty
  disappears (+34.5% -> -4.4%); (negative) `mem_gather` with serial addresses -> ISA changes the
  same way, gain +0.01%; (positive) working-set sweep -> penalty **-0.31% at 4 KB,
  +25.77% at 1 MB, +0.13% at 16 MB**: non-monotonic, it exists only where latency matters but does
  not dominate
- [x] **Generalisation, 20 shaders / 65 variants / 5 runs**: `[loop]` is a **no-op** (0 better,
  0 worse, 20 equal). The variable that matters is `[unroll]`: **9 better, 3 worse, 8 equal**,
  median -3.08%, best -65.89%, **worst regression +40.69%** (`lds_reduce`)
- [x] Class identified: `[unroll]` hurts loops whose body keeps a memory-fed indexed array alive
  across iterations (`pressure24` +34.5%, `pressure48` +31.0%,
  `lds_reduce` +40.7%); it helps where the body is small and operations are independent
- [x] **Bench floor measured: ~3.15 µs** (4 MB store only). `alu_ilp4__all_unroll`
  and `alu_chain_dep` are **at the floor**: their deltas are bounded by bandwidth, not compute
- [x] RGP: two traces captured with `RadeonDeveloperPanelCLI --rgp-auto-capture=dispatch` +
  instruction tracing (`research/17_rgp/*.rgp`). **Not readable from the CLI** (GUI only), so
  **no stall counter measured** — the cause stays *strong*, not *confirmed*
- [x] **Phase 2I** design written and not implemented: `15_robustness/PHASE_2I_DESIGN.md`

### 2I — AI-guided shader search → `research/18_ai_search/` ✔ COMPLETE (positive)
- [x] **Bench self-check made blocking** (`tools/bench_selfcheck.py`): on the first attempt it
  **failed** (reproducibility 2.72% vs 1% threshold), so I redesigned the statistics
  instead of loosening the threshold
- [x] **Paired comparison** with a double reference (default measured in first AND last
  position, mean of the two) and shuffled order: cancels clock drift, measured at
  **+0.35%** on the second position. Paired null noise: **SE 0.049%** -> 1% is 20 SE
- [x] Thresholds fixed beforehand: candidate < -0.5%; accepted < **-1.0%** on **all 3**
  (workload, dataset) combos **and** mean+2SE < 0, 10 processes per combo
- [x] **3-level dedup** (normalised HLSL / DXIL / ISA): 2 variants eliminated without
  measuring them, both informative. `p24__load_then_scale` -> **ISA identical** to the default;
  `bdiv__select` -> **DXIL identical** (DXC already canonicalises if/else into select)
- [x] Two-tier correctness on 5 datasets: **1 eliminated** (`trig__unroll4`, max rel 4.4e-4)
- [x] **9 variants of 23 beat the REAL default**, all on 3/3 combos:
  `bdiv__hoist_parity` **-69.5%**, `bdiv__hoist_parity_batch` -49.7%, `trig__unroll` -25.4%
  (**bit-exact**), `ldsred__wave` -14.5%, `ldsred__tree` -14.4%, `mix__unroll` -6.2%,
  `dot__unroll` -5.8%, `dot__acc4` -5.8%, `dot__acc4_unroll` -1.2%
- [x] The winner is **strict** (max rel 4e-7): not a win bought with precision
- [x] **On `p24` no variant beats the default**: 7 transformations, 0 accepted. The
  compiler is already fine on that shader
- [x] **Cause isolated with 5 controls, initial hypothesis falsified.** It is not memory
  parallelism: doubling loads without the branch gives **-4.3%** (worse). `hoist_seq` has the
  **same arithmetic** as the default (128 v_sin, 128 v_cos) and only 32->2 divergent branches,
  95->2 exec-mask operations: **-67.0%**. The AMD backend derives 32 divergent branches from a
  select, a choice that never pays off when the condition always splits the wave
- [x] **Coalesced LDS staging is the worst result of the phase**: +109.8% / +99.9% /
  +93.0% on three shaders. The occupancy cost exceeds the coalescing gain
- [x] Produced `search_history.csv`, `accepted_variants.csv`, `rejected_correctness.csv`,
  `accepted_correctness.csv`, `isa_dedup.csv`, `confirm_detail.csv`, `causal_bdiv.csv`,
  `best_variants.md`
- [ ] Not done: automatic generation of transformations (in 2I I propose them); predictor
  on divergent regions / waitcnt per memory op / LDS bytes per group

### 2J - Feature-Guided Transformation Predictor -> `research/19_predictor/` COMPLETE (positive)
- [x] **Transformations are now mechanical**: the shader is an IR (`tools/ir2j.py`), each
  transformation is an IR->IR function, the HLSL is generated by the program. Check: the emitter
  reproduces 2I's `bdiv__hoist_parity` mechanically. **17 transformations, 10 rules**
- [x] Split declared BEFORE the rules: **6 dev** (already measured in 2H/2I) + **8 validation**
  never used to build them, 3 of which are deliberate traps
- [x] Separate features: 21 source (from the IR) + 9 DXIL (`dxc -Fc`) + 15 ISA (RGA) + estimated
  occupancy. The predictor sees **only the baseline**
- [x] **ANSWER: yes, ~4x fewer attempts.** Guided with budget **2** (-37.18%) beats random
  with budget **8** (-35.03%). With budget 5 it finds **the exact optimum on 7 shaders of 8**, and
  on those 7 random never beats it (P=0.000 over 4000 draws). Hit rate 62.5% vs 36.5%
- [x] **The credit is NOT the rules'**: rules alone = 80.1% of the oracle versus **77.7% for
  random**. With the evidence measured on the devs: **96.9%**. The system works because it remembers
  measurements, not because it reasons
- [x] **Online learning = zero** (C identical to B): with 8 shaders and budget 5 there is not
  enough transfer. Clean negative
- [x] The two defeats are the same mistake, **rules deduced by reasoning instead of measuring**:
  R2 ("uniform condition -> hoisting useless") is FALSE, on `v_cond_uniform` hoisting is worth
  **-46.26%**; R5 ("live array -> no unroll") holds at n=24/48 but **not at n=16**, where unroll
  is worth -16.16% (`v_pipe16`, the only shader where random beats guided)
- [x] "Catalogue order" control (97.4%) reported but **declared invalid**: I wrote that order
  and it contains the same priors
- [x] **Correctness found 10 of MY bugs in 112 variants**, none of the compiler's: wrong LDS
  staging index; `tg32/tg128` **semantically invalid** when the condition reads
  `gid.x`; modulo-4 hoisting emitted with 2 branches instead of 4. After the fixes 112/112
- [x] 3-level dedup: 14 variants of 140 eliminated before measuring them
- [x] Produced `shader_features.csv`, `transform_proposals.csv`, `search_history.csv`,
  `validation_results.csv`, `budget_sweep.csv`, `correctness.csv`, `dedup.csv`,
  `predictor_vs_random.md`
- [ ] Not done: real shaders captured from a DX12 workload; `v_pipe16` remains unsolved (I did not
  adjust the rules to make it pass, that would have been fitting on validation)

### 2K - Generalisation on REAL shaders + measurement memory -> `research/20_real/` COMPLETE
- [x] **Real corpus**: DirectX-Graphics-Samples (Microsoft) + FidelityFX-SDK (AMD), cloned
  shallow+sparse. 476 HLSL files -> 66 compute entry points that compile standalone -> 64 unique
  -> **64/64 executable** -> 58 measurable -> **34 dev / 24 REAL_VALIDATION** (split by hash,
  fixed before any ranking)
- [x] **New generic bench** (`bench2.cpp`): root signature **synthesised from the binding table
  read in the DXIL**, dummy resources typed per slot (Texture2D/2DArray, CBV,
  sampler, structured/raw/counter buffers). Verification dump extended to RWTexture2D,
  without which correctness would have been empty for most of these shaders
- [x] Persistent **measurement memory**: `measurement_memory.csv`, 216 rows with baseline
  features, transformation, parameters, two-tier correctness, Delta%, SE, workload,
  dataset, DXIL hash, VGPR/SGPR/LDS/branch/waitcnt/load-use/clause, validity
- [x] **Evidence-only** predictor: kNN (k=5) on normalised features, weighted mean of the
  Deltas observed on similar devs. No hand-written rules
- [x] **ANSWER: yes, ~2.5x.** Memory with budget **2** (-7.02%) = random with budget **5**.
  At budget 1: memory **-6.57%** versus random **+1.59%** (a regression on average)
- [x] **Smaller advantage than on the synthetic corpus (2J: 4x), for a structural reason**: on
  arbitrary HLSL only loop attributes, wave size and numthreads remain mechanically safe ->
  **3.6 transformations per shader** versus ~11 on the IR. The structural transformations that in
  2I/2J were worth -30%/-70% need a real HLSL AST: **not implemented**, not omitted
- [x] **Method error found and fixed**: `tg*` gave false -50% on
  `numthreads(1,1,1)` shaders with idempotent writes. The correctness gate **could not**
  catch it (identical result, different work). Added a mechanical invariant: the
  transformation must **preserve the total number of threads**. 9 measurements invalidated
- [x] **The synthetic corpus had taught something false**: in 2F/2H `wave64` was **always**
  worse (+7%..+20%). On real shaders it is the **most often accepted** transformation
  (23/51, best **-49.86%**); `wave32` remains a no-op (0/51)
- [x] **Real gains on unmodified Microsoft/AMD code**, all with *strict* correctness:
  `BitonicPreSortCS` **-77.43%** with `[unroll(4)]`, `ParticleSpawnCS` **-49.86%** with wave64,
  `DoFPass2CS` -17.85%, `DebugDrawHistogramCS` -15.27%. **12 shaders of 24** with at least one
  accepted variant; correctness rejection 4.7%
- [x] "Rules only" baseline (-8.47% at budget 2-3) **declared invalid**: I wrote the order
  after seeing 2J. The only clean baseline is random
- [x] Produced `REAL_GENERALIZATION.md`, `measurement_memory.csv`, `shader_features.csv`,
  `transform_proposals.csv`, `validation_results.csv`, `corpus.csv`, `probe.csv`,
  `PHASE_2L_DESIGN.md` (designed, **not executed**)
- [ ] Not done: HLSL AST for structural transformations; real data instead of dummy
  resources; ISA-level dedup on variants (RGA cost)

### 2L - End-to-end optimisation on a real workload -> `research/21_workload/` COMPLETE (negative)
- [x] **Real workload built from source**: MiniEngine ModelViewer (DirectX-Graphics-Samples),
  Sponza scene, MSBuild toolset v145, Profile configuration. Selection criterion declared
  BEFORE profiling; 51 of the 58 shaders in the 2K corpus come from MiniEngine
- [x] **Instrumentation added to the app**: headless benchmark mode, CSV export of the GPU timer
  tree, mean over ALL frames (StatHistory averages only the last 64), VSync off with
  fixed 1/60 time step. **Run-to-run frame spread from 18.03% to 1.13%**
- [x] Baseline: **GPU frame 1.0680 ms**, 2000 frames after 400 warm-up, 7 runs
- [x] **Ranking by real cost**: `Render Color` **48.71%** of the frame (pixel/vertex, OUTSIDE the
  2K corpus, which is compute only). The reachable compute passes add up to ~33%
- [x] **ANSWER: no, end-to-end gain zero.** Two integrations: `bitonic` set
  (micro -79.9%/-51.2%) -> pass **+1.24%**, frame **-0.27%**; `culling` set (micro -76.4%/-65.8%)
  -> pass **+1.83%**, frame **+0.35%**. Both within noise, both with the pass WORSE
- [x] **Cause 1: optimised shaders the app does not run.** `BitonicPreSortCS`/-77% comes from
  `D3D12RaytracingFallback`, not MiniEngine; `Sort()` is called with
  `IsPartiallyPreSorted=true` (PreSort never dispatched); and a `ScopedTimer` inside
  `BitonicSort::Sort` **never appears** in the profile: the scene uses the tiled rendering path
- [x] **Cause 2: 2K's correctness rejections were FALSE NEGATIVES.** The **same `.cso`
  measured twice** gives different output on `ParticleBinCullingCS` (max rel 0.38),
  `ParticleLargeBinCullingCS` (0.18), `ParticlePreSortCS`: they are **non-deterministic** (append
  buffers/atomics). 2K's gate was measuring their non-determinism, not the transformation
- [x] **Cause 3: the gain inverts.** Micro at ~1 M threads with fake resources versus
  `DispatchIndirect` with data-derived counts and few particles: -76% -> +1.83%
- [x] **The image oracle falls too**: the UNMODIFIED build gives **2 distinct hashes over 6 runs**.
  My earlier tests (3 and 4 runs) were too short. All "different image" verdicts of
  this phase are uninterpretable
- [x] Amdahl computed before each integration; `[WaveSize]` not testable because the app
  compiles at SM 6.2 and 6.6 is needed
- [x] Produced `PHASE_2L_RESULTS.md`, `baseline_profile.csv`, `pass_ranking.csv`,
  `ab_bitonic.csv`, `ab_culling.csv`
- [ ] The three fixes to make before redoing the phase: build the corpus from the shaders the
  workload **runs** with their **real** dispatches; test baseline determinism
  before any numerical gate; reproduce the real dispatch in the microbenchmark

### 2M - Runtime-First Hot Shader Optimization -> `research/22_runtime/` COMPLETE (negative, informative)
- [x] **Clean environment verified** (Chrome/Discord closed, 0 noisy processes). GPU frame
  spread 0.5-1.4% over 5-7 runs
- [x] **Runtime inventory inside the app** (`Core/ShaderInventory.{h,cpp}`): scope -> PSO -> FNV-1a
  hash of VS/PS/CS bytecode -> calls/frame -> real dispatch/draw sizes.
  **40 shader instances actually executed, 40/40 mapped to source**
- [x] **Mapping must be done by HASH, not by name**: the `Render Color` PSO is called
  "Sponza: Depth PSO" because MiniEngine does `m_ModelPSO = m_DepthPSO` and the copy carries the name.
  Only the hash identifies `ModelViewerPS` (12,612 bytes, confirmed by compiling with DXC)
- [x] **Real ranking**: `Render Color` **48.71%** of the frame (PS `ModelViewerPS` + VS
  `ModelViewerVS`, 28.90 draws/frame); the first 7 passes make up **76%**
- [x] Optimizer extended to **pixel shaders**: `Lighting.hlsli` (22 loops, included ONLY by
  `ModelViewerPS`), transformations applied, app rebuilt, clean A/B
- [x] **ANSWER: no.** `all_unroll4` **+0.61%** on Render Color, `all_loop` **+0.36%**.
  No gain
- [x] **The why, measured not assumed.** Two Amdahl probes: removing all 128 local
  lights -> **+0.36%**; zeroing **the whole pixel shader** (`mrt.Color = 0`, bytecode from 12,612
  to ~4,900 bytes) -> **+0.66%**. **`Render Color` is not limited by pixel-shader ALU.**
  Comparison: `Opaque` draws the same geometry with the same 28.90 draws without PS and costs
  0.032 ms versus 0.520 ms — but that 16x is not in the shader code
- [x] **My defect (a)**: after changing the layout of the `PSO` class, the incremental
  build left Model/ModelViewer not rebuilt -> access violation. `-t:Rebuild` is needed
  after every change to a shared header
- [x] **My defect (b)**: the image oracle introduced in 2L **is broken** — with the PS forced
  to black the dump is byte-identical to the baseline. **All "identical/different image" verdicts
  of 2L and 2M must be discarded.** I have no frame-level correctness check; I state it
  instead of inventing one
- [x] Produced `PHASE_2M_RESULTS.md`, `runtime_inventory.csv`, `shader_map.csv`, `hot_ranking.csv`
- [ ] Not done: compute replay with real dispatches (the data is in `runtime_inventory.csv`);
  understand with hardware counters what really limits `Render Color` (render-target bandwidth? ROP?
  texture?); repair the end-to-end correctness oracle

### 2N - Hardware bottleneck classification -> `research/23_bottleneck/` COMPLETE
- [x] **Counters ENUMERATED, not guessed**: `gpaenum.exe` opens a GPUPerfAPI DX12 context and
  finds **145 real counters on Navi 21** in 13 groups. 31 were enabled (13 passes)
- [x] **GPUPerfAPI 4.4.5 integrated into the application** (`Core/GpaProfiler.{h,cpp}`), hooked
  to the profiler scopes and to the command-list lifecycle. RGP remains unusable from the CLI
- [x] **CLASSIFICATION**:
  `Render Color` 48.7% -> **texture-unit throughput bound**;
  `Resolve Image` 9.5% -> **memory bandwidth bound**;
  `Render Shadow Map` 4.5% and `Z PrePass` 3.0% -> **raster/geometry bound**;
  `Culling & Sorting` 4.4% -> **latency/serialization bound**;
  `Sharpen or Copy` 3.3% -> **bandwidth bound**; `Generate SSAO` -> **memory latency bound**
- [x] `Render Color` is texture-bound and nothing else, by exclusion from the numbers: TexUnit **94.6%**
  busy with only **0.4%** stall; ROP `PSExportStalls` 0.01% and `WriteUnitStalled` 0.00%;
  raster `PAStalledOnRasterizer` 0.2% (versus 49-52% for the truly raster-bound passes); bandwidth
  **73 GB/s** versus 555 and 621 GB/s for other passes in the same frame. With L0 at 97.6% the
  limit is the **filtering rate**, not byte transport
- [x] **SERIOUS BUG FOUND IN MY TOOLS**: checking the executable's hash I discovered
  that a build with a modified shader produced an **identical binary with the same mtime** — MSBuild
  was silently skipping recompilation (timestamp granularity). The same binary was being
  measured twice
- [x] **Retroactive corrections to 2M**: (a) "zeroing the pixel shader does not change Render Color" has
  **invalid evidence**, but the conclusion *not ALU-bound* is confirmed independently by the
  counters; (b) "the image oracle is broken" is **RETRACTED**: the identical dump was explained by the
  identical binary
- [x] Remedy: `tools/buildv.py` with `-t:Rebuild` and a check on the hash of the **compiled shader
  header** (deterministic; the executable's is not, it changes at every link)
- [x] **About 12% of the frame (raster + serialisation) is not reachable by any
  shader transformation.** Render Color's 48.7% is, but only by reducing the **number of
  sampling operations** — not with loop attributes, the only thing the catalogue can do
- [ ] Not done: the ablation controls (empty PS / no textures / single render target)
  fail compilation with `-t:Rebuild` and the cause is not diagnosed; `HDR Tone Mapping`
  produces no data (scope not registered by the GPA hook); `CSBusy`/`CSVALUUtilization` were not
  in the enabled set

## 2O — Handoff audit and ablation gate (2026-09-05)

- [x] Read-only audit of sources/data, history, toolchain and real clones; output in
  `research/CODEX_HANDOFF_AUDIT.md` and `research/handoff_audit_20260905/`.
- [x] Offline mapping: 40/40 scope/stage/hash associations in the historical CSV match
  the current headers; this is not yet proof that a new variant propagates.
- [x] Preregistered plan in 8 steps, at most 6 cycles, §7 of the audit.
- [x] **Build gate — PASSED** (2026-09-06). `tools/test_buildv.py`: 17 failure modes out of 17
  rejected without a GPU (process error, missing/ambiguous header, unchanged hash, unexpected hash,
  corrupted bytecode, wrong runtime PSO). Recompiling the PS through the chain yields the
  historical artifact again: **12,612 bytes, `52CE6C5E64AB2E82`**.
- [!] **GPA gate — cannot be passed with 2N's instrumentation.** That set needs 13 passes;
  among the 145 *derived* counters none separates filtering rate from cache/latency/ALU and
  none exists for pixel-stage ALU. `25_gpa_validity/GPA_VALIDITY.md`.
- [x] **Option (a) executed — raw counters available** → `research/26_gpa_hwcounters/`.
  `kGpaOpenContextEnableHardwareCountersBit`: **145 → 4001 counters**, verified offline (virtual
  context, device `1002:73A5:C0`) **and live** (real DX12 context, RX 6950 XT); the two sets of
  names are identical. **96 `SQ` counters masked `PS`** (`INSTS_VALU`, `INST_CYCLES_VALU`,
  `ITEM_CYCLES_VALU`, `INSTS_SALU`, `INSTS_TEX_LOAD/STORE`, `WAVES`/`WAVES_32`/`LEVEL_WAVES`) and
  **14 `TA` events × 80 CUs** (`TA_BUSY`, `ANISO_{1..16}_CYCLE_QUADS`, `MIP`, `VOL`). `TD` exposes
  only ray-tracing BVH. **Measured pass counts:** 36 `SQ_PS*` = **1**; `TA_BUSY` × 80 CUs = **1**;
  full `TA` distribution = 7 (`TA` holds 2 events/pass); `SQ`+`TA_BUSY` = 2; +`GPUTime` = 3.
  Cost depends on events per block, **not** on instances → per-CU coverage for free.
  **Option (c) not needed.** No counter has been read from a workload yet.
- [ ] To fix before any capture: 10 ignored GPA return codes, `Begin`/`OnContextBegin`
  order, `ComputeContext::Begin` that never registers, `Shutdown()` never
  called. And pin the semantics of the raw counters to AMD documentation before
  interpreting their numbers.

### O1 — build propagation ✔ **PASS** (cycle 1/6) → `research/24_phase2o_build_gate/`

- [x] `O1_20260906_010146`. A baseline → B canary → A2 restore, all with the bytecode SHA-256
  **preregistered before the build**.
- [x] Bytecode present **exactly once** in `Model.lib` and `ModelViewer.exe`;
  **34 draws** of `Render Color` with the expected PSO hash on 2 native PSOs, 836,757 indices.
- [x] Canary detected **as a value**: 100.00% of pixels, R channel only, all positive,
  median decoded delta **+0.124268** (= +0.125 quantised in R11). G and B unchanged to the bit.
- [x] A2 reproduces an image **bit-identical** to A with an executable of different SHA-256 → the build
  really happened. Direct check of the 2N defect "MSBuild skipped recompilation".
- [x] Baseline spread **measured 0 over 3 processes**. Recorded as measured spread, **not**
  as determinism: `FillLightGridCS.hlsli:163` uses `InterlockedAdd`, the mechanism exists.
- [x] Capture at frame 140: `RenderLightShadows` copies **one** slice out of `MaxLights=128` per frame.
- [x] **14 defects removed before the cycle.** The tlog `CL.read.1.tlog` cannot contain the generated
  header (FileTracker excludes outputs and Packages: **this is the cause of the
  `dxc.write.1.tlog` anomaly, not timestamps**); `-MD` puts DXC in dependencies-only mode;
  a regex that truncated `.hlsli`; `inline constexpr` in a C++14 build. Full list in the report.
- [x] **3266 files of the original clone re-verified, 0 modified.** No deletes, no Clean.

### O2 — semantics, workload identity, baseline ✔ **PASS** (cycle 2/6) → `research/27_o2_counters/`

- [x] `O2_20260906_014011`. Shader **unmodified** (same SHA-256 as O1), no ablation,
  no performance verdict. 4 sessions: `sq_ps` (32 counters, 1 pass), `ta_busy` (80, 1),
  `crosspass` (85, 2), `aniso` (721, 5); 8 samples on consecutive frames from 140.
- [x] **Aggregation validated by measuring, not reading**: `CPF_STAT_BUSY`=`GPUBusyCycles` exact;
  `TexAveAnisotropy`=exact weighted mean (1.2181); `TexUnitBusyCycles` **is not the sum** of the 80
  `TA_BUSY` but the **maximum**, and `TexUnitBusy%`=`max/GPUBusyCycles·100` exact (94.627017).
- [x] **Workload identity**: aniso bucket totals **bit-identical over a
  5-pass session** (40 frames); `ITEM_CYCLES_VALU` exact everywhere. Cross-pass `Σ TA_BUSY`: 0.43%
  difference versus 1.72% frame-to-frame noise → **PASS**.
- [x] Preregistered identity criterion (0.1% on every counter) **FAILED** and reported as
  such: it was too coarse, mixing aggregate work, per-instance work and timing.
- [x] **Baseline**: PS waves 39,214, **`WAVES_32`=0 → pixel shader in wave64**, VALU 71.0 M inst /
  183.2 M cycles, `INSTS_TEX_LOAD` 6.12 M, `Σ TA_BUSY` 89.0 M, `GPUTime` 802 µs (±19.9%),
  11.22 M aniso quads with mean 1.2181 samples/quad. 14.56 TA cycles per PS texture instruction.
- [ ] Not established: `TA_BUSY` **is not attributed to a stage** (needs a session with
  `SQ_VS*_PERF_SEL_INSTS_TEX_LOAD`); the `INSTS_TEX_LOAD`↔quad↔`TA_BUSY` link is not a clean
  identity; `{emulated}` counters are worth ±0.4%.

### O3 — material sampling ablation ✔ (`research/28_o3_material_ablation/`)
- [x] 4 builds (`mat0..mat3`), each gated on a bytecode SHA-256 **preregistered offline
  before** any build ran. Type-preserving substitutions at the sample site.
- [x] **Exact dose**: 1.06 / 2.07 / 3.34 texture instructions removed per PS wave out of **155.9**.
  The three material samples are **2.1%** of the pixel shader's texture instructions; the
  other ~153 are the light and shadow-map fetches of `ShadeLights`. Anyone expecting "the material
  textures" to dominate this pass was wrong by a factor of ~50.
- [x] **Confounder quantified, not assumed**: `mat3` is not a texture-only ablation — it removes
  2.1% of texture and **11.3% of VALU**, because the TBN maths that consumed the values dies too.
  `mat1` is the useful point: texture down, ALU **up** by 0.55%.
- [x] Monotonic response: Δ`TA_BUSY` −2.33 / −5.71 / **−13.91%**, Δ`GPUTime` −1.53 / −3.39 /
  −11.43%, with A/A threshold max(2%, 3×1.03%) = 3.09%. **The 3 material samples cost 13.9% of the
  texture unit's busy cycles while being 2.1% of its instructions.**
- [x] **Instrumentation defect found**: per-shader-engine SQ counters are sometimes
  corrupted (SE0 and SE2: values of one event under the name of another, bit-identical to a
  different session). New gate `tools/sq_validity.py`; O3 doses use only SE1+SE3. No earlier
  conclusion is affected (O2's `sq_ps` session passes the gate; TA counters are healthy).
- [x] Does not establish "texture-filter-throughput bound": it establishes that a verified reduction
  of texture-unit work gives a **proportional but damped** time reduction (0.59–0.82).

### O4 — sampler-only ablation ✔ (`research/29_o4_sampler/`) — **falsifies 2N**
- [x] 5 builds (`s_base`, `s_aniso1`, `s_aniso16`, `s_point`, `s_bilinear`): **only** the
  static sampler in C++ changes, the pixel-shader bytecode is **byte-identical** in all of them
  (`52CE6C5E64AB2E82`) and the gate enforces it. Scope verified in the source: inside `Render Color`
  only the opaque+cutout Sponza draws run, and they sample **exclusively** via `defaultSampler`.
- [x] **ALU held fixed and verified**, not just argued: `INSTS_VALU`, `INST_CYCLES_VALU`,
  `ITEM_CYCLES_VALU`, `INSTS_TEX_LOAD`, `WAVES` unchanged within **0.07%**, with all 4
  shader engines healthy under O3's gate.
- [x] Dose: aniso histogram **collapsed** (mean 1.2181 → 1.0000), **−17.9%** of aniso cycles,
  quads constant within 0.06%.
- [x] Response: Δ`TA_BUSY` −2.73 / −3.50 / −3.54%, Δ`GPUBusyCycles` −2.20 / −2.63 / −2.78%,
  Δ`GPUTime` −2.31 / −2.86 / −2.52%. Per-metric thresholds from the A/A control: `GPUBusyCycles` 2.00%
  (they pass), `GPUTime` 3.88% (does **not** pass). Conservative co-primary verdict: **reduction of
  `TA_BUSY` and `GPUBusyCycles` established, time reduction suggestive but not confirmed.**
- [x] **RESULT**: switching anisotropic filtering off entirely — and in `s_point` dropping to the
  cheapest filter the hardware has — moves `Render Color` **by at most ~3%**. 2N's hypothesis
  "`Render Color` is texture-filter-throughput bound" predicted a large effect: **it is not
  supported**. The texture unit is 94% busy, but not *filtering*.
- [x] **Bidirectionality failed and declared as such**: the upward arm (`s_aniso16`) produces
  only +0.71% dose because the content almost never asks for more than 8×. Its null
  falsifies nothing; only the downward arms count.
- [x] **No O3/O4 cost partition**: 3.50/13.91 = 25% compares two **different** interventions,
  it is not a "25% filtering / 75% rest" decomposition: additivity never measured.
- [x] Defects found and reported: `CubeMapSamplerDesc` is a copy of `DefaultSamplerDesc` so it
  also changed `s12` (out of scope, no number affected, but the written invariant was false);
  `defaultSampler` is also used by `DepthViewerPS`/`SkyboxPS` out of scope and can warm the
  cache differently; **identical DXIL does not guarantee identical native ISA** (the driver sees the
  root signature at PSO creation) — answered by the ALU measurement above.
- [x] **Independent audit by Codex** (via herdr): dose and response recomputed from scratch from the raw
  CSVs and reproduced; the three defects above, the rejection of bidirectionality and the refusal
  of the 25/75 partition come from there and were adopted. Kept in `29_o4_sampler/audit/`.
- [ ] Not measured: TCP/TCC/cache counters. Part of the −3.5% may be reduced memory traffic
  instead of filtering. O4 measures the cost of the whole sampler path.

### O5 — stage attribution + cache/memory classification ✔ (`research/30_o5_memory/`)
- [x] **No build**: reused O4's 5 executables (SHA-256 re-verified at prepare and at every run),
  only the counter sets change. O4's sampler variants thus become a **memory-traffic lever
  at byte-identical bytecode**. Passes measured offline before running:
  `tcp_ta` 320 counters/**1 pass**, `l1l2` 96/**1**, `dram` 144/**1**, `stage_tex` 16/2, `stage_all` 56/7.
- [x] **Stage attribution closed, but a control was needed to close it.** `SQ_VS*` reads
  zero waves and zero texture: on its own it does not distinguish "the vertex stage does not sample" from "the vertex
  stage does not run under that mask". Sweep of **all 8 masks**: vertex work sits
  under `GS` (NGG primitive shader), 9,596 waves, and **issues 28,852 texture instructions = 0.47%**
  (3.007 per wave: a 3-stream attribute fetch — `INSTS_TEX_LOAD` also counts buffer loads).
  Preregistered prediction <1% → **PASS**; all texture ratios of O2/O3/O4 hold within 0.47%.
- [x] **It is not the L0 cache**: `Σ TCP_TA_REQ_STALL / Σ TA_BUSY` = **0.24%** versus a
  preregistered "not the cache" band of ≤10%. The counter is not dead: the sampler intervention moves
  it as its meaning requires (TCP req −12%, L0 miss −30%, stall −24%).
- [x] **It is not miss traffic nor DRAM**: L0 hit **97.66%**, 0.21 misses per texture
  instruction; **31.88 MB read = 39.6 GB/s**, versus the 555–621 GB/s 2N measures on other passes
  of the same frame. **Cross-check**: L2 misses × 64 B = 31.90 MB versus 31.88 MB computed
  independently from `EA_RDREQ_*` → **0.06% gap**, and this is the proof that the reading
  of the hierarchy is reliable.
- [x] Key numbers: **156.0 texture instructions per PS wave**, **14.51 `TA_BUSY` cycles per
  instruction**, 9.07 L0 requests per instruction, **TA duty cycle 93.25%** (consistent with
  O2's `TexUnitBusy` 94.63%, which is the *maximum* over the 80 CUs).
- [x] **Correction added after O6**: the "what is still standing" section listed only candidates on the
  texture path, and read as if the texture path were *the* limit. It is not: pixel-shader
  ALU was a fifth candidate never tested there.

### O6 — replication/falsification at fixed bytecode ✔ (`research/31_o6_lightcount/`)
- [x] Lever: **number of lights surviving culling**, C++ data in `CreateRandomLights`
  (`radiusSq = 0` by index stride, so the sphere/cone/shadowed-cone mix stays
  proportional and the surviving lights are bit-identical). 4 builds, 4 distinct executables,
  **a single bytecode** (`52CE6C5E64AB2E82`) enforced by the gate.
- [x] **Dose measured, not deduced from the stride**: texture instructions per wave 155.99 → 100.86 →
  49.92 → 33.40 (−35.4 / −68.1 / −78.6%), with waves constant within 0.19%. The 155.99 reproduces
  O5's 156.0 exactly from a different build and session.
- [x] **REPLICATED on both preregistered bands**: Δ`TA_BUSY`/Δtex = **0.94 / 0.90 / 0.90**
  (band [0.75–1.25]) and **13.6 / 13.1 / 13.1 cycles** per removed instruction (band [10–19],
  O5's prediction: 14.5). The pass drops by **−32.5 / −60.2 / −69.4%** of `GPUBusyCycles`.
- [x] Linear fit: `GPUBusyCycles` = 0.1710 × (texture instructions) + 139,365 → **88.2% of the pass's
  cycles scale with the instruction count**; for `TA_BUSY` 90.4%.
- [x] **MY ERROR FOUND AND FIXED IN THE SAME DRAFT**: I had divided `INST_CYCLES_VALU` by
  320 SIMDs (GCN layout) instead of **160** (RDNA2 has 2 SIMD32 per CU). VALU duty is not
  48.3% but **96.64%**. The check that exposes it: ÷80 would give an impossible 193%.
- [x] **Consequence, which weakens the conclusion**: at baseline the pass is **co-saturated** —
  VALU 96.64% and texture addresser 93.61%, with ALU *marginally higher*. O6 **cannot
  rank** texture above ALU: both drop with the same loop. As the loop gets
  shorter they diverge (VALU 96.6→71.8%, TA 93.6→88.5%).
- [x] `GPUTime` unreliable here (N95 13.99%): the first process of each batch runs at a lower
  clock (1.476 vs 1.688 cycles/ns) while `GPUBusyCycles` moves <0.7%. Conclusions on
  `GPUBusyCycles` and `TA_BUSY`.
- [x] Two `prepare` runs rejected and kept (`_SUPERSEDED_prepare_01/02`): manifest not
  overwritable (a gate that works) and `experiment_id` not matching the workspace name
  (which would have failed every build). **Neither built or measured anything.**

- [x] **Independent audit by Codex (via herdr)**: dose, elasticity (0.935/0.905/0.904), marginal
  cost (13.576/13.132/13.117) and the 4-point OLS fit reproduced to the sixth digit. It
  found **on its own the same SIMD-divisor error** (citing the RDNA2 ISA) and added
  four adopted corrections: the 13.1 cycles are unit-cycles summed over 80 TAs and **not** pass
  duration cycles (that is 0.171 `GPUBusyCycles`/instruction); R²=0.9996 says the arms lie
  on a line, **not** that textures cause the duration; an ALU-bound hypothesis survives all of
  O6 through two concrete mechanisms (each iteration carries stable TA work with it; removing
  iterations shortens the waves); the `TCP→TA` result excludes *that* back-pressure, not
  memory latency in general. Kept in `31_o6_lightcount/codex_audit_o5_o6.txt`.


**PHASE 2O CONCLUSION.** `Render Color` is dominated by the **per-light loop of `ShadeLights`**:
**88% of the pass's GPU cycles lie on a line in that loop's work** (R²=0.9996 over 4 arms),
and at baseline that loop leaves **both** pixel-shader VALU (96.6%) **and** the texture
addresser (93.6%) close to saturation. Four alternative explanations eliminated **by measurement**,
each within its declared scope: texture filtering (O4, ≤3%), `TCP→TA` back-pressure (0.24%),
L0 miss traffic (hit 97.66%), DRAM bandwidth **saturation** (39.6 GB/s out of 555–621). Bandwidth
saturation is excluded, **not** memory latency in general: no counter measures it.
**Not established:** which of the two saturated units is binding at baseline — they are 3
points apart and every O6 arm moves them together, so all of O6 is compatible with an ALU-bound pass
in which each removed iteration takes 13.1 addresser cycles with it. O4 is the only arm of the
phase that moved just one (texture, at fixed ALU) and it is worth 3.5%. The mirror of O4 would be needed,
an arm that moves only ALU — ideally a factorial ALU × texture design: it was not
run.
**What it means for the initial question:** the localisable cost is the **number of texture
and ALU operations the shading algorithm issues per pixel** (the 10-tap PCF kernel of
`GetDirectionalShadow`, the per-light fetches of `ShadeLights`). It is a property of the application,
**not** a driver setting, a compiler flag, a sampler state or a cache
configuration. 2E–2K had already established that no codegen lever is reachable from outside the driver;
2O adds that on this workload the reachable cost was never in codegen to begin with.

### 2P — per-light loop optimiser ✔ COMPLETE (`research/33..39`, 8 cycles)
- [x] **Clean-room replication of 2O** on a machine verified idle (GPU 1.69%): work counters
  at **+0.00%** and **+0.01%**, O4 and O6 arms within tolerance by one to two orders of magnitude.
  **CLEAN_REPLICATION = PASS**: background load was not driving any 2O conclusion.
- [x] Hypotheses from the real ISA (RGA gfx1030, root signature reconstructed): `(gloss+2)/8` is **already**
  hoisted by the compiler; `FSchlick`'s `pow(x,5)` is **not** — it comes out as `v_log`+`v_mul`+`v_exp`.
- [x] **Four transformations accepted**, all with a **bit-identical** image: `fresnel5`
  (−3.17%), `shadowskip` (−5.48%), `falloffskip` (**−27.59%**), `scalar` (−3.84%, enables the
  `SCALAR_BRANCH` path that the engine shipped disabled).
- [x] **Best variant `stack3_scalar`: `Render Color` −41.60%** (GPA cycles) / **−40.34%**
  (engine timer, independent instrument), **GPU frame −24.39%** (≈−21.7% net of a
  quantified clock effect), **byte-identical image**. 68 diff lines, a single HLSL file.
- [x] **2O's missing arm was provided**: `fresnel5` moves ALU at fixed texture
  (−0.08%) and the pass follows by −3.17%; O4 moved texture at fixed ALU and the pass followed by
  −2.6%. **Both saturated units are on the critical path, neither dominates.**
- [x] Correctness: `ndotlskip` **rejected** by the preregistered criterion; the criterion itself was
  however unachievable (1 ULP of R11G11B10 is worth ~1.6% relative) and is replaced **going forward**,
  without touching the verdict already issued. Null control `base_pad` (different bytecode, same
  work): **+0.01%**.
- [x] Generality measured: at a quarter of the lights the gain **drops to −20.19%** but remains.
- [ ] Not separated: how much of the gain comes from occupancy rather than removed work — two
  failed attempts (`LEVEL_WAVES` returns an impossible value identical on every build; the
  padding is rematerialised by the compiler). Remaining argument: three variants in the same
  VGPR bucket range from −3% to −37%.
- [ ] Not proven: full-precision equivalence (the oracle is a quantised target) and
  generality beyond this scene. → `research/PHASE_2P_FINAL_REPORT.md`

### 2Q — full-precision equivalence ✔ COMPLETE (`research/40..42`)
- [x] Diagnostic capture in `R32G32B32A32_FLOAT` (env-gated, `ME_Q_R32`): float32 determinism
  verified, then each transformation judged on its own.
- [x] `SCALAR_BRANCH` **bit-identical in float32**; the rest within **7 ULP** and **4.4e-7**
  relative, **zero NaN/Inf/−0**.
- [x] `fresnel5` verified **exhaustively on all 1,065,353,217 float32 of its domain**:
  never beyond **3 ULP** from the true value (double-precision reference) versus **8,388,608 ULP**
  for `pow(x,5)` — the transformation is **more accurate** than what it replaces.
- [x] Data contract **measured** with a canary: never fired on any light of any pixel.
- [x] Final 7-process replication: `Render Color` **−41.43%**; GPU frame **−24.47% measured** /
  **−21.78% clock-corrected estimate**, never mixed.
- [ ] No independent review (reviewer out of quota).

### 2R — generalisation to a second workload ✔ COMPLETE, negative outcome (`research/43..44`)
- [x] Selection criteria written beforehand; chose `D3D12nBodyGravity` (O(N²) n-body, compute, LDS).
- [x] Built, instrumented, gated; **A/A N95 0.05%**, exact oracle (particle state
  byte-identical over 5 processes).
- [x] Three ISA-driven transformations: `unroll4` **already done by the compiler**, `lds_float3`
  bit-identical but **+1.28% slower**, `mass_hoist` **−3.58% but rejected by correctness**
  (ill-conditioned sum, 164,301 ULP after **a single step**).
- [x] **No transformation accepted.** Negative result obtained with the same method.
- [ ] Bottleneck classified with a model, not with hardware counters.

### Adversarial review + freeze ✔ (`research/POC_FROZEN.md`, `47..48`)
- [x] Review on four declared targets: ULP/sweep **HOLDS WITH RESERVATIONS**, canary **BROKEN**,
  conditioning **BROKEN in its wording**, occupancy **HOLDS WITH RESERVATIONS**.
- [x] **Canary rebuilt** (Q4): v1 wrote the sentinel into the value that was then multiplied
  by zero, so it was blind exactly on the early-out paths. v2 propagates a mask
  set before every multiplication: **0 pixels out of 2,073,600**. Positive control (Q5):
  **2,073,600 out of 2,073,600** — v2's silence is evidence, not artefact.
- [x] Sweep provenance gap closed; every field reproduced identically with a tracked host.
- [x] **Provenance audit:** 64 builds, 422 runs, 22 cycles, **zero discrepancies**.
- [x] **2P/2Q/2R frozen** as a validated PoC, with the declared limits. No further
  optimisation on ModelViewer.

### 2S — infrastructure consolidation
- [ ] Not started; absorbed into the next proposed phase.

### 2T — hit rate of the method (proposal, just one)
- [ ] 3–5 D3D12 open-source workloads declared **before** looking at them, frozen pipeline left
  unmodified, and the question: **how often does it produce an accepted transformation?** Negatives
  included. It is the only thing that turns "it worked once and not twice" into a measured
  property of the method.

**Next action:** write `research/PHASE_1_REPORT.md` — the 14 questions and the ranked table
of optimisation surfaces, which can now be filled in with evidence instead of
hypotheses. The strategic paths and the log below are historical.

## Final report
- [ ] `research/PHASE_1_REPORT.md` — 14 questions + ranked table of optimisation surfaces

---

## Highest-value path (do first)

1E harness → 1C cache forensics → 1D cold/warm → 1F RGP on Wukong.
The goal is the chain `shader hash → cache blob → ISA → GPU cost`.
Even building it partially is worth more than months of driver decompilation.
1B/1K prepare the ground; they do not produce results on their own.

## Log

- **2026-09-03 (1)** — Reconnaissance: tools and paths verified, GPU/driver/OS confirmed, cache
  baseline counted (63/48/10 files). Wrote CLAUDE.md and PLAN.md. Wukong benchmark missing.
- **2026-09-03 (3)** — Phase 1.5. ETW pipeline built and validated (8 kHz, per-module and RVA
  attribution without symbols); Fortnite captures waiting for the operator. Targeted static analysis
  of the installed UMD: two routes closed with evidence (`GetSettingsBlobsAllDecoded` stub,
  `DXCTuningsFileName` on the KMD side) and one open and much more promising (shader compiler
  config via env var/file, 272 `SCOption_*`, ISA dump per shader hash).
  Produced `research/PHASE_1_5_DECISION_GATE.md`. **No changes to driver, cache, registry
  or environment.**
- **2026-09-03 (2)** — Phases **1A + 1B + 1E** completed on 7 Fortnite runs + 7 Steel Nomad runs
  supplied by the operator. Parser validated against PresentMon and 3DMark. Baseline noise established
  (±0.11% / ±1.3%). Driver package mapped with evidence (724 files). Discovered that the package is
  not the installed revision and that the DX12 UMD contains the shader compiler.
  Produced `research/PHASE_1_STATUS.md`, `01_driver_map/component_analysis.md`,
  `04_benchmarks/analysis/{METHOD,fortnite_baseline,steelnomad_baseline,baseline_comparison}.md`.
  **No changes to driver, cache, registry or system.**
- **2026-09-04 (8)** — Phase **2H**. Found that 2G's "−30%" was measured against a baseline
  with an `[unroll]` written by me: against **DXC's default** the gain is **zero**. Fixed two
  bench measurement defects (warm-up by iterations, duty cycle) worth up to 5.2×; the 2G set
  remeasured gives −16.3% and drops the third winner. Strong correctness on 20 datasets ×
  3 workloads with full output: the variants leave 1e-4 on 7 datasets, but **so does DXC's
  default**, so the shader is ill-conditioned. Cause determined with three controls
  (null/negative/positive): it is **load scheduling**, not occupancy or register pressure;
  confidence *strong*, stall counters not measured (RGP readable only from the GUI). Corpus of
  20 shaders: `[loop]` is a no-op, `[unroll]` improves 9 times and worsens 3, worst regression
  **+40.7%**. Produced `15_robustness/PHASE_2H_RESULTS.md` and `PHASE_2I_DESIGN.md`.
  **No changes to driver, cache, registry or games.**
- **2026-09-04 (9)** — Phase **2I**. First positive answer of the project: **9 variants of 23
  beat the real DXC/AMD default**, all on 3/3 workload/dataset combinations with
  10 processes each. The best, `bdiv__hoist_parity`, is **−69.5%** and is **strict**
  (max rel 4e−7). Made the bench self-check blocking: it failed on the first round and led
  to replacing the comparison between independent medians (noise 1.1–1.3%) with a **paired
  comparison with double reference** (SE 0.049%). The cause was isolated with 5 controls and
  my initial hypothesis — memory parallelism — was **falsified**: it is the number of
  divergent regions (32 → 2). On `pressure24` no variant beats the default: 7 tried,
  0 accepted. Coalesced LDS staging is the worst result of the phase (up to +109.8%).
  Produced `research/18_ai_search/best_variants.md`.
  **No changes to driver, cache, registry or games.**
- **2026-09-05 (10)** — Phase **2J**. Automated the *proposal* of transformations: shaders
  as IR, transformations as IR→IR functions, interpretable predictor on
  source/DXIL/ISA features. **Guided with 2 benchmarks beats random with 8** (~4× fewer attempts), and
  with budget 5 it finds the exact optimum on 7 validation shaders of 8. But the result that matters
  is another: **the hand-written rules alone are worth 80.1% of the oracle versus 77.7% for
  random** — all the advantage comes from measured evidence (96.9%). The two rules deduced
  by reasoning instead of measuring are exactly the ones that did damage. The correctness
  gate rejected 10 variants of 112, all due to bugs in my transformations, including
  a case where `tg32/tg128` is semantically invalid. Produced
  `research/19_predictor/predictor_vs_random.md`.
  **No changes to driver, cache, registry or games.**
- **2026-09-05 (11)** — Phase **2K**. The system leaves the synthetic corpus: 24 **real**
  compute shaders from DirectX-Graphics-Samples and FidelityFX-SDK, never seen, run with a
  generic bench that synthesises the root signature from DXIL bindings. **Measurement memory with 2
  benchmarks equals random with 5** (~2.5×); at budget 1 it finds −6.57% where random on average
  gets worse (+1.59%). Found real gains on unmodified Microsoft code, all *strict*:
  `BitonicPreSortCS` −77.43%, `ParticleSpawnCS` −49.86%. Two uncomfortable results: (a) on
  arbitrary HLSL only 3.6 mechanically safe transformations per shader remain, versus ~11
  on the IR, and that is what compresses the advantage; (b) the synthetic corpus had taught that
  `wave64` is always worse — on real shaders it is the most often accepted transformation.
  Found and fixed an artefact that correctness could not catch (`numthreads` that
  changes the work without changing the result). Produced
  `research/20_real/REAL_GENERALIZATION.md` and `PHASE_2L_DESIGN.md`.
  **No changes to driver, cache, registry or games.**
- **2026-09-05 (12)** — Phase **2L**. End-to-end chain walked in full: MiniEngine
  ModelViewer built from source, instrumented, profiled (GPU frame 1.068 ms, spread brought
  from 18% to 1.13%), optimised shaders integrated and recompiled, A/B measured. **The end-to-end
  gain is zero**: −0.27% and +0.35%, both within noise, with the target pass
  worse in both cases. The causes were isolated and are all concrete: (1) the
  biggest microbenchmarks were on shaders the app **does not run**; (2) 2K's correctness
  rejections were **false negatives** — those shaders are non-deterministic, the same
  binary gives different outputs; (3) where transformations were applied to executed shaders,
  the −76% became **+1.83%**, because the microbenchmark dispatches 1M threads with fake data and
  the app uses data-dependent DispatchIndirect. The image oracle falls too: the unmodified
  build gives 2 hashes over 6 runs. Produced `research/21_workload/PHASE_2L_RESULTS.md`.
  **No changes to driver, cache, registry or games.**
- **2026-09-05 (13)** — Phase **2M**. Applied the "profile first" rule: runtime inventory
  inside the app (scope → PSO → bytecode hash → calls → real dispatches), **40/40 shaders
  executed mapped to source by hash**. Identified without ambiguity the real
  bottleneck: `Render Color` = **48.71%** of the frame, pixel shader `ModelViewerPS`. Optimizer
  extended to pixel shaders and clean A/B: no gain (+0.61% / +0.36%). But the Amdahl probe
  gives the result that matters: **zeroing the whole pixel shader changes the pass by +0.66%** —
  that pass is not limited by shader ALU, so no source transformation can
  help it. Found two of my defects: inconsistent incremental build after changing the layout of
  `PSO` (access violation, `-t:Rebuild` needed) and a **broken image oracle** — with the PS forced to
  black the dump is byte-identical, so all image verdicts of 2L and 2M must be discarded.
  Produced `research/22_runtime/PHASE_2M_RESULTS.md`.
  **No changes to driver, cache, registry or games.**
- **2026-09-05 (14)** — Phase **2N**. Enumerated the **145 real hardware counters** of Navi 21 and
  integrated GPUPerfAPI inside MiniEngine. Classified the passes: **`Render Color` (48.7% of the frame)
  is texture-unit throughput bound** — TexUnit 94.6% busy with 0.4% stall, ROP and raster idle,
  and just 73 GB/s versus the 555–621 GB/s of other passes in the same frame. `Resolve Image` is
  bandwidth bound, `Z PrePass` and `Render Shadow Map` raster bound, `Culling & Sorting`
  latency/serialization bound. Also found a **serious bug in my tools**: MSBuild
  silently skipped recompilation when the source was written in the same second
  as the previous build, so the same binary was being measured twice. This **invalidates
  the evidence** of 2M's ablation and **retracts** the conclusion "image oracle broken".
  Remedy in `tools/buildv.py`. Produced `research/23_bottleneck/PHASE_2N_RESULTS.md`.
  **No changes to driver, cache, registry or games.**
- **2026-09-05 (15) — HANDOFF AUDIT.** Rebuilt the history and kept inventory/hashes/diffs/tlogs.
  Found build gates that were not fail-closed and runners not integrated, the GPA requirement of an identical workload
  not met, a wrong MRT/overdraw interpretation and 2K scoring contaminated by rejects.
  2N's texture-throughput classification goes back to being a hypothesis to test; the root cause of DXC
  tracking still to be diagnosed. Stop at the gate as per the brief: **0/6 cycles, no builds or measurements**.
  2O plan and criteria in `research/CODEX_HANDOFF_AUDIT.md`; log and session report produced.
  No changes to operational sources, driver, cache, Registry, security or games;
  no files deleted or personal applications closed.
- **2026-09-06 (16)** — **2O cycles O3 and O4.** O3: dose-response on the three material samples,
  with the dose measured (1.06 / 2.07 / 3.34 texture instructions per wave out of 155.9) instead of
  assumed, and the ALU confounder quantified (`mat3` also removes 11.3% of VALU). Result:
  those three samples are **2.1% of texture instructions but 13.9% of the texture unit's busy
  cycles**; the other ~153 fetches per wave are lights and shadow maps. Found an
  instrumentation defect — per-shader-engine SQ counters sometimes come back **corrupted** on SE0/SE2, with
  the value of one event under the name of another — and added the gate `tools/sq_validity.py`.
  O4: the same question without the confounder, changing **only the static sampler in C++** with
  the pixel-shader bytecode byte-identical and ALU verified unchanged within 0.07%.
  **Switching anisotropic off entirely, or dropping to point filtering, moves `Render Color` by at
  most ~3%**: the "texture-filter-throughput bound" hypothesis inherited from 2N is **falsified**.
  Also reported as failed: the bidirectional arm (`s_aniso16` produces only +0.71% dose)
  and the temptation to deduce a 25/75 partition between filtering and the rest (additivity never
  measured). Codex, via herdr, recomputed dose and response from scratch from the raw CSVs,
  confirming them, and its three methodological objections were adopted in the report.
  Produced `research/28_o3_material_ablation/PHASE_2O_O3_RESULTS.md`,
  `research/29_o4_sampler/PHASE_2O_O4_RESULTS.md`, `tools/o4_analyse.py`, `tools/sq_validity.py`.
  **No changes to driver, cache, registry or games.**
- **2026-09-06 (17)** — **2O cycles O5 and O6: phase closed, 6/6.** O5 without building anything: reused
  O4's executables and changed only the counters, which turns the sampler variants into a
  memory-traffic lever at identical bytecode. Closed stage attribution, and closing it
  needed a control: `SQ_VS*` reads zero, but only because on RDNA2 the vertex shader runs under
  the `GS` mask — sweep of all 8 masks, **99.53% of texture work is pixel**, the
  0.47% is the primitive shader's attribute fetch. Three explanations eliminated by measurement: L0 cache
  stall on the addresser **0.24%** (band ≤10%), L0 hit **97.66%**, **39.6 GB/s** of DRAM
  versus 555–621 available — with a cross-check worth more than the single numbers: L2 misses × 64 B
  = 31.90 MB versus 31.88 MB computed from different counters, **0.06% gap**.
  O6 tested the remaining coefficient: varying **the number of lights** (C++ data,
  byte-identical bytecode, 4 builds gated on the same hash) texture instructions per wave drop
  from 156 to 33 and **`TA_BUSY` follows them at 13.1 cycles each** — O5's prediction was 14.5, and
  88% of the pass's cycles scale with the count. **REPLICATED** on both preregistered bands.
  But in the same draft I found an error of mine that *weakens* the conclusion: I had divided
  `INST_CYCLES_VALU` by 320 SIMDs instead of 160 (RDNA2 has 2 SIMD32 per CU), so VALU duty
  is not 48% but **96.6%**. At baseline the pass is **co-saturated**, VALU 96.6% and texture
  addresser 93.6%: O6 cannot rank one above the other, and the only arm that moved just
  one remains O4 (texture at fixed ALU, 3.5%). The O6 report and O5's "what is still standing"
  section were corrected accordingly. Phase conclusion: the cost is in the **per-light loop of
  `ShadeLights`** — a property of the application, not of the driver, compiler, sampler
  or cache. Produced `research/30_o5_memory/PHASE_2O_O5_RESULTS.md`,
  `research/31_o6_lightcount/PHASE_2O_O6_RESULTS.md`, `tools/run_o5.py`, `tools/run_o6.py`.
  **No changes to driver, cache, registry or games.**
- **2026-09-06 (18)** — **Phase 2P, 8 cycles, first real end-to-end gain of the project.** First
  replicated 2O on a machine verified idle (work counters at +0.00%/+0.01%): background
  load was driving nothing. Then attacked the per-light loop of `ShadeLights` with
  semantically equivalent transformations, hypothesised by reading the **real ISA** and not the source: the compiler
  already hoists `(gloss+2)/8` but does **not** reduce `pow(x,5)`, which comes out as log+mul+exp. Four
  transformations accepted with a **bit-identical image**; the best, `stack3_scalar`, is worth
  **−41.60% of `Render Color`** (confirmed at −40.34% by an independent instrument) and
  **−24.39% of GPU frame**, in 68 diff lines in a single HLSL file. Also provided the arm
  2O was missing — ALU moved at fixed texture — which closes the question: **both saturated units
  are on the critical path, neither dominates**. A preregistered correctness criterion turned
  out to be unachievable and **was replaced going forward** without touching the verdict already issued;
  two occupancy checks failed and are reported as such; the review of the final
  candidate was not obtained because the reviewer ran out of usage quota. Produced
  `research/PHASE_2P_FINAL_REPORT.md`, `PHASE_2P_WORKLOG.md`, `PHASE_2P_MEASUREMENT_MEMORY.csv`,
  `tools/run_2p.py`, `tools/isa_2p.py`, `tools/run_clean.py`.
  **No changes to driver, cache, registry or games.**
- **2026-09-07 (19)** — **Autonomous overnight session: phases 2Q and 2R, 5 cycles of 12.** 2Q closes the
  doubt left by 2P: capturing in `R32G32B32A32_FLOAT`, `SCALAR_BRANCH` is **bit-identical even
  in float32** and the rest of the stack differs by at most **7 ULP** and 4.4e-7 relative, with no
  NaN/Inf/−0; `fresnel5` was verified **exhaustively on all 1,065,353,217 values of its
  domain** and turns out **more accurate** than `pow(x,5)` (3 ULP versus 8,388,608 from the true value); the
  data contract of the early-outs was **measured** with a canary that never fired. Final
  7-process replication: `Render Color` **−41.43%**, GPU frame **−24.47% measured** / −21.78%
  clock-corrected. 2R carries the same method to `D3D12nBodyGravity` (O(N²) n-body, compute, LDS):
  baseline with A/A N95 **0.05%** and exact oracle, three transformations tried, **none accepted**
  — one was already done by the compiler, one bit-identical but slower, and `mass_hoist` (−3.58%,
  algebraically exact) was **rejected by correctness** because the force sum has
  conditioning ~1e5. The gate stopped five defects before they produced numbers, including
  **two preregistrations compiled with the wrong DXC**. No independent review: the reviewer
  had run out of usage quota. Produced `research/OVERNIGHT_FINAL_REPORT.md`,
  `OVERNIGHT_SESSION_LOG.md`, `PHASE_2R_MEASUREMENT_MEMORY.csv`, `tools/fp32_sweep/`,
  `tools/nb_probe.h`, `tools/run_2r.py`.
  **No changes to driver, cache, registry or games.**
- **2026-09-07 (20)** — **Adversarial review of 2Q/2R and freeze of the PoC.** The reviewer
  **broke the data-contract canary**: it wrote the sentinel into the value then multiplied
  by zero, so it was blind exactly on the paths the early-outs skip. Rebuilt out
  of band with a propagated mask set before every multiplication (**0 pixels out of
  2,073,600**) and given the **positive control** v1 lacked (**2,073,600 out of 2,073,600**),
  so that silence is evidence. Also corrected the quantification of conditioning in 2R
  (median amplification ~20 epsilon, not κ≈1e5) and closed the sweep's provenance gap.
  Full audit: **64 builds, 422 runs, 22 cycles, zero discrepancies**. **2P/2Q/2R frozen** as a
  validated proof of concept with the declared limits; no further optimisation.
  Produced `research/POC_FROZEN.md`. Next proposed phase, just one: **2T, measure the hit rate
  of the method** on 3–5 D3D12 workloads declared before looking at them.
  **No changes to driver, cache, registry or games.**
- **2026-09-07 (21)** — **Phase 2T closed: hit rate of the method measured, 7 cycles of 10.** The
  frozen pipeline, unmodified, on 4 D3D12 workloads chosen by name before opening a
  single line: **0 hits of 4**, **5 transformations built and measured, none accepted**. W1
  `D3D12ExecuteIndirect` and W3 `D3D12MeshShaders` closed **before any hypothesis**, rightly — a
  5.76 µs dispatch (0.03% of arithmetic peak) and a **480 ns** draw, 48 counter ticks,
  cannot be improved by changing a shader; W1 does not even have an oracle, the back buffer changes at
  every run because the animation reads the wall clock. W2 `D3D12Multithreading`: 3 hypotheses from the ISA,
  all below threshold (−0.99% / −0.22% / −1.22% versus 2.88%). **W4 `D3D12VariableRateShading` is the
  informative miss**: baseline with a byte-identical oracle over 14 processes in two sessions, A/A N95
  0.44%, and an **Amdahl probe giving −16.59%** — unlike 2M the ceiling is there. The pipeline
  got nothing out of it. `gather_pcf`, deduced from W4's ISA (4 of the 6 `image_sample` are the
  2x2 PCF taps and the sampler is POINT, so one `gather4` covers them all), did exactly what
  it promised — 6 `image_sample` → 2 + 1 `image_gather4_lz` — and **halving the texture
  instructions is worth 0.5% of the pass**: whatever that 16.6% is, it is not texture throughput. It
  was **rejected by correctness**, and not for rounding noise: the half-texel offset lands on a
  different texel on 43 pixels of 921,600, with deltas up to 41. `zeroskip_shadow` is
  the only one in the project besides 2P to come back **byte-identical** — the argument `0 * finite == 0`
  holds — and is worth **+0.13%**, i.e. nothing: with a single point light almost no wave is
  entirely unlit. Its provenance is **declared**: the pattern comes from 2P, not
  from W4's ISA, and it is counted separately precisely so that a hit would not be credited to the
  ISA-only pipeline. **The gate stopped two defects before they produced numbers**: the headers in `aux`
  were never saved or restored (dirty workspace after a build that touches
  `Common.hlsli`, caught by the preregistered hash of `Glass_PSMain`), and the analyser paired
  runs by rep number — with the base drifting by 1.2% between the two sessions it would have scored
  `gather_pcf` at ~−1.5% and **fabricated an acceptance**. Both fixed at the root and W1–W3
  reanalysed (verdicts unchanged). **Honest reading: counting 2P and 2R the method stands at 1 hit in 6
  workloads, and 2P's −41% looks more like an outlier than a rate.** Produced
  `research/PHASE_2T_RESULTS.md`, `research/52_2t_w4/verdict.json`, `tools/run_2t.py`
  (`preregister` action, `source_rels()`, time pairing).
  **No changes to driver, cache, registry or games.**
- **2026-09-07 (22)** — **Phase 2U closed, 12 cycles: hit rate 0 of 4, and now we know why.**
  Three preregistered changes to the pipeline, all did their job, none produced
  a hit. **(1) Ceiling gate**: the ceiling is measured by ablating the shader body *before* any
  hypothesis, and below 3% the workload is closed without spending attempts. It closed **U-A
  `D3D12DynamicIndexing` (ceiling −0.38%)** and **U-C `D3D12HDR` (+0.22%)** in one cycle each:
  deleting the whole pixel shader moves nothing, they are limited by draw calls and fetch, not
  by shading. They stay in the denominator. **(2) Ceiling decomposition**: on W4 72% of the
  ceiling is the shadow term and only 14% of that is texture taps — which explains in
  hindsight why 2T's `gather_pcf` was worth 0.5%; on U-B `D3D12Raytracing/ProceduralGeometry`
  (**ceiling −79%**) it is **shadow rays −43.5% and reflection rays −26.9%, while Phong is
  1%**, so any ALU transformation was useless *before* building it. **(3) Two-tier
  correctness rule**: not needed, because **two candidates of three came back
  byte-identical**. **The project's near-success**: `shadow_tmax` limits the shadow ray's TMax
  to the light distance — **byte-identical image**, −2.18%, replicated at 2000
  frames/process at **−1.81% with full separation** (every variant process faster than every
  base process) — and the preregistered threshold (4.02%, 2.76% in the replication) **rejects it**. The
  replication was done *because* it was a near-success, this is declared, and **it did not save it**.
  Two standard beliefs measured false: hoisting uniform work to the vertex stage costs
  **+4.31%** on W4 (attributed by region, with the depth-only pass at **+7.24%** and the postprocess
  steady at +0.14% as a negative control, prediction **wrong in sign**), and Microsoft's PERFORMANCE TIP
  about not carrying values across `TraceRay` is worth **−0.09%**. Built the
  **measurement memory** (`MEASUREMENT_MEMORY.csv`, 39 rows, from artifacts only): 2P's −41.6%
  on MiniEngine versus **−2.18% as the best result of everything else** — that regime is an
  outlier, not a rate. **Six defects stopped by the gate** before producing numbers, including
  rep-number pairing that would have **fabricated an acceptance**. Prepared the
  Cyberpunk milestone: `tools/capture_game.py` **validated on a live DX12 process** (11,030 frames,
  exit 0), `pmparse.py` extended to the three CSV schemas with **the 14 existing baselines identical** after
  the change, operating procedure written. **Superposition downloaded, UNIGINE signature verified,
  installed silently on E: with an uninstaller** — but it is DX11/OpenGL/Vulkan, not DX12: it is a
  machine-state check, not a workload. Produced `research/PHASE_2U_RESULTS.md`,
  `PHASE_2U_PREREGISTRATION.md`, `PHASE_2U_W4_CEILING.md`, `C2077_OPERATOR_PROCEDURE.md`,
  `MEASUREMENT_MEMORY.csv`, three `verdict.json`, `tools/isa_2u.py`, `tools/memory.py`,
  `tools/capture_game.py`.
  **No changes to driver, cache, registry or games.**
- **2026-09-08 (23) — Cyberpunk fullscreen scaling, v2 reanalysis completed.**
  Regenerated `native_analysis_v2` for fs1440_r1/fs1080_r1/fs720_r1/fs1440_r2:
  **112.368 / 163.965 / 185.826 / 111.905 FPS**, anchor drift −0.411%.
  Fixed N-interval duration and alignment diagnostics in `tools/c2077_native.py`;
  the locator proposed from QPC duration alone was disproved, not adopted.
  720p keeps a one-frame offset between blocks: global window 6415–18356,
  explicit +/-1 uncertainty and verified sensitivity, not exact frame identity.
  720p GPUBusy/CPUBusy/GPUWait = **4.172 / 5.230 / 1.107 ms**: GPU dominant at 1440p
  (strong), non-GPU/CPU-submission limit at 720p (probable); CPU vs driver not isolated.
  No hard ceiling at 186 FPS nor shader speed-up shown. Synthetic/real tests PASS,
  33 historical hashes unchanged. Reproducible check: `tools/c2077_scaling_check.py`.
  Report: `research/62_c2077_fullscreen_scaling/VERDICT_V2.md`; data in
  `scaling_analysis_v2.json` in the same directory. No new capture needed
  for this verdict; a separate WPR is needed only to attribute game vs driver/sync.
  **No changes to driver, cache, registry or games.**
- **2026-09-08 (24) — Cyberpunk WPR CPU+GPU: harness fixed, benchmark capture waiting for the click.**
  `capture_etw.ps1` now keeps default sampling, uses QPC in ms, checks exit/timeout,
  does not stop other people's sessions and saves the incomplete ETL instead of deleting it. Pure test and real
  smoke PASS: zero events/buffers lost, CPU stacks and DxgKrnl queues present, 1 ms sampling.
  Cyberpunk started normally, saved settings 1440p fullscreen unchanged; no benchmark
  capture made yet, no attribution concluded. Only the menu needs preparing
  and the benchmark started by a manual click; the rest stays autonomous. Status and the agent's next command
  in `research/63_c2077_wpr_attribution/STATUS.md`. No changes to the game.

- **2026-09-26 (25) — Takeover from Claude and portable handoff.**
  Created `HANDOFF.md` in the root with goal, chronology, results, limits, sources and next actions.
  Claude unavailable per the user's instruction; no new start of that harness.
  Found the real WPR capture from 22:28 on 8 September, later than the old STATUS:
  ETL 21,098,397,696 bytes, PresentMon exit 0, 1 ms sampling. Offline recovery completed:
  5304 native frames strictly aligned to rows 7745–13048, 64.2440852 s / 82.56013 FPS;
  Hardware Independent Flip over the whole window. Tracestats and check_loss PASS, losses 0/0.
  Saved normalised copies and native_analysis_v2 without altering the raw data; hashes verified.
  Three self-checks PASS; verified the 21 relative links of the handoff. STATUS updated.
  What remains is CPU/driver/GPU attribution and assessment of the perturbation, not a new
  pre-emptive benchmark. No new capture or changes to game, driver, cache, Registry or security.

- **2026-10-16 (26) — Offline analysis of the existing WPR, within the limits of validated evidence.**
  No new benchmark. OpenTrace/TDH raw-QPC reader and parsers specific to the verified layouts;
  439,214,592 events read, properties decoded without errors. ETL clock validated against
  1276 SampleProf, 51,340 CSwitch, 26,314 ReadyThread and 10 independent DXGI events, zero discrepancies.
  All 5304 frames matched to a contiguous sequence of Present stops: ETL window
  [49.9097700, 114.1538552) s. Online/WPR timestamps not bit-identical (residuals 0.2–12.9 µs),
  no offset fitting. Game CPU: 444,920 samples; 48.80% executable, 28.40% ntoskrnl,
  8.44% ntdll, 7.87% amdxc64, 1.23% D3D12Core. Running time of 34 threads matching xperf within
  0.5 µs; effective paths WaitForSingleObjectEx/ReleaseSemaphore, without declaring them removable.
  Mapped device/context/owner/node; target DMA FIFO replay 75.7717% of the window,
  93,450 starts and 2714 preempted segments, zero timeouts. This is not hardware occupancy or shader cost.
  Distinct layouts validated: 178 DMA, 244 scalar WAIT=4, 245 array SIGNAL=5; 52,876 Unwaits associated.
  Kept but rejected the attempts with inverted enum/reused pointer and the ambiguous
  Profile stack filter. Sampled CPU callers still not validated, even after diagnostics on the
  historical smoke without a PID filter; full critical path not proven. In the window,
  13.964 CPU-s sampled in Etw*/Etwp* symbols and 27.277 CPU-s in two StackWalk helpers: significant tracing,
  but the causal share of the drop versus the passive runs is not isolated. No driver tuning justified,
  no shader/PSO provenance and no speed-up shown. New/existing tests, native
  comparisons and input hashes PASS; ETL SHA-256 e2e4ae42ccb8bb1e41d8717513abe1bb469d6e4969ef1b8e363f229a5b21e739.
  Report `research/63_c2077_wpr_attribution/OFFLINE_ATTRIBUTION_20261016.md`; artifacts/commands
  in `fs1440_r1/offline_20261016/`. Updated HANDOFF and STATUS. Next decision: close
  sampled callers/perturbation or shader provenance with a motivated route; no new
  automatic capture and no changes to game, driver, cache, Registry, boot or security.

- **2026-10-16 (27) — Started the concrete route of Cyberpunk shader experiments.**
  Lorenzo asks to move to motivated/reversible changes, not more general analysis.
  Hashes of the installed shader containers taken before copying: identical to the September inventory;
  analysis exclusively on copies in `research/64_c2077_shader_access_20261016/copies/`.
  A probe with self-check finds 19,950 structurally readable DXBC/DXIL containers: 19,037 in the
  main container, 913 in the static one. Occurrences per stage: 5238 pixel, 13,983 vertex,
  661 compute, 68 library; not all unique or shown to be active in the benchmark. Extracted one payload
  per stage with hash/offset; one pixel and one compute disassembled by the installed DXC, exit 0,
  empty stderr. Real IR now available, but no variant applied or optimised yet.
  Next experiment: offline round trip/validation and a truly supported and reversible
  reinsertion path, then an identifiable canary and oracle; no patching of the
  signed driver or speculative replacement of caches. Runtime measurements only when the
  test phase reopens. Status: `research/64_c2077_shader_access_20261016/STATUS.md`; HANDOFF updated.
  No new benchmark, no changes to installed game files, driver or AMD caches.

- **2026-10-16 (28) — Real round trip and first DXIL canary, PASS_OFFLINE.**
  SDK utility `tools/dxil_roundtrip.cpp`: Microsoft assembler and external validator, hashes/signatures
  of the SDK DLLs verified, no -Vd. Pixel/compute/glass rebuilt: whole IR identical
  (newline normalisation only) and SFI0/ISG1/OSG1/PSV0 parts identical; payloads not bit-identical.
  Removed the STAT reflection added by the assembler with ContainerBuilder, then external validation
  and a second validation of the resulting files. Glass selection with GUID 15973390170752892218
  linked to the compilation string renderstage_transparent/MeshStatic/PassIndex 0.
  Preregistration C2077-DXIL-CANARY-001: only the four RGBA outputs of target 0 replaced with
  (1,0,1,1); discard/target 1 and the rest of the module unchanged. Canary compiled and validated,
  SHA-256 9da6f87440e40e8d42a4f6bc2afba073a6675d0ddffec91805426142a4e085db.
  Three negatives PASS: wrong syntax, opcode 999 rejected by the external validator (0x80aa0009),
  overwrite denied/hash unchanged. 21 subprocesses recorded. RDHS v10 parser verified on
  19,037 shaders and 19,647 compilation records; upstream stage labels corrected with neutral A/B slots
  after cross-checking with the DXIL tokens. No-op repacking byte-identical, control/canary
  repacked only in research with 19,036 other payloads and metadata unchanged.
  Installed caches still original; copies not declared accepted by the game or ready to install.
  No documented REDmod route found for this arbitrary DXIL; possible ReShade/RenoDX DX12
  loader to review and authorise specifically before installing/hooking Cyberpunk only.
  Do not replace installed caches or the driver and do not use in anti-cheat games.
  Status `research/65_c2077_dxil_roundtrip_20261016/STATUS.md`; preregistration and r1/result.json.
  Updated HANDOFF and phase 64. No game/benchmark started, no speed-up claimed.

- **2026-10-16 (29) — Cyberpunk loader authorised, CONTROL installed; runtime pending.**
  Specific user authorisation for loader/hooking in Cyberpunk only and the necessary downloads.
  Official ReShade 6.8.0 Full Add-on x64: setup downloaded but not run, only the x64 DLL extracted;
  SDK API 20/commit 18deaa52de0c425a78b329e9cb3c497281cd00ec. OptiScaler not needed.
  Local add-on with path and EXE SHA guard, pixel bytecode comparison over all bytes:
  observes init_pipeline including for libraries, creates a PSO clone with the same layout and redirects binds
  without mutating original PSOs, caches or pre-existing DLLs. Phase 65 payloads embedded unchanged.
  Effects, depth/sync add-ons and overlay shortcuts disabled. No HDR/FG/resolution change.
  PASS C++ self-test of descriptors/selection/negatives/wrong host and Python install/mode/rollback/
  collisions/changed file/unknown user file. r0 restore on the real target PASS:
  84 original files, 527,653,806 bytes, same set of names/hashes; own directory removed.
  Identical package reinstalled in control: only five new files, manifest/archive present.
  EXE/engine caches at original hashes. ReShade host NotSigned, setup chain locally not
  trusted: explicit limit, no certificate import or protection changes.
  Driver currently reads 32.0.21045.11001, unlike the historical 32.0.21045.5002; no pooling.
  No game/benchmark/capture started: waiting for a manual session, then check PSO clone/bind
  and normal image before the canary. A bind does not prove the shader executed/visible fragments;
  no cost or speed-up shown. Status/preregistration/manifest in
  `research/66_c2077_shader_loader_20261016/`; HANDOFF updated.

- **2026-10-16 (30) — Control runtime: PSOs accepted and target binds observed.**
  Manual start by the user, PID 5396; add-on EXE guard passed. Live snapshots preserved in
  phase 66 `runtime_control_r1/`: 5316 DX12 inits, 5 exact matches, 5 control PSO clones,
  zero clone errors and 406 target binds. First reading still at 4 clones/0 binds;
  later update positive, not classified as a bug. A transient D3D11 cycle
  ends before the active D3D12 reload; separate logs. One IDXGIFactory2 reference count WARN
  (4) in the host log kept, no ERROR in the sample. Confirmed loading/creation/
  bind, not draw/GPU completion/visible fragments/image correctness or cost.
  Asked for confirmation of a normal image and closure by the user before the canary at a new manual start.
  No automatic benchmark/capture, no change to the package or control mode.

- **2026-10-16 (31) — Qualitative control accepted, canary armed.**
  User confirms "closed, normal image"; Cyberpunk process verified absent.
  Final copies of own logs/config in `runtime_control_r1/closed/`: last heartbeat 5360 inits,
  5 matches/clones, zero clone errors, 1044 binds. Final unload of the D3D12 cycle
  missing; host ends with Finished exiting but reports swap-chain reference count and add-ons still
  loaded at exit. WARNs kept, cause/full lifecycle/exit code not shown.
  Operator visual check is qualitative, not a quantitative pixel comparison or GPU proof.
  Verified immutable hashes and EXE, set only mode.txt=canary via CLI with the game closed;
  no new build or DLL/cache replacement. Deployment manifest updated; frozen
  package unchanged. Evidence `canary_r1/preparation.json`; waiting for a manual start in the same scene,
  new PID/canary log and magenta marker. No game/benchmark started automatically,
  no speed-up. STATUS/HANDOFF updated.

- **2026-10-16 (32) — Canary runtime accepted and target binds confirmed, marker pending.**
  New manual start by the user, PID 14612; mode=canary logs distinct from control 5396.
  Live snapshot `canary_r1/live_snapshot_1/`: 5239 DX12 inits, 5 matches/PSO clones, zero clone
  errors, 544 target binds, EXE guard and first_target_bind present. Immutable DLLs
  at the frozen hashes. No ERROR in the host sample, one IDXGIFactory2 reference count WARN
  at startup kept. Does not prove draws, visible fragments, GPU completion or speed-up.
  Asked the operator whether pink-magenta surfaces are visible; no visual answer yet.
  Package/mode unchanged with the process active, no automatic benchmark/capture.
  STATUS/HANDOFF updated, evidence in `canary_r1/RESULT.md`.

- **2026-10-16 (33) — Canary visually negative; targeted observer installed.**
  User: no pink surface, image unchanged. Visual gate not passed; PID 14612
  then closed, last heartbeat 5 PSOs/2033 binds/zero clone errors. Negative raw data and final
  logs preserved. Shader HASH/digest/DXIL distinguished; four magenta outputs correct;
  all whole payloads in the installed binary. SDK factory/bind sources reviewed:
  static facts are not equivalent to GPU execution/marker, cause still unknown.
  Preregistered phase 67 C2077-SHADER-PROBE-001: a separate observation-only add-on for
  RT count/formats/write masks/blend/depth and CPU counters of draw/indirect/bundle/submission.
  No GPU modify/create/query API, draw callback always false. PASS C++ self-test of
  state/reset/rebind/device key/bundle/submission/empty/masks/zero RT/wrong host; PASS Python
  probe-log rollback, preservation of unknown files and chronological ordering of logs (not by PID).
  New observer added atomically with the process absent and to the ownership manifest;
  host/ShaderLab/bytecode/canary mode unchanged. Removal extended to recognised probe logs only.
  Current WMI driver still 32.0.21045.11001. No automatic start/benchmark, no fix or
  speed-up declared; unattended GPU/image loop missing. Waiting for a manual session in the same
  scene for new probe logs. Status `research/67_c2077_canary_probe_20261016/STATUS.md`.

- **2026-10-16 (34) — Probe r1 active, four PSOs known but target not bound in the observed commands.**
  Manual start PID 11348. The probe receives global draw/queue events, but target binds/draws/
  submissions still zero; four created PSOs have RT0 present, RGB mask 0xF, src RGB one,
  op add, dst source1_color. The latter is dual-source blending: SV_Target1 is not
  necessarily a second independent RT. The fifth PSO bound in earlier
  sessions not reconstructed and discard/occlusion/compositing not excluded. Snapshots/enums verified
  in phase 67 `r1/`. Asked only for a short non-paused visual walk-around in the same session,
  no restart or benchmark, to observe a target bind. Original cause still unknown;
  no live change and no inference of GPU absence based on CPU counters alone.

- **2026-10-17 (35) — Walk-around finished with no target use observed; back-buffer catalogue installed.**
  User "done", still zero target binds/draws in the commands of session 11348, then closed.
  Final logs preserved; do not ask for more walk-arounds for the same glass. Cause of the old missing
  marker not established, earlier binds not withdrawn. ShaderLab switched to observe with the process
  absent; no shader replacement active. New C2077-BACKBUFFER-PROBE-001 read-only:
  swap-chain resource/RTV0 identity, shader SHA256, direct/indexed/indirect draws and submissions.
  Old observer verified, archived/removed; new file in the manifest, host/ShaderLab
  unchanged. No mutating GPU API or timing, compute/UAV/copies/bundles remain limits.
  PASS C++ self-test of resource/device/resize/reset/rebind/empty/submission/SHA/host and Python
  own/unknown logs/rollback. Offline index of 8340 unique SHAs / 19,950 occurrences prepared.
  Waiting for a normal manual start in the same scene, then choose a candidate actually observed;
  no new shader/canary, benchmark or automatic start. Phase 68 status, HANDOFF updated.

- **2026-10-28 (36, added at archive time) — Project paused and published.** The phase-68 manual
  run (PID 276) selected PSO serial 243 / pixel shader SHA-256
  `1642c9e5c2f2bca229198fc354cf8e5bd712f26baa467a6392f7c5125abc9d4c`, a full-screen pass writing
  the real back buffer, matched to one offset in the offline static cache copy. Phase 69
  (C2077-DXIL-CANARY-002, a magenta canary on that shader) was preregistered on 2026-10-17 but
  nothing was built. The repository was published with binaries and game-derived data excluded
  (hashes in `data/manifests/`).
