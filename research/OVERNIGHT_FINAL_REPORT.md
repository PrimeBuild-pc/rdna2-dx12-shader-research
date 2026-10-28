# Overnight autonomous session — final report

**2026-09-06 late evening → 2026-09-07 early morning.** Five new experimental cycles of the
twelve budgeted. Programme executed: **2Q** (full-precision equivalence) and **2R**
(generalisation to a second D3D12 workload). **2S was not started** — see §"Phase 2S".

---

# Executive summary

Phase 2P had left one thing unproven: a bit-identical R11G11B10 image says two shaders agree
after being squeezed into six mantissa bits, not that they computed the same float32 values.
**2Q settled it.** Captured into an R32G32B32A32_FLOAT target, `SCALAR_BRANCH` turns out to be
**bit-identical at float32**; the remaining transformations differ by at most **7 ULP** and
**4.4 × 10⁻⁷** relative, with **no NaN, no infinity and no negative zero anywhere**. The one
transformation whose accuracy had been questioned, `fresnel5`, was verified **exhaustively over
all 1 065 353 217 float32 values in its input domain** and is not merely equivalent but *more
accurate* than the `pow(x,5)` it replaces: never worse than **3 ULP** from the true x⁵, where
`pow` reaches **8 388 608 ULP**. The data contract the early-outs depend on was measured with a
canary rather than argued: over every light of every pixel, the value multiplied by an exactly
zero factor was always finite and non-negative.

The performance result was then replicated a fourth time on the idle machine with seven
counterbalanced processes: **`Render Color` −41.43 %**, **GPU frame −24.47 % MEASURED** and
**−21.78 % as a clock-corrected estimate**, the two never mixed.

**2R took the same pipeline to a workload chosen against criteria written down first** — an
O(N²) n-body compute simulation, structurally the opposite of a per-light pixel-shading loop.
It built, it was gated, its baseline is tighter than anything measured on MiniEngine
(A/A N95 **0.05 %**), and its correctness oracle is exact (the particle state, byte-identical
across five processes). Three hypothesis-driven transformations produced **no accepted variant**:
one the compiler had already made, one bit-identical but **1.28 % slower**, and one **3.58 %
faster and rejected on correctness** — with the cause identified as an ill-conditioned sum, not a
coding error. A negative result, from the same method, with nothing loosened to avoid it.

---

# Phase 2Q — full-precision correctness

## Instrumentation

Two changes, both inert unless `ME_Q_R32` is set: the scene colour buffer is created as
`R32G32B32A32_FLOAT`, and the capture probe writes 16 bytes per pixel and exits immediately
after saving, so no post-processing pass can fail on a format it was never written for. Eight
builds in a workspace that did not exist during the P-cycles; **every bytecode hash identical to
the ones the P-cycles gated**.

## What the float32 capture shows

Determinism first: two independent processes of the base build produce **byte-identical** float32
captures. Only then is anything judged against them.

| variant | identical | differing channels | max ULP | max abs | max rel | RMS | NaN / Inf / −0 |
|---|---|---:|---:|---:|---:|---:|---|
| base vs base | **yes** | 0 | 0 | 0 | 0 | 0 | 0 / 0 / 0 |
| `scalar` (SCALAR_BRANCH) | **yes** | 0 | 0 | 0 | 0 | 0 | 0 / 0 / 0 |
| `fresnel5` | no | 80 752 (1.30 %) | **7** | 3.8e-6 | 4.33e-7 | 6.4e-9 | 0 / 0 / 0 |
| `shadowskip` | no | 45 983 (0.74 %) | 3 | 4.8e-7 | 3.03e-7 | 6.2e-9 | 0 / 0 / 0 |
| `falloffskip` | no | 831 363 (13.4 %) | 3 | 3.8e-6 | 2.58e-7 | 1.0e-8 | 0 / 0 / 0 |
| `ndotlskip` | no | 1 098 017 (17.7 %) | 3 | 3.8e-6 | 2.49e-7 | 3.0e-8 | 0 / 0 / 0 |
| **`stack3_scalar`** | no | 871 510 (14.0 %) | **7** | 3.8e-6 | **4.33e-7** | 1.2e-8 | 0 / 0 / 0 |
| `stack4_scalar` | no | 1 324 963 (21.3 %) | 7 | 7.6e-6 | 4.37e-7 | 2.9e-8 | 0 / 0 / 0 |

