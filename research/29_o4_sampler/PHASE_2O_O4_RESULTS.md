# Phase 2O — cycle O4: sampler-only ablation on `Render Color`

**Date:** 2026-09-06 · **Experiment ID:** `O4_20260906_021230` · cycle **4 of 6** ·
`diagnostic_only` — filtering quality changes, so the image changes; no variant here is an
accepted optimisation.

O3 could not separate texture work from ALU: removing a sample also removes the arithmetic that
consumed it (`mat3` = −2.1 % texture instructions and −11.3 % VALU). O4 removes that confounder
by construction. **Nothing in the shader changes.** Only the static sampler that the material
textures are read through is altered, in C++, and the build gate rejects any build whose pixel
shader bytecode is not the O1/O2/O3 baseline.

| variant | sampler | bytecode | gate |
|---|---|---|---|
| `s_base` | `MaxAnisotropy = 8` (the O1/O2/O3 baseline) | `52CE6C5E64AB2E82` | pass |
| `s_aniso1` | `MaxAnisotropy = 1` | `52CE6C5E64AB2E82` | pass |
| `s_aniso16` | `MaxAnisotropy = 16` | `52CE6C5E64AB2E82` | pass |
| `s_point` | aniso 1 + `MIN_MAG_MIP_POINT` | `52CE6C5E64AB2E82` | pass |
| `s_bilinear` | aniso 1 + `MIN_MAG_LINEAR_MIP_POINT` | `52CE6C5E64AB2E82` | pass |

All five executables carry the same 12 612-byte pixel shader, SHA-256
`3fbca1dd…74c6`. Instruction count, register pressure and scheduling are therefore held fixed —
subject to the caveat in §6.

Scope verified in source: the GPA scope is `SponzaRenderer.cpp:383-384`, containing only the
Sponza opaque and cutout draws on `m_ModelPSO` / `m_CutoutModelPSO`. Both run `ModelViewerPS`,
which samples `texDiffuse`, `texNormal` and `texSpecular` **exclusively through `defaultSampler`
(`s10`)** — the sampler this experiment changes. No skybox, no `DefaultPS`, no `cubeMapSampler`
inside the measured scope.

---

## 1. The dose, measured exactly

`aniso` session, 8 samples, 80 TA instances, 721 counters. `ANISO_k_CYCLE_QUADS` counts quads
that took *k* cycles in the addresser, so `Σ k · quads_k` is the filtering work in cycles.

| variant | quads | aniso cycles | mean aniso | `TexAveAnisotropy` | Δ aniso cycles | Δ MIP cycles |
|---|---:|---:|---:|---:|---:|---:|
| `s_base` | 11 224 454 | 13 671 995 | 1.2181 | 1.2181 | — | — |
| `s_aniso1` | 11 217 188 | 11 217 188 | 1.0000 | 1.0000 | **−17.96 %** | **+6.29 %** |
| `s_aniso16` | 11 224 386 | 13 768 487 | 1.2267 | 1.2267 | **+0.71 %** | −0.03 % |
| `s_point` | 11 222 924 | 11 222 924 | 1.0000 | 1.0000 | **−17.91 %** | −4.56 % |
| `s_bilinear` | 11 218 699 | 11 218 699 | 1.0000 | 1.0000 | **−17.94 %** | −4.60 % |

The quad count is constant to 0.06 %: the same texels are addressed the same number of times.
What changes is how many cycles each quad occupies the addresser. The histogram collapses
completely for the three downward variants — every quad lands in the 1-cycle bucket — and
`TexAveAnisotropy` confirms the dose independently (1.2181 → 1.0000).

**The upward arm produced almost no dose.** `s_aniso16` moves 44 056 quads out of the 8-cycle
bucket into 10/12/14/16, worth **+0.71 %** of aniso cycles, because at this camera position the
content almost never asks for more than 8× anisotropy. The preregistered bidirectionality is
therefore formally present but experimentally ineffective — see §5.

**The dose is not one-dimensional.** `s_aniso1` keeps trilinear filtering and its MIP work goes
*up* 6.29 % (2-cycle MIP quads 535 302 → 1 282 689), while `s_point`/`s_bilinear` remove MIP
blending entirely (2-cycle MIP quads → 0, −4.6 %). Aniso and MIP cost are not varied
independently here.

## 2. ALU held fixed — verified, not assumed

Same bytecode is an argument, not a measurement. `sq_ps` session, 16 samples, all four shader
engines healthy under `tools/sq_validity.py` (unlike O3, where SE0/SE2 were corrupted):

