# Phase 2U — raising the hit rate: what worked, what did not, and what the number really is

**Closed 2026-09-07, 12 cycles.** Preregistration:
[`PHASE_2U_PREREGISTRATION.md`](PHASE_2U_PREREGISTRATION.md), written before any new workload was
opened. Phase 2T measured the frozen pipeline at **0 hits in 4 workloads, 5 transformations, none
accepted**. 2U's job was to raise that, without moving the goalposts.

## The answer

> **Primary hit rate: 0 of 4 workloads attempted.** Three candidate transformations built and
> measured, **none accepted**. Two workloads were closed by the ceiling gate before any hypothesis
> was written, and they stay in the denominator.
>
> **Conditional hit rate (ceiling ≥ 3 %): 0 of 2.**
>
> Counting the whole programme — 2T, 2U, and the two workloads reported separately — the method
> stands at **1 hit in 9 workloads**.

The three changes made to the pipeline all did what they were supposed to do. None of them
produced a hit, and the reason is now specific rather than vague: **idea generation was never the
bottleneck. Exactness and the acceptance threshold are.**

## Per workload

| workload | ceiling | gate | attempts | best candidate | verdict |
|---|---:|---|---:|---|---|
| **W4** `D3D12VariableRateShading` (re-attempt) | −16.59 % | pass | 1 | `vs_lightspace` **+4.31 %** | MISS |
| **U-A** `D3D12DynamicIndexing` | −0.38 % | **fail** | 0 | — | MISS, `NO_HEADROOM` |
| **U-B** `D3D12Raytracing/ProceduralGeometry` | −79.02 % | pass | 2 | `shadow_tmax` **−2.18 %**, byte-exact | MISS |
| **U-C** `D3D12HDR` | +0.22 % | **fail** | 0 | — | MISS, `NO_HEADROOM` |

W4's 2T miss stands in the record; 2U's re-attempt is reported as a re-attempt and does not erase
it. Details: [`PHASE_2U_W4_CEILING.md`](PHASE_2U_W4_CEILING.md),
[`53_2u_ua/verdict.json`](53_2u_ua/verdict.json), [`54_2u_ub/verdict.json`](54_2u_ub/verdict.json),
[`55_2u_uc/verdict.json`](55_2u_uc/verdict.json).

## Change 1 — the ceiling gate. It works, and it is cheap

Every workload got its ceiling measured before any hypothesis: ablate the candidate shader's body
and measure what the workload loses. Two of four came back at **−0.38 %** and **+0.22 %**.

- **U-A**: deleting the entire pixel shader — two texture samples and a multiply — moves the pass
  by 0.38 %. It is bound by its 100 draw calls, not by shading.
- **U-C**: deleting every colour conversion in the present shader — sRGB, Rec.2020, ST.2084 —
  moves the *present pass itself* by −0.46 % and the frame by +0.22 %. That pass is 69 % of the
  frame and is still not limited by its arithmetic.

Both were closed for **one cycle each, zero attempts**. In 2T, workloads like these were closed on
profiling judgement; the ceiling probe turns that judgement into a number, and the number is
unambiguous in a way a 5.76 µs dispatch time is not.

**This is the honest way the conditional rate rises: it separates "there was nothing here" from
"the method failed".** Both rates are reported and the primary one is the strict one.

## Change 2 — ceiling decomposition. It changes what gets built

Splitting the ceiling into blocks, before proposing anything, was the most useful change of the
phase — and it was useful mostly by ruling things out.

**W4** — 16.59 % ceiling, decomposed:

| block | Δ frame | share |
|---|---:|---:|
| shadow term, whole | **−11.98 %** | **72 %** |
| ↳ its four texture taps only | −2.34 % | 14 % |
| ↳ therefore its address math | ≈ −9.6 % | ≈ 58 % |
| normal map + tangent frame | −3.92 % | 24 % |
| per-light distance and N·L | −2.32 % | 14 % |

This retroactively explains 2T's `gather_pcf`: halving the shader's texture instructions bought
0.5 % because the taps are 14 % of the ceiling, not the bulk of it. 2T could not have known that.

**U-B** — 79.02 % ceiling, decomposed:

