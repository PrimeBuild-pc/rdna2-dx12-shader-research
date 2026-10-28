# Overnight autonomous session — log

Started 2026-09-06 late evening, continuing into 2026-09-07. Budget: **12 new cycles or ~8 hours**.
Programme: **2Q** full-precision equivalence → **2R** generalisation to a second D3D12 workload →
**2S** infrastructure, if time remains.

Entering state: Phase 2P accepted `stack3_scalar` at `Render Color` −41.6 % (GPU busy cycles),
−40.3 % on MiniEngine's own timer, GPU frame −24.4 % raw / ≈−21.7 % clock-corrected, with a
**bit-identical R11G11B10 image**. What that does *not* prove is float32 equivalence, which is
what 2Q exists to settle.

Environment at start: 108 GB free on C:. Cycle counter below is for this session only.

---

## Cycle 1 — Q1: the float32 equivalence measurement · **the question 2P left open, answered**

**Hypothesis.** A bit-identical R11G11B10 image proves only that two shaders agree after being
squeezed into six mantissa bits. Captured at full precision, the accepted transformations will
differ — and the size of that difference is what decides whether they are equivalent.

**Pre-registration.** Determinism must be shown first: two independent processes of the same
build must produce byte-identical float32 captures, or nothing else can be judged against them.
Each accepted transformation is measured **alone**, so a failure attributes to one of them.
Metrics fixed before measuring: differing channels, max ULP (on a monotonic mapping of the IEEE
bit patterns, the only way to count representable steps across zero), max abs, max rel, RMS,
NaN, ±Inf, −0.

**Experiment.** `research/40_2q_fullprecision`, experiment `P_20260907_000419`, fresh workspace.
Two instrumentation changes, both inert unless `ME_Q_R32` is set: the scene colour buffer is
created as `R32G32B32A32_FLOAT`, and the capture probe writes 16 bytes per pixel and exits the
process straight after saving, so no post-processing pass can fail on a format it was never
written for. Eight builds, every bytecode hash **identical to the ones the P-cycles gated**,
from a workspace that did not exist then.

**Correctness — the result.**

| variant | identical | differing channels | max ULP | max abs | max rel | RMS | NaN / Inf / −0 |
|---|---|---:|---:|---:|---:|---:|---|
| base vs base | **yes** | 0 | 0 | 0 | 0 | 0 | 0 / 0 / 0 |
| `scalar` | **yes** | 0 | 0 | 0 | 0 | 0 | 0 / 0 / 0 |
| `fresnel5` | no | 80 752 (1.30 %) | **7** | 3.8e-6 | **4.33e-7** | 6.4e-9 | 0 / 0 / 0 |
| `shadowskip` | no | 45 983 (0.74 %) | 3 | 4.8e-7 | 3.03e-7 | 6.2e-9 | 0 / 0 / 0 |
| `falloffskip` | no | 831 363 (13.4 %) | 3 | 3.8e-6 | 2.58e-7 | 1.0e-8 | 0 / 0 / 0 |
| `ndotlskip` | no | 1 098 017 (17.7 %) | 3 | 3.8e-6 | 2.49e-7 | 3.0e-8 | 0 / 0 / 0 |
| `stack3_scalar` | no | 871 510 (14.0 %) | **7** | 3.8e-6 | **4.33e-7** | 1.2e-8 | 0 / 0 / 0 |
| `stack4_scalar` | no | 1 324 963 (21.3 %) | 7 | 7.6e-6 | 4.37e-7 | 2.9e-8 | 0 / 0 / 0 |

**`SCALAR_BRANCH` is bit-identical at float32** — the accumulation-order argument is now measured,
not reasoned. Everything else differs at the last bit or two: max 7 ULP, max relative 4.4e-7,
which is 3.6 × float32 epsilon. **No NaN, no Inf, no negative zero in any capture**, and the
baseline's own value range is [0, 56.33].

