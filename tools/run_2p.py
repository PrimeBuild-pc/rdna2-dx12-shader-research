"""Phase 2P: semantics-preserving reductions of the per-light loop of ShadeLights.

Phase 2O located the cost: about 88 % of `Render Color`'s GPU cycles lie on a line in the work
issued by the per-light loop, which leaves the pixel-shader VALU (96.6 %) and the texture
addresser (93.6 %) both near saturation, with no evidence able to rank them. 2P attacks that loop
with transformations that must not change what the shader computes, and judges them end-to-end on
`Render Color` in the real workload - never on instruction counts, VGPRs or a microbenchmark.

Every variant is built through the same fail-closed gate as 2O, against a bytecode SHA-256
preregistered from an offline DXC compile before any build runs, and the baseline source is
restored on every exit path.

    python -B tools/run_2p.py prepare
    python -B tools/run_2p.py build <variant>
    python -B tools/run_2p.py run   <variant> <set> [--samples N] [--rep R]
    python -B tools/run_2p.py image <variant> [--rep R]
    python -B tools/run_2p.py analyse
"""
import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import sys

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G
import run_o1 as O1
import run_o2 as O2
import run_o5 as O5

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/33_2p_shadelights"
LIGHTING = "MiniEngine/Model/Shaders/Lighting.hlsli"
FIRST_FRAME = 140

# --------------------------------------------------------------------------- transformations
#
# Each entry is (relative shader file, exact bytes to replace, replacement). The anchor must be
# unique in the file or prepare aborts. `kind` records what the transformation is expected to
# touch, which is what makes the ALU / texture separation possible; `equivalence` records why it
# preserves semantics, and is the claim the correctness gate tests.

CYCLE = "p1"          # set by main(); selects the transform set and the output directory
CYCLE_DIR = {"p1": "research/33_2p_shadelights", "p2": "research/34_2p_earlyout",
             "p3": "research/35_2p_cycle3", "p4": "research/36_2p_cycle4",
             "p5": "research/37_2p_cycle5", "p6": "research/38_2p_cycle6",
             "p7": "research/39_2p_cycle7",
             "q1": "research/40_2q_fullprecision", "q2": "research/41_2q_cycle2",
             "q3": "research/42_2q_replication", "q4": "research/47_2q_canary2", "q5": "research/48_2q_canary_control",
             "r1": "research/43_2r_workload", "r2": "research/44_2r_cycle2",
             "r3": "research/45_2r_cycle3", "r4": "research/46_2r_cycle4",
             "s1": "research/47_2s_pipeline"}

P1_TRANSFORMS = {
    # Measured in the baseline ISA (gfx1030, RGA): FSchlick's pow(x, 5.0) is emitted as
    # v_log_f32 + v_mul_f32 by 5.0 + v_exp_f32 - two quarter-rate transcendentals - in all three
    # light loops. Neither DXC nor the AMD backend strength-reduces it.
    "fresnel5": dict(
        kind="alu_only",
        edits=[(LIGHTING,
                b"    float fresnel = pow(1.0 - saturate(dot(lightDir, halfVec)), 5.0);",
                b"    float f1 = 1.0 - saturate(dot(lightDir, halfVec));\n"
                b"    float f2 = f1 * f1;\n"
                b"    float fresnel = f2 * f2 * f1;")],
        equivalence="x^5 by repeated multiplication instead of exp2(5*log2(x)). Mathematically "
                    "identical, including at x = 0 (log2(0) = -inf, exp2(-inf) = 0). Not "
                    "bit-identical: the multiply form is the more accurate of the two, so the "
                    "image is compared with a tolerance, not by hash.",
        texture_work="unchanged by construction - no sample, load or address is touched"),

    # ApplyConeShadowedLight computes shadow, then multiplies it by ApplyConeLight, which returns
    # zero whenever the cone or distance falloff is zero. Doing the falloff first and sampling
    # only when the result can matter is exactly equivalent (0 * shadow == 0 for finite shadow)
    # and skips the 4x4 matrix load, the matrix multiply, the rcp and the shadow-map sample.
    "shadowskip": dict(
        kind="texture_and_alu",
        edits=[
            # 1. compute the lit contribution first ...
            (LIGHTING,
             b"    float4 shadowCoord = mul(shadowTextureMatrix, float4(worldPos, 1.0));\n"
             b"    shadowCoord.xyz *= rcp(shadowCoord.w);\n"
             b"    float shadow = GetShadowConeLight(lightIndex, shadowCoord.xyz);\n"
             b"\n"
             b"    return shadow * ApplyConeLight(\n",
             b"    float3 lit = ApplyConeLight(\n"),
            # 2. ... then sample the shadow map only where that contribution can matter.
            (LIGHTING,
             b"        coneAngles\n        );\n}\n",
             b"        coneAngles\n        );\n"
             b"\n"
             b"    if (!any(lit != 0.0))\n"
             b"        return 0.0;\n"
             b"\n"
             b"    float4 shadowCoord = mul(shadowTextureMatrix, float4(worldPos, 1.0));\n"
             b"    shadowCoord.xyz *= rcp(shadowCoord.w);\n"
             b"    return GetShadowConeLight(lightIndex, shadowCoord.xyz) * lit;\n}\n"),
        ],
        equivalence="the original returns shadow * lit. When lit is exactly zero the product is "
                    "zero for any finite shadow, and GetShadowConeLight returns the square of a "
                    "SampleCmpLevelZero result, which is finite and non-negative; when lit is "
                    "non-zero the identical product is computed, and float multiplication is "
                    "commutative and exact. So the surviving path is bit-identical and the "
                    "skipped path returns the value it would have produced.",
        texture_work="reduced, data-dependently: the four matrix loads, the matrix multiply, the "
                     "rcp and the shadow-map sample are skipped for lights whose cone or "
                     "distance falloff is zero at that pixel. The dose is measured, not assumed."),
}

# Cycle P2: the same "do not pay for a contribution that is exactly zero" idea, one and two
# levels further up the call chain, plus the stack of P1's two accepted transformations, whose
# additivity has to be measured rather than assumed.
FALLOFF_POINT = (LIGHTING,
                 b"    return distanceFalloff * ApplyLightCommon(\n",
                 b"    if (distanceFalloff == 0.0)\n"
                 b"        return 0.0;\n"
                 b"\n"
                 b"    return distanceFalloff * ApplyLightCommon(\n")
FALLOFF_CONE = (LIGHTING,
                b"    return (coneFalloff * distanceFalloff) * ApplyLightCommon(\n",
                b"    float atten = coneFalloff * distanceFalloff;\n"
                b"    if (atten == 0.0)\n"
                b"        return 0.0;\n"
                b"\n"
                b"    return atten * ApplyLightCommon(\n")
NDOTL = (LIGHTING,
         b"    float3 halfVec = normalize(lightDir - viewDir);\n"
         b"    float nDotH = saturate(dot(halfVec, normal));\n"
         b"\n"
         b"    FSchlick( diffuseColor, specularColor, lightDir, halfVec );\n"
         b"\n"
         b"    float specularFactor = specularMask * pow(nDotH, gloss) * (gloss + 2) / 8;\n"
         b"\n"
         b"    float nDotL = saturate(dot(normal, lightDir));\n"
         b"\n"
         b"    return nDotL * lightColor * (diffuseColor + specularFactor * specularColor);\n",
         b"    float nDotL = saturate(dot(normal, lightDir));\n"
         b"    if (nDotL == 0.0)\n"
         b"        return 0.0;\n"
         b"\n"
         b"    float3 halfVec = normalize(lightDir - viewDir);\n"
         b"    float nDotH = saturate(dot(halfVec, normal));\n"
         b"\n"
         b"    FSchlick( diffuseColor, specularColor, lightDir, halfVec );\n"
         b"\n"
         b"    float specularFactor = specularMask * pow(nDotH, gloss) * (gloss + 2) / 8;\n"
         b"\n"
         b"    return nDotL * lightColor * (diffuseColor + specularFactor * specularColor);\n")

