# Phase 2T — the hit rate of the frozen pipeline

**Closed 2026-09-07.** Preregistration: [`PHASE_2T_PREREGISTRATION.md`](PHASE_2T_PREREGISTRATION.md),
written before any of the four workloads was inspected. The pipeline frozen in
[`POC_FROZEN.md`](POC_FROZEN.md) was run unchanged on all four, in the order fixed in advance.

## The answer

> **Hit rate: 0 of 4 workloads.** Five candidate transformations built and measured, **none
> accepted**. The phase ends because W1–W4 are all closed, at 7 of the 10 budgeted cycles.

The two workloads already reported separately and **not** counted here were 1 hit
(MiniEngine ModelViewer, −41.4 %) and 1 miss (`D3D12nBodyGravity`). Counting them the method
stands at **1 hit in 6 attempted workloads**.

## Per workload

| | workload | verdict | attempts | where it stopped |
|---|---|---|---|---|
| W1 | `D3D12ExecuteIndirect` | **MISS** | 0 | profile / oracle |
| W2 | `D3D12Multithreading` | **MISS** | 3 | correctness ×2, performance ×1 |
| W3 | `D3D12MeshShaders` | **MISS** | 0 | profile |
| W4 | `D3D12VariableRateShading` | **MISS** | 2 | correctness ×1, performance ×1 |

### W1 — `D3D12ExecuteIndirect` · [verdict](49_2t_w1/verdict.json)

The cull dispatch runs ~41 000 ALU operations in 5.76 µs, about 0.03 % of this GPU's arithmetic
peak: dispatch-latency bound, so no change to the shader can move it. The draw region is 1024
indirect draws of one triangle each — command-processor bound. Separately, the workload has **no
correctness oracle**: the triangles are animated from wall-clock time, so the back buffer differs
on every run (`60a068f9`, `843fca9c`, `bbb2396e`) and could only be made deterministic by
modifying the workload. Closed before any hypothesis. A/A N95 2.72 %, so a transformation would
have had to be worth more than 8 % of the draw region to be detectable at all.

### W2 — `D3D12Multithreading` · [verdict](50_2t_w2/verdict.json)

A/A N95 0.96 %, threshold 2.88 %. Three hypotheses, all from this workload's ISA (372
instructions, 3 `v_sqrt` + 7 `v_rcp` + 9 `v_rsq`: lengths taken and then divided by, not fused
into a reciprocal square root). They removed the arithmetic they targeted and the pass did not
care.

| transformation | Δ region | image | verdict |
|---|---:|---|---|
| `rsqrt_dist` | −0.99 % | 2 bytes of 3 686 400 differ, 1 LSB each | REJECTED (correctness), also below threshold |
| `light_dir_norm` | −0.22 % | identical | REJECTED (performance) |
| `both` | −1.22 % | changed | REJECTED (correctness), also below threshold |

The two changed images are the 1-LSB rounding class phase 2Q characterised: under 2P's ULP rule
they would pass, under this phase's byte-exact rule they do not. **The verdict does not depend on
which rule is used**, because all three are also below the acceptance threshold.

### W3 — `D3D12MeshShaders` · [verdict](51_2t_w3/verdict.json)

The entire draw — every mesh-shader dispatch over the model — takes **480 ns**, which is 48 ticks
of this queue's 100 MHz timestamp counter. Halving it would sit at the edge of what the instrument
resolves. The oracle is fine (byte-identical across three processes); there is simply nothing to
optimise. Closed before any hypothesis.

### W4 — `D3D12VariableRateShading` · [verdict](52_2t_w4/verdict.json)

The best-behaved workload of the four and the most informative miss.

**Baseline.** Whole GPU frame 150.36 µs; refraction pass 57.40 µs, scene pass 40.54 µs,
postprocess 13.86 µs. Back buffer **byte-identical across 14 base processes in two sessions**.
A/A N95 0.44 % → acceptance threshold 1.32 %.