**Exhaustive verification of `fresnel5`.** `saturate` clamps its input to [0,1] and maps NaN to
zero, so the domain of `pow(x, 5)` there is exactly the 1 065 353 217 float32 values in [0,1].
All of them were swept on the GPU (`tools/fp32_sweep`, a new minimal D3D12 compute host):

- the two forms differ on 204 485 077 inputs (19.2 %);
- for x ≥ 2⁻²⁵ the disagreement is bounded: **max 156 ULP, max relative 9.4e-6, max absolute
  1.19e-7** (one ULP at 1.0);
- below 2⁻²⁵ the relative error reaches 1.0 and the ULP distance 8 388 608 — but the absolute
  magnitude there is at most **1.18e-38**, and the 7 cases where one form gives exactly zero and
  the other a denormal all live in that region;
- **no NaN, no Inf, no negative zero anywhere in the domain.**

**And which form is right?** A second sweep computes the reference in **double precision** and
asks which of the two is closer to the true x⁵, again over all 1 065 353 217 values:

| | `pow(x,5)` | `f2*f2*f1` |
|---|---:|---:|
| strictly closer to the true value | 4 852 143 (0.46 %) | **196 984 236 (18.49 %)** |
| equally close | 863 516 838 (81.06 %) | — |
| **max ULP error vs the true x⁵** | **8 388 608** | **3** |
| **max relative error vs the true x⁵** | **9.35e-6** | **2.52e-7** |

The P1 review had flagged "the multiply form is more accurate" as an undemonstrated claim. It is
now demonstrated, exhaustively and in the right direction: the transformation is **never worse
than 3 ULP from the exact value anywhere in its domain**, while `pow` reaches 9.35e-6 relative —
its error grows with |log₂ x| because it is `exp2(5·log2(x))`.

**Verdict.** `scalar`: **PASS_STRICT** — float32-identical. `fresnel5`: exhaustively verified over
its whole reachable domain and strictly more accurate than what it replaces. `shadowskip`,
`falloffskip`, `ndotlskip`: differences bounded at 3 ULP on the real frame with no non-finite or
negative-zero value anywhere — **PASS_CONTRACT**, pending the contract canary of the next cycle.
No threshold was loosened: none had been preregistered for float32, so the prompt's own
PASS_STRICT / PASS_CONTRACT definitions are used rather than one invented after seeing the data.

**Next.** The three control-flow transformations rest on "0 × X = 0 for finite non-negative X".
Q2 measures X directly across the whole frame instead of arguing about it.

## Cycle 2 — Q2: the data contract, measured

**Hypothesis.** `shadowskip`, `falloffskip` and `ndotlskip` are exactly equivalent *if* the value
they multiply by an exactly-zero factor is finite and non-negative. That is an assumption about
the workload's data, and it can be measured instead of argued.

**Experiment.** `contract_canary`: the baseline shader plus a detector. `ApplyLightCommon` checks
its return value, `lightColor` and `specularFactor`; `GetShadowConeLight` checks its result;
`ApplyConeShadowedLight` checks that `shadowCoord.w` is finite and non-zero. Any NaN, infinity or
negative value turns the pixel into 1e30. The baseline's maximum is 56.33, so a single violation
anywhere in the frame is unmissable in a full-precision capture. Not a candidate — the arithmetic
is untouched.

**Result.** Maximum of the canary capture: **56.3287467956543** — bit-for-bit the baseline's own
maximum. **Zero pixels at or above 1e3. No non-finite value, no negative value, no negative zero.**

**Verdict.** The data contract holds for every light of every pixel of the measured frame:
`0 × X = 0` exactly, so the three control-flow transformations are exactly equivalent **on this
workload**, by measurement. Note the canary's own capture differs from the baseline by up to 3
ULP — restructuring the return changes instruction contraction, exactly as `ndotlskip` did — which
is why the verdict is read from the maximum and not from an image hash.

## Cycle 3 — Q3: the final performance replication

Fresh cycle, fresh baseline, **7 counterbalanced processes** for the pass and 5 for the frame, on
the verified-idle machine (GPU 1.72 %, 102 GB free).

