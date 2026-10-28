# 2U cycles U1–U2 — W4's ceiling, decomposed and then attacked

Workload: `D3D12VariableRateShading / ShadowsFogScatteringSquidScene`, carried forward from
phase 2T, where it missed. Its 2T miss stands; this is a re-attempt and is reported as one.

Baseline unchanged: whole GPU frame 150.66 µs, back buffer byte-identical across 22 base
processes, A/A N95 0.48 % → acceptance threshold 1.44 %.

## U1 — where the 16.59 % actually is

Phase 2T measured the ceiling with one ablation: deleting the whole lighting body of
`ShadowsAndScenePass_PSMain` is worth **−16.59 %** of the frame. U1 splits that into blocks. Each
probe removes exactly one block and keeps the others alive — `abl_lightmath` still consumes
`pixelNormal` so the normal-map block cannot be dead-coded along with it, and `abl_shadow_taps`
still consumes the transformed depth so both 4×4 transforms stay.

| probe | ISA instructions | image_sample | Δ frame (3 processes) | share of the 16.59 % |
|---|---:|---:|---:|---:|
| `abl_shadow` — the whole shadow term | −111 of 227 | −4 | **−11.98 %** | **72 %** |
| ↳ `abl_shadow_taps` — its four texture taps only | −22 | −4 | −2.34 % | 14 % |
| ↳ therefore its address math, by difference | ≈ −89 | 0 | ≈ −9.6 % | ≈ 58 % |
| `abl_normalmap` — normal fetch + tangent frame | −43 | −1 | −3.92 % | 24 % |
| `abl_lightmath` — distance, falloff and N·L | −26 | 0 | −2.32 % | 14 % |
| `ablate_ps` — the whole body (2T) | −205 | −5 | −16.59 % | 100 % |

The blocks sum to 110 % of the whole-body ablation. They are **not additive** and are not
reported as if they were: removing one block lets the rest overlap better, exactly the effect
phase 2O documented. The ordering is what the decomposition is for, and the ordering is
unambiguous.

**Three quarters of everything available in this shader is the shadow term, and two thirds of
*that* is not the texture taps but the address math** — two chained 4×4 transforms by matrices
that are uniform for the whole draw, a perspective divide, `frac`, and the bilinear weights,
evaluated per pixel. This also closes 2T's open question: 2T found that halving the shader's
texture instructions bought 0.5 %, and now we know why — the taps are 14 % of the ceiling, not
the bulk of it.

## U2 — hoisting the address math to the vertex stage

The transformation the decomposition points at: `lights[0].view` and `lights[0].projection` are
uniform for the draw, so `mul(mul(worldpos, view), projection)` is a linear function of the world
position. Compute it once per vertex, interpolate it, and the pixel shader loses 32 `v_fma` and
gains 8 `v_interp`.

**Preregistered prediction, written before the build:** performance −1.8 % to −3.0 %; correctness
fails tier A *and* tier B, because the shadow test is a hard comparison and interpolating the
light-space position flips it on boundary pixels.

Built through the gate. ISA confirms the mechanism: **−31 instructions, −26 VALU, +6 interp,
−3 VGPR, −24 SGPR**, and `Glass_PSMain` comes out byte-identical, so the delegating wrapper the
refactor needed is genuinely free.

**Measured: +4.31 %. The prediction was wrong in sign.**

Attribution by region says why, and the sample's own postprocess pass acts as a negative control:

| region | base | vs_lightspace | Δ |
|---|---:|---:|---:|
| whole frame | 150 660 ns | 157 160 ns | **+4.31 %** |
| shadow-map pass + gaps — **no pixel shader at all** | 38 520 ns | 41 310 ns | **+7.24 %** |
| scene pass | 40 680 ns | 42 270 ns | +3.91 % |
| refraction pass | 57 580 ns | 59 680 ns | +3.65 % |
| postprocess — does not use this shader | 13 880 ns | 13 900 ns | +0.14 % |

The depth-only shadow-map pass has **no pixel shading**, so its +7.24 % is entirely the vertex
shader doing 32 more `v_fma` per vertex. The scene and refraction passes carry both the vertex
cost and the pixel saving and are still net slower. The postprocess pass, which does not use this
shader, does not move — the instrument is measuring what it claims to.

**This workload is vertex-sensitive.** SquidRoom's geometry goes through this vertex shader three
times a frame — shadow map, refraction, scene — against 1280×720 of pixel coverage, and the
textbook "hoist uniform work to the vertex stage" is a net loss here. That is worth more than the
transformation would have been: it is a case where the standard advice is measurably wrong on this
machine and this workload, and only the region split shows it.

Correctness came out exactly as predicted: 46 pixels of 921 600 differ, max delta 17 — a flipped
shadow comparison, not a rounding of the same arithmetic. **Fails tier A and tier B.**

## Verdict on W4 for 2U: MISS, with the ceiling fully explained

Attempts in 2U: 1 (`vs_lightspace`). Cumulative on W4 across 2T and 2U: **3 candidates, 0
accepted**.

What the two cycles establish, which the 2T miss did not:

1. **The ceiling is real, large and localised.** 72 % of it is one block.
2. **That block is protected by a hard comparison.** Every arithmetic change to the shadow
   address math — a different tap address (`gather_pcf`), a different transform order
   (`vs_lightspace`) — flips `vShadowDepths >= vLightSpaceDepth` on boundary pixels and produces
   pixel deltas of 17 to 41, not one LSB. Under both preregistered correctness tiers that is a
   rejection, and tier B was written to reject exactly this before any of it was measured.
3. **The one bit-exact lever in the shader has no payload.** 2T's `zeroskip_shadow` was
   byte-identical and worth +0.13 %: with one point light covering most of the visible geometry,
   almost no wave is entirely unlit.
4. **Moving work between stages costs more than it saves here**, measured, with a negative
   control.

Two further hypotheses were considered and **declined on a stated prediction rather than a
measurement**, which is recorded here so the choice is auditable:

- *Fold `view × projection` on the CPU and upload one matrix.* Would remove 16 `v_fma` from the
  pixel shader with no vertex cost and no extra interpolant — a better version of `vs_lightspace`,
  predicted ≈ −1.7 %. Declined because `(p·V)·P ≠ p·(V·P)` in floating point lands on the same
  hard comparison, so it is predicted to fail both tiers for the identical structural reason. It
  is listed here as an unmeasured prediction, not as a result.
- *Upload pre-divided reciprocals for `viewport` and `vFalloffs.y`, removing 3 of the 4 `v_rcp`.*
  Declined: the GPU's `v_rcp_f32` is an approximation, so a CPU-computed exact reciprocal is a
  different number, and two of the three feed texture addresses.

One hypothesis was checked against the ISA and **ruled out without a build**: the bilinear weights
and `vTexelUnits` are computed in the source before the early-out that does not use them, but the
ISA shows the compiler already sinks both inside the branch (`v_fract` appears after
`s_cbranch_execz`). Nothing to move.

**W4 is closed.** Not because the pipeline ran out of ideas, but because the ceiling has been
located and shown to be unreachable under a correctness rule that was fixed in advance.

## Defect the gate caught in U2

`variant_source` converted every anchor to CRLF whenever the file contained a single CRLF
anywhere. W4's `Common.hlsli` is **mixed** — LF through the body, CRLF on its last two lines, and
no trailing newline — so a correct anchor written against the LF region was rewritten into one
that does not exist. It failed loudly here; on a file where both forms occur it could have matched
the wrong place silently. Fixed at the root: the anchor is now tried as written, converted only if
that misses, and an anchor that would match in **both** forms is refused.
