# Phase index

Every folder under `research/`, in order. Phase codes match [PLAN.md](../PLAN.md). Folders ending in
`_SUPERSEDED_prepare_NN` or `_FAILED_*` are attempts that a gate stopped before (or instead of)
producing numbers; they are kept for provenance and can be ignored for results.

Reports are mostly in Italian. Look for `STATUS.md`, `RESULT*.md`, `PHASE_*_RESULTS.md`,
`PREREGISTRATION.md` and `verdict.json` in each folder.

## Phase 1 / 1.5 — driver and baseline

| Folder | Phase | Summary |
|---|---|---|
| `00_inventory/` | 1A | Hardware, OS, GPU and software versions. HAGS on; root package ≠ installed driver. |
| `01_driver_map/` | 1B | All 724 files of the AMD package: hashes, PE metadata, signatures, INF map, component roles. |
| `04_benchmarks/analysis/` | 1E | PresentMon parser validation, metric definitions (`METHOD.md`), Fortnite/Steel Nomad baselines and noise, charts. |
| `fortnite_DX12_PerformanceMode/` | 1E | Raw PresentMon captures of 7 Fortnite runs (large CSVs are in the release zip). |
| `3DMark_SteelNomad_DX12/` | 1E | Steel Nomad results and screenshots. |
| `08_etw_fortnite/` | 1.5A | WPR CPU attribution on Fortnite: `amdxc64.dll` is 2.1% of the critical path. |
| `09_umd_settings/` | 1.5B | UMD settings surfaces; discovery of `AMD_SC_OPTIONS`, 272 `SCOption_*`. |

## Phase 2A–2N — compiler and shader lab

| Folder | Phase | Summary |
|---|---|---|
| `10_sc_probe/` | 2A–2C | `AMD_SC_OPTIONS` parser active in retail; first ISA/stats dumps via RGA. |
| `11_compiler_experiments/` | 2E | Compiler options cannot be set; 0 of 24 compilations change ISA. Closed. |
| `12_d3d12_microbench/` | 2F | D3D12 timestamp-query bench; wave32 vs wave64; `AmdExt` intrinsics recon. |
| `13_scoptions_static/` | — | Which `SCOption_*` are active per shader (34/272, mostly HW workarounds). |
| `14_optimizer/` | 2G | Automated shader optimizer loop with correctness check (later corrected by 2H). |
| `15_robustness/` | 2H | Bench defects fixed; `[unroll]` vs DXC default; load scheduling as cause. |
| `16_corpus/` | 2H | 20-shader corpus for loop-attribute generalisation. |
| `17_rgp/` | 2H | Two RGP traces and a latency sweep (RGP not readable from CLI). |
| `18_ai_search/` | 2I | Guided search: 9/23 variants beat the real default; best −69.5%. |
| `19_predictor/` | 2J | IR-based mechanical transformations; predictor vs random (evidence beats rules). |
| `20_real/` | 2K | 24 real compute shaders (DirectX-Graphics-Samples, FidelityFX); measurement memory. |
| `21_workload/` | 2L | First end-to-end test in MiniEngine: zero gain, three causes isolated. |
| `22_runtime/` | 2M | Runtime shader inventory; `Render Color` = 48.7% of frame. |
| `23_bottleneck/` | 2N | GPUPerfAPI counters, per-pass bottleneck classification; MSBuild skip bug found. |

## Phase 2O — audit and ablations (MiniEngine `Render Color`)

| Folder | Phase | Summary |
|---|---|---|
| `24_phase2o_build_gate*/` | O1 | Fail-closed build gate on bytecode SHA-256; canary propagation PASS. |
| `25_gpa_validity/` | 2O | Why 2N's derived counters could not answer the question. |
| `26_gpa_hwcounters/` | 2O | Raw HW counters: 145 → 4001 available. |
| `27_o2_counters*/` | O2 | Counter semantics (`TexUnitBusy` = max over CUs), workload identity, baseline. |
| `28_o3_material_ablation/` | O3 | Material samples: 2.1% of texture instr, 13.9% of TA busy cycles. |
| `29_o4_sampler/` | O4 | Sampler-only ablation: filtering is ≤3% — falsifies 2N. Includes independent audit. |
| `30_o5_memory/` | O5 | Stage attribution (99.5% pixel); cache/DRAM ruled out. |
| `31_o6_lightcount*/` | O6 | Light-count lever: 88% of pass cycles scale with the per-light loop; VALU/TA co-saturated. |
| `32_clean_replication/` | 2P | Clean-room replication of 2O on an idle machine: PASS. |