| metric | `stack3_scalar` | `stack4_scalar` |
|---|---:|---:|
| `Render Color` `GPUBusyCycles` (GPA, 7 processes) | **−41.43 %** | −42.76 % |
| per process | −41.43, −41.59, −41.47, −41.21, −41.45, −41.37, −41.34 | −42.63 … −43.05 |
| `TA_BUSY` | −44.18 % | −45.31 % |
| `Render Color` (MiniEngine timer, 5 processes) | **−40.24 %** | −41.31 % |
| **GPU frame — MEASURED** | **−24.47 %** | −25.23 % |
| **GPU frame — CLOCK-CORRECTED ESTIMATE** | **−21.78 %** | — |

A/A control across 7 processes: `GPUBusyCycles` N95 0.56 %, acceptance threshold 1.67 %.
The two numbers for the frame are kept apart and never mixed: MEASURED is the median of five
independent processes; CLOCK-CORRECTED removes the −3.44 % that `Z PrePass` and `Generate SSAO`
also show — passes this change cannot touch — on the assumption that it is a clock/power effect.

The correctness section of this cycle's analysis reads "incomplete" because no R11G11B10 capture
was taken here; correctness was settled at full precision in Q1 and Q2 and is not re-litigated.

**Phase 2Q verdict: the accepted stack survives full-precision scrutiny.** `SCALAR_BRANCH` is
float32-identical (PASS_STRICT); `fresnel5` is exhaustively verified over its entire reachable
domain and is *more* accurate than what it replaces; the three early-outs are PASS_CONTRACT with
the contract measured rather than assumed. **Nothing was removed from the stack.**

## Cycle 4 — R1: a second workload, built, instrumented and gated

**Selection criteria written before choosing** (`43_2r_workload/experiment_manifest.json`):
open source, D3D12, buildable with the toolchain already verified here, repeatable, no
anti-cheat, modifiable, GPU-bound enough to measure, **structurally different** from
ModelViewer/Sponza, and small enough for the budget — and chosen *without* first checking
whether it contained a shader that looked easy to optimise.

Rejected under those criteria and recorded: eighteen samples too small or not GPU-bound;
`D3D12RaytracingMiniEngineSample` because it is MiniEngine again; the other raytracing samples
and the FidelityFX sample framework as too large for the budget; 3DMark Steel Nomad, which is
installed and GPU-heavy but closed source.

**Chosen: `Samples/Desktop/D3D12nBodyGravity`** — an O(N²) n-body simulation, one compute
shader, 10 000 particles, LDS tiling, no textures, no lighting, no light grid. About as far from
a per-light pixel-shading loop as this repository offers.

**Getting it to build was itself a provenance exercise.** The project wants three NuGet packages;
two were already in the clone, the third (DXC 1.8.2505.32) was fetched. Then **the build gate
rejected the first build**: the preregistered bytecode had been compiled with the Windows SDK's
DXC (1.8.2502.11) while the project builds with its own package's DXC (1.8.2505.32) — different
compiler, different blob, different hash. That is exactly what the gate is for. Two further
prepares were superseded (a probe header that did not compile, and the same compiler mismatch
uncorrected); none of the three produced a measurement.

**Instrumentation** (`tools/nb_probe.h`, inert unless `NB_DIR` is set): a timestamp pair on the
compute queue around the simulation dispatch, per-iteration timing after a warm-up, VSync off,
and — the part that matters — **the particle buffer copied back and written as float32**. For a
deterministic simulation the state after a fixed number of steps is a far sharper correctness
oracle than any image.

**Baseline, 5 independent processes:** dispatch **156 400 ns** (156 360 / 156 360 / 156 400 /
156 480 / 156 520), **A/A N95 = 0.10 %**, and the particle dump **byte-identical across all five
processes**. Tighter than anything measured on MiniEngine.

## Cycle 5 — R2: three hypothesis-driven transformations, and a correctness gate that earned its keep

