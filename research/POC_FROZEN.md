# Proof of concept — FROZEN

**2026-09-07.** Phases **2P**, **2Q** and **2R** are frozen as a validated proof of concept.
Nothing in them is to be re-tuned for a larger number. What follows is the exact state being
frozen, the evidence behind it, and the limits it is frozen *with*.

The freeze is declared **after** an adversarial review that broke one of its four load-bearing
claims and after that claim was rebuilt and re-verified — not before.

---

## 1. What is frozen

**The accepted transformation**, `stack3_scalar`: 68 diff lines in one file,
`MiniEngine/Model/Shaders/Lighting.hlsli`, and no other file.

- `FSchlick`: `pow(1 − saturate(dot(l,h)), 5.0)` → `f2 = f1*f1; fresnel = f2*f2*f1`
- `ApplyPointLight`: `if (distanceFalloff == 0.0) return 0.0;`
- `ApplyConeLight`: `atten = coneFalloff * distanceFalloff; if (atten == 0.0) return 0.0;`
- `ApplyConeShadowedLight`: compute `lit` first, `if (!any(lit != 0.0)) return 0.0;`, then sample
- `#if 0 // SM6.0` → `#if 1`, and `BIT_MASK_SORTED` → `SCALAR_BRANCH`

**Performance, on MiniEngine ModelViewer / Sponza, RX 6950 XT:**

| metric | value | how it was obtained |
|---|---:|---|
| `Render Color`, GPU busy cycles | **−41.43 %** | GPA, 7 counterbalanced processes, A/A N95 0.56 % |
| `Render Color`, engine timer | **−40.24 %** | MiniEngine's own GPU timer tree, an independent instrument |
| GPU frame, **MEASURED** | **−24.47 %** | 5 processes, 1000 frames after 300 warm-up |
| GPU frame, **CLOCK-CORRECTED ESTIMATE** | **−21.78 %** | the two are never combined |

Replicated in four separate cycles (P3, P4, P5, Q3), each with its own baseline build.

**Correctness, at full precision:** ≤ **7 ULP** and ≤ **4.33 × 10⁻⁷** relative over 6 220 800
float32 channels, no NaN, no infinity, no negative zero. One component (`SCALAR_BRANCH`) is
float32-identical. One (`fresnel5`) is *more accurate* than the code it replaces, over its entire
reachable domain.

**The method**, which is the part that generalises: preregistered criteria → fail-closed build
gate on a bytecode SHA-256 → ISA-driven hypotheses → correctness oracle → paired A/B on the real
workload → adversarial review.

## 2. The evidence, and what each piece is worth

| claim | evidence | strength |
|---|---|---|
| the speed-up is real on this workload | 4 cycles, 2 instruments, 7 processes, null control at +0.01 % | **confirmed** |
| provenance is intact | full audit: **64 build records, 422 runs, 22 cycle directories, zero mismatches** (`PROVENANCE_AUDIT.json`) | **confirmed** |
| `SCALAR_BRANCH` is exactly equivalent | float32-identical captures | **confirmed** |
| `fresnel5` is more accurate than `pow(x,5)` | exhaustive sweep of all 1 065 353 217 float32 in [0,1] against an fp64 reference: 3 ULP vs 8 388 608 | **confirmed within the reference's own accuracy** |
| the early-outs' data contract holds | out-of-band canary v2, 0/2 073 600 pixels, **with a positive control at 2 073 600/2 073 600** | **confirmed for the measured frame** |
| the gain is work, not occupancy | five variants at 9 waves/SIMD spanning −3.17 % to −41.60 %; `scalar` at 10 waves gives only −3.84 % | **strong for the ordering, not exclusive** |
| the method transfers | second workload built, gated, measured; A/A N95 0.05 %; exact oracle | **confirmed for the pipeline** |
| the method wins on other workloads | one second workload, **no accepted transformation** | **not established** |

## 3. The limits this is frozen with

1. **Scene-dependent magnitude.** −41.6 % at 128 lights, −20.2 % at a quarter of the light
   density. Nothing says what it would be elsewhere.
2. **Contract, not universality.** The early-outs are exactly equivalent when the multiplied
   factor is finite and non-negative. That was *measured* over every light of one frame, not
   proven for arbitrary inputs. Outside it, a negative factor would give +0 where the original
   gives −0, and a non-finite one 0 where the original gives NaN.