P2_TRANSFORMS = {
    "combo": dict(
        kind="alu_and_texture",
        edits=P1_TRANSFORMS["fresnel5"]["edits"] + P1_TRANSFORMS["shadowskip"]["edits"],
        equivalence="the two P1 transformations applied together; each is argued and measured "
                    "separately in cycle P1. Their combined effect is measured here, never "
                    "assumed to be the sum.",
        texture_work="as shadowskip"),

    "falloffskip": dict(
        kind="alu_only_dynamic",
        edits=[FALLOFF_POINT, FALLOFF_CONE],
        equivalence="ApplyPointLight returns distanceFalloff * ApplyLightCommon(...) and "
                    "ApplyConeLight returns (coneFalloff * distanceFalloff) * "
                    "ApplyLightCommon(...). When that scalar factor is exactly zero the product "
                    "is zero for any finite ApplyLightCommon result, and every term in it is "
                    "finite: nDotH and nDotL are saturated into [0,1], pow(x, gloss) with "
                    "x in [0,1] and gloss > 0 is in [0,1], and the albedo and light colours come "
                    "from textures and the light buffer. max(0, ...) also normalises -0 to +0, "
                    "so the comparison is exact. The non-zero path is untouched.",
        texture_work="unchanged: no sample or load is skipped, only arithmetic. The shadow-map "
                     "sample of the shadowed-cone path happens before this point in the "
                     "unmodified code, so this transformation cannot reach it."),

    "ndotlskip": dict(
        kind="alu_only_dynamic",
        edits=[NDOTL],
        equivalence="ApplyLightCommon returns nDotL * lightColor * (...). nDotL is a saturated "
                    "dot product, so it is exactly zero for every light at or behind the "
                    "surface, and the product is then zero for any finite right-hand side. "
                    "Computing nDotL first and returning early skips the half-vector normalise, "
                    "both pow() calls and the Fresnel term for those lights. The surviving path "
                    "computes exactly the same expression in the same order.",
        texture_work="unchanged: arithmetic only"),
}

# Cycle P3: stack what P1 and P2 accepted, and re-judge ndotlskip under a correctness rule that
# a non-bit-identical image can actually pass. P2's rule (max relative channel error <= 1e-3) is
# unreachable in R11G11B10, whose ULP is about 1/64 = 1.6 % relative: it could only ever pass a
# byte-identical image. The rule below is preregistered here, before P3 measures anything, and
# P2's verdicts are left exactly as they were recorded.
P3_TRANSFORMS = {
    "stack3": dict(
        kind="alu_and_texture",
        edits=(P1_TRANSFORMS["fresnel5"]["edits"] + P1_TRANSFORMS["shadowskip"]["edits"]
               + P2_TRANSFORMS["falloffskip"]["edits"]),
        equivalence="the three transformations accepted in P1 and P2, applied together. Each is "
                    "argued and measured on its own in its own cycle; the stack's effect is "
                    "measured here and never assumed to be the sum.",
        texture_work="as shadowskip plus the light-colour load the compiler sinks behind "
                     "falloffskip's branch"),
    "stack4": dict(
        kind="alu_and_texture",
        edits=(P1_TRANSFORMS["fresnel5"]["edits"] + P1_TRANSFORMS["shadowskip"]["edits"]
               + P2_TRANSFORMS["falloffskip"]["edits"] + P2_TRANSFORMS["ndotlskip"]["edits"]),
        equivalence="stack3 plus ndotlskip, whose own P2 image differed from the baseline by "
                    "exactly one ULP on 2 of 2,073,600 pixels. Judged here under the ULP rule.",
        texture_work="as stack3"),
}

# Cycle P4: does the win survive a different light density, and what does it do to the whole
# frame? The light-count lever is cycle O6's, in C++ data only, and is a DIAGNOSTIC regime
# change, not an optimisation: fewer lights is a different image, so the L32 arms are compared
# against the L32 baseline and never against the L128 one.
LIGHTMGR = "MiniEngine/Model/LightManager.cpp"
L32_EDIT = (LIGHTMGR,
            b"        std::memcpy(m_LightData[n].shadowTextureMatrix, &shadowTextureMatrix, "
            b"sizeof(shadowTextureMatrix));",
            b"        std::memcpy(m_LightData[n].shadowTextureMatrix, &shadowTextureMatrix, "
            b"sizeof(shadowTextureMatrix));\n"
            b"        if (n % 4 != 0) m_LightData[n].radiusSq = 0.0f;")

P4_TRANSFORMS = {
    "stack3": dict(kind="alu_and_texture", edits=P3_TRANSFORMS["stack3"]["edits"],
                   equivalence=P3_TRANSFORMS["stack3"]["equivalence"],
                   texture_work=P3_TRANSFORMS["stack3"]["texture_work"]),
    "base_l32": dict(kind="regime_only", edits=[L32_EDIT],
                     equivalence="not a transformation of the shader at all: the unmodified "
                                 "shader with one quarter of the lights surviving tile culling. "
                                 "It is the BASELINE of the sparse regime.",
                     texture_work="fewer lights, so less of everything - by design"),
    "stack3_l32": dict(kind="alu_and_texture_in_sparse_regime",
                       edits=P3_TRANSFORMS["stack3"]["edits"] + [L32_EDIT],
                       equivalence="stack3 applied in the sparse-light regime; judged against "
                                   "base_l32, whose image it must match.",
                       texture_work="as stack3"),
}

# Cycle P5: separate "less work" from "more waves in flight". Every accepted variant also
# lowers VGPR use (61 -> 55 for stack3), which on RDNA2 raises the theoretical wave occupancy,
# so the P2/P3 review is right that the two are not separated. This cycle adds a control that
# keeps stack3's arithmetic exactly and pushes the register allocation back up: N float4 values
# are computed before the light loops, kept live across them, and consumed under a condition
# that is false at runtime but opaque to the compiler (FrameIndexMod2 is 0 or 1, never 2).
# The output is therefore unchanged, and the only thing that moves is register pressure.
PAD_HEAD = "    uint lightBitMaskGroups[4] = { 0, 0, 0, 0 };\n"
PAD_TAIL = ("        colorSum += ApplyConeShadowedLight(SHADOWED_LIGHT_ARGS);\n"
            "    }\n#endif\n}\n")


def pad_edits(n):
    decl = "".join(
        f"    float4 vgprPad{i} = float4(worldPos, gloss) * (float)(FrameIndexMod2 + {i + 2});\n"
        for i in range(n))
    sink = " + ".join(f"vgprPad{i}.xyz * vgprPad{i}.www" for i in range(n))
    return [(LIGHTING, PAD_HEAD.encode(), (PAD_HEAD + decl).encode()),
            (LIGHTING, PAD_TAIL.encode(),
             ("        colorSum += ApplyConeShadowedLight(SHADOWED_LIGHT_ARGS);\n"
              "    }\n#endif\n"
              "    if (FrameIndexMod2 == 2)     // never true at runtime, opaque to the compiler\n"
              f"        colorSum += {sink};\n"
              "}\n").encode())]


P5_TRANSFORMS = {
    "stack3": dict(kind="alu_and_texture", edits=P3_TRANSFORMS["stack3"]["edits"],
                   equivalence=P3_TRANSFORMS["stack3"]["equivalence"],
                   texture_work=P3_TRANSFORMS["stack3"]["texture_work"]),
    "stack3_pad": dict(
        kind="occupancy_control",
        edits=P3_TRANSFORMS["stack3"]["edits"] + pad_edits(3),
        equivalence="stack3 plus dead-at-runtime padding. The padded values are consumed only "
                    "under `FrameIndexMod2 == 2`, and that constant is 0 or 1 in every frame, so "
                    "the branch is never taken and the output is stack3's output. The compiler "
                    "cannot prove it, so the values stay live and the register allocation rises.",
        texture_work="unchanged relative to stack3"),
    "base_pad": dict(
        kind="occupancy_control",
        edits=pad_edits(3),
        equivalence="the unmodified shader plus the same dead-at-runtime padding, to show what "
                    "the padding alone costs.",
        texture_work="unchanged relative to base"),
}

# Cycle P6: MiniEngine ships an alternative light-iteration path behind `#if 0 // SM6.0`, using
# wave intrinsics. SCALAR_BRANCH is the variant that keeps the original three loops and their
# order intact and only asks, per wave, whether every lane shares the same tile; when they do,
# the tile offset becomes wave-uniform and the light data can be fetched into scalar registers.
# Same lights, same arithmetic, same accumulation order - so the image must not change.
WAVE_ON = (LIGHTING,
           b"#if 0 // SM6.0\n#define _WAVE_OP\n#endif\n",
           b"#if 1 // SM6.0\n#define _WAVE_OP\n#endif\n")
WAVE_SCALAR = (LIGHTING,
               b"//# define BIT_MASK\n# define BIT_MASK_SORTED\n//# define SCALAR_LOOP\n"
               b"//# define SCALAR_BRANCH\n",
               b"//# define BIT_MASK\n//# define BIT_MASK_SORTED\n//# define SCALAR_LOOP\n"
               b"# define SCALAR_BRANCH\n")