| block | Δ pass | share |
|---|---:|---:|
| shadow ray, one TraceRay per hit | **−43.51 %** | 55 % |
| recursive reflection ray | −26.89 % | 34 % |
| the Phong evaluation itself | −0.90 % | 1 % |

**Shading arithmetic is one percent of the ceiling.** Any ALU transformation on this workload was
known to be pointless before it was built, which is exactly what a decomposition is for.

## Change 3 — the two-tier correctness rule. It did not need to be used

Both tiers were fixed before any 2U measurement. In the event, **two of the three candidates came
back byte-identical**, so tier A settled them and tier B was never the deciding rule. The one
failure, `vs_lightspace`, fails both tiers for the reason tier B was written to catch: 46 pixels
with deltas up to 17, a flipped shadow comparison rather than a rounding of the same arithmetic.

## The three candidates

### `shadow_tmax` — the closest miss the project has produced

U-B's shadow ray is aimed at the light, so nothing beyond the light can shadow the point, yet its
`TMax` is 10000 and with `ACCEPT_FIRST_HIT_AND_END_SEARCH` an unshadowed ray walks the structure
out to 10000 before giving up. Bounding it at the light distance:

- **Byte-identical image.** Tier A pass.
- **−2.18 %**, all four processes negative.
- Replicated at 2000 frames per process, 6 + 6 processes: **−1.81 %**, all negative, and **every
  variant process faster than every base process** — complete separation.
- **Rejected**: the preregistered threshold is 4.02 % (2.76 % in the replication).

The equivalence is *conditional*, not algebraic — it holds because this scene has nothing behind
its light — and that was declared before the build, in the same class as the data contract phase
2P measured. Its positive control cost nothing: `abl_shadowray` had already shown the oracle is
sensitive to this flag, so a byte-identical result is evidence and not silence.

**The replication was run because the result was a near miss. That is disclosed, and it did not
rescue it.** The finer protocol produced a tighter A/A and the candidate still failed. The
discipline held, which is the only reason the disclosure is cheap.

### `vs_lightspace` — a textbook optimisation that measured backwards

W4's shadow address math is two chained 4×4 transforms by matrices that are uniform for the draw:
32 `v_fma` of the shader's 227 instructions. Hoisting them to the vertex stage is the standard
advice. Predicted −1.8 % to −3.0 %.

**Measured +4.31 %**, and the region split says why, with the sample's own postprocess pass as a
negative control:

| region | Δ |
|---|---:|
| shadow-map pass + gaps — **no pixel shader at all** | **+7.24 %** |
| scene pass | +3.91 % |
| refraction pass | +3.65 % |
| postprocess — does not use this shader | +0.14 % |

The depth-only pass has no pixel shading, so its +7.24 % is entirely the vertex shader doing 32
more `v_fma` per vertex. SquidRoom's geometry goes through that vertex shader three times a frame
against 1280×720 of coverage. **The prediction was wrong in sign, and the measurement is worth
more than the transformation would have been.**

### `hitpos_reuse` — a documented vendor tip measured as a no-op

The DXR sample recomputes `HitWorldPosition()` three or four times per closest-hit shader and
says so deliberately: *"PERFORMANCE TIP: it is recommended to avoid values carry over across
TraceRay() calls."* Computing it once is bit-exact. Predicted 0 % to +2 %, i.e. the tip is right.

**Measured −0.09 %**, byte-identical, and not even consistently signed across four processes. In a
pass whose cost is 99 % ray work, the tradeoff the tip is about is not measurable.

## Measurement memory

[`MEASUREMENT_MEMORY.csv`](MEASUREMENT_MEMORY.csv), 39 rows, built by `tools/memory.py` from
artefacts only — manifests, per-run summaries, ISA reports and the two earlier phase CSVs. Its
declared use is to rank hypothesis kinds by measured median delta, nothing else.

What it shows at a glance is the honest shape of the project:

| | best measured Δ |
|---|---:|
| 2P, MiniEngine ModelViewer | **−41.60 %** (accepted, byte-exact) |
| everything else, 2R + 2T + 2U | **−2.18 %** (rejected) |

