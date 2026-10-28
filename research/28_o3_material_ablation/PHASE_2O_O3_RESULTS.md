# Phase 2O — cycle O3: material sampling ablation on Render Color

**Date:** 2026-09-06 · **Experiment ID:** `O3_20260906_*` · cycle **3 of 6** ·
`diagnostic_only` — the image is expected to differ; nothing here is an accepted optimisation.

Four builds, each gated on a bytecode SHA-256 preregistered from an offline DXC compile
**before any build ran**:

| variant | ablation | bytes | custom hash |
|---|---|---:|---|
| `mat0` | none (the O1/O2 baseline) | 12 612 | `52CE6C5E64AB2E82` |
| `mat1` | `texSpecular` → `float3(0.5,0.5,0.5)` | 12 504 | `F5456A08628CFF0B` |
| `mat2` | + `texNormal` → `float3(0.5,0.5,1.0)` | 12 040 | `422B5C76E36517E5` |
| `mat3` | + `texDiffuse` → `float3(0.5,0.5,0.5)` | 11 268 | `B03C5F67ACB6631F` |

Replacements are type-preserving at the sample site: `texNormal`'s value is consumed as
`*2-1`, so `(0.5,0.5,1.0)` yields the flat tangent-space normal `(0,0,1)`; `texSpecular`'s `.g`
is read, so the constant stays a `float3`.

---

## 1. The dose, measured exactly

| variant | texture instr. removed per PS wave | Δ PS `INSTS_TEX_LOAD` |
|---|---:|---:|
| mat1 | **1.06** | −0.68 % |
| mat2 | **2.07** | −1.33 % |
| mat3 | **3.34** | −2.14 % |

Exactly one, two and three texture instructions per wave, as designed — out of **155.9 texture
instructions per pixel-shader wave**.

**First result: material texture sampling is 2.1 % of the pixel shader's texture instructions
in `Render Color`.** The other ~153 per wave are the light and shadow-map fetches of
`ShadeLights`. Any expectation that "the material textures" dominate this pass was wrong by
roughly a factor of fifty.

## 2. The confounder, measured and not assumed

| variant | Δ texture instr. | Δ `INSTS_VALU` | Δ `INST_CYCLES_VALU` |
|---|---:|---:|---:|
| mat1 | −0.68 % | **+0.55 %** | +0.44 % |
| mat2 | −1.33 % | −1.62 % | −1.59 % |
| mat3 | −2.14 % | **−11.29 %** | −8.90 % |

`mat3` is **not** a texture-only ablation: it removes 2.1 % of texture work and 11.3 % of ALU
work, because the normal-mapping and TBN maths that consumed the sampled values dies with it.
This is exactly the dead-code confounder the handoff audit warned about, now quantified.

`mat1` is the opposite and is the useful point: it removes texture work while ALU goes
*slightly up*.

## 3. Response

Median of 3 independent processes per variant, order interleaved (1: mat0→mat3, 2: reversed,
3: mat0→mat3).

**A/A control on `mat0` across the three processes:** pairwise `GPUTime` differences 0.76 %,
1.03 %, 0.27 % → N95 = 1.03 %, so the preregistered threshold is max(2 %, 3×1.03 %) = **3.09 %**.
`GPUBusyCycles` is markedly quieter: 0.31 %, 0.23 %, 0.08 %.

| variant | Δ`TA_BUSY` | Δ aniso-1 quads | Δ`GPUTime` | Δ`GPUBusyCycles` | above threshold |
|---|---:|---:|---:|---:|---|
| mat1 | −2.33 % | −2.05 % | −1.53 % | −1.21 % | no |
| mat2 | −5.71 % | −4.41 % | −3.39 % | −3.56 % | **yes** |
| mat3 | −13.91 % | −5.57 % | −11.43 % | −12.72 % | **yes** |

Monotonic in every column, and `GPUTime` and `GPUBusyCycles` agree independently.