P6_TRANSFORMS = {
    "scalar": dict(
        kind="wave_scalarisation",
        edits=[WAVE_ON, WAVE_SCALAR],
        equivalence="the engine's own SCALAR_BRANCH path. It runs the same three loops over the "
                    "same tile light list in the same order; the only difference is that when "
                    "every lane of a wave shares a tile - which a wave covering an 8x8 pixel "
                    "block inside a 16x16 tile usually does - the tile offset is read once with "
                    "WaveReadLaneFirst and the loop becomes uniform. The divergent case falls "
                    "back to code identical to the original. Accumulation order is unchanged, so "
                    "the image must be bit-identical; if it is not, that is the finding.",
        texture_work="unchanged in count; what changes is whether the loads can be scalar"),
    "stack3_scalar": dict(
        kind="wave_scalarisation_plus_stack",
        edits=P3_TRANSFORMS["stack3"]["edits"] + [WAVE_ON, WAVE_SCALAR],
        equivalence="stack3 and the SCALAR_BRANCH path together.",
        texture_work="as stack3, with the same scalarisation opportunity"),
}

# Cycle P7: final verification of the best candidate, end to end, plus the one variant that
# might still go further at the cost of no longer being bit-identical.
P7_TRANSFORMS = {
    "stack3_scalar": dict(kind="final_candidate",
                          edits=P6_TRANSFORMS["stack3_scalar"]["edits"],
                          equivalence=P6_TRANSFORMS["stack3_scalar"]["equivalence"],
                          texture_work=P6_TRANSFORMS["stack3_scalar"]["texture_work"]),
    "stack4_scalar": dict(kind="final_candidate_not_bit_identical",
                          edits=P6_TRANSFORMS["stack3_scalar"]["edits"] + [NDOTL],
                          equivalence="stack3_scalar plus ndotlskip, which in P2 changed two "
                                      "pixels by one ULP. Judged under the same ULP rule.",
                          texture_work="as stack3_scalar"),
}

# Phase 2Q, cycle Q1: the same variants again, but captured into an R32G32B32A32_FLOAT target
# so the comparison is on the float32 values the shader actually computed, not on a render
# target with six mantissa bits. Each accepted transformation is verified alone, so a failure
# can be attributed to one of them rather than to the stack.
Q1_TRANSFORMS = {
    "fresnel5": P1_TRANSFORMS["fresnel5"],
    "shadowskip": P1_TRANSFORMS["shadowskip"],
    "falloffskip": P2_TRANSFORMS["falloffskip"],
    "ndotlskip": P2_TRANSFORMS["ndotlskip"],
    "scalar": P6_TRANSFORMS["scalar"],
    "stack3_scalar": P7_TRANSFORMS["stack3_scalar"],
    "stack4_scalar": P7_TRANSFORMS["stack4_scalar"],
}

# Phase 2Q, cycle Q2: the data contract, measured instead of argued. The three control-flow
# transformations all rest on "0 x X == 0", which holds when X is finite and non-negative. This
# variant leaves the arithmetic alone and only watches X: if any light at any pixel ever produced
# a NaN, an infinity or a negative value, the pixel is forced to 1e30 and the full-precision
# capture shows it. The baseline maximum is 56.33, so a violation cannot hide.
Q2_TRANSFORMS = {
    "contract_canary": dict(
        kind="contract_probe",
        edits=[
            (LIGHTING,
             b"    return nDotL * lightColor * (diffuseColor + specularFactor * specularColor);\n",
             b"    float3 v = nDotL * lightColor * (diffuseColor + specularFactor * specularColor);\n"
             b"    if (any(isnan(v)) || any(isinf(v)) || any(v < 0.0) ||\n"
             b"        any(isnan(lightColor)) || any(isinf(lightColor)) || any(lightColor < 0.0) ||\n"
             b"        isnan(specularFactor) || isinf(specularFactor) || specularFactor < 0.0)\n"
             b"        v = float3(1e30, 1e30, 1e30);\n"
             b"    return v;\n"),
            (LIGHTING,
             b"    float result = lightShadowArrayTex.SampleCmpLevelZero(\n"
             b"        shadowSampler, float3(shadowCoord.xy, lightIndex), shadowCoord.z);\n"
             b"    return result * result;\n",
             b"    float result = lightShadowArrayTex.SampleCmpLevelZero(\n"
             b"        shadowSampler, float3(shadowCoord.xy, lightIndex), shadowCoord.z);\n"
             b"    float sq = result * result;\n"
             b"    if (isnan(sq) || isinf(sq) || sq < 0.0)\n"
             b"        sq = 1e30;\n"
             b"    return sq;\n"),
            (LIGHTING,
             b"    float shadow = GetShadowConeLight(lightIndex, shadowCoord.xyz);\n",
             b"    float shadow = GetShadowConeLight(lightIndex, shadowCoord.xyz);\n"
             b"    if (!isfinite(shadowCoord.w) || shadowCoord.w == 0.0)\n"
             b"        shadow = 1e30;\n"),
        ],
        equivalence="not a candidate. It computes exactly what the baseline computes and only "
                    "adds a detector: every value the early-out transformations assume to be "
                    "finite and non-negative is checked, and a violation is turned into 1e30. "
                    "The verdict is read from the maximum of the full-precision capture.",
        texture_work="unchanged"),
}

# Phase 2Q, cycle Q3: the final performance replication, on the stack that survived the
# full-precision correctness work, in a fresh cycle with its own baseline and more processes.
Q3_TRANSFORMS = {
    "stack3_scalar": P7_TRANSFORMS["stack3_scalar"],
    "stack4_scalar": P7_TRANSFORMS["stack4_scalar"],
}

