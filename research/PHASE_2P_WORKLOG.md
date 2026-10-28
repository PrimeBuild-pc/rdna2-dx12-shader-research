# Phase 2P — worklog

Target: the per-light loop of `ShadeLights`, identified by Phase 2O as carrying ~88 % of
`Render Color`'s GPU cycles. Rule for every cycle: no transformation is accepted on fewer
instructions, fewer VGPRs, smaller DXIL, shorter ISA or a microbenchmark. The judge is
`Render Color` in the real workload, with the image unchanged.

Session budget: **10 new cycles.** Used: **8** (R, P1-P7). Stopped on a robust and
replicated conclusion, not on budget. Final report:
[`PHASE_2P_FINAL_REPORT.md`](PHASE_2P_FINAL_REPORT.md).

---

## Cycle R — clean-room replication of Phase 2O · **PASS** · cycle 1/10

Environment verified idle first (`research/32_clean_replication/environment_snapshot.md`):
no browser, no Discord, no game, no encoder; **1.69 % total GPU** (desktop compositor only),
live CPU under 0.5 %. No application was closed.

Three arms, criteria preregistered: baseline work counters within ±2 % (measured **+0.00 %** and
**+0.01 %**), O4's sampler comparison (−3.76 % vs −3.50 % historical), O6's light-count
comparison (−61.75 % vs −61.57 %, marginal cost 13.11 vs 13.13 cycles). All inside tolerance by
one to two orders of magnitude.

**CLEAN_REPLICATION = PASS.** Background load drove none of Phase 2O's conclusions, and the
`GPUTime` clock excursion documented in O4/O6 reappears on the idle machine, so it is intrinsic
to this GPU's clock behaviour. → `research/32_clean_replication/CLEAN_REPLICATION.md`

---

## Cycle P1 — the two cheapest semantics-preserving rewrites in the loop · cycle 2/10

**Where the hypothesis came from.** The baseline pixel shader ISA was generated with RGA for
gfx1030, using a root signature reconstructed from `Renderer::m_RootSig`. Three loops are
visible — sphere (72 instructions), cone (80) and shadowed cone (107) — and the histogram shows,
**per light iteration**, 2 × `v_log_f32` + 2 × `v_exp_f32` and 3 × `v_rsq_f32`. Reading the code
against the ISA:

- `(gloss + 2) / 8` is **already hoisted** out of all three loops by the compiler (the `v_mul` by
  0.125 sits before the first loop). No opportunity there — checked rather than assumed.
- `FSchlick`'s `pow(x, 5.0)` is emitted as `v_log_f32` → `v_mul_f32` by 5.0 → `v_exp_f32`.
  **Neither DXC nor the AMD backend strength-reduces a constant integer exponent.**
- `ApplyConeShadowedLight` samples the shadow map, then multiplies by `ApplyConeLight`, which
  returns zero whenever the cone or distance falloff is zero at that pixel.

**Hypothesis.** Two rewrites reduce real work without changing what the shader computes:
`fresnel5` (x⁵ by multiplication) touches **ALU only**; `shadowskip` (falloff first, sample only
when it can matter) reduces **texture work** data-dependently.

**Criteria, fixed in the manifest before the first build.** Correctness: max relative channel
error ≤ 1e-3 against the base image, no non-finite channel, after a base-vs-base determinism
check. Performance: median Δ`GPUBusyCycles` ≤ −max(1 %, 3 × N95) **and** all three paired
process deltas negative. Three independent processes per variant, order interleaved and reversed.

**Build gate.** Three builds, three distinct preregistered bytecode hashes
(`52CE6C5E64AB2E82` / `497475102E01A389` / `3EEEF5D26C22E733`), all matched. `fresnel5`'s
bytecode is 72 bytes *smaller* than the baseline, `shadowskip`'s 60 bytes larger.

### Dose — what actually changed

