# Phase 2O — cycle O1: build propagation. **PASS**

**Date:** 2026-09-06 · **Experiment ID:** `O1_20260906_010146` ·
**Workspace:** `%TEMP%\claude\O1_20260906_010146`

Executes step 2 of [`CODEX_HANDOFF_AUDIT.md`](../CODEX_HANDOFF_AUDIT.md) §7. Closes the gap
the audit called decisive: *"non esiste ancora una catena fail-closed che dimostri quale
variante viene eseguita"*.

**This cycle proves propagation only. It contains no timing, no counter and no performance
claim.** GPUPerfAPI was disabled for every run.

---

## Verdict

The chain **source → DXC bytecode → linked binary → executed PSO → rendered image** is now
demonstrated, fail-closed, and reversible.

| Stage | Bytecode | Preregistered SHA-256 | Result |
|---|---|---|---|
| **A** baseline | 12 612 B · `52CE6C5E64AB2E82` | `3fbca1dd…74c6` — matched | **PASS** |
| **B** canary | 12 616 B · `863C3DDA7C0BCD9A` | `f226996f…30c7` — matched | **PASS** |
| **A2** restored | 12 612 B · `52CE6C5E64AB2E82` | `3fbca1dd…74c6` — matched | **PASS** |

Both expected hashes were computed offline by DXC and written into
`experiment_manifest.json` **before any build ran**. A build producing anything else is
rejected, so stage B could not have passed on an arbitrary different shader.

## What each stage established

### A — baseline, 3 independent processes

- Bytecode extracted from the generated header equals the DXC object byte for byte, and its
  custom hash `52CE6C5E64AB2E82` at 12 612 bytes reproduces the historical inventory value
  that the handoff audit had only recomputed offline.
- The verified bytes appear **exactly once** in `Model.lib` and **exactly once** in
  `ModelViewer.exe`.
- **34 draws** in `Render Color` per frame, all carrying `ps_hash = 52CE6C5E64AB2E82`,
  `ps_bytes = 12612`, `native_matches = 1`, across **2 distinct native PSOs**
  (`m_ModelPSO` and `m_CutoutModelPSO`), 836 757 indices total.
  This corroborates the audit's correction that the **28,90 draws/frame** in
  `PHASE_2M_RESULTS.md` was one of the two components of the scope, not the whole scope.
- Three separate processes produced a **byte-identical** captured image
  (`83a96ce982c68fc8…`, 0 changed pixels, 0 ULP on every channel).

### B — canary, detected as a value and not merely as a difference

Canary: `mrt.Color = colorSum;` → `mrt.Color = colorSum + float3(0.125, 0.0, 0.0);`

| Measure | Value |
|---|---|
| Changed pixels | 2 073 557 = **100,00 %** of the frame |
| Changed fraction R / G / B | **1.0 / 0.0 / 0.0** |
| Positive fraction R / G / B | **1.0** / 0.0 / 0.0 |
| Median decoded delta, dark pixels | **+0,124268** / 0 / 0 |

`+0.125` in an R11 channel (6-bit mantissa) quantises to `0.124268`. The change is present
on **every** pixel, **only** on red, **always** positive, at **exactly** the injected
magnitude. Green and blue are untouched down to the bit.

### A2 — reversibility

Restoring the source reproduces A's bytecode SHA-256 and an image **bit-identical** to A
(0 changed pixels). The executable SHA-256 differs from A's, as a fresh link must — so the
identical image comes from a genuinely rebuilt binary, not from a skipped build. That is the
direct control for the 2N finding that MSBuild had silently skipped recompilation and the
same binary was measured twice.

## Determinism — what is and is not shown

Measured baseline spread: **0 changed pixels over 3 independent processes.**

This is **not** a determinism proof. `Model/Shaders/FillLightGridCS.hlsli:163-173` allocates
per-tile light slots with `InterlockedAdd`, and `Lighting.hlsli` accumulates `colorSum` by
walking that list, so the float summation order is not guaranteed between runs. The
mechanism is real and present in this code; it simply **did not manifest** in three runs at
this capture point. Phase 2L found its second image hash in 1 run out of 6, and its capture
included the particle system, which this capture point precedes.

Recorded as *measured spread 0/3*, not as *deterministic*. Any future gate that needs
baseline determinism must re-measure it for its own capture point and run count.

## Why the capture is at frame 140

`Sponza::RenderLightShadows` copies **one** of `Lighting::MaxLights = 128` shadow slices per
frame (`Model/SponzaRenderer.cpp:214-240`, `static uint32_t LightIndex`). Before frame 128
the shadow array is partly unrendered and its content changes every frame. The original
plan's frame 7 would have captured 7 of 128 slices.

