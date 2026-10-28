# Phase 2O — cycle O2: counter semantics, workload identity, Render Color baseline

**Date:** 2026-09-06 · **Experiment ID:** `O2_20260906_014011` · cycle **2 of 6**

**No ablation.** The pixel shader is byte-identical to the O1 baseline
(12 612 bytes, `52CE6C5E64AB2E82`, same SHA-256), verified by the same fail-closed build gate.
No performance verdict is drawn here.

Four counter sessions on the unmodified app, all through the raw-counter context
(`kGpaOpenContextEnableHardwareCountersBit`), sampling the real `Render Color` scope on
consecutive frames from frame 140:

| Set | Counters | Passes | Samples |
|---|---:|---:|---:|
| `sq_ps` — pixel-stage SQ | 32 | 1 | 8 |
| `ta_busy` — `TA_BUSY` on all 80 CUs | 80 | 1 | 8 |
| `crosspass` — the same 80 + derived + `CPF_STAT_BUSY` | 85 | 2 | 8 |
| `aniso` — 9 aniso buckets × 80 CUs + `TexAveAnisotropy` | 721 | 5 | 8 |

---

## 1. Aggregation — three formulas validated, two of them against a wrong natural guess

The SDK declares which raw counters each derived counter is built from, but not the formula.
So the formula was **measured**: raw and derived counters were captured in the same session and
the candidate formulas tested against the SDK's own value.

| Claim | Result |
|---|---|
| `CPF_PERF_SEL_CPF_STAT_BUSY` = `GPUBusyCycles` | **exact match** |
| `TexAveAnisotropy` = `Σ(N · quads_N) / Σ(quads_N)` | **exact match**, 1.2181 both |
| `TexUnitBusyCycles` = `Σ TA_i_BUSY` over the 80 CUs | **FALSE** — 88 646 506 vs 1 124 256 |
| `TexUnitBusyCycles` = `max over CUs of TA_BUSY` | **exact match** |
| `TexUnitBusy %` = `max(TA_BUSY) / GPUBusyCycles × 100` | **exact match**, 94.627017 both |

**`TexUnitBusy` is a maximum over compute units, not an average and not a total.** The
94.6 % in `PHASE_2N_RESULTS.md` therefore means *the single busiest CU's texture addresser was
busy for 94.6 % of GPU-busy cycles* — a statement about one CU out of eighty, not about the
texture units as a whole.

On this workload the distinction happens not to change the number much: measured per-CU
`TA_BUSY` is mean 1 112 895, min 1 084 292, max 1 127 503, **imbalance max/mean 1.013**. The CUs
are evenly loaded here. But the counter's meaning is now established rather than assumed, and
on an unbalanced workload the same 94.6 % would have meant something entirely different.

Independent corroboration of provenance: `TexUnitBusy` measures **94.63 %** here against
**94.609951 %** recorded in phase 2N — the same quantity on the same scene.

## 2. Workload identity — the answer is layered, and the preregistered test was too coarse

**Preregistered criterion:** *"a single-pass set must give identical values on every sampled
frame; any counter varying by more than 0.1 % fails the identity claim."*

**Result: FAILED, on every set.** Worst per-counter spread: `sq_ps` 0.63 %, `ta_busy` 3.87 %,
`crosspass` 19.92 % (`GPUTime`), `aniso` 64.52 %.

That criterion lumped together three different kinds of quantity. The decomposition below
**goes beyond what was preregistered** and is labelled as such:

| Kind | Example | Across 8 consecutive frames |
|---|---|---|
| Work, **aggregated over all instances** | aniso quad histogram; `ITEM_CYCLES_VALU` | **bit-identical, 0.0000 %** |
| Work, **per instance** | `TA18_…_QUADS`, `SQ_PS0_INSTS_VALU` | varies — work redistributes across CUs and shader engines |
| **Timing** | `GPUTime` 19.9 %, `TA_BUSY` 1.7 %, `GPUBusyCycles` 0.81 % | always varies |

The decisive measurement: **the aniso bucket totals over all 80 CUs are bit-identical across
all 8 samples of a FIVE-PASS session** — that is, across 40 different frames, with the 721
counters scheduled into 5 different passes. `ITEM_CYCLES_VALU` is likewise exactly
4 943 027 896 on every sample and every shader engine.

So the GPU really does execute the same work every frame in this frozen configuration. What
is not reproducible is *which CU does which part of it*, and *how long it takes*.

### Consequence for finding A03

**Cross-pass test (preregistered): PASS.** `Σ TA_BUSY` measured in the 1-pass session is
89 032 254; in the 2-pass session, 88 646 506 — a difference of **0.43 %**, against a
frame-to-frame spread of **1.72 %** for the same quantity. Passes do not differ by more than
consecutive frames within one pass do.

Combined with the bit-identical work totals across a 5-pass session, the practical rule is:

- Multipass is **valid for aggregate work counters** — they are exactly reproducible.
- Multipass is **not the dominant error for timing counters** either, but timing counters carry
  a frame-to-frame spread that must be reported with them, never a single value.
- **Per-instance values must not be treated as reproducible** at all.

Phase 2N's 13-pass capture mixed all three kinds and reported single values. That remains
invalid — but the reason is now measured, and it is not "every pass ran a different frame so
everything is wrong": the work was identical; the timing and the per-CU distribution were not.

### Caveat on the SQ instruction counters