# Cycle Q4: the canary rebuilt out of band, after the reviewer showed v1 could be silenced.
# v1 wrote its sentinel into the value that is then multiplied by zero, so on the very paths the
# early-outs skip (`distanceFalloff == 0`, `lit == 0`) the sentinel became 0 * 1e30 == 0. v2
# threads a violation mask through the call chain: it is set before any multiplication, is never
# multiplied itself, and is applied to colorSum once at the end of ShadeLights. One bit per
# contract, so a firing canary says which assumption failed.
L = LIGHTING
Q4_TRANSFORMS = {
    "canary2": dict(
        kind="contract_probe_v2",
        edits=[
            # a helper, and the violation mask threaded through ApplyLightCommon
            (L,
             b"void FSchlick( inout float3 specular, inout float3 diffuse, float3 lightDir, float3 halfVec )\n",
             b"// Phase 2Q canary v2: one bit per contract the early-outs depend on.\n"
             b"uint CanaryScalar(float x, uint bit)\n"
             b"{\n"
             b"    uint v = 0;\n"
             b"    if (isnan(x) || isinf(x) || x < 0.0) v |= bit;\n"
             b"    if (asuint(x) == 0x80000000u) v |= 64u;\n"
             b"    return v;\n"
             b"}\n"
             b"uint CanaryVector(float3 x, uint bit)\n"
             b"{\n"
             b"    uint v = 0;\n"
             b"    if (any(isnan(x)) || any(isinf(x)) || any(x < 0.0)) v |= bit;\n"
             b"    if (any(asuint(x) == 0x80000000u)) v |= 64u;\n"
             b"    return v;\n"
             b"}\n"
             b"\n"
             b"void FSchlick( inout float3 specular, inout float3 diffuse, float3 lightDir, float3 halfVec )\n"),

            (L,
             b"    float3	lightColor		// Radiance of directional light\n"
             b"    )\n"
             b"{\n"
             b"    float3 halfVec = normalize(lightDir - viewDir);\n",
             b"    float3	lightColor,		// Radiance of directional light\n"
             b"    inout uint viol\n"
             b"    )\n"
             b"{\n"
             b"    float3 halfVec = normalize(lightDir - viewDir);\n"),

            # check the right-hand side BEFORE it is multiplied by nDotL, and the result after
            (L,
             b"    return nDotL * lightColor * (diffuseColor + specularFactor * specularColor);\n",
             b"    float3 rhs = lightColor * (diffuseColor + specularFactor * specularColor);\n"
             b"    viol |= CanaryVector(rhs, 1u);\n"
             b"    float3 outv = nDotL * rhs;\n"
             b"    viol |= CanaryVector(outv, 2u);\n"
             b"    return outv;\n"),

            # ApplyDirectionalLight is outside the early-out contract; give it a local sink
            (L,
             b"    float shadow = GetDirectionalShadow(shadowCoord, ShadowMap);\n"
             b"\n"
             b"    return shadow * ApplyLightCommon(\n",
             b"    float shadow = GetDirectionalShadow(shadowCoord, ShadowMap);\n"
             b"    uint directionalViol = 0;   // not part of the early-out contract\n"
             b"\n"
             b"    return shadow * ApplyLightCommon(\n"),
            (L,
             b"        normal,\n"
             b"        viewDir,\n"
             b"        lightDir,\n"
             b"        lightColor\n"
             b"        );\n"
             b"}\n"
             b"\n"
             b"float3 ApplyPointLight(\n",
             b"        normal,\n"
             b"        viewDir,\n"
             b"        lightDir,\n"
             b"        lightColor,\n"
             b"        directionalViol\n"
             b"        );\n"
             b"}\n"
             b"\n"
             b"float3 ApplyPointLight(\n"),

            # ApplyPointLight: check distanceFalloff before it multiplies anything
            (L,
             b"    float3	lightColor		// Radiance of directional light\n"
             b"    )\n"
             b"{\n"
             b"    float3 lightDir = lightPos - worldPos;\n"
             b"    float lightDistSq = dot(lightDir, lightDir);\n"
             b"    float invLightDist = rsqrt(lightDistSq);\n"
             b"    lightDir *= invLightDist;\n"
             b"\n"
             b"    // modify 1/d^2 * R^2 to fall off at a fixed radius\n"
             b"    // (R/d)^2 - d/R = [(1/d^2) - (1/R^2)*(d/R)] * R^2\n"
             b"    float distanceFalloff = lightRadiusSq * (invLightDist * invLightDist);\n"
             b"    distanceFalloff = max(0, distanceFalloff - rsqrt(distanceFalloff));\n"
             b"\n"
             b"    return distanceFalloff * ApplyLightCommon(\n",
             b"    float3	lightColor,		// Radiance of directional light\n"
             b"    inout uint viol\n"
             b"    )\n"
             b"{\n"
             b"    float3 lightDir = lightPos - worldPos;\n"
             b"    float lightDistSq = dot(lightDir, lightDir);\n"
             b"    float invLightDist = rsqrt(lightDistSq);\n"
             b"    lightDir *= invLightDist;\n"
             b"\n"
             b"    float distanceFalloff = lightRadiusSq * (invLightDist * invLightDist);\n"
             b"    distanceFalloff = max(0, distanceFalloff - rsqrt(distanceFalloff));\n"
             b"    viol |= CanaryScalar(distanceFalloff, 4u);\n"
             b"\n"
             b"    return distanceFalloff * ApplyLightCommon(\n"),

            # ApplyConeLight: same, plus the cone factor and the product
            (L,
             b"    float3	coneDir,\n"
             b"    float2	coneAngles\n"
             b"    )\n"
             b"{\n",
             b"    float3	coneDir,\n"
             b"    float2	coneAngles,\n"
             b"    inout uint viol\n"
             b"    )\n"
             b"{\n"),
            (L,
             b"    float coneFalloff = dot(-lightDir, coneDir);\n"
             b"    coneFalloff = saturate((coneFalloff - coneAngles.y) * coneAngles.x);\n"
             b"\n"
             b"    return (coneFalloff * distanceFalloff) * ApplyLightCommon(\n",
             b"    float coneFalloff = dot(-lightDir, coneDir);\n"
             b"    coneFalloff = saturate((coneFalloff - coneAngles.y) * coneAngles.x);\n"
             b"    viol |= CanaryScalar(distanceFalloff, 4u);\n"
             b"    viol |= CanaryScalar(coneFalloff, 8u);\n"
             b"    viol |= CanaryScalar(coneFalloff * distanceFalloff, 8u);\n"
             b"\n"
             b"    return (coneFalloff * distanceFalloff) * ApplyLightCommon(\n"),

            # ApplyConeShadowedLight: the shadow term and shadowCoord.w
            (L,
             b"    float4x4 shadowTextureMatrix,\n"
             b"    uint	lightIndex\n"
             b"    )\n"
             b"{\n"
             b"    float4 shadowCoord = mul(shadowTextureMatrix, float4(worldPos, 1.0));\n"
             b"    shadowCoord.xyz *= rcp(shadowCoord.w);\n"
             b"    float shadow = GetShadowConeLight(lightIndex, shadowCoord.xyz);\n",
             b"    float4x4 shadowTextureMatrix,\n"
             b"    uint	lightIndex,\n"
             b"    inout uint viol\n"
             b"    )\n"
             b"{\n"
             b"    float4 shadowCoord = mul(shadowTextureMatrix, float4(worldPos, 1.0));\n"
             b"    if (isnan(shadowCoord.w) || isinf(shadowCoord.w) || shadowCoord.w == 0.0)\n"
             b"        viol |= 32u;\n"
             b"    shadowCoord.xyz *= rcp(shadowCoord.w);\n"
             b"    float shadow = GetShadowConeLight(lightIndex, shadowCoord.xyz);\n"
             b"    viol |= CanaryScalar(shadow, 16u);\n"),

            # the argument macros carry the flag to every call site
            (L, b"    lightData.color\n", b"    lightData.color, \\\n    viol\n"),
            (L, b"#define CONE_LIGHT_ARGS \\\n    POINT_LIGHT_ARGS, \\\n"
                b"    lightData.coneDir, \\\n    lightData.coneAngles\n",
                b"#define CONE_LIGHT_ARGS \\\n    diffuseAlbedo, \\\n    specularAlbedo, \\\n"
                b"    specularMask, \\\n    gloss, \\\n    normal, \\\n    viewDir, \\\n"
                b"    worldPos, \\\n    lightData.pos, \\\n    lightData.radiusSq, \\\n"
                b"    lightData.color, \\\n    lightData.coneDir, \\\n"
                b"    lightData.coneAngles, \\\n    viol\n"),
            (L, b"#define SHADOWED_LIGHT_ARGS \\\n    CONE_LIGHT_ARGS, \\\n"
                b"    lightData.shadowTextureMatrix, \\\n    lightIndex\n",
                b"#define SHADOWED_LIGHT_ARGS \\\n    diffuseAlbedo, \\\n    specularAlbedo, \\\n"
                b"    specularMask, \\\n    gloss, \\\n    normal, \\\n    viewDir, \\\n"
                b"    worldPos, \\\n    lightData.pos, \\\n    lightData.radiusSq, \\\n"
                b"    lightData.color, \\\n    lightData.coneDir, \\\n"
                b"    lightData.coneAngles, \\\n    lightData.shadowTextureMatrix, \\\n"
                b"    lightIndex, \\\n    viol\n"),

            # the three internal call sites have to carry the flag too
            (L,
             b"        lightDir,\n"
             b"        lightColor\n"
             b"        );\n"
             b"}\n"
             b"\n"
             b"float3 ApplyConeLight(\n",
             b"        lightDir,\n"
             b"        lightColor,\n"
             b"        viol\n"
             b"        );\n"
             b"}\n"
             b"\n"
             b"float3 ApplyConeLight(\n"),
            (L,
             b"        lightDir,\n"
             b"        lightColor\n"
             b"        );\n"
             b"}\n"
             b"\n"
             b"float3 ApplyConeShadowedLight(\n",
             b"        lightDir,\n"
             b"        lightColor,\n"
             b"        viol\n"
             b"        );\n"
             b"}\n"
             b"\n"
             b"float3 ApplyConeShadowedLight(\n"),
            (L,
             b"        coneDir,\n"
             b"        coneAngles\n"
             b"        );\n"
             b"}\n",
             b"        coneDir,\n"
             b"        coneAngles,\n"
             b"        viol\n"
             b"        );\n"
             b"}\n"),

            # declare the mask, and apply it once at the end, out of band
            (L,
             b"    uint lightBitMaskGroups[4] = { 0, 0, 0, 0 };\n",
             b"    uint viol = 0;\n"
             b"    uint lightBitMaskGroups[4] = { 0, 0, 0, 0 };\n"),
            (L,
             b"        colorSum += ApplyConeShadowedLight(SHADOWED_LIGHT_ARGS);\n"
             b"    }\n#endif\n}\n",
             b"        colorSum += ApplyConeShadowedLight(SHADOWED_LIGHT_ARGS);\n"
             b"    }\n#endif\n"
             b"    // Out of band: the mask is never multiplied by anything, so a violation on a\n"
             b"    // path an early-out would skip cannot be silenced by a zero factor.\n"
             b"    if (viol != 0)\n"
             b"        colorSum = float3(1e30, (float)viol, 1e30);\n"
             b"}\n"),
        ],
        equivalence="not a candidate. It computes what the baseline computes and adds a violation "
                    "mask that is set before any multiplication and applied to colorSum once, "
                    "after every light. The green channel carries the mask, so a firing canary "
                    "identifies which contract failed.",
        texture_work="unchanged"),
}

