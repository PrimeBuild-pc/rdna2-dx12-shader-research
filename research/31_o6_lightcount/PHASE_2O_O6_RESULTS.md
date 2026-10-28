# Phase 2O — cycle O6: replicating O5 by moving the texture instruction count

**Date:** 2026-09-06 · **Experiment ID:** `O6_20260906_185359` · cycle **6 of 6** ·
`diagnostic_only` — fewer lights, so the image changes; no variant here is an accepted
optimisation. Criteria, bands and the falsification rule were written into
`experiment_manifest.json` **before the first build ran**.

O5 ended with a claim about a coefficient:

> `TA_BUSY` in `Render Color` is set by the *count* of pixel-stage texture instructions —
> 156 per wave, ~14.5 addresser cycles each — with the data essentially always in L0.

A coefficient is falsifiable by moving it. This cycle moves the instruction count **without
changing one byte of shader code**: the number of lights that survive tile culling is C++ data
written by `Lighting::CreateRandomLights`, and fewer lights means fewer iterations of the light
loop in `ShadeLights`. Lights are culled by index stride, so the sphere / cone / shadowed-cone
mix laid out in blocks of 32 is thinned proportionally rather than truncated to one type, and
every surviving light keeps bit-identical parameters (the random draws are untouched — the
culling line is appended after them).

| variant | culling | pixel shader bytecode | executable |
|---|---|---|---|
| `L128` | none (baseline) | `52CE6C5E64AB2E82` | `c5765f5e6ce4` |
| `L64` | `n % 2 != 0` → `radiusSq = 0` | `52CE6C5E64AB2E82` | `197fb6850720` |
| `L32` | `n % 4 != 0` | `52CE6C5E64AB2E82` | `c1e05048d740` |
| `L16` | `n % 8 != 0` | `52CE6C5E64AB2E82` | `79561d19ecad` |

Four builds, four distinct executables, one pixel shader. Every `sq_ps` session passes
`tools/sq_validity.py` (12/12).

---

## 1. The dose — measured, never inferred from the stride

Culling by radius was not assumed to be perfect. Whatever it actually removed is what the dose
reports (`sq_ps`, single pass, median of 3 processes):

| variant | PS waves | texture instructions | per wave | Δ tex | VALU instructions | Δ VALU |
|---|---:|---:|---:|---:|---:|---:|
| `L128` | 39 166 | 6 109 436 | **155.99** | — | 70 943 913 | — |
| `L64` | 39 146 | 3 948 375 | 100.86 | **−35.37 %** | 45 414 578 | −35.99 % |
| `L32` | 39 103 | 1 952 172 | 49.92 | **−68.05 %** | 23 733 276 | −66.55 % |
| `L16` | 39 090 | 1 305 722 | 33.40 | **−78.63 %** | 16 569 102 | −76.64 % |

The wave count is constant to 0.19 %: the same pixels are shaded, only the per-pixel light loop
is shorter. 155.99 texture instructions per wave reproduces O5's 156.0 exactly, from a different
build and a different session.

**The confounder is real and is not hidden: VALU work falls in near-lockstep with texture work.**
O6 on its own cannot separate them. §4 is where that is dealt with.

## 2. A/A control on `L128`

| metric | pairwise |Δ| between the 3 processes | N95 | threshold |
|---|---|---:|---:|
| `TA_BUSY` | 0.01 %, 0.01 %, 0.00 % | 0.01 % | 2.00 % |
| TCP requests | 0.00 %, 0.00 %, 0.00 % | 0.00 % | 2.00 % |
| `GPUBusyCycles` | 0.66 %, 0.57 %, 0.09 % | 0.66 % | 2.00 % |
| `GPUTime` | 13.93 %, 13.99 %, 0.05 % | **13.99 %** | 41.97 % |

`GPUTime` misbehaved badly here and the cause is visible in the raw numbers: the **first process
of each batch ran at a lower GPU clock**. Cycles per nanosecond were 1.476 / 1.686 / 1.688 on
`L128` and 1.392 / 1.690 / 1.688 on `L64`, while `GPUBusyCycles` moved by less than 0.7 %. It is
a clock/DVFS warm-up artefact, not a change in work; the median over three processes absorbs it.
`GPUBusyCycles` is the outcome used, as in O4.

## 3. Response — and the coefficient under test

