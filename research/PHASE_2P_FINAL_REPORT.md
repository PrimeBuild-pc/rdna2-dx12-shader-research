# Phase 2P — final report

**Per-light shading optimiser.** 2026-09-06, autonomous session. Target: the `ShadeLights` loop
that Phase 2O identified as carrying ~88 % of `Render Color`'s GPU cycles. Rule enforced
throughout: no transformation is accepted on fewer instructions, fewer VGPRs, smaller DXIL,
shorter ISA or a microbenchmark — the judge is `Render Color` in the real workload, with the
image unchanged.

---

## 1. Clean-room replication outcome

Before any new work, the three Phase 2O results that carry a conclusion were repeated on a
machine verified idle (no browser, no Discord, no game, no encoder; **1.69 % total GPU**,
desktop compositor only; live CPU under 0.5 %; no application was closed to achieve this).
Criteria and the historical numbers to beat were written into the manifest first.

| arm | clean | historical | |
|---|---:|---:|---|
| baseline `TA_BUSY` | 88 701 626 | 88 700 482 (**+0.00 %**) | OK |
| baseline PS texture instructions | 6 112 392 | 6 111 703 (**+0.01 %**) | OK |
| baseline `GPUBusyCycles` | 1 186 280 | 1 189 003 (−0.23 %) | OK |
| O4 sampler arm, Δ`TA_BUSY` | −3.76 % | −3.50 % | OK |
| O6 light-count arm, Δ`TA_BUSY` | −61.75 % | −61.57 % | OK |
| O6 marginal cost | 13.11 cycles | 13.13 cycles | OK |

**CLEAN_REPLICATION = PASS.** Background load drove none of Phase 2O's conclusions, and the
`GPUTime` clock excursion documented in O4/O6 reappears on the idle machine, so it is intrinsic
to this GPU rather than contention. → `32_clean_replication/CLEAN_REPLICATION.md`

## 2. Cycles used

**8 of the 10** budgeted: R (replication), P1, P2, P3, P4, P5, P6, P7. Stopped on condition (A),
a robust and replicated conclusion, not on budget.

## 3. The hot loop, as it actually is

`ShadeLights` (`MiniEngine/Model/Shaders/Lighting.hlsli`) runs the **SM 5.0 path** — the wave-op
paths ship disabled behind `#if 0`. Three sequential loops over the tile's light list: sphere,
cone, shadowed cone. Baseline ISA (RGA, gfx1030, root signature reconstructed from
`Renderer::m_RootSig`): **61 VGPR, 54 SGPR, no scratch**, 553 instructions, of which the three
loop bodies are 72 / 80 / 107 instructions with **3 / 5 / 10 VMEM** and **7 / 7 / 8
transcendentals** *per light iteration*.

Read against the source, three things stood out — and one did not:

- `(gloss + 2) / 8` is **already hoisted** out of all three loops by the compiler. Checked, not
  assumed; no opportunity there.
- `FSchlick`'s `pow(x, 5.0)` is emitted as `v_log_f32` → `v_mul` by 5.0 → `v_exp_f32`. **Neither
  DXC nor the AMD backend strength-reduces a constant integer exponent.**
- `ApplyConeShadowedLight` samples the shadow map *before* multiplying by `ApplyConeLight`, which
  returns zero whenever the falloff is zero at that pixel.
- `ApplyPointLight` / `ApplyConeLight` multiply the whole of `ApplyLightCommon` by a scalar
  falloff that is frequently exactly zero.

## 4. Transformations tried

| id | what | kind |
|---|---|---|
| `fresnel5` | x⁵ by repeated multiplication instead of `pow(x, 5)` | ALU only |
| `shadowskip` | compute the lit contribution first; sample the shadow map only if it can matter | texture + ALU |
| `falloffskip` | return early when the distance/cone falloff is exactly zero | ALU (+ a load the compiler sinks) |
| `ndotlskip` | compute `nDotL` first; return early when it is exactly zero | ALU |
| `combo` | `fresnel5` + `shadowskip` | — |
| `stack3` | `fresnel5` + `shadowskip` + `falloffskip` | — |
| `stack4` | `stack3` + `ndotlskip` | — |
| `scalar` | enable the engine's own `SCALAR_BRANCH` wave path | scalarisation |
| `stack3_scalar` | `stack3` + `SCALAR_BRANCH` | — |
| `stack4_scalar` | `stack4` + `SCALAR_BRANCH` | — |
| `base_pad` / `stack3_pad` | inert dead-at-runtime padding — controls, not candidates | control |
| `base_l32` / `stack3_l32` | sparse-light regime — generality test | regime |