| variant | kind | texture instr | Δ | VALU instr | Δ | VALU cycles | Δ |
|---|---|---:|---:|---:|---:|---:|---:|
| `base` | — | 6 110 270 | — | 70 955 814 | — | 183 102 476 | — |
| `fresnel5` | alu_only | 6 105 478 | **−0.08 %** | 71 349 039 | +0.55 % | 172 326 937 | **−5.88 %** |
| `shadowskip` | texture+alu | 4 871 496 | **−20.27 %** | 68 441 158 | −3.54 % | 176 720 716 | −3.49 % |

`fresnel5` is the mechanism made visible: the VALU **instruction** count goes slightly *up* while
VALU **cycles** drop 5.88 %. Three multiplies replace log + mul + exp — the same number of
instructions, a quarter of the issue cost, because transcendentals are quarter-rate.

### Response (paired against `base`; A/A control N95: `GPUBusyCycles` 0.27 %, `TA_BUSY` 0.20 %)

| variant | Δ`GPUBusyCycles` (per process) | Δ`TA_BUSY` | Δ`GPUTime` |
|---|---|---:|---:|
| `fresnel5` | **−3.17 %** (−2.97, −3.17, −3.24) | −3.21 % | −2.49 % |
| `shadowskip` | **−5.48 %** (−5.48, −5.57, −5.42) | −12.40 % | −5.45 % |

### Correctness

Base vs base: **identical**. `fresnel5` vs base: **bit-identical**. `shadowskip` vs base:
**bit-identical**. Not merely within tolerance — the captured 1920×1080 R11G11B10 images are
byte-for-byte equal. For `shadowskip` that is what the equivalence argument predicts; for
`fresnel5` the float32 differences are far below this format's 6-bit mantissa.

### Verdict

**Both ACCEPTED.** The first end-to-end wins of the project: −3.17 % and −5.48 % of
`Render Color`, on unmodified Microsoft engine code, with an identical image.

### What P1 settles that Phase 2O could not

`fresnel5` is **the mirror of O4**. O4 moved texture work with ALU verified fixed and the pass
followed by −2.6 %. P1 moves ALU work with the texture instruction count fixed (−0.08 %, inside
the ±0.4 % emulation band) and the pass follows by −3.17 %.

> **Both saturated units are on the critical path, and neither dominates.** Reducing either one
> alone reduces the pass. This is the factorial arm 2O said was missing.

`TA_BUSY` behaves differently in the two variants and that is informative: under `fresnel5` it
falls 3.21 % against a 3.17 % fall in pass duration, i.e. the addresser stays pinned at its ~93.6 %
duty and `TA_BUSY` simply tracks the shorter pass; under `shadowskip` it falls 12.40 % against
5.48 %, i.e. the addresser genuinely drains. So `TA_BUSY` is **not** a pure work counter in this
pass — a caveat that applies to how O6 read it.

**Next:** stack the two (additivity must be measured, not assumed) and test the same early-out
idea one level up, in `ApplyPointLight` / `ApplyConeLight`, where a zero distance falloff
currently still pays for the whole of `ApplyLightCommon`.

---

## Cycle P2 — the same idea further up the call chain, and the stack · cycle 3/10

**Hypothesis.** P1's `shadowskip` works because it refuses to pay for a contribution that is
exactly zero. The same refusal applies one level up (`ApplyPointLight` / `ApplyConeLight`, where
a zero distance or cone falloff still pays for the whole of `ApplyLightCommon`) and two levels up
(`ApplyLightCommon` itself, where `nDotL == 0` for every light at or behind the surface). Plus:
is P1's pair additive?

Three variants, all preregistered before building: `combo` (fresnel5 + shadowskip),
`falloffskip`, `ndotlskip`. Four distinct gated bytecode hashes. Statistics strengthened after
the P1 review: **5 independent processes** per variant on the response set, order counterbalanced
so no variant is always in the same position.

### Dose