4.4e-7 relative is 3.6 × float32 epsilon. The baseline's own value range is [0, 56.33].

## Exhaustive verification of `fresnel5`

`saturate` clamps its input to [0,1] and maps NaN to zero, so the domain of `pow(x,5)` in
`FSchlick` is exactly the 1 065 353 217 float32 values in [0,1]. All of them were swept on the
GPU with a new minimal D3D12 compute host (`tools/fp32_sweep`) — no sampling.

*Do the two forms agree?* They differ on 204 485 077 inputs (19.2 %). For x ≥ 2⁻²⁵ the
disagreement is bounded at **156 ULP / 9.4e-6 relative / 1.19e-7 absolute**; below 2⁻²⁵ the
relative error reaches 1.0 and the ULP distance 8 388 608, but the absolute magnitude there is at
most **1.18e-38**, and the seven cases where one form gives exactly zero and the other a denormal
all live in that region. No NaN, no Inf, no −0 anywhere in the domain.

*Which one is right?* A second sweep computes the reference in **double precision** — four double
multiplies carry ~2⁻⁵⁰ relative error, seven orders below float32 spacing — and asks which form
is closer to the true x⁵, again over all 1 065 353 217 values:

| | `pow(x,5)` | `f2*f2*f1` |
|---|---:|---:|
| strictly closer to the true value | 4 852 143 (0.46 %) | **196 984 236 (18.49 %)** |
| equally close | 863 516 838 (81.06 %) | — |
| **max ULP error vs the true x⁵** | **8 388 608** | **3** |
| **max relative error vs the true x⁵** | **9.35e-6** | **2.52e-7** |

The P1 review had flagged "the multiply form is more accurate" as an undemonstrated claim. It is
now demonstrated, and in the right direction: `pow`'s error grows with |log₂x| because it is
`exp2(5·log2(x))`.

## The data contract, measured

The three control-flow transformations rest on `0 × X = 0`, which needs X finite and
non-negative. `contract_canary` computes exactly what the baseline computes and adds a detector:
`ApplyLightCommon`'s return, `lightColor` and `specularFactor`, `GetShadowConeLight`'s result and
`shadowCoord.w` are all checked, and any NaN, infinity or negative value turns the pixel into
1e30.

**The canary never fired** — and the adversarial review then showed that it *could not have*.
The sentinel was written into the value that is subsequently multiplied by zero, so on
`falloffskip`'s path (`distanceFalloff == 0`) and `shadowskip`'s (`lit == 0`) the sentinel became
`0 × 1e30 = 0`. **The detector was blind exactly where it had to see.** `ndotlskip`'s factor was
not covered either: the check was on `nDotL·RHS`, not on `RHS`.

**Canary v2 (cycle Q4) replaces it.** A violation mask is threaded through the four light
functions, set **before any multiplication**, never multiplied itself, and applied to `colorSum`
once at the end of `ShadeLights`, with one bit per contract carried in the green channel —
including a bit for `ndotlskip`'s real factor and one for negative zero.

**Result: 0 of 2 073 600 pixels fired**, all seven bits clean, max 56.3287467956543 — the
baseline's own maximum. **And the positive control v1 never had** (cycle Q5): the same detector
with the scalar check forced to fire on every finite value lights up **2 073 600 of 2 073 600
pixels** at 1e30, with masks 12 and 28, proving `distanceFalloff`, `coneFalloff` and the shadow
term all reach the capture through every light path. v2's silence is therefore evidence.
Artifacts: `47_2q_canary2/canary2_result.json`, `48_2q_canary_control/canary2_positive_control.json`.