`INSTS_VALU`, `INSTS_SALU`, `INSTS_TEX_LOAD` and `WAVES` vary by **0.35–0.40 %** even as
totals, while `ITEM_CYCLES_VALU` and the TA quad counters are exact. AMD marks the former
`{emulated}` and several `{global}`. Whether that 0.4 % is real work variation or an artefact
of counter emulation is **not established here**. Treat those counters as ±0.4 %, not exact.

## 3. Render Color baseline — unmodified shader

Median over 8 samples. Pixel-stage SQ counters summed over the 4 shader engines; TA counters
summed over the 80 CUs.

| Quantity | Value |
|---|---:|
| PS waves | 39 214 |
| PS waves that are wave32 | **0** |
| PS VALU instructions | 71 015 448 |
| PS VALU instruction cycles (SIMD) | 183 167 994 |
| PS VALU item-cycles | 4 943 027 896 |
| PS SALU instructions | 6 296 226 |
| PS texture instructions (`INSTS_TEX_LOAD`) | 6 115 386 |
| PS texture stores | 0 |
| `TA_BUSY`, sum over 80 CUs | 89 032 254 |
| `TA_BUSY` per CU: mean / min / max | 1 112 895 / 1 084 292 / 1 127 503 |
| `GPUBusyCycles` | 1 188 712 |
| `GPUTime` | 801 920 ns (median; 705 480 – 881 000) |

Aniso histogram, all 80 CUs — *"quads requiring N aniso samples"* in AMD's wording:

| N | Quads | Share |
|---:|---:|---:|
| 1 | 9 937 801 | 88.5 % |
| 2 | 884 028 | 7.9 % |
| 4 | 268 862 | 2.4 % |
| 6 | 89 707 | 0.8 % |
| 8 | 44 056 | 0.4 % |
| 10–16 | 0 | 0 % |
| **total** | **11 224 454** | mean **1.2181** samples/quad |

Derived ratios, reported as measurements and **not** as bottleneck claims:

- **14.56 `TA_BUSY` cycles per pixel-stage texture instruction** (89 032 254 / 6 115 386).
- 2.58 VALU instruction-cycles per VALU instruction.
- 11.6 texture instructions per PS wave; 1 810 VALU instructions per PS wave.

**The pixel shader runs wave64**: `WAVES_32` is exactly 0 on every sample and every shader
engine, while `WAVES` is 39 214.

## 4. What this cycle does NOT establish

- **No bottleneck claim.** Nothing here says `Render Color` is texture-bound, ALU-bound, or
  anything else. That needs the ablations of O3/O4 against this baseline.
- **`TA_BUSY` is not attributed to a shader stage.** The TA block serves every stage; the
  14.56 cycles-per-instruction figure divides a whole-block timing counter by a pixel-stage
  work counter. `ModelViewerVS` is not expected to sample textures, but that was not measured.
  The enumeration contains `SQ_VS*_PERF_SEL_INSTS_TEX_LOAD`, so it is one cheap single-pass
  session away from being checked.
- **The relationship between `INSTS_TEX_LOAD`, filtered quads and `TA_BUSY` is not pinned
  down.** 6.115 M texture instructions against 11.22 M aniso-path quads and 89.03 M TA busy
  cycles does not reduce to a clean identity, and no story is offered for it here.
- **`GPUTime` varies by 19.9 % frame to frame** in this configuration. Any future timing
  comparison must account for that; a single-frame GPU time is not a measurement.

## 5. Defects found and fixed before this cycle produced a number

Four build attempts were rejected by the gate. None produced a counter or a timing value.

1. **`CommandContext::Flush` invalidates a GPA command-list registration** — it does
   `ExecuteCommandList` then `m_CommandList->Reset(...)`. `SponzaRenderer.cpp:371` flushes
   before `Render Color`, inside `if (SSAO::AsyncCompute)`; the frozen config sets that false,
   so it does not run. `O2Gpa::Scope` now **requires** the live command list to equal the
   registered one, so this is checked rather than relied upon.
2. **A measuring frame that produced no sample** would have left the pass permanently
   incomplete and hung the session; now rejected.
3. **GPA include path** was declared only in `Core.vcxproj`; `Model` and `ModelViewer` compile
   the O2 header too. Moved into the shared property sheet.
4. **`ModelViewer.cpp` called `O2Gpa::` without including its header.**

`tools/o2_gpa.h` is a new module, deliberately not a patch of `Core/GpaProfiler.cpp`: every GPA
return code is checked, a counter that fails to enable aborts the run instead of silently
shrinking the set, the pass count is required to match the value preregistered from the offline
query, and the session is deleted and the context closed at the end.

## Files

`experiment_manifest.json` (preregistered criteria) · `build_result.json` · `o2_analysis.json` ·
`sets/*.txt` · `runs/{sq_ps,ta_busy,crosspass,aniso}/` each with `gpa_results.csv`,
`gpa_session.txt`, `process.log`, `run.json` · `build_logs/O2.1/` · `input_hashes.csv` ·
`instrumented_source_hashes.csv`

## NEXT RECOMMENDED ACTION

**O3 — material sampling ablation**, measured against this baseline with the `sq_ps` and
`ta_busy` single-pass sets, reporting frame-to-frame spread alongside every timing number.
Before it, one cheap single-pass session should add `SQ_VS*_PERF_SEL_INSTS_TEX_LOAD` to
establish how much of `TA_BUSY` in this scope is not pixel-stage work — otherwise every
texture attribution in O3 inherits an unmeasured assumption.