**Hot shader.** `ShadowsAndScenePass_PSMain` (`38a3891b…`), bound by both the scene-pass and the
refraction-pass PSO — together 65 % of the frame. Its ISA on gfx1030: 237 instructions, 23 VGPR,
no scratch, **6 `image_sample`**, 4 `v_rsq` + 4 `v_rcp` + 1 `v_sqrt`. The ISA also shows the
compiler has already dead-coded the angle-falloff term, which the source computes and then
overwrites with `1.0f`.

**The Amdahl probe first, before spending cycles on hypotheses.** Deleting the whole lighting
body — keeping geometry, rasterisation and the one diffuse fetch — takes the frame down
**−16.59 %** (−16.59, −16.68, −16.53 over three processes). Unlike MiniEngine's `Render Color` in
phase 2M, this pass **does** have headroom. The misses below are not a ceiling problem. The probe
is a diagnostic, not an attempt: its image is deliberately wrong and it is not counted in the
hit rate.

| transformation | Δ frame | image | verdict |
|---|---:|---|---|
| `gather_pcf` | −0.34 % | 43 pixels of 921 600 differ, max delta 41 | REJECTED (correctness), also below threshold |
| `zeroskip_shadow` | +0.13 % | **identical** | REJECTED (performance) |

`gather_pcf` came from W4's own ISA: 4 of the 6 `image_sample` are one cluster — the 2×2 PCF taps
— and the C++ creates that sampler as `D3D12_FILTER_MIN_MAG_MIP_POINT`, so four point samples of
one texel quad are exactly what a single `gather4` returns. It did what it promised in the ISA
(6 `image_sample` → 2 `image_sample` + 1 `image_gather4_lz`, 23 → 22 VGPR) and **halving this
shader's texture instructions bought 0.5 % of the pass**. Whatever the 16.6 % is, it is not
texture-instruction throughput. The correctness failure is not rounding noise: the half-texel
offset rounds onto a different texel on some shadow-boundary pixels, a tap flips between 0 and 1,
and the weighted PCF result moves by up to a quarter.

`zeroskip_shadow` is the one transformation in this phase whose image came back **byte-identical**
— the bit-exactness argument (`0 * finite == 0`, both factors out of a `saturate`) held, and it
held against an oracle that would have shown a non-finite shadow term as a changed pixel rather
than letting it pass. It bought nothing: one point light covers most of the visible geometry, so
few whole waves are entirely unlit and the branch almost never skips.

**Its provenance is declared rather than hidden.** The preregistration says *no transformation is
proposed from memory of what worked before*. The pattern of `zeroskip_shadow` — do not compute
what is multiplied by an exact zero — is phase 2P's, transferred. Its application here was found
in W4's own source and ISA, but the pattern was not. It is reported separately so that, had it
hit, the hit would not have been credited to the ISA-only pipeline. It did not hit, so nothing
turns on it; the disclosure stands anyway.

## The metrics, as they were defined before measuring

- **Hit rate** — workloads with ≥1 accepted transformation ÷ workloads attempted: **0 / 4**. No
  workload was swapped for an easier one; W1 and W3 stay in the denominator with their reasons
  recorded. W5 was never used: it was reserved for a workload that could not be attempted at all,
  and all four were attempted.
- **Cost in attempts** — transformations built and measured ÷ accepted: **5 / 0**, undefined. Five
  candidates were built, gated on their preregistered bytecode, and measured over 4 paired
  processes each (3 for the diagnostic).
- **Quality of gains** — none to report.
- **Failure taxonomy**, every attempt counted:

| reason | count | where |
|---|---:|---|
| build failure | 0 | — |
| no measurable pass | 2 workloads | W1 (dispatch-latency and command-processor bound), W3 (480 ns) |
| no hypothesis found | 0 | — |
| compiler already does it | — | not a rejection here, but observed: W4's angle falloff is dead-coded before the ISA |
| correctness rejected | 3 | W2 `rsqrt_dist`, W2 `both`, W4 `gather_pcf` |
| performance rejected | 2 | W2 `light_dir_norm`, W4 `zeroskip_shadow` |
| no deterministic oracle | 1 workload | W1, on top of its profile result |