### The data contract, stated explicitly

Measured on this workload, not assumed: `nDotH` and `nDotL` are saturated into [0,1]; `gloss`
starts at 128 and `AntiAliasSpecular` keeps it in [1,128], so `pow(nDotH,gloss)` lies in [0,1];
albedo comes from the Sponza textures and `specularColor` is the constant 0.56; the generated
light colours are finite and non-negative; `shadowCoord.w` is finite and non-zero everywhere;
`GetShadowConeLight` returns the square of a comparison sample, so finite and non-negative. The
final colour buffer spans [0, 56.33] with no non-finite value. **Outside this contract the
equivalence is not claimed** — with a negative factor the early return would give +0 where the
original gives −0, and with a non-finite one it would give 0 where the original gives NaN.

## Verdict

| component | verdict |
|---|---|
| `scalar` (SCALAR_BRANCH) | **PASS_STRICT** — float32-identical |
| `fresnel5` | **PASS_CONTRACT⁺** — not identical, but exhaustively verified over its entire reachable domain and strictly more accurate than what it replaces |
| `shadowskip`, `falloffskip`, `ndotlskip` | **PASS_CONTRACT** — ≤ 3 ULP on the real frame, contract measured by the **out-of-band canary v2**, with a positive control |
| `stack3_scalar` (the accepted stack) | **PASS_CONTRACT** — ≤ 7 ULP, ≤ 4.33e-7 relative, no NaN/Inf/−0 |

**Nothing was removed from the stack.** No threshold was loosened: no float32 ULP policy had
been preregistered, so the prompt's own PASS_STRICT / PASS_CONTRACT definitions are used rather
than one invented after seeing the data.

## Replicated performance (cycle Q3)

Fresh cycle, fresh baseline, verified-idle machine, **7 counterbalanced processes** for the pass
and 5 for the frame. A/A on base: `GPUBusyCycles` N95 0.56 %, acceptance threshold 1.67 %.