| variant | `INSTS_VALU` | `INST_CYCLES_VALU` | `ITEM_CYCLES_VALU` | `INSTS_TEX_LOAD` | `WAVES` |
|---|---:|---:|---:|---:|---:|
| `s_base` | 35 658 701 | 92 019 721 | 2 473 066 940 | 3 070 686 | 19 706 |
| `s_aniso16` | +0.07 % | +0.05 % | −0.00 % | +0.07 % | +0.07 % |
| `s_point` | +0.05 % | +0.02 % | −0.01 % | +0.05 % | +0.05 % |

Every counter is inside the ±0.4 % band AMD marks `{emulated}`; `ITEM_CYCLES_VALU`, which O2
showed to be exact, agrees to 0.01 %. `WAVES_32 = 0` throughout — still wave64.
**Whatever the sampler change does to the pass, it does not do it through ALU work.**

## 3. Response

`resp` session (80 × `TA_BUSY`, 80 × `ANISO_1_CYCLE_QUADS`, `GPUTime`, `GPUBusyCycles`),
32 samples per run, **3 independent processes per variant**, order interleaved: rep 1 forward
`s_base…s_bilinear`, rep 2 reversed, rep 3 forward.

**A/A control on `s_base` across the three processes** (pairwise |Δ| between process medians,
relative to the pair mean):

| metric | pairwise | N95 | threshold = max(2 %, 3·N95) |
|---|---|---:|---:|
| `TA_BUSY` | 0.20 %, 0.07 %, 0.12 % | 0.20 % | 2.00 % |
| `ANISO_1_QUADS` | 0.00 %, 0.00 %, 0.00 % | 0.00 % | 2.00 % |
| `GPUTime` | 1.29 %, 0.25 %, 1.04 % | 1.29 % | 3.88 % |
| `GPUBusyCycles` | 0.12 %, 0.20 %, 0.32 % | 0.32 % | 2.00 % |

Median of the three processes:

| variant | Δ`TA_BUSY` | Δ`GPUTime` | Δ`GPUBusyCycles` | verdict |
|---|---:|---:|---:|---|
| `s_aniso1` | **−2.73 %** | −2.31 % | **−2.20 %** | split |
| `s_aniso16` | +0.10 % | −0.18 % | +0.25 % | no effect |
| `s_point` | **−3.50 %** | −2.86 % | **−2.63 %** | split |
| `s_bilinear` | **−3.54 %** | −2.52 % | **−2.78 %** | split |

Paired per process, the mechanistic counters are extremely stable:

| variant | Δ`TA_BUSY` p1 / p2 / p3 | Δ`GPUBusyCycles` p1 / p2 / p3 | Δ`GPUTime` p1 / p2 / p3 |
|---|---|---|---|
| `s_aniso1` | −2.81 / −2.61 / −2.67 % | −2.20 / −2.19 / −2.34 % | −3.13 / −0.03 / −2.31 % |
| `s_aniso16` | −0.10 / +0.24 / +0.10 % | +0.16 / +0.39 / +0.05 % | −10.65 / +1.15 / −0.18 % |
| `s_point` | −3.59 / −3.38 / −3.50 % | −2.59 / −2.52 / −2.89 % | −1.79 / −2.12 / −2.86 % |
| `s_bilinear` | −3.61 / −3.44 / −3.50 % | −2.78 / −2.62 / −3.04 % | −3.58 / −1.33 / −2.52 % |

`s_aniso16` process 1 read `GPUTime` 720 620 ns against ~803 000 in the other two while its
`GPUBusyCycles` barely moved: cycles-per-nanosecond 1.65 vs 1.48, consistent with a different
clock/DVFS regime, cause not measured. The median absorbs it, and it is the concrete reason
`GPUTime` is the least trustworthy of the three outcomes at this effect size.

### The threshold, honestly

The preregistration names **both** `GPUTime` and `GPUBusyCycles` as response outcomes and never
says which one feeds N95. Applying the same formula to each outcome with its own A/A control:

- **`GPUTime`** (threshold 3.88 %): no variant passes. **Null.**
- **`GPUBusyCycles`** (threshold 2.00 %): all three downward variants pass.
- **`TA_BUSY`**, the preregistered mechanistic response (threshold 2.00 %): all three pass.

Choosing the quieter metric after seeing the data would be cherry-picking, so the verdict
recorded here is the **conservative co-primary one: both outcomes must pass, and they do not.**
The reduction in texture-unit busy cycles and in GPU busy cycles is established; the reduction
in wall-clock GPU time is suggestive and **not confirmed**. Note also that "N95" is the maximum
of three pairwise differences, not a real 95th percentile.

## 4. What this establishes

**Turning anisotropic filtering off entirely — and, in `s_point`, dropping to the cheapest
filter the hardware has — moves `Render Color` by at most about 3 %, with the pixel shader
byte-identical and its ALU work measured unchanged.**