Every one was built through the fail-closed gate against a bytecode SHA-256 preregistered from an
offline DXC compile **before any build ran**; the baseline source is restored on every exit path.
**No transformation compiled to the baseline bytecode**, i.e. the compiler was not already doing
any of them.

## 5. Candidates rejected on correctness

**`ndotlskip` (cycle P2).** Image differed on 2 pixels of 2 073 600, max relative error 1.32e-2,
against a preregistered threshold of 1e-3 → **REJECTED**, and the threshold was not relaxed after
the fact. Its −9.76 % is recorded as an observation and never counted as a win.

The diagnosis matters more than the verdict: 6.25e-2 at a channel value of ~4.73 is **exactly one
ULP** of an R11G11B10 channel. A relative threshold of 1e-3 is unreachable in a format whose ULP
is ~1.6 % relative — **the criterion as written could only ever pass a byte-identical image.**
That was a flaw in my criterion, not evidence about `ndotlskip`. It was fixed *forward* in P3,
with a ULP-based rule written into P3's manifest before P3 measured anything, and P2's verdict
left exactly as recorded.

## 6. Candidates rejected on performance

**`base_pad` (cycle P5): +0.01 %** (+0.01, +0.12, +0.20, −0.07, −0.04 across five processes) —
this is the null control, not a failed optimisation. A different binary with a different bytecode
(+112 bytes) and identical work moves this measurement by nothing.

No transformation was rejected for being slower. Two *controls* failed to do what they were built
for, which is reported in §12.

## 7. Accepted candidates

All bit-identical unless noted; all with every paired process delta negative.

| variant | Δ`Render Color` (`GPUBusyCycles`) | processes | image |
|---|---:|---:|---|
| `fresnel5` | −3.17 % | 3 | bit-identical |
| `shadowskip` | −5.48 % | 3 | bit-identical |
| `combo` | −7.32 % | 5 | bit-identical |
| `falloffskip` | **−27.59 %** | 5 | bit-identical |
| `stack3` | **−37.51 / −37.38 / −37.49 %** (P3/P4/P5) | 5 each | bit-identical |
| `stack4` | −39.42 % | 5 | 1 ULP on 3 pixels |
| `scalar` | −3.84 % | 5 | bit-identical |
| **`stack3_scalar`** | **−41.55 % (P6), −41.60 % (P7)** | 5 each | **bit-identical** |
| `stack4_scalar` | −42.94 % | 5 | 1 ULP on 3 pixels |

Additivity was measured, never assumed, and is **sub-additive** every time: −3.17 % and −5.48 %
give −7.32 % together, not −8.65 %.

## 8. Best `Render Color` delta

**`stack3_scalar`: −41.60 %** (per process −41.60, −41.53, −41.84, −41.69, −41.53), against an
A/A control whose N95 is 0.40 % and a preregistered acceptance threshold of 1.20 %.
Cross-checked by a second, independent instrument in the same cycle — MiniEngine's own GPU timer
tree — at **−40.34 %**. `TA_BUSY` −44.40 %.

## 9. Best GPU frame delta

**−24.39 %**: 1.0295 ms → 0.7784 ms, benchmark mode, 1000 frames after 300 of warm-up, three
processes (base 1.0314 / 1.0295 / 1.0236, variant 0.7784 / 0.7778 / 0.7794).

**Honest correction.** That figure includes −3.0 % on `Z PrePass` and −4.1 % on `Generate SSAO`,
passes the change cannot touch. The most likely cause is a clock/power effect: a cheaper frame
lets the GPU hold a slightly higher clock, and these are millisecond figures. Treating those
passes as a clock probe and correcting the whole frame by ~3.5 % gives an **attributable frame
gain of about −21.7 %**. The pass-level numbers are immune to this, because `GPUBusyCycles` is a
cycle count: it fell 41.60 % while the millisecond figure for the same pass fell 40.34 %, i.e.
slightly *less*, so no clock boost is inflating the pass result.