## What this says about the method

1. **The profiling stage is doing most of the work, and it is doing it correctly.** Two of four
   workloads were closed before a single hypothesis was written, on measurements that were right:
   a 5.76 µs dispatch and a 480 ns draw cannot be improved by changing a shader. The pipeline
   fails cheap when it fails.
2. **Headroom is not the constraint; it is either absent or unreachable.** W4 has 16.6 % of its
   frame inside one pixel shader and the pipeline still could not take any of it. The two
   candidates split the reasons cleanly: the one that was fast enough to matter was not exact, and
   the one that was exact did not matter.
3. **The 2P result looks more like an outlier than a rate.** One hit in six workloads, and the hit
   was worth −41 % while nothing else cleared 1.3 %. The honest reading is that MiniEngine's
   `ShadeLights` had an unusually large, unusually removable per-light body, not that the method
   generalises at that magnitude.
4. **The byte-exact oracle is a real gate, not a formality.** It rejected 3 of 5 candidates,
   including one where the difference was a genuinely different texel on 43 pixels, not rounding.
   Under 2P's ULP rule two of those three would have passed — and both were below their thresholds
   anyway, so no verdict in this phase depends on the choice of rule. That is luck, not design,
   and a future phase that wants to use the ULP rule should preregister it.
5. **The corpus was less independent than its names suggested.** W2 and W4 both build on the
   Microsoft sample framework and share `CalcLightingColor` almost verbatim. They were chosen by
   directory name, as preregistered, and the overlap only became visible after the source was
   opened — but it means 2 of the 4 "structurally distinct" workloads were not.

## Defects the gate caught in this phase

- **Aux headers were never snapshotted or restored.** The runner restored only shader entry-point
  files, so after a build that edited `Common.hlsli` the workspace stayed dirty. The next build
  was stopped by its preregistered hash (`Glass_PSMain 57cd15bf != 886d0b8a`) **before it produced
  a number**. Fixed at the root: `source_rels()` in `tools/run_2t.py` now covers `aux` at all
  three snapshot and restore sites, the W4 baseline snapshot was repaired from the untouched
  upstream copy and verified equal to it (`1f4c6117…`), and all three W4 variants were rebuilt to
  their preregistered hashes afterwards.
- **The analyser paired runs by rep number.** W4's base moved 1.2 % between the session that ran
  `base_r1..r3` and the session that ran everything else, so index pairing would have scored
  `gather_pcf` at roughly −1.5 % against a stale baseline and **manufactured an acceptance**.
  Fixed: every run is now paired with the base run nearest to it in wall-clock time, and the A/A
  control no longer mixes sessions. W1–W3 were re-analysed with the fix; their verdicts are
  unchanged (W2's `rsqrt_dist` moves −1.03 % → −0.99 %, `light_dir_norm` −0.37 % → −0.22 %).
- Three superseded `prepare` directories in W2–W4 (probe header in the wrong directory, output
  directory assumed at the solution level, a two-region instrumentation replaced by four) were
  rejected before producing numbers and are kept under their `_SUPERSEDED_` names.

## Limits of this result

- Four workloads, one GPU, one driver, one scene each. A hit rate of 0/4 has a wide interval; it
  rules out "usually works", not "sometimes works".
- Two of the four share a shader family, so the effective sample is smaller than 4.
- All four came from one repository, chosen for a common toolchain. Nothing here says how the
  method behaves on an engine that was written to be fast.
- The acceptance rule was preregistered and never moved after a number was seen. It is also
  strict: `zeroskip_shadow` was byte-exact and would have been accepted at any threshold below
  its own noise, which is to say it was never close.

**No modification to driver, cache, Registry, security settings or games. Nothing deleted.**