## Defects found and fixed before this cycle could be valid

Fourteen. The ones that would have produced a **false or spurious verdict**:

| Defect | How found | Consequence avoided |
|---|---|---|
| `CL.read.1.tlog` used as propagation evidence | measured: 3134 header entries, **0** under the output tree | spurious FAIL. Replaced by the bytecode-in-binary check. Also diagnoses the audit's open `dxc.write.1.tlog` question: MSBuild's file tracker **excludes the output and package trees** — it is not timestamp granularity |
| B built with `expected=None` | code review | B would have accepted *any* differing bytecode |
| `-MD` puts DXC in dependency-only mode: writes the depfile, emits no `-Fh`/`-Fo`, exits 0 | offline rehearsal | the single combined invocation produced **no shader header at all** |
| `(?:hlsl\|hlsli)` matches `hlsl` first, truncating `Common.hlsli` | offline rehearsal | `resolve(strict=True)` raised `FileNotFoundError` |
| Capture at frame 7 | source reading | unrepresentative, frame-varying shadow state |
| Baseline gated at 1 ULP | source reading | a known nondeterminism mechanism would have failed the run for an unrelated reason |
| `inline constexpr` in a C++14 build | the compiler, at stage A attempt 1 | build failure — **correctly rejected by the gate**, which is the behaviour finding A01 said was absent |
| `replace_once` matched `\n` against a CRLF file | prepare attempt 1 | half-patched workspace |

Also fixed: executable SHA not re-verified between build and run; the instrumented-source
inventory written but never checked; workspace path taken from a mutable JSON without
validation; the 8 GB budget counting only half the tree; the canary oracle checking only a
changed-pixel fraction and not the decoded magnitude; a single baseline repeat; stage
directories that could not be reused after a failure.

Ten of these came from an independent adversarial review; two from rehearsing the DXC half
of `build()` offline against the real workspace; one from the compiler; one from running
`prepare`.

## Budget and preservation

**0 of the 6 experimental cycles of §7 consumed by failures.** O1 itself is cycle 1 of 6.
No timing, counter, variance or image-quality measurement was produced by any failed attempt.
Three superseded `prepare` runs and one failed stage A are preserved with their causes in
`research/24_phase2o_build_gate_{FAILED_prepare_01, SUPERSEDED_prepare_02,
SUPERSEDED_prepare_03, FAILED_A_01}`.

Nothing deleted, no `Clean`. Driver, shader caches, Registry and Windows security untouched;
no game launched; no personal application closed. All work happened in copies under
`%TEMP%\claude\O1_*`; the original clone at `%TEMP%\claude\src\dxs` was re-verified against
its pre-experiment SHA-256 inventory after the cycle.

## Files

`experiment_manifest.json` (preregistration) · `A_result.json` · `B_result.json` ·
`A2_result.json` · `baseline_spread.json` · `input_hashes.csv` ·
`instrumented_source_hashes.csv` · `preregistered/` · `build_logs/{A.1,B.1,A2.1}/` ·
`runs/{A,A_repeat1,A_repeat2,B,A2}/` (each with `runtime.csv`, `image.json`, `color.bin`,
`process.log`) · `source_revisions/`

## NEXT RECOMMENDED ACTION

Cycle **O2** — null run and workload identity — but its GPA half needs replanning first.
The parallel investigation in [`../25_gpa_validity/GPA_VALIDITY.md`](../25_gpa_validity/GPA_VALIDITY.md)
established that the 31-counter set of 2N schedules into **13 passes** (queried offline
against the local counter library for device `1002:73A5:C0`), and — more importantly — that
**no counter among the 145 enumerated discriminates texture-filter rate from cache/latency
or from ALU**: `TexUnitBusy` is documented as including all extra fetches and cache/memory
effects, and there is **no pixel-stage VALU/SALU or occupancy counter at all**. The largest
single-pass subset containing `TexUnitBusy` holds 7 counters; `TexAveAnisotropy` alone needs 5
passes.

Therefore **O5 as preregistered — a counter-based filter-versus-other discriminant — is not
executable with the default GPA context.** Before O2, decide between: re-enumerating with
`kGpaOpenContextEnableHardwareCountersBit` to see whether raw `SQ`/`TA` events are exposed
(the SDK defines those blocks; that they would help here is an **inference**, not verified),
or an authorised RGP/SQTT capture, or dropping the causal claim and pursuing O3/O4 time-based
ablations only.