## 10. Counters, before and after (`stack3_scalar` vs `base`)

| counter | base | after | Δ |
|---|---:|---:|---:|
| PS texture instructions | 6 112 280 | — | **−34 %** (`stack3`; scalarisation does not change the count) |
| PS VALU instructions | 70 975 385 | — | −44.9 % |
| PS VALU issue cycles | 183 120 746 | — | **−49.6 %** |
| Σ `TA_BUSY` (80 CUs) | ~88.7 M | — | **−44.40 %** |
| `GPUBusyCycles` (Render Color) | ~1.187 M | ~0.693 M | **−41.60 %** |
| PS waves | 39 181 | 39 1xx | −0.15 % (the same pixels are shaded) |
| VGPR / SGPR | 61 / 54 | 54 / 62 | scalarisation moves light data into scalar registers |

## 11. ISA and codegen explanation

- **`fresnel5`**: the ISA shows 2 `v_log_f32` + 2 `v_exp_f32` per loop iteration; the transform
  removes one pair per iteration (22 → 16 transcendentals across the three loops). Transcendentals
  are quarter-rate, so three multiplies replace log + mul + exp at the *same instruction count*
  and a quarter of the issue cost. The measurement is the signature of exactly that: VALU
  **instructions +0.55 %**, VALU **cycles −5.88 %**, against an ISA-derived prediction of −6.2 %.
- **`falloffskip` is not ALU-only**, though it was labelled so: texture instructions fell 13.87 %
  as well, because `lightData.color` is needed only on the non-early path and the compiler sinks
  that buffer load behind the new branch. Labelled by intent, corrected by measurement.
- **`shadowskip`** removes, per skipped light, four matrix loads, the matrix multiply, the `rcp`
  and the shadow-map sample.
- **`scalar`** turns the tile offset wave-uniform when all lanes share a tile, so light data can
  live in SGPRs: VGPR 61 → 48, SGPR 54 → 62, `TA_BUSY` −12.43 % on its own.
- **Static size is not the story.** The accepted stack's loop bodies grow from 259 to 305 static
  instructions while the executed work halves. A phase that spent 2E–2K learning to distrust
  static metrics gets one final illustration.

## 12. ALU versus texture — what P1 settled, and what P5 could not

Phase 2O could not rank the two saturated units because every arm it had moved both. **P1
supplied the missing arm.** `fresnel5` moves ALU work with the texture instruction count fixed
(−0.08 %, inside the ±0.4 % emulation band) and the pass falls 3.17 %; O4 moved texture work with
ALU verified fixed (0.07 %) and the pass fell 2.6 %. **Both units are on the critical path and
neither dominates** — reducing either one alone reduces the pass.

**The occupancy confound is real and only partly resolved.** Every accepted variant also lowers
VGPR use, which raises theoretical wave occupancy. Two attempts to separate it failed:

1. `SQ_PS*_PERF_SEL_LEVEL_WAVES` returns **73 786 976 294 838 206 464 on every build**, identical
   to the digit — an unusable counter, recorded as an instrumentation defect and discarded.
2. `stack3_pad` keeps values live under a runtime-false condition to hold registers up. The image
   is bit-identical so the construct is inert, but VGPR moved only 55 → 56: the compiler
   rematerialises the padding. The control does not exist.

What does answer it comes from data already in hand: `fresnel5` (56 VGPR), `shadowskip` (54) and
`stack3` (55) all fall in the **same 56-VGPR allocation bucket — the same theoretical occupancy**,
9 waves per SIMD against the baseline's 8 — and they span **−3.17 %, −5.48 % and −37.49 %**.
Occupancy cannot produce that spread; the work reduction can. It may still contribute to the
first points, and nothing here separates that part.

## 13. Results invalidated during the work

- **None of the measurements.** No accepted number was retracted.
- **One preregistered criterion was invalidated by its own first use** — the 1e-3 relative image
  threshold (§5) — and replaced forward, without changing the verdict it had produced.