| variant | texture instr | VALU instr | VALU cycles |
|---|---:|---:|---:|
| `combo` | **−20.29 %** | −2.92 % | **−9.33 %** |
| `falloffskip` | −13.87 % | **−40.62 %** | **−44.63 %** |
| `ndotlskip` | −6.14 % | −11.14 % | −15.75 % |

`falloffskip` was declared `alu_only` and **is not**: texture instructions fall 13.87 % as well.
The reason is visible in the code — `lightData.color` is only needed on the non-early path, so
the compiler sinks that buffer load behind the new branch. Labelled by intent, corrected by
measurement.

### Response (A/A on base over 5 processes: `GPUBusyCycles` N95 0.60 %, threshold 1.80 %)

| variant | Δ`GPUBusyCycles` | per process | Δ`TA_BUSY` |
|---|---:|---|---:|
| `combo` | **−7.32 %** | −7.23, −7.16, −7.40, −7.64, −7.32 | −13.54 % |
| `falloffskip` | **−27.59 %** | −27.74, −27.53, −27.59, −28.09, −27.56 | −25.64 % |
| `ndotlskip` | −9.76 % | −9.76, −9.57, −9.58, −10.16, −9.81 | −8.27 % |

`GPUTime` is unusable at this precision here — its A/A N95 came out at **13.05 %**, the same
first-process clock excursion documented in O6 and confirmed on the idle machine in cycle R.
`GPUBusyCycles` N95 is 0.60 %.

**Additivity is sub-additive and was measured, not assumed:** `fresnel5` −3.17 % and
`shadowskip` −5.48 % would sum to −8.65 %; together they give **−7.32 %**.

### Correctness — the gate rejected one, and the criterion itself was wrong

| variant | image |
|---|---|
| `combo` | **bit-identical** |
| `falloffskip` | **bit-identical** |
| `ndotlskip` | **differs**: 2 pixels of 2 073 600, max abs 6.25e-2, max rel **1.32e-2** |

Against the preregistered threshold (max relative channel error ≤ 1e-3) `ndotlskip` **FAILS**, and
it is recorded as rejected. The threshold is not relaxed after the fact.

The diagnosis, for the record: 6.25e-2 at a channel value of ~4.73 is **exactly one ULP** of an
R11G11B10 channel at that magnitude. Reordering `nDotL` above the half-vector maths changes FMA
contraction in the surviving path, so two pixels round differently. **A relative threshold of
1e-3 is unreachable in a format whose ULP is ~1/64 ≈ 1.6 % relative** — the criterion as written
can only ever pass a bit-identical image. That is a flaw in my criterion, not evidence about
`ndotlskip`, and it is fixed forward in P3 with a ULP-based criterion preregistered before the
next measurement.

### Verdict

`combo` **ACCEPTED**. `falloffskip` **ACCEPTED — −27.59 % of `Render Color`, image
bit-identical.** `ndotlskip` **REJECTED (correctness)**; it is not counted as a win anywhere and
its −9.76 % is reported only as an observation.

---

## Cycle P3 — the stack, and a correctness rule that can actually be met · cycle 4/10

**Two things at once.** Stack everything P1 and P2 accepted, and replace the correctness rule
that P2 showed to be unmeetable. The new rule is written into P3's manifest **before** P3
measures anything, and P2's verdicts are left exactly as recorded:

> every differing channel differs by at most **1 ULP** of its stored R11G11B10 representation, at
> most **0.05 %** of channels differ at all, and no channel is non-finite.

One ULP is the smallest change this render target can represent, so the rule admits a different
rounding and nothing more.

| variant | contents |
|---|---|
| `stack3` | `fresnel5` + `shadowskip` + `falloffskip` — the three accepted ones |
| `stack4` | `stack3` + `ndotlskip` |

### Dose and registers

| variant | texture instr | VALU instr | VALU cycles | VGPR | static loop instructions |
|---|---:|---:|---:|---:|---:|
| `base` | — | — | — | 61 | 259 |
| `stack3` | **−34.10 %** | **−44.92 %** | **−49.59 %** | 55 | 305 |
| `stack4` | −34.87 % | −45.23 % | −50.35 % | 47 | 341 |