3. **The fp64 reference is not a formal oracle.** Certifying the 3-ULP bound would need exact or
   MPFR arithmetic.
4. **Occupancy is not separated.** Every comparison against base also crosses the 8 → 9 wave
   boundary. Two attempts to separate it failed (`LEVEL_WAVES` returns an impossible constant;
   register padding is rematerialised).
5. **One frame, one scene, one GPU, one driver.**
6. **The second workload has no hardware counters** — its bottleneck is a model accounting for
   ~82 % of the measured time.
7. **Nothing about games.** No driver, Registry, boot, signature, anti-cheat, Fortnite or Warzone
   interaction, at any point in the project.

## 4. What broke during review, and what it cost

The adversarial review was asked to falsify, and it did:

- **The data-contract canary was broken outright.** Its sentinel could be multiplied away on
  exactly the paths it was built to watch. Rebuilt out of band (Q4) and given the positive control
  it had lacked (Q5). **This is the single most valuable thing the review produced**, and without
  it the contract claim would have been resting on a detector that could not fire.
- **The conditioning quantification was wrong** — corrected before the review reported, and its
  independent recomputation agrees and goes further.
- **A provenance hole in the sweep artifacts** — closed by re-running with a provenanced host,
  reproducing every field exactly.

Two targets survived with reservations, all documented in §3.

## 5. Frozen artifacts

```
research/PHASE_2O_FINAL_REPORT.md      what the bottleneck is, and what it is not
research/PHASE_2P_FINAL_REPORT.md      the optimisation, and how it was found
research/PHASE_2P_WORKLOG.md           per-cycle log of 2P
research/OVERNIGHT_FINAL_REPORT.md     2Q and 2R, with the review folded in
research/OVERNIGHT_SESSION_LOG.md      per-cycle log of 2Q, 2R and the review
research/OVERNIGHT_REVIEW_2Q_2R.txt    the adversarial review, verbatim
research/PROVENANCE_AUDIT.json         64 builds, 422 runs, zero mismatches
research/PHASE_2P_MEASUREMENT_MEMORY.csv   17 rows, failures included
research/PHASE_2R_MEASUREMENT_MEMORY.csv    5 rows, failures included
research/24..48_*                      every cycle, including superseded prepares
tools/                                 buildv.py (the gate), run_o1/o2/2p/2r/clean,
                                       o1_probe.h, nb_probe.h, fp32_sweep/, isa_2p.py
```

`39_2p_cycle7/stack3_scalar.diff` is the change itself.

---

## FINAL VERDICT

**Frozen as a validated proof of concept, within the limits of §3.**

A 41 % reduction of the dominant GPU pass and ~24 % of the GPU frame, on unmodified Microsoft
engine code, from 68 lines of application HLSL — with the image byte-identical after
quantisation, float32 agreement within 7 ULP, one component provably more accurate than what it
replaced, the data contract confirmed by a detector that was itself broken, rebuilt and
positively controlled, and provenance verified across every build and run in the project.

What is *not* frozen as established is that the method wins in general: it was applied to a
second workload chosen against criteria written first, and there it found nothing acceptable —
rejecting a variant that was 3.58 % faster and mathematically exact because a legal reassociation
moved an ill-conditioned sum. One success and one honest negative is a proof of concept, not a
track record.

## NEXT RECOMMENDED ACTION — one phase

**Phase 2T — measure the method's hit rate.** Declare, before looking at any of them, a set of
three to five further open-source D3D12 workloads; run the frozen pipeline end to end on each
without altering it — profile, hot pass, shader identity by hash, ISA, hypotheses, gate,
correctness oracle, paired A/B — and report **how often it produces an accepted transformation**,
counting the negatives.

It is the right next phase because it is the only one that converts "this worked once and not
twice" into a measured property of the method; because it forces the pipeline to be automated
rather than re-hand-built per workload, which is what 2S would have done as an end in itself; and
because it is the cheapest way to find out whether the two results so far are a method or a
coincidence. Everything else — separating occupancy, certifying the ULP bound with exact
arithmetic, hardware counters on new workloads — is refinement of a claim whose generality is
still unknown.