**Hypotheses from the ISA** (RGA, gfx1030: 85 VGPR, 16 SGPR, 2 KB LDS, no scratch). Two things
the ISA settled before anything was written: `1.0f / sqrt(distSqr)` is **already** a single
`v_rsq_f32` — the compiler does that strength reduction itself — and the softening constant is
already folded into a `v_fmaak_f32`. What remained: arithmetic the compiler is not allowed to
move, and shapes that cost registers.

| variant | hypothesis | Δ dispatch | correctness |
|---|---|---:|---|
| `unroll4` | halve the unrolled body to cut the 85-VGPR pressure | — | **bytecode identical to base**: DXC fully unrolls both, so the source unroll factor is invisible |
| `lds_float3` | only `.xyz` of `sharedPos` is ever read; store `float3` and cut LDS 2048 → 1536 B | **+1.28 %** (slower, 5/5) | **bit-identical** |
| `mass_hoist` | the particle mass is a constant factor of every term: `Σ rᵢ·m·cᵢ = m·Σ rᵢ·cᵢ`, so one multiply per interaction disappears | **−3.58 %** (5/5) | **FAIL** |
| `all3` | the three together | −5.91 % (5/5) | **FAIL** |

A/A on base across 5 processes: **N95 0.05 %**, acceptance threshold 1.00 %.

**The interesting one is `mass_hoist`.** It is 3.58 % faster and mathematically exact, and the
gate rejected it. After 600 simulation steps its particle state differed from the baseline's by
up to 2.3 × 10⁹ ULP — which on its own would be explained away as chaos in an n-body system. So
the question was settled by measuring **after a single step**: 32 336 of 80 000 values differ,
**max 164 301 ULP, max relative 1.06 × 10⁻²**. That is not chaos and not a coding error: it is
the force sum being ill-conditioned. Ten thousand vectors largely cancel, so a rounding-order
change of one part in 10⁷ per term lands as one part in 10² in the result — a condition number
around 10⁵. Reassociation is legal in algebra and not in this sum.

**Verdict for the second workload: no accepted transformation.** One no-op the compiler had
already made, one bit-identical variant that measured *slower*, and one fast variant rejected on
correctness with the cause identified. A negative result, obtained by exactly the pipeline 2P
used, and the threshold was not touched after seeing the number.

---

## Cycle 6 — the adversarial review of 2Q and 2R, and what it broke

The reviewer (Codex, via Herdr; quota restored) was asked to **falsify**, not confirm, four named
targets. It recomputed everything independently in `%TEMP%` and read the DXIL. Verdicts:

| target | verdict |
|---|---|
| 1. ULP and the exhaustive sweep | **REGGE CON RISERVA** |
| 2. The data-contract canary | **ROTTO** |
| 3. The conditioning diagnosis in 2R | **ROTTO in the form stated**; no algebraic error found |
| 4. The occupancy argument in 2P | **REGGE CON RISERVA** |

**Target 2 is the real hit, and it is decisive.** The canary writes its 1e30 sentinel *into the
value that is then multiplied by zero*. So on `falloffskip`'s path, `distanceFalloff == 0` gives
`0 × 1e30 = 0`; on `shadowskip`'s, `lit == 0` gives `lit × 1e30 = 0`. **The sentinel is silenced
exactly on the paths the early-outs skip** — the ones it was built to watch. "Any violation
becomes a 1e30 pixel" is false. Further: `ndotlskip` is not covered rigorously (the check is on
`nDotL·RHS`, not on `RHS`); one frame is not "every light of every pixel" in general; and the
canary ran only on the base build.

**Target 1 holds with reservations**, all verified from the artifacts: the sweep's `pow(x,5)` is
genuinely `Log → ×5 → Exp` in the DXIL and the reference is genuinely fp64 (`fpext`, four
`fmul double`, `fptrunc`) — so the comparison is not vacuous. But "the true value" is slightly
too strong for an fp64 reference carrying a `fast` flag; the seven zero-mismatches sit below
2⁻²⁵ and are **not reachable** by `1 - saturate(y)`; the denormal mode is not pinned at compile
time; and — a real provenance hole — the earliest `sweep_*.json` files predate the host's
`slots_raw` field, so they came from an earlier binary, with no CSO/EXE hash or DXC version
recorded.