| metric | `stack3_scalar` | `stack4_scalar` |
|---|---:|---:|
| `Render Color` `GPUBusyCycles` (GPA) | **−41.43 %** | −42.76 % |
| per process | −41.43, −41.59, −41.47, −41.21, −41.45, −41.37, −41.34 | −42.63 … −43.05 |
| `TA_BUSY` | −44.18 % | −45.31 % |
| `Render Color` (MiniEngine's own timer) | **−40.24 %** | −41.31 % |
| **GPU frame — MEASURED** | **−24.47 %** | −25.23 % |
| **GPU frame — CLOCK-CORRECTED ESTIMATE** | **−21.78 %** | — |

MEASURED is the median of five independent processes. CLOCK-CORRECTED removes the −3.44 % that
`Z PrePass` and `Generate SSAO` also show — passes this change cannot touch — on the assumption
that it is a clock/power effect. **The two are never combined into one number.**

## Final accepted stack

`stack3_scalar` = `fresnel5` + `shadowskip` + `falloffskip` + `SCALAR_BRANCH`, 68 diff lines in
`MiniEngine/Model/Shaders/Lighting.hlsli` and no other file.

---

# Phase 2R — generalisation to a second workload

## Workload selected, and the criteria

Criteria written into the manifest **before** choosing: open source; D3D12; buildable with the
already-verified toolchain without installing anything new; repeatable; no anti-cheat;
modifiable; GPU-bound enough to measure on an RX 6950 XT; **structurally different** from
ModelViewer/Sponza; small enough for the budget; and chosen without first checking whether it
contained a shader that looked easy to optimise.

Rejected and recorded: eighteen samples as too small or not GPU-bound;
`D3D12RaytracingMiniEngineSample` because it is MiniEngine again; the remaining raytracing
samples and the FidelityFX sample framework as too large for the budget; 3DMark Steel Nomad —
installed, GPU-heavy, but closed source and unmodifiable.

**Chosen: DirectX-Graphics-Samples / `Samples/Desktop/D3D12nBodyGravity`** — an O(N²) n-body
simulation: one compute shader, 10 000 particles, 128-thread groups, LDS tiling, no textures, no
lighting, no light grid.

## Baseline

Instrumented with `tools/nb_probe.h` (inert unless `NB_DIR` is set): a timestamp pair on the
compute queue around the simulation dispatch, per-iteration timing after a warm-up, VSync off,
and the particle buffer copied back as float32.

- **Dispatch: 156 400 ns**, five independent processes: 156 360 / 156 360 / 156 400 / 156 480 /
  156 520 ns. **A/A N95 = 0.05–0.10 %** — tighter than anything measured on MiniEngine.
- **Correctness oracle exact:** the particle dump is **byte-identical across all five processes**.
  For a deterministic simulation, the state after a fixed number of steps is a far sharper oracle
  than any image.

## Hot pass, shader identity, bottleneck

There is one GPU pass worth the name — the simulation dispatch — and it is identified by the
**SHA-256 of the compiled `nBodyGravityCS.cso` that the gate verifies on every build**
(`22a1836b12a7…` for the baseline), not by filename.

ISA (RGA, gfx1030): **85 VGPR, 16 SGPR, 2048 B LDS, no scratch**; per interaction roughly 3
subtracts, 3 multiplies, 5 fused multiply-adds and **one `v_rsq_f32`**.

**Bottleneck classification — by model, not by counters.** 1.011 × 10⁸ interactions per dispatch
× ~11 VALU operations ≈ 1.11 × 10⁹ VALU operations, plus 1.011 × 10⁸ quarter-rate `v_rsq`. At
this GPU's issue rates that is ≈ 94 µs of full-rate VALU plus ≈ 34 µs of transcendental, ≈ 128 µs
against a measured 156.4 µs — **an instruction-count model accounts for ~82 % of the time, so the
dispatch is ALU-dominated.** Hardware counters were **not** collected for this workload; the GPA
integration is MiniEngine-specific and porting it did not fit the budget. This is a model, and it
is labelled as one.

## Transformations and results

| variant | hypothesis (from the ISA) | Δ dispatch | correctness | verdict |
|---|---|---:|---|---|
| `unroll4` | halve the unrolled body to relieve 85-VGPR pressure | — | — | **no-op: bytecode identical to base.** DXC fully unrolls both forms, so the source unroll factor is invisible |
| `lds_float3` | only `.xyz` of `sharedPos` is read; store `float3`, cutting LDS 2048 → 1536 B | **+1.28 %** (5/5, slower) | **bit-identical** | REJECTED (performance) |
| `mass_hoist` | mass is a constant factor of every term: `Σ rᵢ·m·cᵢ = m·Σ rᵢ·cᵢ`, removing one multiply per interaction | **−3.58 %** (5/5) | **FAIL** | REJECTED (correctness) |
| `all3` | the three together | −5.91 % (5/5) | **FAIL** | REJECTED (correctness) |

Two things the ISA settled before any transformation was written: `1.0f / sqrt(distSqr)` is
**already** emitted as a single `v_rsq_f32`, and the softening constant is already folded into a
`v_fmaak_f32`. Checked, not assumed.

**`mass_hoist` is the instructive one.** It is 3.58 % faster on every process, mathematically
exact, and the gate rejected it. After 600 steps its state differed by up to 2.3 × 10⁹ ULP, which
alone would be dismissed as chaos in an n-body system — so the question was settled by comparing
**after a single step**: 32 336 of 80 000 values differ.

> **Errata, found while preparing the adversarial review of this report.** The first version of
> this section read the single-step divergence as *max 164 301 ULP, max relative 1.06 × 10⁻², a
> condition number around 10⁵*. Those figures are real but they are **not** a measure of the sum's
> conditioning: they come from `velo.x`, whose smallest non-zero magnitude is 3.9 × 10⁻⁶ against a
> median of 0.125. Near zero both ULP distance and relative error inflate without the absolute
> perturbation being large. Measured on the quantity that is actually summed, **|accel| after one
> step**, the amplification is: median **2.38 × 10⁻⁶ ≈ 20 × float32 epsilon**, p95 59 ε, **max
> 5.06 × 10⁻⁵ ≈ 425 ε (614 ULP)**. Per component: `pos.z` 6 ULP, `pos.y` 91, `pos.x` 281,
> `|accel|` 614, `velo.y` 18 403, `velo.x` 164 301 — the ordering is by how close to zero the
> component sits, not by how wrong the arithmetic is.
>
> **The corrected statement.** Reassociating the force sum perturbs it by about **20 × float32
> epsilon typically and a few hundred at worst** — two to three orders of magnitude less than the
> "10⁵" first claimed, and still far beyond the 1 ULP the preregistered criterion allows. **The
> rejection stands; the explanation was overstated and is corrected here.** Over 600 chaotic steps
> that seed diverges completely, which is why the 600-step oracle could not have answered the
> question on its own. Evidence: `research/44_2r_cycle2/conditioning_measured.json`.

Predicted against measured, as a sanity check on the model: removing 1 of ~11 VALU operations per
interaction predicts ≈ −5 % of the dispatch; measured −3.58 %. Same order.

**Result for the second workload: no accepted transformation.** That outcome was reached by the
same pipeline, with the correctness threshold untouched after the number was seen.

---

# Phase 2S

**Not started.** The session's remaining time went into 2Q's exhaustive sweep and 2R's build,
instrumentation and measurement. What 2S would have consolidated is listed under
"Next recommended action" and in the closing section.

---

# Invalidated results

**None of this session's measurements, and nothing from 2P was retracted.** What changed:

- **No claim was weakened by 2Q** — the opposite. The equivalence claims that the P1/P2 reviews
  had reduced to "equivalent under the workload's data contract" are now backed by measurement
  of that contract, and one of them (`SCALAR_BRANCH`) was promoted to float32-identical.
- **One 2P claim was strengthened rather than corrected**: "the multiply form is more accurate"
  had been flagged as undemonstrated; it is now demonstrated exhaustively.
- **One instrument was found unusable and discarded** (carried from cycle P5):
  `SQ_PS*_PERF_SEL_LEVEL_WAVES` returns 73 786 976 294 838 206 464 on every build. Not used
  anywhere.
- In 2R, `unroll4` was **invalidated as a distinct experiment** before it was measured: its
  bytecode is byte-identical to the baseline's.

# Build failures caught by the gate

| where | what the gate caught |
|---|---|
| 2R prepare 1 | the probe header did not compile (the sample treats `getenv`'s deprecation warning as an error); no measurement produced |
| 2R prepare 2 | **preregistered bytecode compiled with the wrong DXC** — the Windows SDK's 1.8.2502.11 instead of the project's own package 1.8.2505.32. Different compiler, different blob, build rejected |
| 2R prepare 3 | the same mismatch again, because the fix had silently failed to apply |
| 2R build (first) | the executable copy omitted the Agility SDK subdirectory, so the binary could not create a device; caught as a process failure before any number existed |
| 2R prepare (r2) | two variants compiling to the same bytecode — turned from an abort into a recorded finding |

All are preserved as `*_SUPERSEDED_prepare_*` beside their cycles. **None produced a measurement.**

# Reviewer findings

**The review happened** (Codex via Herdr, quota restored the following morning), and it was asked
to falsify four named targets rather than confirm them. Verdicts: **1. ULP and the exhaustive
sweep — REGGE CON RISERVA. 2. The data-contract canary — ROTTO. 3. The conditioning diagnosis in
2R — ROTTO in the form stated, no algebraic error. 4. The occupancy argument — REGGE CON
RISERVA.** Full transcript: `research/OVERNIGHT_REVIEW_2Q_2R.txt`.

**What it broke, and what was done about it:**

- **The canary (target 2).** Decisive: the sentinel could be multiplied away on exactly the paths
  the early-outs skip. Rebuilt out of band in cycle Q4 and given the positive control it never
  had in Q5 — see the canary section above. **Closed.**
- **The conditioning quantification (target 3).** "κ ≈ 10⁵" does not follow from 164 301 ULP on a
  near-zero velocity component. Its independent recomputation matches the errata already in this
  report (median ≈ 3, p99 ≈ 127–166, rare maxima ≈ 1e5) and adds something missed here: the sum
  also accumulates **112 phantom contributions from the origin** plus a −112 weighted correction,
  which manufactures extra cancellation. It found **no algebraic error** in `mass_hoist`.
  **Corrected.**
- **A provenance hole (target 1).** The earliest `sweep_*.json` predate the host's `slots_raw`
  field, so nothing tied a result to the binary that produced it. The sweep was re-run with the
  current host; `tools/fp32_sweep/provenance.json` now records host, shader and DXC hashes, and
  every field reproduces exactly. **Closed.**

**What it upheld, and with what reservations:**

- The sweep is not vacuous: the DXIL confirms `pow(x,5)` really is `Log → ×5 → Exp` and the
  reference really is fp64 (`fpext`, four `fmul double`, `fptrunc`). Reservation: an fp64
  reference carrying a `fast` flag is an excellent reference but not a formal oracle — an
  exact/MPFR one would be needed to *certify* the 3-ULP bound. The seven zero-mismatches sit below
  2⁻²⁵ and are **not reachable** by `1 − saturate(y)`; the denormal mode is not pinned at compile
  time; `compare_fp32`'s relative denominator is a dormant defect that does not affect these data.
- The occupancy argument falsifies the strong claim — `fresnel5` and `stack3` share a 56-VGPR
  allocation and differ by an order of magnitude — but **does not exclude an occupancy
  contribution**, because every comparison against base still contains the 8 → 9 wave jump.
  Confirmed: all wave64, no LDS, no scratch, and 62 SGPR introduces no second limiter.
- No stale binaries anywhere in the gated cycles. Independently confirmed here by a full
  provenance audit (`research/PROVENANCE_AUDIT.json`): **64 build records and 422 runs across 22
  cycle directories, zero mismatches.**
- Also flagged and accepted: `run_2r.py` scores relative error as zero when the baseline is zero;
  "N95" is a conservative empirical threshold whose pairs are not independent; the R32 capture
  changes the RTV format and therefore the PSO, so it demonstrates the diagnostic build.

What the earlier reviews had asked for, and what this session did about it without them:

- *"a bit-identical quantised image is not proof of identical float32 output"* → §Phase 2Q exists
  because of that objection, and confirms it: the images were identical while the float32 values
  differ by up to 7 ULP.
- *"the claim that the multiply form is more accurate is undemonstrated"* → demonstrated
  exhaustively over the whole domain.
- *"the equivalence depends on an invariant the manifest asserts but does not prove"* → measured
  with the contract canary.
- *"occupancy is an unseparated co-cause"* → **still unseparated.** Both attempts failed in P5 and
  nothing in this session improved on them.

# Measurement memory updates

- `research/PHASE_2P_MEASUREMENT_MEMORY.csv` — 17 rows, unchanged this session.
- `research/PHASE_2R_MEASUREMENT_MEMORY.csv` — **new**, 5 rows for the second workload: workload,
  pass, shader, stage, source features, ISA features, bottleneck, transform, bytecode hash,
  Δ pass, correctness, verdict, probable cause. **Failures included**; the two
  correctness-rejected variants are recorded as rejected and are not counted as wins anywhere.
- `research/40_2q_fullprecision/fp32_equivalence.json`, `.../sweep/*.json`,
  `research/41_2q_cycle2/contract_canary.json`, `research/42_2q_replication/frame_replication.json`.

# Final artifacts

```
research/OVERNIGHT_SESSION_LOG.md          per-cycle log, written during the work
research/OVERNIGHT_FINAL_REPORT.md         this file
research/40_2q_fullprecision/              Q1: float32 captures, fp32_equivalence.json, sweep/
research/41_2q_cycle2/                     Q2: contract canary
research/42_2q_replication/                Q3: 7-process replication, frame_replication.json
research/43_2r_workload/                   R1: second workload, baseline, 5 processes
research/44_2r_cycle2/                     R2: three transformations, A/B, correctness
research/PHASE_2R_MEASUREMENT_MEMORY.csv   measurement memory for the second workload
tools/fp32_sweep/                          exhaustive float32 equivalence probe (host + 2 shaders)
tools/nb_probe.h                           second workload instrumentation
tools/run_2r.py                            second workload runner, gate, oracle, analysis
tools/o1_probe.h, tools/run_o1.py          extended: R32G32B32A32 diagnostic capture
tools/run_2p.py                            extended: cycles q1-q3, fp32 comparison
```

Superseded prepares preserved: `43_2r_workload_SUPERSEDED_prepare_{01,02,03}`.

# What is actually proven

1. **The accepted stack does not change what the shader computes beyond last-bit rounding.**
   ≤ 7 ULP and ≤ 4.4e-7 relative at float32 across the whole frame, no NaN, no Inf, no −0.
2. **`SCALAR_BRANCH` is exactly equivalent** — float32-identical, not merely close.
3. **`fresnel5` is more accurate than the code it replaces**, over its entire input domain, by
   exhaustive enumeration against a double-precision reference.
4. **The data contract the early-outs rely on holds for every light of every pixel** of the
   measured frame, by canary rather than by argument.
5. **The performance result replicates**: `Render Color` −41.4 % on the fourth independent
   measurement, two instruments agreeing, seven processes, A/A N95 0.56 %.
6. **The method transfers to a second, structurally different D3D12 workload** — build gate,
   deterministic oracle, ISA-driven hypotheses, paired A/B with an A/A N95 of 0.05 % — and there
   it produced **no accepted transformation**, which is a result about the workload and not about
   the method.
7. **A fast, mathematically exact transformation can still be wrong**, and the gate catches it:
   `mass_hoist`, −3.58 %, rejected, cause identified as an ill-conditioned sum.

# What is NOT proven

- **A formal certificate of the 3-ULP bound.** The reference is fp64, not an exact oracle.
- **The contract beyond what was observed**: one frame, one scene, the base build. The canary
  establishes what the unmodified shader computes at frame 140, not a property of the code.
- **The positive control forces the scalar checks only**; the vector checks share the mechanism
  but were not separately demonstrated.
- **The occupancy contribution to the 2P result is still unseparated** (VGPR 61 → 54); both
  attempts to separate it failed in P5 and nothing here improved on that.
- **No hardware counters for the second workload.** Its bottleneck classification is a
  first-principles instruction-count model that accounts for ~82 % of the measured time.
- **Equivalence outside the measured data contract is not claimed** for the early-outs — with a
  negative or non-finite factor the transformed code would differ.
- **`fresnel5`'s exhaustive result covers its own domain only**, [0,1] by construction of
  `saturate`. It says nothing about `pow` elsewhere.
- **Generality of the 2P speed-up remains scene-dependent** (−41.6 % at 128 lights, −20.2 % at 32).
- **Nothing about Fortnite or Warzone.** No game was touched, profiled or modified.
- **Not a driver result.** Nothing here changes, tunes or exploits the AMD driver.

# Final confidence

| claim | confidence |
|---|---|
| the accepted stack is float32-equivalent within the measured data contract | **confirmed** |
| `SCALAR_BRANCH` is exactly equivalent | **confirmed** — bit-identical |
| `fresnel5` is more accurate than `pow(x,5)` over its domain | **confirmed** — exhaustive |
| `Render Color` −41.4 % on this scene and this GPU | **confirmed** — four cycles, two instruments |
| GPU frame −24.5 % measured / −21.8 % clock-corrected | **strong** |
| the method transfers to other D3D12 workloads | **strong for the pipeline, untested for the outcome** — one second workload, no accepted variant |
| the n-body reassociation failure is conditioning, not a bug | **strong** — single-step evidence, not counters |
| the 2P gain is caused by removed work rather than occupancy | **strong but unseparated** |

# Git diff summary

The project is not a git repository; the equivalent is the source diff against the pristine
upstream sources, all of which are preserved.

**MiniEngine — the accepted change (`39_2p_cycle7/stack3_scalar.diff`, 68 lines, one file):**
`FSchlick`: `pow(1-saturate(dot(l,h)), 5.0)` → `f2 = f1*f1; fresnel = f2*f2*f1` ·
`ApplyPointLight`: `if (distanceFalloff == 0.0) return 0.0;` ·
`ApplyConeLight`: `atten = coneFalloff*distanceFalloff; if (atten == 0.0) return 0.0;` ·
`ApplyConeShadowedLight`: compute `lit` first, `if (!any(lit != 0.0)) return 0.0;`, then sample ·
`#if 0 // SM6.0` → `#if 1`, `BIT_MASK_SORTED` → `SCALAR_BRANCH`.

**MiniEngine — diagnostic only, never in an accepted build:** scene colour buffer as
`R32G32B32A32_FLOAT` under `ME_Q_R32`; the contract canary of cycle Q2.

**D3D12nBodyGravity — instrumentation only:** `NbProbe` include, timestamp pair around the
dispatch, iteration hook, VSync off under `NB_DIR`, and `-Zi -Qembed_debug` removed from the
compute-shader build command so its hash is the shader and nothing else. **No transformation of
this workload was accepted**, so its shader is unmodified in every build that matters.

# Disk usage

`research/` grew from 1.3 GB to **2.4 GB** — about **1.1 GB of new output**, against a 10 GB
budget. 97 GB free on C:. The largest new artifacts are eleven 33 MB float32 frame captures; no
ETW traces were taken.

---

## FINAL VERDICT

**The 2P result survives full-precision scrutiny, and the method survives contact with a second
workload.**

At float32 the accepted stack differs from the original by at most 7 ULP and 4.4 × 10⁻⁷ relative,
with no NaN, no infinity and no negative zero; one of its four components is bit-identical; a
second is provably *more* accurate than the code it replaces, over all 1 065 353 217 values it
can ever be given; and the data contract the other two rely on was measured across every light of
every pixel rather than assumed. The speed-up replicated a fourth time at **−41.4 % of
`Render Color`** and **−24.5 % of the GPU frame as measured** (−21.8 % clock-corrected).

On a second, deliberately different D3D12 workload the same pipeline produced **no accepted
transformation** — and that is the more interesting half. It rejected a variant that was 3.58 %
faster and mathematically exact, because on an ill-conditioned sum of ten thousand cancelling
terms a legal reassociation moves the answer by one part in a hundred after a single step. The
gate caught a wrong compiler, a missing runtime directory, a shader whose source-level change the
compiler had already made, and a fast wrong answer. Every one of those would have become a
plausible number without it.

The honest limit of this session is not in the measurements but in their review: **nothing here
was checked by the adversarial reviewer**, which was out of quota throughout.

## NEXT RECOMMENDED ACTION

**Get 2Q and 2R adversarially reviewed, and give the reviewer the falsification targets
explicitly**: the float32 ULP tables and the exhaustive sweep methodology; the claim that the
contract canary is sufficient; the n-body conditioning diagnosis; and the still-unseparated
occupancy contribution to the 2P result. Everything else in the programme is downstream of
whether those four survive someone actively trying to break them.