## 4. What it means

**The three material samples cost 13.9 % of the texture unit's busy cycles while being 2.1 % of
its instructions.** They are anisotropically filtered 2D samples; the ~153 shadow and light
fetches per wave are comparison fetches and buffer loads, which occupy the addresser far less.
Instruction counts are therefore a poor proxy for texture-unit cost here — a factor of about
seven apart.

**Texture-unit work is on the critical path of `Render Color`, but does not fully explain it.**
The cleanest evidence is `mat1`, where ALU rises 0.55 % while `TA_BUSY` falls 2.33 % and time
falls 1.53 %: that reduction cannot be attributed to ALU. Across the three variants the time
reduction is **0.59–0.82 of the `TA_BUSY` reduction** — non-zero, and below one.

`mat3` cannot arbitrate between texture and ALU, since both fall by ~11–14 %.

**This does not establish that `Render Color` is "texture-filter-throughput bound".** It
establishes that a verified reduction of texture-unit work produces a proportional-but-damped
reduction in the pass's GPU time. Separating filtering cost from the rest of the texture path,
with ALU held fixed by construction, is cycle O4.

## 5. Instrumentation defect found — per-shader-engine SQ counters are unreliable

While computing the dose, the four shader engines disagreed impossibly: e.g.
`SQ_PS0_PERF_SEL_INSTS_SALU` = 1 238 071 980 with `INSTS_VALU`, `INST_CYCLES_VALU`,
`ITEM_CYCLES_VALU` and `INSTS_TEX_LOAD` all reading exactly 0 on the same instance.

That value is **bit-for-bit the `SQ_PS0_PERF_SEL_ITEM_CYCLES_VALU` measured in a different
session in cycle O2**. The counters are not noisy — the values are landing under the wrong
event names on those instances.

- Affected: shader engine instances **0 and 2**, in every O3 session and in O2's `stage_tex`,
  `tex_all` and `tex_gs` sessions. Instances **1 and 3 are healthy in all of them** and agree
  with O2's clean session to 0.1–0.3 %.
- Not caused by pass count (a 1-pass set is affected) and not by sample count (8, 16 and 32
  all affected). O2's `sq_ps` session, which was clean, is the outlier.
- **`tools/sq_validity.py`** now rejects any session in which the shader engines disagree by
  more than 25 % on an event that is non-zero. Healthy sessions agree to ~2 %.

All O3 dose figures above are computed from **SE1+SE3 only**. This is legitimate for a
dose-response, which needs ratios rather than absolutes, and shader-engine symmetry was
*verified* rather than assumed: in O2's clean session the four engines agreed within 2.1 %.

**No earlier conclusion is affected.** O2's baseline came from its clean `sq_ps` session, which
passes the new gate; every O2 conclusion about TA counters, aggregation and workload identity
used the TA block, which shows no such defect (per-CU spread 4 %).

## 6. Other defects

- **Intermittent crash at shutdown** (`0xC0000005`) on one `mat3` run, after all counters were
  collected and written. The gate rejected that run; a repeat completed cleanly and was used
  instead. The crashed run's data was **not** used. Cause not diagnosed; it did not recur.

## Files

`experiment_manifest.json` (preregistered criteria and variant hashes) · `build_mat*.json` ·
`runs/mat{0..3}_{sq_ps,resp}_r*/` · `build_logs/` · `preregistered/` · `source_revisions/` ·
`input_hashes.csv` · `instrumented_source_hashes.csv`

## NEXT

**O4 — sampler-only ablation.** Change only the static sampler the material textures are read
through, in C++, so the pixel shader bytecode stays byte-identical to `52CE6C5E64AB2E82` and
the build gate enforces it. Instruction count, ALU and scheduling are then fixed by
construction and only the filtering cost varies, in both directions
(`MaxAnisotropy` 1 / 8 / 16, plus bilinear and point filtering).