**Target 3 matches the errata I had already written**, and sharpens it: median condition number
≈ 3, p99 ≈ 127–166, rare maxima ≈ 1e5 — not "≈1e5" as a general figure. It also found something
I had missed: the sum accumulates **112 phantom contributions from the origin** plus a −112
weighted correction term, which manufactures extra cancellation. No algebraic error in
`mass_hoist`: `mass` is common to the correction term too, and `accel *= mass` precedes both uses.

**Target 4 holds in the weak form only.** The same-bucket comparison does falsify "the gain is
just the VGPR bucket jump" — `fresnel5` and `stack3` share a 56-VGPR allocation and differ by an
order of magnitude in effect. It does **not** exclude an occupancy contribution, because every
comparison against base still contains the 8 → 9 wave jump. Confirmed from the ISA: all wave64,
no LDS, no scratch, and 62 SGPR does not introduce a second limiter.

Also flagged: `run_2r.py` scores relative error as zero when the baseline is zero; "N95" is a
conservative empirical threshold, not a percentile, and its pairs are not independent; the R32
capture changes the RTV format and therefore the PSO, so it demonstrates the diagnostic build;
the clock confounder in the frame numbers is real and is why MEASURED and CLOCK-CORRECTED are
kept apart.

**Its recommended single experiment is the one being run next**: rebuild the canary out-of-band,
so a violation cannot be multiplied away.

**No freeze.** Two of four targets did not survive. Full transcript:
`research/OVERNIGHT_REVIEW_2Q_2R.txt`.

## Cycle 7 — closing what the review broke: the canary rebuilt out of band, with a positive control

**The defect.** Canary v1 wrote its 1e30 sentinel *into* the value that is later multiplied by
zero. On `falloffskip`'s path `distanceFalloff == 0` gives `0 × 1e30 = 0`; on `shadowskip`'s,
`lit == 0` gives the same. The detector was blind exactly where it needed to see.

**Canary v2.** A violation mask is threaded through `ApplyLightCommon`, `ApplyPointLight`,
`ApplyConeLight` and `ApplyConeShadowedLight` and out through the argument macros. It is set
**before any multiplication**, is never multiplied itself, and is applied to `colorSum` once at
the end of `ShadeLights`. One bit per contract, carried in the green channel so a firing canary
says *which* assumption failed:

| bit | contract | why it is there |
|---:|---|---|
| 1 | `lightColor * (diffuse + specFactor·spec)` finite and non-negative | **`ndotlskip`'s actual factor — v1 never checked it** |
| 2 | `ApplyLightCommon`'s result | |
| 4 | `distanceFalloff` | `falloffskip`, point lights |
| 8 | `coneFalloff` and `atten` | `falloffskip`, cone lights |
| 16 | the shadow term | `shadowskip` |
| 32 | `shadowCoord.w` finite and non-zero | `shadowskip` |
| 64 | any factor is a negative zero | the −0 question |

**Result: 0 of 2 073 600 pixels fired**, every bit clean, max red 56.3287467956543 — the
baseline's own maximum.

**And the control v1 never had.** `canary2_positive` is the same detector with the scalar check
forced to fire on every finite value. It lights up **2 073 600 of 2 073 600 pixels**, max red
1.0e30, with masks 12 and 28 — i.e. `distanceFalloff`, `coneFalloff` and the shadow term all
reach the capture through every light path. So v2's silence is evidence, not an artefact. (The
control forces the scalar checks; the vector checks use the same mask and the same final
application, so they are covered by construction rather than by demonstration.)

**Provenance hole closed too.** The reviewer found that the earliest `sweep_*.json` predate the
host's `slots_raw` field, so no hash tied a result to the binary that produced it. The sweep was
re-run with the current host and `provenance.json` now records the host EXE and source hashes,
both shaders' HLSL/DXIL/disassembly hashes and the DXC version. Every field of the re-run matches
the original exactly: 1 065 353 217 values, 204 485 077 differing, max ULP 8 388 608, 7
zero-mismatches.