# Cycle Q5: the positive control the v1 canary never had. Same detector as canary2, but the
# scalar check is made to fire on every finite value. If the capture does not light up, "the
# canary never fired" would mean "the canary cannot fire" - which is exactly how v1 failed.
Q5_TRANSFORMS = {
    "canary2_positive": dict(
        kind="contract_probe_positive_control",
        edits=Q4_TRANSFORMS["canary2"]["edits"] + [
            (LIGHTING,
             b"    if (isnan(x) || isinf(x) || x < 0.0) v |= bit;\n",
             b"    if (isnan(x) || isinf(x) || x < 0.0 || x >= 0.0) v |= bit;   // positive control\n"),
        ],
        equivalence="not a candidate and not equivalent: it deliberately reports a violation for "
                    "every finite value, to prove the detector can reach the capture at all.",
        texture_work="unchanged"),
}

CYCLES = {"p1": P1_TRANSFORMS, "p2": P2_TRANSFORMS, "p3": P3_TRANSFORMS, "p4": P4_TRANSFORMS,
          "p5": P5_TRANSFORMS, "p6": P6_TRANSFORMS, "p7": P7_TRANSFORMS, "q1": Q1_TRANSFORMS,
          "q2": Q2_TRANSFORMS, "q3": Q3_TRANSFORMS,
          "q4": Q4_TRANSFORMS, "q5": Q5_TRANSFORMS}

# Correctness rule per cycle. Recorded in each manifest at prepare time and applied at analysis,
# so a rule written for a later cycle can never retroactively change an earlier verdict.
CORRECTNESS_RULE = {"p1": "max_rel_1e-3", "p2": "max_rel_1e-3"}
# P4 compares two regimes, so each arm is judged against the baseline of its own
# regime; the pairing is set in analyse() by BASELINE_OF.
BASELINE_OF = {"p4": {"stack3": "base", "stack3_l32": "base_l32",
                      "base_l32": "base"}}
DEFAULT_RULE = "ulp1_0.05pct"
RULE_TEXT = {
    "max_rel_1e-3": "maximum relative channel error <= 1e-3 and no non-finite channel",
    "ulp1_0.05pct": "every differing channel differs by at most 1 ULP of its stored "
                    "R11G11B10 representation, at most 0.05 % of channels differ at all, and no "
                    "channel is non-finite. One ULP is the smallest change this render target can "
                    "represent, so this admits a different rounding and nothing more.",
}
TRANSFORMS = P1_TRANSFORMS
VARIANTS = ["base"] + sorted(TRANSFORMS)


def select(cycle):
    """Point the module at one cycle's transform set and output directory."""
    global CYCLE, OUT, TRANSFORMS, VARIANTS
    G.require(cycle in CYCLES, f"unknown cycle {cycle}")
    CYCLE, OUT = cycle, ROOT / CYCLE_DIR[cycle]
    TRANSFORMS = CYCLES[cycle]
    VARIANTS = ["base"] + sorted(TRANSFORMS)

CRITERIA = dict(
    principle="no transformation is accepted on fewer instructions, fewer VGPRs, smaller DXIL, "
              "shorter ISA or a microbenchmark. The judge is Render Color in the real workload.",
    quality="image quality must not be reduced. No variant may remove a light, a PCF tap, a "
            "texture, a mip level or precision. Every transformation here is an algebraic or "
            "control-flow rewrite that computes the same thing.",
    correctness="the captured Render Color image (R11G11B10, 1920x1080, frame 140) is compared "
                "against the base build's image. The rule that decides is the `correctness_rule` "
                "field of this manifest and nothing else. Baseline-vs-baseline is measured "
                "first, from two independent processes, to establish that the capture is "
                "deterministic before any variant is judged against it.",
    performance="paired against `base`, AT LEAST 3 and preferably 5 independent processes per "
                "variant, order counterbalanced. Primary outcome GPUBusyCycles of the Render "
                "Color sample; GPUTime reported but not decisive (2O measured its N95 at "
                "1.3-14 %). A variant is ACCEPTED only if the median delta is <= -max(1.0 %, "
                "3 x N95) with N95 from the base A/A control measured in this cycle, AND every "
                "paired process delta is negative, AND correctness passes. N95 here is the "
                "largest of the pairwise differences between the base processes, not a "
                "statistical percentile, and those pairs are not independent of each other.",
    counters="SQ_PS INSTS_VALU / INST_CYCLES_VALU (the ALU dose) and TA_BUSY + TCP (the texture "
             "dose) are measured for every variant, so what moved is known rather than guessed.",
    alu_vs_texture="`fresnel5` changes ALU work only, with the texture instruction count fixed "
                   "by construction. It is therefore the mirror of cycle O4, which changed "
                   "texture work at fixed ALU. Together they can rank the two saturated units - "
                   "the question 2O could not answer.",
    thresholds_fixed_before="yes - written into this manifest by prepare, before any build.")


def variant_source(label, work=None):
    """Bytes of every file this variant edits: {relative path: patched bytes}.

    Anchors are written with LF; the shader sources are CRLF, so both sides of every edit are
    translated into the file's own line ending before matching."""
    root = work or O1.ORIGINAL
    out = {}
    if label == "base":
        return out
    for rel, old, new in TRANSFORMS[label]["edits"]:
        src = out.get(rel) or (root / rel).read_bytes()
        if b"\r\n" in src:
            old = old.replace(b"\n", b"\r\n")
            new = new.replace(b"\n", b"\r\n")
        G.require(src.count(old) == 1, f"{label}: anchor not unique in {rel}")
        out[rel] = src.replace(old, new)
    return out


def precompile_variants(stage):
    """Preregister the exact bytecode each variant must produce, before any build runs."""
    shaders = (O1.ORIGINAL / O1.PS_REL).parent
    out = {}
    for label in VARIANTS:
        d = stage / label
        shutil.copytree(shaders, d / "Shaders")
        for rel, data in variant_source(label).items():
            (d / "Shaders" / Path(rel).name).write_bytes(data)
        (d / "Output/Model/CompiledShaders").mkdir(parents=True)
        G.run_checked([O1.DXC, "-nologo", "-E", "main", "-T", "ps_6_2", "-D", "_GAMING_DESKTOP=1",
                       "-Fh", d / "Output/Model/CompiledShaders/ModelViewerPS.h",
                       "-Vn", "g_pModelViewerPS", "-HV", "2021", d / "Shaders/ModelViewerPS.hlsl"],
                      d / "Shaders", stage / f"dxc_{label}.log", timeout=180)
        out[label] = G.shader_artifact(d)
    G.require(out["base"]["custom_hash"] == "52CE6C5E64AB2E82",
              "base is not the shader O1/O2 verified")
    # A transformation that compiles to the baseline bytecode is a finding, not an error: it
    # means DXC already performs it. Recorded rather than aborted on.
    same = [k for k in TRANSFORMS
            if out[k]["bytecode_sha256"] == out["base"]["bytecode_sha256"]]
    return out, same