- **One label was wrong and was corrected by measurement**: `falloffskip` as `alu_only` (§11).
- Carried in from the P1 review and applied throughout: `TA_BUSY` is **not** a pure work counter
  in this pass. Under `fresnel5` it falls 3.21 % while the pass falls 3.17 % — the addresser stays
  pinned at ~93.6 % duty and `TA_BUSY` tracks the shorter pass; under `shadowskip` it falls
  12.40 % against 5.48 %, i.e. the addresser genuinely drains. This weakens, retroactively, how
  cycle O6 read `TA_BUSY` as an addresser-work measure.
- Three `prepare` attempts were rejected by the gate before producing anything and are preserved
  as `*_SUPERSEDED_prepare_*`; two intermittent `0xC0000005` process crashes were rejected by the
  runner and repeated.

## 14. Independent review (Codex, via Herdr)

Three adversarial reviews were requested. Two completed and every one of their findings was
adopted; the third could not be completed.

**On P1** — numbers reproduced independently from the raw CSVs. Findings adopted: `fresnel5` is
*algebraically*, not bitwise, equivalent, and the claim that multiplication is "more accurate" is
undemonstrated; `shadowskip` differs on −0 (the branch returns +0 where the original could return
−0) and its exactness depends on `shadowCoord.w` being finite, an invariant asserted but not
proven; a bit-identical R11G11B10 image proves identity of the *quantised* target, not of the
float32 results; the "mirror of O4" claim needed the register data before it could stand; the
`TA_BUSY` reading above; and 3 processes give a sign test of at best p = 0.125, so 5 were used
from P2 onward with counterbalanced order.

**On P2/P3** — all dose and response figures reproduced to five decimals, and every build record,
manifest hash and ISA report verified consistent. Findings adopted: occupancy is a co-cause that
these data cannot separate (§12); the ULP rule is an honest sequential correction rather than a
post-hoc requalification, but `stack4` should be called "equivalent within the preregistered ULP
oracle", not "exactly equivalent"; the manifests still said "3 processes" while 5 were used —
a documentation defect, since the stricter practice is not preregistered by the text; `N95` is
the largest of pairwise differences among non-independent pairs, not a percentile; and processes
run seconds apart are independent as processes, not as thermal states. Its verdict: *"the −37.5 %
is a solid principal result for this scene and this hardware; what would be overstated is
presenting it as a general gain or attributing it entirely to the early-outs."*

**On P7 (the final candidate) — not obtained.** The reviewer verified the artifacts and began
recomputing, then **hit its account usage limit mid-review**. The final candidate therefore has
**no completed independent review**, which is stated here rather than papered over. What it was
asked and what I answer myself: the `SCALAR_BRANCH` path iterates the same three loops over the
same list in the same order, and its divergent branch is code identical to the original, so the
accumulation order is unchanged — consistent with the bit-identical image, subject to that
oracle's quantisation; and the unrelated-pass improvements are handled in §9.

## 15. Confidence

| claim | confidence |
|---|---|
| `stack3_scalar` makes `Render Color` ~41 % cheaper **on this scene, this camera, this GPU** | **confirmed** — 5 paired processes, two independent instruments (−41.60 % cycles, −40.34 % ms), replicated across three cycles for `stack3` and two for `stack3_scalar`, null control at +0.01 % |
| the image is unchanged within the capture oracle | **confirmed** — byte-identical 1920×1080 R11G11B10, and the oracle's sensitivity was established by cycle O1's canary |
| the transformations preserve semantics for *this* workload's data | **strong** — argued term by term and reviewed; the general case is not proven (§16) |
| the gain is caused mainly by the removed work rather than by occupancy | **strong** — same-occupancy variants span −3 % to −37 % |
| GPU frame ~−22 to −24 % | **strong** — three processes, tight, with the clock caveat quantified in §9 |
| the size of the gain generalises to other scenes | **weak** — measured to shrink to −20.19 % at one quarter of the light density |

## 16. What is NOT demonstrated

- **Not a general result.** The magnitude is content-dependent: −41.6 % at 128 lights, −20.2 % at
  32. Nothing here says what it would be in another engine, scene or camera.
- **Not proven for arbitrary inputs.** `falloffskip` and `shadowskip` rely on the multiplied term
  being finite and non-negative, which holds for this workload's materials and lights (gloss in
  [1, 128], saturated dot products, finite light colours) but is not a property of the code in
  general. With a negative term the early return would give +0 where the original gives −0; with
  a non-finite one, 0 where the original gives NaN.