MiniEngine's `ShadeLights` is not a typical case that the method reproduces. It is an outlier
regime — an unusually large per-light body, most of it multiplied by exact zeros over most of the
screen — and eight further workloads have not found another one.

## What 2U establishes about the method

1. **Profiling and hypothesis generation are not the bottleneck.** Every workload was profiled
   correctly, every ceiling was located, and where a ceiling existed the decomposition put a
   number on each block. Candidates were derived from the workload's own ISA and source.
2. **Exactness is the first wall.** W4's ceiling is 72 % shadow term, and the shadow term sits
   behind a hard comparison: every arithmetic change to it flips `depth >= depth` on boundary
   pixels and produces deltas of 17 to 41, not one LSB. There is no bit-exact route to it.
3. **The acceptance threshold is the second wall.** `shadow_tmax` is byte-exact, reproducible and
   completely separated at −1.8 to −2.2 %, and the rule rejects it. The rule asks for three times
   the *worst* A/A pair, which on this hardware means roughly 3 % on a quiet workload and 4 % on a
   noisy one. **Only large structural wins can ever be accepted.** That is a property of the rule.
   It was preregistered, it was not changed, and it is stated here rather than fixed after the
   fact.
4. **A methodological defect in the rule, recorded not repaired.** "N95" is implemented as the
   *maximum* pairwise A/A difference, so the threshold **grows with the number of baseline runs**:
   careful measurement is punished. For U-B a true 95th percentile would have given 2.58 % instead
   of 4.02 % — and `shadow_tmax` fails under both, so no verdict in this phase depends on it. A
   future phase should preregister a paired statistical test instead.
5. **Two standard beliefs measured false or empty on this hardware**: hoisting uniform work to the
   vertex stage (+4.31 %), and Microsoft's DXR tip about carrying values across `TraceRay`
   (−0.09 %).

## Defects the gate caught in 2U

None of these produced a number before being caught.

- **Aux headers were never snapshotted or restored** — the workspace stayed dirty after a build
  that edited `Common.hlsli`, caught by `Glass_PSMain`'s preregistered hash. Fixed at the root.
- **`analyse` paired runs by rep number** — W4's base moved 1.2 % between sessions, so index
  pairing would have scored `gather_pcf` at ≈ −1.5 % and **manufactured an acceptance**. Fixed:
  nearest-in-time pairing, and the A/A no longer mixes sessions.
- **Anchor matching assumed a file has one line-ending style** — W4's `Common.hlsli` is LF in its
  body and CRLF in its last two lines. Fixed: one matcher, tried as written, converted only on a
  miss, refused if it would match both ways.
- **Shader sources were staged by basename** — U-B includes `util\HlslCompat.h`, and two aux files
  sharing a basename would have collided silently. Fixed: staged by path relative to the shader's
  own directory.
- **Instrumentation decoded sources as UTF-8** — U-B's C++ contains a Windows-1252 apostrophe.
  Fixed: instrumentation reads and writes bytes, preserving encoding, BOM and line endings.
- **The probe header was copied to one directory only**, and the build ran with a hard-coded `src`
  working directory. Both fixed.

## Anomalies recorded and not explained away

- **U-A, first process of a new build: +11.8 % slower** than its own five other processes. Every
  variant measured in 2T and 2U was checked for the same effect; no other first run deviates by
  more than 0.3 %. No earlier verdict is affected. The cause is **not established** — it is not
  shader compilation, since 200 warm-up frames precede a 500-frame timestamp median.
- **U-C, first process of a session: a different image** from the five that followed — 12 pixels
  in one horizontal band. Runs 2 to 9 are byte-identical. By the preregistered rule that workload's
  oracle **failed**; it changed nothing, because the ceiling gate closed U-C first.
- **The 2K microbench self-check failed once and passed on repeat** (floor reproducibility 6.11 %
  then 3.37 % against a 4.0 % limit). It is marginal on this machine today. It does not touch 2T or
  2U, which measure real workloads against their own A/A controls, but it means a 2K-style
  microbench result taken today would not be trustworthy.

## Scope discipline

No modification to driver, cache, Registry, security settings or games. No injection, no hooking,
no patching. Every workload is an open-source sample built from source on this machine. Nothing
was deleted.