The static loop bodies get **bigger** (259 → 305 → 341 instructions) while the executed work
halves. A phase that spent 2E–2K learning not to trust static metrics gets a final illustration
of why.

### Response (5 counterbalanced processes; A/A on base: `GPUBusyCycles` N95 0.41 %, threshold 1.24 %)

| variant | Δ`GPUBusyCycles` | per process | Δ`TA_BUSY` | Δ`GPUTime` |
|---|---:|---|---:|---:|
| `stack3` | **−37.51 %** | −37.52, −37.40, −37.32, −37.84, −37.51 | −37.13 % | −32.65 % |
| `stack4` | **−39.42 %** | −39.42, −39.39, −39.35, −39.54, −39.48 | −39.24 % | −33.88 % |

### Correctness

| variant | image |
|---|---|
| `stack3` | **bit-identical** to the baseline |
| `stack4` | 3 pixels of 2 073 600 differ by exactly **1 ULP** (0.00005 % of channels) → PASS |

### Verdict

**`stack3` ACCEPTED: −37.51 % of `Render Color` with a byte-identical image.**
`stack4` ACCEPTED under the ULP rule, at −39.42 %; the extra 1.9 points cost the only pixels in
the whole phase that are not bit-identical.

Sub-additivity again, measured: −3.17 %, −5.48 % and −27.59 % individually do not compose to
−37.51 % by any arithmetic — the transformations overlap, and the stack is what was measured.

---

## Cycle P4 — does it survive a different scene, and what does it do to the frame · cycle 5/10

Two questions in one cycle, using cycle P3's gated executables plus two new builds that add
cycle O6's light-count lever (C++ data only) to make a **sparse-light regime**. The L32 arms are
compared against the L32 baseline and never against the dense one; `base_l32` is a *regime
baseline*, not a candidate, and is excluded from the correctness verdict for that reason.

**Whole frame**, measured through a completely independent path — MiniEngine's own GPU timer
tree, benchmark mode, 1000 frames after 300 of warm-up, 3 processes:

| scope | base | stack3 | Δ |
|---|---:|---:|---:|
| **GPU frame** | 1.0249 ms | 0.7987 ms | **−22.06 %** |
| `Render Color` | 0.5109 ms | 0.3231 ms | **−36.75 %** |
| `Scene Render` | 0.9384 ms | 0.7162 ms | −23.68 % |
| `Resolve Image` | 0.0805 ms | 0.0700 ms | −12.98 % |

The −36.75 % on `Render Color` here and the −37.38 % from GPA in the same cycle come from two
different instruments and agree to 0.6 points.

**Generality across light density:**

| regime | Δ`Render Color` (GPA) | Δ GPU frame |
|---|---:|---:|
| dense, 128 lights | **−37.38 %** | −22.06 % |
| sparse, 32 lights | **−20.19 %** | −6.71 % |

The gain **shrinks but survives**. Its size is content-dependent — as the adversarial review of
P1 predicted it might be — while the effect itself is structural. `stack3_l32`'s image differs
from `base_l32` by 1 ULP on one pixel; `stack3`'s is bit-identical.

## Cycle P5 — is it less work or more waves in flight · cycle 6/10

The P2/P3 review's strongest objection: every accepted variant also lowers VGPR use
(61 → 55 for `stack3`), which on RDNA2 raises theoretical wave occupancy, so "less work" and
"better latency hiding" are not separated.

**Attempt 1 — a direct occupancy counter. Failed.** `SQ_PS*_PERF_SEL_LEVEL_WAVES` exists and was
measured on six builds: it returns **73 786 976 294 838 206 464 on every one of them**, identical
to the digit, i.e. ~7.4 × 10¹⁹ waves. The counter is not usable on this ASIC through this path.
Recorded as an instrumentation defect, like the SQ corruption found in O3, and discarded.