- **Not bitwise-provable.** The oracle is a quantised R11G11B10 render target. A diagnostic
  R32_FLOAT dump comparing the two formulas directly was recommended by the reviewer and **not
  built**.
- **The occupancy contribution is not separated** (§12), and both attempts to separate it failed.
- **Nothing about Fortnite or Warzone.** The workload is MiniEngine ModelViewer / Sponza. No game
  was touched, profiled or modified.
- **Not a driver result.** Nothing here changes, tunes or exploits the AMD driver.
- **`ndotlskip` is not shown to be wrong** — only that it is not bit-identical, and that the
  criterion which rejected it was itself unmeetable.

## 17. The change, in full

68 diff lines against `MiniEngine/Model/Shaders/Lighting.hlsli`, no other file
(`39_2p_cycle7/stack3_scalar.diff`):

- `FSchlick`: `pow(1 - saturate(dot(l, h)), 5.0)` → `f2 = f1*f1; fresnel = f2*f2*f1`
- `ApplyPointLight`: `if (distanceFalloff == 0.0) return 0.0;`
- `ApplyConeLight`: `atten = coneFalloff * distanceFalloff; if (atten == 0.0) return 0.0;`
- `ApplyConeShadowedLight`: compute `lit` first, `if (!any(lit != 0.0)) return 0.0;`, then sample
- `#if 0 // SM6.0` → `#if 1`, and `BIT_MASK_SORTED` → `SCALAR_BRANCH`

Nothing was added to the engine and nothing was removed from the image. Four of the five edits
are three lines each; the fifth flips two `#define`s the engine already shipped.

## 18. Principal artifacts

`PHASE_2P_WORKLOG.md` (per-cycle log) · `PHASE_2P_MEASUREMENT_MEMORY.csv` (17 rows: variant,
kind, bytecode hash, VGPR/SGPR, dose, response, processes, correctness, verdict — failures
included) · `32_clean_replication/` · `33_2p_shadelights/` (P1, `codex_review_p1.txt`) ·
`34_2p_earlyout/` (P2) · `35_2p_cycle3/` (P3, `codex_review_p2_p3.txt`) · `36_2p_cycle4/` (P4) ·
`37_2p_cycle5/` (P5) · `38_2p_cycle6/` (P6) · `39_2p_cycle7/` (P7, `stack3_scalar.diff`,
`codex_review_final.txt`) · superseded prepares preserved beside their cycles.
Tools: `tools/run_2p.py`, `tools/isa_2p.py`, `tools/run_clean.py`, `tools/buildv.py` (the gate).

---

## FINAL VERDICT

**Phase 2P found a real, replicated, end-to-end optimisation of the shading loop that Phase 2O
identified — and it required changing 68 lines of application HLSL, not one byte of driver,
compiler flag, sampler state or cache setting.**

`stack3_scalar` makes `Render Color` **41.6 % cheaper** in GPU busy cycles (**40.3 %** by an
independent instrument) and the whole GPU frame **~22–24 %** cheaper, with a **byte-identical
image**, on unmodified Microsoft engine code. Four of its five edits are the same idea applied at
four depths — *do not compute what is multiplied by exactly zero* — and the fifth simply enables
a code path the engine already shipped disabled.

Two things kept it honest and both should survive into any follow-up. The build gate, which
rejected three prepares and two crashed processes before they could produce a plausible number.
And the adversarial review, which never once confirmed a result: it weakened the equivalence
claim from "exact" to "exact under this workload's data contract", showed that a bit-identical
quantised image is not proof of identical float32 output, established that occupancy is an
unseparated co-cause, and caught a correctness criterion that could never have passed anything.
The final candidate's own review was cut short by the reviewer's usage limit and is missing.

## NEXT RECOMMENDED ACTION

**Close the equivalence question with a diagnostic R32_FLOAT probe**: one build that writes both
the original and the transformed per-light expression to a full-precision target for every pixel,
and reports max ULP, NaN/Inf and ±0 counts. It is the one thing that would raise the accepted
transformations from "equivalent within a quantised oracle, for this workload's data" to
"equivalent, measured at full precision" — and it is the prerequisite for proposing any of this
upstream.