## Phase 2P–2R — the proof of concept

| Folder | Phase | Summary |
|---|---|---|
| `33_2p_shadelights/` … `39_2p_cycle7/` | 2P | 8 optimisation cycles on `Lighting.hlsli`; `stack3_scalar` −41.6%. |
| `40_2q_fullprecision/`, `41_2q_cycle2/`, `42_2q_replication/` | 2Q | float32 equivalence (≤7 ULP), final 7-process replication. |
| `43_2r_workload*/`, `44_2r_cycle2/` | 2R | Second workload (nBody): no transformation accepted. |
| `47_2q_canary2*/`, `48_2q_canary_control/` | review | Rebuilt data-contract canary with positive control. See `POC_FROZEN.md`. |

## Phase 2T–2U — hit rate of the method

| Folder | Phase | Summary |
|---|---|---|
| `49_2t_w1/` | 2T | D3D12ExecuteIndirect — closed before hypotheses (5.76 µs dispatch). |
| `50_2t_w2*/` | 2T | D3D12Multithreading — 3 candidates below threshold. |
| `51_2t_w3*/` | 2T | D3D12MeshShaders — closed (480 ns draw). |
| `52_2t_w4*/` | 2T | D3D12VariableRateShading — 16.6% ceiling, nothing captured. |
| `53_2u_ua/` | 2U | D3D12DynamicIndexing — closed by ceiling gate (−0.38%). |
| `54_2u_ub*/` | 2U | D3D12Raytracing ProceduralGeometry — `shadow_tmax` −2.18%, rejected by threshold. |
| `55_2u_uc/` | 2U | D3D12HDR — closed by ceiling gate (+0.22%). |
| `56_capture_validation/` | 2U | Validation of the game-capture harness on a live DX12 process. |

## Cyberpunk 2077

| Folder | Summary |
|---|---|
| `60_c2077/` | First benchmark capture attempt. |
| `60_c2077_20260907_codex/` | Borderless 1440p baseline: 5 manual runs, CV 0.067%; Steel Nomad pre/post checks. |
| `61_c2077_res_scaling/` | Borderless resolution series — invalid for comparison (present path changed). |
| `62_c2077_fullscreen_scaling/` | Fullscreen 1440/1080/720/1440 series; `VERDICT_V2.md` is the current verdict. |
| `63_c2077_wpr_attribution/` | WPR CPU+GPU trace: alignment, loss check, offline attribution report. |
| `64_c2077_shader_access_20261016/` | Reading 19,950 DXIL containers from copies of the game caches. |
| `65_c2077_dxil_roundtrip_20261016/` | DXIL round trip + first ("glass") canary, offline PASS. |
| `66_c2077_shader_loader_20261016/` | ReShade add-on loader; control OK, canary visually negative. |
| `67_c2077_canary_probe_20261016/` | Observer probe: glass PSO not bound to draws in the session. |
| `68_c2077_backbuffer_catalog_20261016/` | Back-buffer probe; selected full-screen shader `1642c9e5…`. |
| `69_c2077_visible_canary_20261017/` | Preregistration only. **Next step.** |

## Top-level reports in `research/`

`PHASE_1_STATUS.md`, `PHASE_1_5_DECISION_GATE.md`, `CODEX_HANDOFF_AUDIT.md` (5 Sep audit),
`PHASE_2O_FINAL_REPORT.md`, `PHASE_2P_FINAL_REPORT.md`, `POC_FROZEN.md` (English),
`PHASE_2T_*`, `PHASE_2U_*`, `MEASUREMENT_MEMORY.csv`, `C2077_*` (Cyberpunk procedure, worklog,
report — the report body is partly superseded, see HANDOFF), `AUTONOMOUS_*` / `OVERNIGHT_*`
(session logs).