**Attempt 2 — hold the registers up while keeping the arithmetic. Failed.** `stack3_pad` keeps
three `float4` values live across the light loops and consumes them under `FrameIndexMod2 == 2`,
a condition that is false in every frame but opaque to the compiler. The image is bit-identical,
so the construct is semantically inert — but VGPR use moved only 55 → 56, because the compiler
rematerialises the padded values rather than keeping them live. The intended control does not
exist.

**What does answer the question, from data already in hand.** VGPR allocation buckets on RDNA2
(granularity 8, wave64) put `fresnel5` (56), `shadowskip` (54) and `stack3` (55) **all in the
same 56-VGPR bucket — the same theoretical occupancy**, 9 waves per SIMD against the baseline's 8:

| variant | VGPR | alloc | waves/SIMD | Δ`GPUBusyCycles` |
|---|---:|---:|---:|---:|
| `base` | 61 | 64 | 8 | — |
| `fresnel5` | 56 | 56 | 9 | −3.17 % |
| `shadowskip` | 54 | 56 | 9 | −5.48 % |
| `stack3` | 55 | 56 | 9 | **−37.49 %** |

Three variants at identical theoretical occupancy span **−3 % to −37 %**. Occupancy cannot
produce that spread; the work reduction can and does. It may still contribute to the first few
points, and nothing here separates that part — but it is not what the result is made of.

**A null control the phase had been missing.** `base_pad` — the unmodified shader plus the same
inert padding, a *different* bytecode (+112 bytes), the same work — measures **+0.01 %**
(+0.01, +0.12, +0.20, −0.07, −0.04 across five processes). Recompiling and shifting the binary
does not move this measurement.

`stack3` replicated a third time here at **−37.49 %** (P3: −37.51 %, P4: −37.38 %).

## Cycle P6 — the engine's own scalarisation path · cycle 7/10

`Lighting.hlsli` ships four alternative light-iteration strategies behind `#if 0 // SM6.0`.
`SCALAR_BRANCH` is the one that keeps the original three loops and their order and only asks,
per wave, whether all lanes share a tile; when they do — which a wave covering an 8×8 pixel block
inside a 16×16 tile usually does — the tile offset is read once with `WaveReadLaneFirst` and the
light data can live in scalar registers. Same lights, same arithmetic, same accumulation order.

| variant | Δ`GPUBusyCycles` | Δ`TA_BUSY` | VGPR | SGPR | image |
|---|---:|---:|---:|---:|---|
| `scalar` | **−3.84 %** | −12.43 % | 48 | 62 | bit-identical |
| `stack3_scalar` | **−41.55 %** | −44.37 % | 54 | 62 | bit-identical |

Scalarisation alone is worth 3.8 %; on top of `stack3` it takes the total from −37.5 % to
**−41.6 %**. VGPR falls to 48 and SGPR rises to 62, which is what moving light data into scalar
registers looks like.

## Cycle P7 — final verification · cycle 8/10

Fresh builds, fresh baseline, five counterbalanced processes, plus the whole-frame benchmark.

| variant | Δ`Render Color` (GPA) | Δ`TA_BUSY` | Δ`Render Color` (engine timer) | Δ GPU frame | image |
|---|---:|---:|---:|---:|---|
| `stack3_scalar` | **−41.60 %** | −44.40 % | −40.34 % | **−24.39 %** | **bit-identical** |
| `stack4_scalar` | −42.94 % | −45.55 % | −41.24 % | −24.93 % | 1 ULP on 3 pixels |

Per process, `stack3_scalar`: −41.60, −41.53, −41.84, −41.69, −41.53 %. GPU frame per process:
base 1.0314 / 1.0295 / 1.0236 ms against 0.7784 / 0.7778 / 0.7794 ms.

**Final candidate: `stack3_scalar`.** The extra 1.3 points of `stack4_scalar` cost the only
pixels in the phase that are not bit-identical, so it is recorded as accepted but not preferred.