| variant | `TA_BUSY` | Δ | `GPUBusyCycles` | Δ | `GPUTime` | Δ | **Δ`TA_BUSY`/Δtex** | **cycles per removed instruction** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `L128` | 88 669 084 | — | 1 184 031 | — | 701 820 | — | — | — |
| `L64` | 59 331 024 | −33.09 % | 799 512 | −32.48 % | 472 960 | −32.61 % | **0.94** | **13.58** |
| `L32` | 34 074 721 | −61.57 % | 471 235 | −60.20 % | 278 500 | −60.32 % | **0.90** | **13.13** |
| `L16` | 25 658 750 | −71.06 % | 362 634 | −69.37 % | 212 220 | −69.76 % | **0.90** | **13.12** |

Against the bands fixed before measuring:

- Δ`TA_BUSY` / Δtex ∈ [0.75, 1.25] on every arm → **0.94, 0.90, 0.90 — in band.**
- marginal cost ∈ [10, 19] cycles → **13.6, 13.1, 13.1 — in band**, against the 14.5 O5 predicted.
- falsification trigger (< 0.5) → not reached. Incompleteness trigger (> 1.5) → not reached.

### Verdict: **REPLICATED.**

Removing 4.80 million pixel-stage texture instructions removed 63.0 million cycles of texture
addresser busy time — 13.1 cycles each — and the pass got 69 % cheaper.

**Read those 13.1 cycles correctly:** `TA_BUSY` is summed over 80 texture units, so this is
13.1 unit-cycles of addresser occupancy, **not** 13.1 cycles of pass duration per instruction.
The pass-duration coefficient is the other one: **0.171 `GPUBusyCycles` per texture instruction**.

Ordinary least squares over all four arms (not just the two extremes):

| fit | slope | intercept | R² | intercept CI95 | sloped share at baseline |
|---|---:|---:|---:|---|---:|
| `TA_BUSY` | 13.0797 | 8 392 174 | 0.99972 | [5.82 M, 10.96 M] | **90.54 %** |
| `GPUBusyCycles` | 0.170523 | 136 696 | 0.99963 | [98 292, 175 099] | **88.46 %** |

The intercept is significantly non-zero in both: roughly 11 % of the pass is fixed cost that the
light loop does not touch. **R² = 0.9996 says the four arms lie on a line; it does not say the
texture count *causes* the duration.** The dose is collinear with VALU work and with the loop
trip count, and with four medians there are two degrees of freedom. The honest reading is
"≈ 88 % of the pass scales with the light loop's work", not "with texture instructions".

## 4. The ALU confounder — and a correction that weakens this cycle's reach

VALU work falls with texture work, so "the pass is ALU-bound" predicts the same direction. The
first draft of this report claimed the two could be separated because the texture addresser
stayed saturated while the ALU drained. **That claim was wrong, and the error was in my own
arithmetic.** `SQ_PS INST_CYCLES_VALU` was divided by 320 SIMDs, i.e. 4 SIMDs per CU, which is
the GCN layout. RDNA2 has **2 SIMD32 per CU**, so Navi 21 has 160, not 320. The corrected
picture is materially different:

| variant | TA duty cycle | VALU issue duty | `TA_BUSY`/tex | VALU cycles/tex |
|---|---:|---:|---:|---:|
| `L128` | 93.61 % | **96.64 %** | 14.51 | 29.97 |
| `L64` | 92.76 % | 91.11 % | 15.03 | 29.52 |
| `L32` | 90.39 % | 79.87 % | 17.45 | 30.85 |
| `L16` | 88.45 % | 71.82 % | 19.65 | 31.91 |

The divisor is not a guess: at ÷80 the duty cycle would be **193 %**, which is impossible, and at
÷160 it is 96.64 %, just under the ceiling. Per-unit, divisor-free: **1 144 278 VALU issue cycles
per SIMD and 1 108 364 `TA_BUSY` cycles per CU, against 1 184 031 GPU busy cycles** — both within
7 % of the pass duration.

**At the baseline the pass is co-saturated: the pixel-shader VALU at 96.6 % and the texture
addresser at 93.6 %, with the ALU marginally the higher of the two.** O6 therefore **cannot** rank
texture work above ALU work at `L128`. Both are driven by the same per-light loop and both fall
with it.

What survives, stated at the strength the evidence supports:

- **The coefficient replicates.** 13.1–13.6 addresser cycles per removed texture instruction,
  against the 14.5 O5 forecast from an entirely different measurement on the unmodified
  baseline. An ALU account has no reason to reproduce that number, but it is a consistency
  result, not an exclusion.