That is the answer to the question O4 was built to ask. The hypothesis carried over from 2N —
that `Render Color` is *texture-filter-throughput bound* — predicted a large effect from exactly
this intervention. An 18 % cut in filtering cycles buys 3.5 % of `TA_BUSY` and no confirmed
change in time, while `TexUnitBusy` stays around 94 %. **The filter-throughput reading of that
94 % is not supported.** The texture unit is busy, but it is not busy *filtering*.

`s_point` and `s_bilinear` are indistinguishable from each other (−3.50 % vs −3.54 % `TA_BUSY`),
which places the marginal cost of bilinear tap blending, on this content, below the measurement
floor.

## 5. What this does **not** establish

- **The bidirectional control failed.** `s_aniso16` delivered +0.71 % of dose, ~25× smaller than
  the downward arms; scaling the observed response predicts ~0.1 %, far under the noise. Its
  null result is therefore uninformative and cannot be used to argue against a one-sided
  artefact, nor to support linearity, symmetry or saturation. Only the downward arms carry
  evidence.
- **No cost partition against O3.** O3 removed the three material samples entirely
  (`TA_BUSY` −13.91 %); O4 makes those same samples point-filtered (−3.50 %). The ratio 25 % is
  a comparison of two *different* interventions, not a decomposition into "25 % filtering,
  75 % everything else": O3 also removed ALU and dependencies, O4 also changes MIP work and
  memory traffic, and additivity was never measured. Reported as a descriptive ratio only.
- **Not a filter-only measurement.** No TCP/TCC/cache/memory counters were collected. Point
  filtering touches fewer texels per quad, so part of the −3.5 % may be reduced memory traffic
  rather than reduced filtering arithmetic. O4 measures the cost of the whole sampler path.
- **What `Render Color` *is* bound by remains open.** O4 removes one candidate.

## 6. Defects found in this cycle

1. **The manifest's own claim "only the material sampler changes" is false.**
   `CubeMapSamplerDesc` is copy-initialised from `DefaultSamplerDesc`
   (`Renderer.cpp:83`), so the static sampler at `s12` changed in every variant too.
   `ModelViewerPS` does not use `s12` and the skybox is outside the measured scope, so no number
   in this report is affected — but the invariant as written was wrong and is corrected here.
2. **`defaultSampler` (`s10`) is also used outside the scope**, by `DepthViewerPS` (cutout alpha
   test in the depth and shadow passes) and by `SkyboxPS`. Those passes are not in the sample,
   but they run before it and can leave the texture caches in a different state. Not separable
   from these data.
3. **Identical DXIL does not guarantee identical native ISA.** The driver compiles the PSO with
   the root signature and its static samplers in hand. The gate pins the bytecode, not the
   generated ISA. The `sq_ps` control in §2 is the empirical answer: VALU instructions, cycles,
   texture-load instructions and wave count are unchanged to within 0.07 %.
4. `tools/o4_analyse.py` originally derived N95 with an order-dependent denominator (0.3155 % vs
   0.3165 % on `GPUBusyCycles`) and hard-coded `GPUTime` as the metric feeding the threshold, a
   choice that appears nowhere in the preregistration. Both fixed; the threshold is now computed
   per outcome and the co-primary rule is explicit.

## 7. Independent audit

The numbers in §1 and §3 were **recomputed independently by a second agent (Codex)** from the
raw CSVs with its own stdlib script, without reading `tools/o4_analyse.py` first: dose
histograms, aniso cycles, `TA_BUSY`, `GPUTime` and `GPUBusyCycles` all reproduce.
Findings 1–3 of §6, the failure of bidirectionality (§5) and the rejection of the O3/O4 cost
partition (§5) come from that audit and were adopted, replacing stronger claims in the first
draft of this report.

Preserved: `audit/codex_recalc_o4.py`, `audit/codex_audit_transcript.txt`.

## 8. Artifacts

`experiment_manifest.json`, `input_hashes.csv`, `instrumented_source_hashes.csv`,
`source_revisions/*_Renderer.cpp`, `build_s_*.json`, `build_logs/`, `runs/`,
`o4_analysis.json`, `tools/o4_analyse.py`, `audit/`.

`runs/` holds 23 runs: 5 × `aniso` (dose, one per variant), 15 × `resp` (5 variants × 3
independent processes), 3 × `sq_ps` (ALU control on `s_base`, `s_point`, `s_aniso16`).

- **Budget:** cycle **4 of 6**.
- **Preservation:** no deletes, no Clean; driver, cache, Registry and security untouched; no
  game files touched. Every build went through the fail-closed gate and every one passed.