def prepare(reuse_from=None):
    """`reuse_from` is a previous 2P cycle's directory. Its workspace is reused instead of
    copying three gigabytes again; every instrumented source is re-verified against that
    cycle's recorded hashes first, so the build inputs are provably the same tree."""
    OUT.mkdir(exist_ok=False)
    eid = "P_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    if reuse_from:
        prev = ROOT / reuse_from
        pm = json.loads((prev / "experiment_manifest.json").read_text())
        work = Path(pm["workspace"]).resolve(strict=True)
        with (prev / "instrumented_source_hashes.csv").open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                G.require(G.sha(row["path"]) == row["sha256"],
                          f"reused workspace has drifted: {row['path']}")
        for name in ("input_hashes.csv", "instrumented_source_hashes.csv", "Build.props.before"):
            if (prev / name).exists():
                shutil.copy2(prev / name, OUT / name)
        shutil.copytree(prev / "baseline_sources", OUT / "baseline_sources")
        # This cycle may patch a file no earlier cycle touched: take its pristine copy from the
        # workspace, and require it to be byte-identical to the untouched clone first.
        for rel in sorted({r for t in TRANSFORMS.values() for r, _, _ in t["edits"]}):
            here = OUT / "baseline_sources" / Path(rel).name
            if not here.exists():
                G.require((work / rel).read_bytes() == (O1.ORIGINAL / rel).read_bytes(),
                          f"workspace copy of {rel} is not the pristine source")
                here.write_bytes((work / rel).read_bytes())
    else:
        work = Path(os.environ["TEMP"]) / "claude" / eid
        work.mkdir(exist_ok=False)
    expected, already_done = precompile_variants(OUT / "preregistered")
    (OUT / "sets").mkdir()
    (OUT / "sets/resp.txt").write_text("\n".join(sorted(set(
        [f"TA{i}_PERF_SEL_TA_BUSY" for i in range(80)] + ["GPUTime", "GPUBusyCycles"]))) + "\n",
        encoding="utf-8")
    (OUT / "sets/sq_ps.txt").write_text("\n".join(sorted(set(O2.sets()["sq_ps"]))) + "\n",
                                        encoding="utf-8")
    (OUT / "sets/tcp_ta.txt").write_bytes((O5.OUT / "sets/tcp_ta.txt").read_bytes())

    G.save_json(OUT / "experiment_manifest.json", dict(
        experiment_id=eid, created_at=datetime.now().astimezone().isoformat(), phase="2P",
        workspace=str(work), workspace_owner_experiment_id=work.name,
        inherits_workspace_from=reuse_from,
        original_source=str(O1.ORIGINAL), dxc_selected=str(O1.DXC),
        configuration="Profile/x64/v145", first_frame=FIRST_FRAME,
        patched_files=sorted({rel for t in TRANSFORMS.values() for rel, _, _ in t["edits"]}),
        transforms={k: {kk: vv for kk, vv in v.items() if kk != "edits"}
                    for k, v in TRANSFORMS.items()},
        transform_edits={k: [[rel, old.decode(), new.decode()] for rel, old, new in v["edits"]]
                         for k, v in TRANSFORMS.items()},
        expected_bytecode={k: v["bytecode_sha256"] for k, v in expected.items()},
        expected_artifact=expected,
        compiler_already_does=already_done,
        ablation_kind="optimisation candidates - semantics preserving, image quality unchanged",
        preregistered_criteria=dict(CRITERIA,
                                    correctness_rule=CORRECTNESS_RULE.get(CYCLE, DEFAULT_RULE),
                                    correctness_rule_text=RULE_TEXT[
                                        CORRECTNESS_RULE.get(CYCLE, DEFAULT_RULE)]),
        workspace_budget_bytes=8_000_000_000))

    if reuse_from:
        print("prepared", work, "(workspace inherited from", reuse_from + ") | compiler already "
              "does:", already_done or "none", flush=True)
        return

    with (OUT / "input_hashes.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "copy", "bytes", "sha256"])
        total = 0
        for area in ["MiniEngine", "Packages", "vcpkg", "vcpkg_installed"]:
            for source in sorted((O1.ORIGINAL / area).rglob("*")):
                if not source.is_file() or (area == "MiniEngine" and
                        source.relative_to(O1.ORIGINAL / area).parts[0] == "Build"):
                    continue
                if area == "vcpkg_installed" and any(x in source.parts for x in ["debug", "tools"]):
                    continue
                target = work / source.relative_to(O1.ORIGINAL)
                h = G.sha(source)
                total += source.stat().st_size
                G.require(total < 3_000_000_000, "input copy budget exceeded")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                G.require(G.sha(target) == h, "copy integrity failure")
                w.writerow([str(source), str(target), source.stat().st_size, h])
        shutil.copy2(O1.ORIGINAL / "vcpkg.json", work / "vcpkg.json")
        for p in [ROOT / "tools/buildv.py", ROOT / "tools/run_o1.py", ROOT / "tools/run_o2.py",
                  ROOT / "tools/run_2p.py", ROOT / "tools/o1_probe.h", ROOT / "tools/o2_gpa.h"]:
            w.writerow([str(p), "", p.stat().st_size, G.sha(p)])

    O1.instrument(work, OUT, o2=True)
    O1.finish_prepare(work, OUT)
    (OUT / "baseline_sources").mkdir()
    for rel in sorted({rel for t in TRANSFORMS.values() for rel, _, _ in t["edits"]}):
        (OUT / "baseline_sources" / Path(rel).name).write_bytes((work / rel).read_bytes())
    shutil.copy2(Path(os.environ["TEMP"]) / "claude/gpa/4_4/bin/GPUPerfAPIDX12-x64.dll",
                 work / "MiniEngine/ModelViewer/GPUPerfAPIDX12-x64.dll")
    print("prepared", work, "| compiler already does:", already_done or "none", flush=True)


def manifest():
    return json.loads((OUT / "experiment_manifest.json").read_text())


def _restore(work, m):
    for rel in m["patched_files"]:
        base = (OUT / "baseline_sources" / Path(rel).name).read_bytes()
        (work / rel).write_bytes(base)
        G.require((work / rel).read_bytes() == base, f"baseline restoration failed: {rel}")


def build(label):
    m = manifest()
    G.require(label in VARIANTS, f"unknown variant {label}")
    work = Path(m["workspace"]).resolve(strict=True)
    # The workspace may be inherited from an earlier 2P cycle, so it is identified by the
    # experiment that created it, which the manifest records. It must still be one of this
    # project's own copies under TEMP/claude and never the pristine clone.
    G.require(work.name == m.get("workspace_owner_experiment_id", m["experiment_id"])
              and work.parent == (Path(os.environ["TEMP"]) / "claude").resolve()
              and O1.ORIGINAL.resolve() not in [work, *work.parents],
              "workspace path is not a workspace this phase created")
    _restore(work, m)
    patched = {str(work / rel) for rel in m["patched_files"]}
    with (OUT / "instrumented_source_hashes.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["path"] not in patched:
                G.require(G.sha(row["path"]) == row["sha256"],
                          f"instrumented source changed since prepare: {row['path']}")
    try:
        for rel, data in variant_source(label, work).items():
            (work / rel).write_bytes(data)
            snap = OUT / "source_revisions" / f"{label}_{Path(rel).name}"
            snap.parent.mkdir(exist_ok=True)
            if snap.exists():
                G.require(snap.read_bytes() == data, "variant source changed since first build")
            else:
                snap.write_bytes(data)
        attempt = 1
        while (work / "build" / f"{label}.{attempt}").exists() or \
              (OUT / "build_logs" / f"{label}.{attempt}").exists():
            attempt += 1
        artifact = G.build(work / "MiniEngine", work / "build" / f"{label}.{attempt}",
                           OUT / "build_logs" / f"{label}.{attempt}", Path(m["dxc_selected"]),
                           expected=m["expected_bytecode"][label])
        G.save_json(OUT / f"build_{label}.json", artifact)
        print(f"{label}: bytecode {artifact['custom_hash']} ({artifact['bytecode_bytes']} B), "
              f"exe {artifact['executable_sha256'][:12]}", flush=True)
    finally:
        _restore(work, m)


def _checked_exe(label):
    m = manifest()
    a = json.loads((OUT / f"build_{label}.json").read_text())
    G.require(G.sha(a["executable"]) == a["executable_sha256"],
              "executable changed since the verified build")
    G.require(a["bytecode_sha256"] == m["expected_bytecode"][label],
              "artifact is not this variant's preregistered bytecode")
    return m, a


def run(label, setname, samples, rep):
    m, a = _checked_exe(label)
    setfile = OUT / "sets" / f"{setname}.txt"
    G.require(setfile.is_file(), f"unknown set {setname}")
    folder = OUT / "runs" / f"{label}_{setname}_r{rep}"
    folder.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ME_", "AMD_", "SC_"))}
    env.update(ME_O2_DIR=str(folder), ME_O2_SET=str(setfile),
               ME_O2_FIRST=str(m["first_frame"]), ME_O2_SAMPLES=str(samples))
    proc = G.run_checked([a["executable"]], Path(m["workspace"]) / "MiniEngine/ModelViewer",
                         folder / "process.log", env=env, timeout=900)
    G.require(not (folder / "gpa_failure.txt").exists(), "GPA reported a failure")
    G.require((folder / "gpa_results.csv").is_file(), "no GPA results")
    G.save_json(folder / "run.json", dict(variant=label, set=setname, rep=rep, pid=proc["pid"],
                                          samples=samples,
                                          bytecode_sha256=a["bytecode_sha256"],
                                          executable_sha256=a["executable_sha256"]))
    print(f"{label}_{setname}_r{rep}: ok", flush=True)


def bench(label, rep, frames=1000, warm=300):
    """Whole-frame A/B with MiniEngine's own headless benchmark mode (added in phase 2L):
    warm-up, then N frames with a fixed 1/60 timestep and VSync off, then the GPU timer tree
    exported as CSV. `Render Color` is one row of that tree, the frame total another, so the
    secondary end-to-end metric comes from the same run as the pass metric."""
    m, a = _checked_exe(label)
    folder = OUT / "runs" / f"{label}_bench_r{rep}"
    folder.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ME_", "AMD_", "SC_"))}
    env.update(ME_BENCH_FRAMES=str(frames), ME_BENCH_WARM=str(warm),
               ME_BENCH_CSV=str(folder / "profile.csv"), ME_BENCH_IMG=str(folder / "frame.bin"))
    proc = G.run_checked([a["executable"]], Path(m["workspace"]) / "MiniEngine/ModelViewer",
                         folder / "process.log", env=env, timeout=1800)
    G.require((folder / "profile.csv").is_file(), "no benchmark profile")
    rows = list(csv.DictReader((folder / "profile.csv").open(encoding="utf-8")))
    G.save_json(folder / "bench.json", dict(variant=label, rep=rep, pid=proc["pid"],
                                            frames=frames, warm=warm, scopes=len(rows),
                                            frame_image_sha256=G.sha(folder / "frame.bin")
                                            if (folder / "frame.bin").exists() else None,
                                            bytecode_sha256=a["bytecode_sha256"]))
    tree = {r["scope"]: r for r in rows}
    print(f"{label}_bench_r{rep}: frame {tree.get('__FRAMES__', {}).get('samples', '?')} frames, "
          f"scopes {len(rows)}", flush=True)


def image(label, rep, r32=False):
    """Capture the Render Color image with the O1 probe, for the correctness gate."""
    m, a = _checked_exe(label)
    folder = OUT / "runs" / f"{label}_{'fp32' if r32 else 'image'}_r{rep}"
    folder.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ME_", "AMD_", "SC_"))}
    env["ME_O1_DIR"] = str(folder)
    if r32:
        env["ME_Q_R32"] = "1"
    proc = G.run_checked([a["executable"]], Path(m["workspace"]) / "MiniEngine/ModelViewer",
                         folder / "process.log", env=env, timeout=600)
    rows = G.verify_runtime(folder / "runtime.csv", a)
    img = json.loads((folder / "image.json").read_text())
    want_fmt, bpp = (2, 16) if r32 else (26, 4)     # DXGI R32G32B32A32_FLOAT = 2, R11G11B10 = 26
    G.require(img["pid"] == proc["pid"] and img["frame_index"] == m["first_frame"]
              and img["dxgi_format"] == want_fmt and img["width"] == 1920 and img["height"] == 1080
              and (folder / "color.bin").stat().st_size == 1920 * 1080 * bpp,
              "image metadata/data mismatch")
    G.save_json(folder / "capture.json", dict(variant=label, rep=rep, pid=proc["pid"],
                                              draws=len(rows), image=img,
                                              image_sha256=G.sha(folder / "color.bin"),
                                              bytecode_sha256=a["bytecode_sha256"]))
    print(f"{folder.name}: {len(rows)} draws, sha {G.sha(folder / 'color.bin')[:12]}", flush=True)


# ------------------------------------------------------------------------------- correctness

def compare_images(a_tag, b_tag):
    import numpy as np
    x, y = [np.fromfile(OUT / "runs" / t / "color.bin", dtype="<u4") for t in (a_tag, b_tag)]
    G.require(x.shape == y.shape == (1920 * 1080,), "image shape mismatch")
    worst_rel, worst_abs, nonfinite = 0.0, 0.0, 0
    worst_ulp, changed_ch, total_ch = 0, 0, 0
    for shift, bits in [(0, 11), (11, 11), (22, 10)]:
        xc = (x >> shift) & ((1 << bits) - 1)
        yc = (y >> shift) & ((1 << bits) - 1)
        nonfinite += int(np.count_nonzero((xc >> (bits - 5)) == 31)
                         + np.count_nonzero((yc >> (bits - 5)) == 31))
        fx, fy = O1.decode(xc, bits), O1.decode(yc, bits)
        d = np.abs(fy - fx)
        worst_abs = max(worst_abs, float(d.max()))
        rel = d / np.maximum(np.abs(fx), 1e-6)
        worst_rel = max(worst_rel, float(rel.max()))
        # ULP distance in the stored representation: for a float11/float10 channel the encoding
        # is monotonic in the unsigned bit pattern, so the integer difference is the ULP count.
        ulp = np.abs(yc.astype(np.int64) - xc.astype(np.int64))
        worst_ulp = max(worst_ulp, int(ulp.max()))
        changed_ch += int(np.count_nonzero(ulp))
        total_ch += ulp.size
    return dict(pair=[a_tag, b_tag], identical=bool(np.array_equal(x, y)),
                changed_pixels=int(np.count_nonzero(x != y)),
                changed_fraction=float(np.mean(x != y)),
                max_abs_error=worst_abs, max_rel_error=worst_rel, nonfinite_channels=nonfinite,
                max_channel_ulp=worst_ulp,
                changed_channel_fraction=changed_ch / total_ch if total_ch else 0.0)


def compare_fp32(a_tag, b_tag):
    """Compare two R32G32B32A32_FLOAT captures on the float32 values themselves.

    ULP distance is computed on the IEEE-754 bit patterns mapped to a monotonic ordering, which
    is the only way to count representable steps across zero. Non-finite values and signed zeros
    are counted separately instead of being folded into an error metric."""
    import numpy as np
    x, y = [np.fromfile(OUT / "runs" / t / "color.bin", dtype="<f4").reshape(-1, 4)[:, :3]
            for t in (a_tag, b_tag)]
    G.require(x.shape == y.shape == (1920 * 1080, 3), "fp32 capture shape mismatch")
    xb, yb = [v.view(np.int32).astype(np.int64) for v in (x, y)]
    mono = lambda b: np.where(b < 0, np.int64(-2147483648) - b, b)   # total order over floats
    finite = np.isfinite(x) & np.isfinite(y)
    ulp = np.abs(mono(xb) - mono(yb))
    ulp_finite = np.where(finite, ulp, 0)
    d = np.where(finite, np.abs(y - x), 0.0)
    denom = np.maximum(np.abs(x), np.finfo(np.float32).tiny)
    rel = np.where(finite, d / denom, 0.0)
    neg_zero_x = int(np.count_nonzero((x == 0) & (np.signbit(x))))
    neg_zero_y = int(np.count_nonzero((y == 0) & (np.signbit(y))))
    return dict(
        pair=[a_tag, b_tag],
        identical=bool(np.array_equal(xb, yb)),
        differing_channels=int(np.count_nonzero(xb != yb)),
        differing_fraction=float(np.mean(xb != yb)),
        max_ulp=int(ulp_finite.max()),
        ulp_histogram={str(k): int(v) for k, v in
                       zip(*np.unique(ulp_finite[ulp_finite > 0], return_counts=True))
                       if int(v) > 0} if np.any(ulp_finite > 0) else {},
        max_abs_error=float(d.max()), rms_error=float(np.sqrt(np.mean(d.astype(np.float64) ** 2))),
        max_rel_error=float(rel.max()),
        rms_rel_error=float(np.sqrt(np.mean(rel.astype(np.float64) ** 2))),
        nonfinite_a=int(np.count_nonzero(~np.isfinite(x))),
        nonfinite_b=int(np.count_nonzero(~np.isfinite(y))),
        nan_a=int(np.count_nonzero(np.isnan(x))), nan_b=int(np.count_nonzero(np.isnan(y))),
        posinf_a=int(np.count_nonzero(np.isposinf(x))), posinf_b=int(np.count_nonzero(np.isposinf(y))),
        neginf_a=int(np.count_nonzero(np.isneginf(x))), neginf_b=int(np.count_nonzero(np.isneginf(y))),
        negative_zero_a=neg_zero_x, negative_zero_b=neg_zero_y,
        min_a=float(x[np.isfinite(x)].min()), max_a=float(x[np.isfinite(x)].max()))


# --------------------------------------------------------------------------------- analysis

def load(tag):
    p = OUT / "runs" / tag / "gpa_results.csv"
    if not p.is_file():
        return None
    by = {}
    for r in csv.DictReader(p.open(encoding="utf-8")):
        by.setdefault(r["counter"], {})[int(r["sample"])] = float(r["value"])
    return {c: [v[i] for i in sorted(v)] for c, v in by.items()}


def tot(d, pat):
    keys = [c for c in d if re.fullmatch(pat, c)]
    if not keys:
        return None
    n = len(d[keys[0]])
    return statistics.median(sum(d[k][i] for k in keys) for i in range(n))


REPS = range(1, 10)     # however many independent processes a cycle actually ran


def per_rep(label, setname, pat):
    """One value per independent process, in rep order, for the reps that exist."""
    return [tot(load(f"{label}_{setname}_r{r}"), pat) for r in REPS
            if load(f"{label}_{setname}_r{r}")]


FIELDS = {"GPUBusyCycles": ("resp", r"GPUBusyCycles"),
          "GPUTime": ("resp", r"GPUTime"),
          "TA_BUSY": ("resp", r"TA\d+_PERF_SEL_TA_BUSY"),
          "PS_tex": ("sq_ps", r"SQ_PS\d_PERF_SEL_INSTS_TEX_LOAD"),
          "PS_VALU": ("sq_ps", r"SQ_PS\d_PERF_SEL_INSTS_VALU"),
          "PS_VALU_cycles": ("sq_ps", r"SQ_PS\d_PERF_SEL_INST_CYCLES_VALU"),
          "PS_waves": ("sq_ps", r"SQ_PS\d_PERF_SEL_WAVES")}


def analyse():
    m = manifest()
    line = "=" * 100
    have = [v for v in VARIANTS if (OUT / f"build_{v}.json").exists()]
    data = {v: {k: per_rep(v, s, p) for k, (s, p) in FIELDS.items()} for v in have}
    data = {v: {k: x for k, x in f.items() if x} for v, f in data.items()}
    med = {v: {k: statistics.median(x) for k, x in f.items()} for v, f in data.items()}

    print(line)
    print("1. DOSE - what each transformation actually changed (sq_ps, 1 pass, median of runs)")
    print(line)
    ref = BASELINE_OF.get(CYCLE, {})
    print(f"{'variant':12s} {'kind':16s} {'PS waves':>10s} {'tex instr':>14s} {'d tex':>8s}"
          f" {'VALU instr':>14s} {'d VALU':>8s} {'VALU cycles':>15s} {'d cyc':>8s}"
          f"   (deltas vs each arm's own baseline)")
    for v in have:
        if "PS_tex" not in med.get(v, {}):
            continue
        b = med[ref.get(v, "base")]
        kind = "baseline" if v == "base" else m["transforms"][v]["kind"]
        f = lambda k: (med[v][k] - b[k]) / b[k] * 100
        print(f"{v:12s} {kind:16s} {med[v]['PS_waves']:10,.0f} {med[v]['PS_tex']:14,.0f}"
              f" {f('PS_tex'):7.2f}% {med[v]['PS_VALU']:14,.0f} {f('PS_VALU'):7.2f}%"
              f" {med[v]['PS_VALU_cycles']:15,.0f} {f('PS_VALU_cycles'):7.2f}%")

    print("\n" + line)
    print("2. A/A CONTROL on base and preregistered thresholds")
    print(line)
    n95, thr = {}, {}
    for k in ("GPUBusyCycles", "GPUTime", "TA_BUSY"):
        vals = data["base"].get(k, [])
        if len(vals) > 1:  # A/A control: every pair of independent base processes
            pw = [abs(a - b) / ((a + b) / 2) * 100 for i, a in enumerate(vals) for b in vals[i + 1:]]
            n95[k] = max(pw)
            thr[k] = max(1.0, 3 * max(pw))
            print(f"   {k:16s} pairwise " + ", ".join(f"{x:.2f}%" for x in pw)
                  + f"  -> N95 {n95[k]:.2f}%, accept threshold {thr[k]:.2f}%")

    print("\n" + line)
    print("3. RESPONSE - paired against base")
    print(line)
    verdicts = {}
    for v in have:
        if v == "base":
            continue
        base_of = ref.get(v, "base")
        row = {}
        for k in ("GPUBusyCycles", "GPUTime", "TA_BUSY"):
            if k not in data.get(v, {}) or k not in data.get(base_of, {}):
                continue
            G.require(len(data[v][k]) == len(data[base_of][k]),
                      f"{v}/{k}: unequal number of processes, pairing would be wrong")
            paired = [(x - b) / b * 100 for x, b in zip(data[v][k], data[base_of][k])]
            row[k] = dict(median=statistics.median(paired), per_process=paired)
        gb = row.get("GPUBusyCycles")
        ok = bool(gb and len(gb["per_process"]) >= 3
                  and gb["median"] <= -thr.get("GPUBusyCycles", 1.0)
                  and all(d < 0 for d in gb["per_process"]))
        verdicts[v] = dict(metrics=row, performance_accepted=ok, baseline=base_of)
        print(f"   {v}   (vs {base_of})")
        for k, r in row.items():
            print(f"      {k:16s} median {r['median']:+7.2f} %   per process "
                  + ", ".join(f"{d:+.2f}%" for d in r["per_process"]))
        print(f"      performance verdict: {'ACCEPT' if ok else 'reject'}"
              f" (needs median <= {-thr.get('GPUBusyCycles', 1.0):.2f} % and all processes < 0)")

    print("\n" + line)
    print("4. CORRECTNESS")
    print(line)
    corr = {}
    tags = {p.name for p in (OUT / "runs").glob("*_image_r*")}
    if "base_image_r1" in tags and "base_image_r2" in tags:
        c = compare_images("base_image_r1", "base_image_r2")
        corr["base_vs_base"] = c
        print(f"   base vs base   identical={c['identical']}  changed={c['changed_pixels']}  "
              f"max_rel={c['max_rel_error']:.3e}   (determinism check, must be identical)")
    for v in have:
        base_of = ref.get(v, "base")
        if v == "base" or f"{v}_image_r1" not in tags or f"{base_of}_image_r1" not in tags:
            continue
        if TRANSFORMS.get(v, {}).get("kind") == "regime_only":
            # Not a candidate: it is the baseline of its own regime, and its image is *supposed*
            # to differ from the dense-regime baseline. Reported, never judged.
            c = compare_images(f"{base_of}_image_r1", f"{v}_image_r1")
            c["passed"] = None
            corr[v] = c
            print(f"   {v:12s} regime baseline, not a candidate: differs from `{base_of}` on "
                  f"{c['changed_fraction']*100:.2f} % of pixels, as intended")
            continue
        c = compare_images(f"{base_of}_image_r1", f"{v}_image_r1")
        rule = m["preregistered_criteria"].get("correctness_rule", "max_rel_1e-3")
        if rule == "max_rel_1e-3":
            c["passed"] = c["max_rel_error"] <= 1e-3 and c["nonfinite_channels"] == 0
        else:
            c["passed"] = (c["max_channel_ulp"] <= 1 and c["changed_channel_fraction"] <= 5e-4
                           and c["nonfinite_channels"] == 0)
        c["rule"] = rule
        corr[v] = c
        print(f"   {v:12s} identical={str(c['identical']):5s} changed={c['changed_fraction']*100:7.5f} %"
              f"  max_ulp={c['max_channel_ulp']}  changed_ch={c['changed_channel_fraction']*100:.5f} %"
              f"  max_rel={c['max_rel_error']:.3e}  [{rule}] -> {'PASS' if c['passed'] else 'FAIL'}")

    print("\n" + line)
    print("5. VERDICT")
    print(line)
    for v in have:
        if v == "base":
            continue
        pf = verdicts.get(v, {}).get("performance_accepted")
        cr = corr.get(v, {}).get("passed")
        final = ("regime baseline (not a candidate)"
                 if TRANSFORMS.get(v, {}).get("kind") == "regime_only" else
                 "ACCEPTED" if pf and cr else
                 "REJECTED (correctness)" if cr is False else
                 "REJECTED (performance)" if pf is False else "incomplete")
        print(f"   {v:12s} {final}")
        verdicts.setdefault(v, {})["final"] = final
        verdicts[v]["correctness"] = corr.get(v)

    G.save_json(OUT / f"analysis_{datetime.now().strftime('%H%M%S')}.json",
                dict(experiment_id=m["experiment_id"], criteria=m["preregistered_criteria"],
                     n95=n95, thresholds=thr, medians=med, verdicts=verdicts,
                     correctness=corr))
    print("\nwrote analysis json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "build", "run", "image", "bench", "analyse"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("setname", nargs="?", default="resp")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--cycle", default="p1")
    ap.add_argument("--reuse-from", default=None)
    ap.add_argument("--r32", action="store_true",
                    help="capture into the R32G32B32A32_FLOAT diagnostic target")
    a = ap.parse_args()
    select(a.cycle)
    if a.action == "prepare":
        prepare(a.reuse_from)
    elif a.action == "build":
        build(a.name)
    elif a.action == "run":
        run(a.name, a.setname, a.samples, a.rep)
    elif a.action == "image":
        image(a.name, a.rep, a.r32)
    elif a.action == "bench":
        bench(a.name, a.rep)
    else:
        analyse()