- **Texture work is on the critical path, from O4, not from here.** That cycle held ALU fixed by
  construction — byte-identical bytecode, VALU verified unchanged to 0.07 % — moved only the
  texture path, and the pass followed: `TA_BUSY` −3.5 %, `GPUBusyCycles` −2.6 %. Small, but it is
  the only arm in the whole phase where one of the two moved alone.
- **As the light loop shortens the two diverge.** VALU duty falls 96.6 % → 71.8 % while TA duty
  falls only 93.6 % → 88.5 %, so by `L16` the addresser is the sole saturated unit. That is
  consistent with the cost mix rather than with a single limiter: the instructions being removed
  are the cheap ones — shadow-map comparison fetches and light-buffer loads at ~13.1 cycles —
  so the three anisotropically filtered material samples, measured by O3 at roughly 3.4× the
  average cost, become a larger share of a shrinking mix. `TA_BUSY` per texture instruction
  rising 14.51 → 19.65 is that mix shift, not a defect.

**How an ALU-bound account could still be saved:** at `L128` it is not excluded at all, and two
mechanisms would let it survive every measurement here. First, each loop iteration issues a
stable amount of texture work, so `TA_BUSY` would fall proportionally with the iteration count
*even if the ALU were the thing setting the duration* — the 13.1-cycle coefficient is then a
property of the loop body, not evidence of a texture limit. Second, removing iterations shortens
the waves themselves, which lowers `TA_BUSY` regardless of which unit binds. Only a cycle that
moves ALU alone — the mirror of O4, ideally a factorial ALU × texture design — would settle the
ranking, and no such arm exists in this phase.

## 5. What Phase 2O concludes

Six cycles, each one a preregistered gate:

| cycle | question | outcome |
|---|---|---|
| O1 | does the build chain propagate source → bytecode → PSO → image, fail-closed | **PASS** |
| O2 | what do the raw counters mean, and is the workload identical frame to frame | **PASS**; aggregation validated against the SDK, `TexUnitBusy` shown to be a max, not a mean |
| O3 | do the material samples explain the pass | no — 2.1 % of texture instructions, 13.9 % of TA cycles |
| O4 | is it filtering throughput | **falsified** — anisotropy off entirely moves the pass ≤ 3 % |
| O5 | is it cache or memory | **falsified** — 0.24 % L0 stall, 97.7 % L0 hit, 39.6 GB/s |
| O6 | does the pass scale with the texture instruction count | **replicated** — 13.1 cycles each, ~88 % of the pass |

**What is established.** `Render Color` is dominated by the **per-light shading loop** in
`ShadeLights`. Roughly **88 % of the pass's GPU busy cycles lie on a line in that loop's work**
(R² = 0.9996 over four arms), and at the baseline the loop leaves *both* the pixel-shader VALU
(96.6 %) and the texture addresser (93.6 %) near saturation. Four candidate explanations were
tested and eliminated by measurement rather than by argument — each within the scope stated:

| candidate | measurement | verdict |
|---|---|---|
| texture **filtering** throughput | anisotropy off, byte-identical bytecode: pass moves ≤ 3 % | falsified (O4) |
| L0 cache back-pressure on the addresser (`TCP→TA` request stall) | stall / busy = 0.24 %, band was ≤ 10 % | falsified (O5) |
| L0 miss traffic | 97.66 % hit, 0.21 misses per texture instruction | falsified (O5) |
| DRAM bandwidth **saturation** | 39.6 GB/s against 555–621 GB/s reached elsewhere in this frame | falsified (O5) |

Those are bounded claims. What is excluded is bandwidth saturation and `TCP→TA` back-pressure —
**not** memory latency in general, for which no counter was collected.

**What is not established.** Which of the two saturated units — VALU or texture addresser — is
the binding one at the baseline. They are within 3 points of each other and every arm in this
cycle moves both, so the whole cycle is consistent with an ALU-bound pass in which each removed
loop iteration happens to carry a stable 13.1 cycles of addresser work. O4 is the only arm in the
phase that moved one alone; it moved the texture path by 3.5 %, enough to place texture work on
the critical path, not enough to rank it. Settling this needs the mirror of O4 — an arm that
moves ALU alone at fixed texture count, ideally a factorial ALU × texture design. It was not run.

Stated at the strength the evidence actually supports:

> In this workload the light loop makes texture instructions, VALU work, `TA_BUSY` and pass
> duration co-scale almost linearly. O5 rules out bandwidth saturation and strong `TCP→TA`
> back-pressure, and O4 rules out filtering throughput; but the data do not causally separate a
> texture-addresser limit from an ALU limit or from the loop's other effects.

**What it means for the original question.** The cost this phase can actually locate is the
**number of texture and ALU operations the shading algorithm issues per pixel** — the 10-tap PCF
kernel in `GetDirectionalShadow`, the per-light shadow fetches and light-buffer loads in
`ShadeLights`. That is a property of the application. It is **not** a driver setting, a compiler
flag, a sampler state, or a cache configuration. Phase 2E–2K had already established that no
codegen lever is reachable from outside the driver; 2O adds that on this workload the reachable
cost was never in codegen to begin with.

## 6. Limits

- **O6 cannot separate ALU from texture on its own**, and after the divisor correction in §4
  it cannot rank them at the baseline either: VALU 96.6 % against TA 93.6 %.
- **A wrong number was published in this report's first draft** (VALU duty 48.3 %, from
  dividing by 320 SIMDs instead of 160) and it supported a stronger conclusion than the
  data allow. Corrected in §4 and §5; the arithmetic check that catches it is that ÷80
  yields an impossible 193 %.
- **Not an optimisation.** Fewer lights is a different image. Nothing here is a proposed change.
- **The lever changes more than a count.** Zeroing `radiusSq` changes the light grid itself, so
  the surviving accesses differ in type, locality and shadow-array layer, not only in number. It
  also shortens the waves. `Render Shadow Map` does not read `radiusSq` and its commands are
  unchanged, but `FillLightGrid` runs differently before the measured scope and can alter L2
  residency entering it. None of these is measured.
- **`TCP→TA` stalling grows as the loop shrinks**: absolute stall cycles rise 208 076 → 553 606
  and stall / `TA_BUSY` rises 0.23 % → 2.16 % from `L128` to `L16`. Still an order of magnitude
  below the decision band, but it means the back-pressure is not constant across the sweep.
- `GPUTime` at this precision is unreliable on this machine (§2). Conclusions rest on
  `GPUBusyCycles` and `TA_BUSY`.
- Two prepare attempts were rejected before the valid one and are preserved as
  `31_o6_lightcount_SUPERSEDED_prepare_{01,02}`; neither built or measured anything.

## 7. Independent audit

Both cycles were audited by a second agent (Codex, driven through Herdr), which recomputed the
O5 and O6 tables from the raw CSVs with its own script and reproduced every figure — dose,
elasticities 0.935 / 0.905 / 0.904, marginal cost 13.576 / 13.132 / 13.117, and the four-point
OLS to the sixth decimal.

Findings adopted from that audit, each of which weakened a claim in the draft:

1. The SIMD divisor (§4) — found independently, with the RDNA2 ISA document cited. It had already
   been corrected here; the audit confirms the correction and adds that `INST_CYCLES_VALU` is an
   emulated counter better described as normalised issue-cycle demand than as exclusive occupancy.
2. The 13.1 cycles are addresser unit-cycles summed over 80 TAs, not pass-duration cycles (§3).
3. R² is not causation: the dose is collinear with VALU work and loop length (§3).
4. An ALU-bound account survives all of O6 by two concrete mechanisms (§4).
5. The `TCP→TA` result excludes that specific back-pressure, not memory latency generally (§5).
6. The final conclusion was overstated; the wording now in §5 follows the audit's proposal.

The audit also verified positively that the `TCP` counter is live (80/80 instances non-zero,
per-instance medians 1 596–3 159 cycles; it is GPA's own numerator for `MemUnitStalledCycles`)
and that `Render Shadow Map` does not read `radiusSq`.

Preserved: `codex_audit_o5_o6.txt`.

## 8. Artifacts

`experiment_manifest.json` (preregistration incl. bands and the falsification rule),
`input_hashes.csv`, `instrumented_source_hashes.csv`, `baseline_LightManager.cpp`,
`source_revisions/L*_LightManager.cpp`, `build_L*.json`, `build_logs/`, `runs/` (36 runs:
4 variants × 3 processes × {`sq_ps`, `tcp_ta`, `resp`}), `o6_analysis.json`, `tools/run_o6.py`.

- **Budget:** cycle **6 of 6** — Phase 2O complete.
- **Preservation:** no deletes, no Clean; driver, cache, Registry, security and game files
  untouched. Every build passed the fail-closed bytecode gate.
