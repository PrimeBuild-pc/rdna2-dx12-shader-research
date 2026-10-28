"""Phase 2T - the hit-rate study: the frozen pipeline, unchanged, on workloads chosen before
they were inspected.

One runner, several workloads. Each workload contributes a descriptor saying where its sources
are, how its shaders are compiled (so the gate can preregister their hashes), where the
instrumentation hooks go, and which render target is its correctness oracle. Everything else -
the gate, the A/A control, the paired A/B, the acceptance rule - is the same code for all of
them, which is the point: the method is what is under test, not the workloads.

    python -B tools/run_2t.py prepare  --workload w1
    python -B tools/run_2t.py build    <variant> --workload w1
    python -B tools/run_2t.py run      <variant> --workload w1 [--rep R]
    python -B tools/run_2t.py analyse  --workload w1
"""
import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import statistics
import sys

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = Path(os.environ["TEMP"]) / "claude/src/dxs/Samples/Desktop"
PRISTINE = Path(os.environ["TEMP"]) / "claude/src/t2"
MSBUILD = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\amd64\MSBuild.exe")
PKG_SRC = Path(os.environ["TEMP"]) / "claude/src/nbody/src/packages"


def once(data, old, new, what):
    """Apply one anchored edit to bytes, in whichever line-ending form the file actually uses.

    Line endings are per-region, not per-file: w4's Common.hlsli is LF in its body and CRLF in
    its last two lines. So the anchor is tried as written first, converted only if that misses,
    and an anchor that would match in both forms is refused rather than guessed.
    """
    if isinstance(old, str):
        old, new = old.encode(), new.encode()
    crlf_old, crlf_new = old.replace(b"\n", b"\r\n"), new.replace(b"\n", b"\r\n")
    n_lf = data.count(old)
    n_crlf = data.count(crlf_old) if crlf_old != old else 0
    G.require(n_lf + n_crlf == 1,
              f"{what}: anchor matched {n_lf} times as written and {n_crlf} times CRLF-converted; "
              f"exactly one match is required")
    return data.replace(old, new) if n_lf else data.replace(crlf_old, crlf_new)


# --------------------------------------------------------------------------- workloads
#
# `shaders`  : {output cso name: (target, entry, source file)} - how the gate preregisters hashes
# `edits`    : instrumentation, applied to the workspace copy; every anchor must be unique
# `regions`  : what each timestamp region measures, for the report

# w4 spans two source files; these name them for its edit list.
MAIN_UA = "src/D3D12DynamicIndexing.cpp"
MAIN = "src/D3D12VariableRateShading.cpp"
SCENE = "src/ShadowsFogScatteringSquidScene.cpp"
VRS = "src/VariableRateShadingScene.cpp"

WORKLOADS = {
    "w1": dict(
        name="D3D12ExecuteIndirect",
        dir="D3D12ExecuteIndirect",
        proj="src/D3D12ExecuteIndirect.vcxproj",
        main="src/D3D12ExecuteIndirect.cpp",
        shaders={"compute.cso": ("cs_6_0", "CSMain", "src/compute.hlsl"),
                 "shaders_VSMain.cso": ("vs_6_0", "VSMain", "src/shaders.hlsl"),
                 "shaders_PSMain.cso": ("ps_6_0", "PSMain", "src/shaders.hlsl")},
        regions={0: "compute cull dispatch", 1: "indirect draw command list"},
        edits=[
            ('#include "D3D12ExecuteIndirect.h"',
             '#include "D3D12ExecuteIndirect.h"\n#include "TProbe.h"'),
            ('ThrowIfFailed(m_swapChain->Present(1, 0));',
             'ThrowIfFailed(m_swapChain->Present(TProbe::Enabled() ? 0 : 1, 0));\n'
             '        TProbe::EndFrame(m_renderTargets[m_frameIndex].Get(),\n'
             '                         D3D12_RESOURCE_STATE_PRESENT);'),
            ('        m_computeCommandList->Dispatch(static_cast<UINT>(ceil(TriangleCount / float(ComputeThreadBlockSize))), 1, 1);',
             '        TProbe::Init(m_device.Get(), m_commandQueue.Get());\n'
             '        TProbe::Begin(m_computeCommandList.Get(), 0);\n'
             '        m_computeCommandList->Dispatch(static_cast<UINT>(ceil(TriangleCount / float(ComputeThreadBlockSize))), 1, 1);\n'
             '        TProbe::End(m_computeCommandList.Get(), 0);'),
            ('        m_commandList->ResourceBarrier(_countof(barriers), barriers);\n'
             '\n'
             '        ThrowIfFailed(m_commandList->Close());',
             '        m_commandList->ResourceBarrier(_countof(barriers), barriers);\n'
             '\n'
             '        TProbe::End(m_commandList.Get(), 1);\n'
             '        TProbe::Resolve(m_commandList.Get());\n'
             '        ThrowIfFailed(m_commandList->Close());'),
            ('        m_commandList->SetGraphicsRootSignature(m_rootSignature.Get());',
             '        TProbe::Begin(m_commandList.Get(), 1);\n'
             '        m_commandList->SetGraphicsRootSignature(m_rootSignature.Get());'),
        ],
        primary_region=1),

    "w2": dict(
        name="D3D12Multithreading",
        dir="D3D12Multithreading",
        proj="src/D3D12Multithreading.vcxproj",
        main="src/D3D12Multithreading.cpp",
        shaders={"shaders_VSMain.cso": ("vs_6_0", "VSMain", "src/shaders.hlsl"),
                 "shaders_PSMain.cso": ("ps_6_0", "PSMain", "src/shaders.hlsl")},
        regions={0: "whole frame: shadow pass + shadowed scene, all worker lists"},
        edits=[
            ('#include "D3D12Multithreading.h"',
             '#include "D3D12Multithreading.h"\n#include "TProbe.h"'),
            # A fixed timestep while measuring, so the captured frame is deterministic and the
            # correctness oracle means something. Untouched when the probe is off.
            ('    float frameTime = static_cast<float>(m_timer.GetElapsedSeconds());',
             '    float frameTime = TProbe::Enabled() ? (1.0f / 60.0f)\n'
             '                                        : static_cast<float>(m_timer.GetElapsedSeconds());'),
            ('        ThrowIfFailed(m_swapChain->Present(1, 0));',
             '        ThrowIfFailed(m_swapChain->Present(TProbe::Enabled() ? 0 : 1, 0));\n'
             '        TProbe::EndFrame(m_renderTargets[m_frameIndex].Get(),\n'
             '                         D3D12_RESOURCE_STATE_PRESENT);'),
            # Bracket every worker list: begin in the Pre list, end and resolve in the Post one.
            ('    m_pCurrentFrameResource->m_commandLists[CommandListPre]->ClearDepthStencilView('
             'm_dsvHeap->GetCPUDescriptorHandleForHeapStart(), D3D12_CLEAR_FLAG_DEPTH, 1.0f, 0, 0, nullptr);',
             '    m_pCurrentFrameResource->m_commandLists[CommandListPre]->ClearDepthStencilView('
             'm_dsvHeap->GetCPUDescriptorHandleForHeapStart(), D3D12_CLEAR_FLAG_DEPTH, 1.0f, 0, 0, nullptr);\n'
             '    TProbe::Init(m_device.Get(), m_commandQueue.Get());\n'
             '    TProbe::Begin(m_pCurrentFrameResource->m_commandLists[CommandListPre].Get(), 0);'),
            ('    ThrowIfFailed(m_pCurrentFrameResource->m_commandLists[CommandListPost]->Close());',
             '    TProbe::End(m_pCurrentFrameResource->m_commandLists[CommandListPost].Get(), 0);\n'
             '    TProbe::Resolve(m_pCurrentFrameResource->m_commandLists[CommandListPost].Get());\n'
             '    ThrowIfFailed(m_pCurrentFrameResource->m_commandLists[CommandListPost]->Close());'),
        ],
        primary_region=0),

    "w3": dict(
        name="D3D12MeshShaders / MeshletRender",
        dir="D3D12MeshShaders",
        proj="src/MeshletRender/D3D12MeshletRender.vcxproj",
        main="src/MeshletRender/D3D12MeshletRender.cpp",
        shaders={"MeshletMS.cso": ("ms_6_5", "main", "src/MeshletRender/MeshletMS.hlsl"),
                 "MeshletPS.cso": ("ps_6_3", "main", "src/MeshletRender/MeshletPS.hlsl")},
        regions={0: "the whole draw: mesh-shader dispatches over the model"},
        edits=[
            ('#include "D3D12MeshletRender.h"',
             '#include "D3D12MeshletRender.h"\n#include "TProbe.h"'),
            ('    ThrowIfFailed(m_swapChain->Present(1, 0));',
             '    ThrowIfFailed(m_swapChain->Present(TProbe::Enabled() ? 0 : 1, 0));\n'
             '    TProbe::EndFrame(m_renderTargets[m_frameIndex].Get(),\n'
             '                     D3D12_RESOURCE_STATE_PRESENT);'),
            ('    m_commandList->ClearDepthStencilView(dsvHandle, D3D12_CLEAR_FLAG_DEPTH, 1.0f, 0, 0, nullptr);',
             '    m_commandList->ClearDepthStencilView(dsvHandle, D3D12_CLEAR_FLAG_DEPTH, 1.0f, 0, 0, nullptr);\n'
             '    TProbe::Init(m_device.Get(), m_commandQueue.Get());\n'
             '    TProbe::Begin(m_commandList.Get(), 0);'),
            ('    const auto toPresentBarrier = CD3DX12_RESOURCE_BARRIER::Transition('
             'm_renderTargets[m_frameIndex].Get(), D3D12_RESOURCE_STATE_RENDER_TARGET, '
             'D3D12_RESOURCE_STATE_PRESENT);',
             '    TProbe::End(m_commandList.Get(), 0);\n'
             '    TProbe::Resolve(m_commandList.Get());\n'
             '    const auto toPresentBarrier = CD3DX12_RESOURCE_BARRIER::Transition('
             'm_renderTargets[m_frameIndex].Get(), D3D12_RESOURCE_STATE_RENDER_TARGET, '
             'D3D12_RESOURCE_STATE_PRESENT);'),
        ],
        primary_region=0),

    "ua": dict(
        name="D3D12DynamicIndexing",
        dir="D3D12DynamicIndexing",
        proj="src/D3D12DynamicIndexing.vcxproj",
        main=MAIN_UA,
        shaders={"shader_mesh_dynamic_indexing_pixel.cso":
                     ("ps_6_0", "PSMain", "src/shader_mesh_dynamic_indexing_pixel.hlsl"),
                 "shader_mesh_simple_vert.cso":
                     ("vs_6_0", "VSMain", "src/shader_mesh_simple_vert.hlsl")},
        regions={0: "the whole Draw cities region: every city mesh, one draw each"},
        edits=[
            (MAIN_UA, '#include "D3D12DynamicIndexing.h"',
             '#include "D3D12DynamicIndexing.h"\n#include "TProbe.h"'),
            # The camera only moves on key input, but the timestep is pinned anyway while
            # probing so the captured frame cannot depend on wall-clock time at all.
            (MAIN_UA, '    m_camera.Update(static_cast<float>(m_timer.GetElapsedSeconds()));',
             '    m_camera.Update(TProbe::Enabled() ? 0.0f\n'
             '                                      : static_cast<float>(m_timer.GetElapsedSeconds()));'),
            (MAIN_UA, '    PIXBeginEvent(m_commandList.Get(), 0, L"Draw cities");',
             '    TProbe::Init(m_device.Get(), m_commandQueue.Get());\n'
             '    PIXBeginEvent(m_commandList.Get(), 0, L"Draw cities");\n'
             '    TProbe::Begin(m_commandList.Get(), 0);'),
            (MAIN_UA, '    PIXEndEvent(m_commandList.Get());',
             '    TProbe::End(m_commandList.Get(), 0);\n'
             '    TProbe::Resolve(m_commandList.Get());\n'
             '    PIXEndEvent(m_commandList.Get());'),
            (MAIN_UA, '    ThrowIfFailed(m_swapChain->Present(1, 0));',
             '    ThrowIfFailed(m_swapChain->Present(TProbe::Enabled() ? 0 : 1, 0));\n'
             '    TProbe::EndFrame(m_renderTargets[m_frameIndex].Get(),\n'
             '                     D3D12_RESOURCE_STATE_PRESENT);'),
        ],
        primary_region=0),
    "w4": dict(
        name="D3D12VariableRateShading / ShadowsFogScatteringSquidScene",
        dir="D3D12VariableRateShading",
        proj="src/D3D12VariableRateShading.vcxproj",
        main="src/D3D12VariableRateShading.cpp",
        shaders={"ShadowsAndScenePass_VSMain.cso": ("vs_6_0", "VSMain", "src/ShadowsAndScenePass.hlsl"),
                 "ShadowsAndScenePass_PSMain.cso": ("ps_6_0", "PSMain", "src/ShadowsAndScenePass.hlsl"),
                 "PostprocessPass_VSMain.cso": ("vs_6_0", "VSMain", "src/PostprocessPass.hlsl"),
                 "PostprocessPass_PSMain.cso": ("ps_6_0", "PSMain", "src/PostprocessPass.hlsl"),
                 "Glass_VSMain.cso": ("vs_6_0", "VSMain", "src/Glass.hlsl"),
                 "Glass_PSMain.cso": ("ps_6_0", "PSMain", "src/Glass.hlsl")},
        aux=["src/Common.hlsli"],
        # The UI layer draws a text overlay with the measured frame rate in it, which would make
        # the oracle depend on the machine's mood. The sample already has a switch for it.
        args=["-disableUI"],
        regions={0: "whole GPU frame: shadow pass, refraction pass, scene pass on all worker "
                    "lists, postprocess",
                 1: "postprocess pass alone", 2: "scene pass, all worker lists",
                 3: "refraction pass alone"},
        edits=[
            (MAIN, '#include "D3D12VariableRateShading.h"',
             '#include "D3D12VariableRateShading.h"\n#include "TProbe.h"'),
            # Fixed timestep while measuring, so the captured frame is a function of the frame
            # count alone. Untouched when the probe is off.
            (MAIN, '    m_scene->Update(m_timer.GetElapsedSeconds());',
             '    m_scene->Update(TProbe::Enabled() ? (1.0 / 60.0)\n'
             '                                      : m_timer.GetElapsedSeconds());'),
            (MAIN, '            m_scene->Render(m_commandQueue.Get(), bSetBackbufferReadyForPresent);',
             '            TProbe::Init(m_device.Get(), m_commandQueue.Get());\n'
             '            m_scene->Render(m_commandQueue.Get(), bSetBackbufferReadyForPresent);'),
            (MAIN, '            ThrowIfFailed(m_swapChain->Present(0, DXGI_PRESENT_ALLOW_TEARING));',
             '            ThrowIfFailed(m_swapChain->Present(0, DXGI_PRESENT_ALLOW_TEARING));\n'
             '            TProbe::EndFrame(m_renderTargets[m_frameIndex].Get(),\n'
             '                             D3D12_RESOURCE_STATE_PRESENT);'),
            (SCENE, '#include "ShadowsFogScatteringSquidScene.h"',
             '#include "ShadowsFogScatteringSquidScene.h"\n#include "TProbe.h"'),
            # Region 0 opens in the Pre list after the clears and closes in the Post list, so it
            # spans every worker list submitted in between.
            (SCENE, '    pCommandListPre->ClearDepthStencilView(m_depthDsvs[DepthGenPass::Scene], '
                    'D3D12_CLEAR_FLAG_DEPTH, 1.0f, 0, 0, nullptr);',
             '    pCommandListPre->ClearDepthStencilView(m_depthDsvs[DepthGenPass::Scene], '
             'D3D12_CLEAR_FLAG_DEPTH, 1.0f, 0, 0, nullptr);\n'
             '    TProbe::Begin(pCommandListPre, 0);'),
            (SCENE, '    m_pCurrentFrameResource->m_gpuTimer.Start(pCommandListPost, Timestamp::PostprocessPass);',
             '    TProbe::Begin(pCommandListPost, 1);\n'
             '    m_pCurrentFrameResource->m_gpuTimer.Start(pCommandListPost, Timestamp::PostprocessPass);'),
            (SCENE, '    m_pCurrentFrameResource->m_gpuTimer.Stop(pCommandListPost, Timestamp::PostprocessPass);',
             '    m_pCurrentFrameResource->m_gpuTimer.Stop(pCommandListPost, Timestamp::PostprocessPass);\n'
             '    TProbe::End(pCommandListPost, 1);'),
            # Regions 2 and 3 sit exactly where the sample's own GPU timer already brackets
            # its scene and refraction passes, so the split is the sample's own definition.
            (SCENE, 'm_pCurrentFrameResource->m_gpuTimer.Start(pSceneCommandList, Timestamp::ScenePass);',
             'TProbe::Begin(pSceneCommandList, 2);\n'
             '                m_pCurrentFrameResource->m_gpuTimer.Start(pSceneCommandList, Timestamp::ScenePass);'),
            (SCENE, 'm_pCurrentFrameResource->m_gpuTimer.Stop(pSceneCommandList, Timestamp::ScenePass);',
             'm_pCurrentFrameResource->m_gpuTimer.Stop(pSceneCommandList, Timestamp::ScenePass);\n'
             '                TProbe::End(pSceneCommandList, 2);'),
            (VRS, '#include "VariableRateShadingScene.h"',
             '#include "VariableRateShadingScene.h"\n#include "TProbe.h"'),
            (VRS, '    m_pCurrentFrameResource->m_gpuTimer.Start(pCommandListMid, VRSSceneEnums::Timestamp::RefractionPass);',
             '    TProbe::Begin(pCommandListMid, 3);\n'
             '    m_pCurrentFrameResource->m_gpuTimer.Start(pCommandListMid, VRSSceneEnums::Timestamp::RefractionPass);'),
            (VRS, '    m_pCurrentFrameResource->m_gpuTimer.Stop(pCommandListMid, VRSSceneEnums::Timestamp::RefractionPass);',
             '    m_pCurrentFrameResource->m_gpuTimer.Stop(pCommandListMid, VRSSceneEnums::Timestamp::RefractionPass);\n'
             '    TProbe::End(pCommandListMid, 3);'),
            (SCENE, '    m_pCurrentFrameResource->EndFrame(pCommandListPost);',
             '    m_pCurrentFrameResource->EndFrame(pCommandListPost);\n'
             '    TProbe::End(pCommandListPost, 0);\n'
             '    TProbe::Resolve(pCommandListPost);'),
        ],
        primary_region=0),
}

# --------------------------------------------------------------------------- workload U-B
# D3D12Raytracing / ProceduralGeometry. Declared after WORKLOADS because its paths are long
# enough to be worth naming, and merged in below.
UB_DIR = "Samples/Desktop/D3D12Raytracing/src/D3D12RaytracingProceduralGeometry"
UB_MAIN = UB_DIR + "/D3D12RaytracingProceduralGeometry.cpp"
UB_DEV = UB_DIR + "/util/DeviceResources.cpp"
UB_HLSL = UB_DIR + "/Raytracing.hlsl"

WORKLOADS["ub"] = dict(
    name="D3D12Raytracing / ProceduralGeometry",
    dir="D3D12RaytracingPG",
    stage=["Packages", "Samples/Desktop/D3D12Raytracing"],
    proj=UB_DIR + "/D3D12RaytracingProceduralGeometry.vcxproj",
    main=UB_MAIN,
    dxc="sdk",
    shader_flags=["-HV", "2021", "-Zpr"],
    shaders={"Raytracing.dxil": ("lib_6_3", None, UB_HLSL)},
    aux=[UB_DIR + "/RaytracingHlslCompat.h",
         UB_DIR + "/ProceduralPrimitivesLibrary.hlsli",
         UB_DIR + "/RaytracingShaderHelper.hlsli",
         UB_DIR + "/AnalyticPrimitives.hlsli",
         UB_DIR + "/VolumetricPrimitives.hlsli",
         UB_DIR + "/SignedDistancePrimitives.hlsli",
         UB_DIR + "/SignedDistanceFractals.hlsli",
         UB_DIR + "/RaytracingSceneDefines.h",
         UB_DIR + "/util/HlslCompat.h"],
    artifact=dict(rel="obj/x64/Release/CompiledShaders/Raytracing.hlsl.h", var="g_pRaytracing"),
    regions={0: "the DispatchRays call: the whole raytracing pass"},
    edits=[
        (UB_MAIN, '#include "D3D12RaytracingProceduralGeometry.h"',
         '#include "D3D12RaytracingProceduralGeometry.h"\n#include "TProbe.h"'),
        # Fixed timestep while probing. The sample animates its geometry by accumulating elapsed
        # seconds, so without this the captured frame is a function of wall time.
        (UB_MAIN, '    float elapsedTime = static_cast<float>(m_timer.GetElapsedSeconds());',
         '    float elapsedTime = TProbe::Enabled()\n'
         '                      ? (1.0f / 60.0f)\n'
         '                      : static_cast<float>(m_timer.GetElapsedSeconds());'),
        (UB_MAIN, '    DoRaytracing();\n    CopyRaytracingOutputToBackbuffer();',
         '    TProbe::Init(device, m_deviceResources->GetCommandQueue());\n'
         '    TProbe::Begin(commandList, 0);\n'
         '    DoRaytracing();\n'
         '    TProbe::End(commandList, 0);\n'
         '    CopyRaytracingOutputToBackbuffer();\n'
         '    TProbe::Resolve(commandList);'),
        # The back-buffer pointer is taken before Present, which advances the index.
        (UB_MAIN, '    m_deviceResources->Present(D3D12_RESOURCE_STATE_PRESENT);\n}',
         '    ID3D12Resource* probeTarget = m_deviceResources->GetRenderTarget();\n'
         '    m_deviceResources->Present(D3D12_RESOURCE_STATE_PRESENT);\n'
         '    TProbe::EndFrame(probeTarget, D3D12_RESOURCE_STATE_PRESENT);\n}'),
        (UB_DEV, '#include "DeviceResources.h"',
         '#include "DeviceResources.h"\n#include "TProbe.h"'),
        (UB_DEV, '        hr = m_swapChain->Present(1, 0);',
         '        hr = m_swapChain->Present(TProbe::Enabled() ? 0 : 1, 0);'),
    ],
    primary_region=0)


# --------------------------------------------------------------------------- workload U-C
UC_MAIN = "src/D3D12HDR.cpp"
UC_SAMPLE = "src/DXSample.cpp"
UC_PS = "src/presentPS.hlsl"

WORKLOADS["uc"] = dict(
    name="D3D12HDR",
    dir="D3D12HDR",
    proj="src/D3D12HDR.vcxproj",
    main=UC_MAIN,
    shaders={"gradientPS.cso": ("ps_6_0", "PSMain", "src/gradientPS.hlsl"),
             "gradientVS.cso": ("vs_6_0", "VSMain", "src/gradientVS.hlsl"),
             "palettePS.cso": ("ps_6_0", "PSMain", "src/palettePS.hlsl"),
             "paletteVS.cso": ("vs_6_0", "VSMain", "src/paletteVS.hlsl"),
             "presentPS.cso": ("ps_6_0", "PSMain", UC_PS),
             "presentVS.cso": ("vs_6_0", "VSMain", "src/presentVS.hlsl")},
    aux=["src/color.hlsli", "src/gradient.hlsli", "src/palette.hlsli", "src/present.hlsli"],
    regions={0: "the whole scene: gradients, palettes and the present pass",
             1: "the present pass alone: one full-screen triangle through presentPS"},
    edits=[
        (UC_MAIN, b'#include "D3D12HDR.h"', b'#include "D3D12HDR.h"\n#include "TProbe.h"'),
        (UC_SAMPLE, b'#include "DXSample.h"', b'#include "DXSample.h"\n#include "TProbe.h"'),
        # The Direct2D UI layer draws live numbers, which would make the oracle depend on the
        # machine's mood. The sample already has this switch and toggles it on a key.
        (UC_SAMPLE, b"    m_enableUI(true)", b"    m_enableUI(!TProbe::Enabled())"),
        (UC_MAIN,
         b"""    ThrowIfFailed(m_commandList->Reset(m_commandAllocators[m_frameIndex].Get(), m_pipelineStates[GradientPSO].Get()));
""",
         b"""    ThrowIfFailed(m_commandList->Reset(m_commandAllocators[m_frameIndex].Get(), m_pipelineStates[GradientPSO].Get()));
    TProbe::Init(m_device.Get(), m_commandQueue.Get());
    TProbe::Begin(m_commandList.Get(), 0);
"""),
        (UC_MAIN,
         b"""        PIXBeginEvent(m_commandList.Get(), 0, L"Apply HDR");
""",
         b"""        TProbe::Begin(m_commandList.Get(), 1);
        PIXBeginEvent(m_commandList.Get(), 0, L"Apply HDR");
"""),
        (UC_MAIN,
         b"""    m_commandList->ResourceBarrier(_countof(barriers), barriers);

    ThrowIfFailed(m_commandList->Close());
""",
         b"""    TProbe::End(m_commandList.Get(), 1);
    m_commandList->ResourceBarrier(_countof(barriers), barriers);

    TProbe::End(m_commandList.Get(), 0);
    TProbe::Resolve(m_commandList.Get());
    ThrowIfFailed(m_commandList->Close());
"""),
        (UC_MAIN,
         b"""        ThrowIfFailed(m_swapChain->Present(1, 0));
""",
         b"""        ID3D12Resource* probeTarget = m_renderTargets[m_frameIndex].Get();
        ThrowIfFailed(m_swapChain->Present(TProbe::Enabled() ? 0 : 1, 0));
        TProbe::EndFrame(probeTarget, D3D12_RESOURCE_STATE_PRESENT);
"""),
    ],
    primary_region=0)

# U-C's ceiling probe, written before its baseline is measured: the present pass keeps its two
# texture fetches and loses the whole colour-transform chain.
UC_TRANSFORMS = {
    "ablate_present": dict(
        kind="diagnostic_ceiling", candidate=False,
        edits=[(UC_PS,
                b"""    float3 result = lerp(scene, SRGBToLinear(uiLayer.rgb), uiLayer.a);
""",
                b"""    float3 result = scene + uiLayer.rgb;
    return result;
""")],
        equivalence="none: diagnostic, the image is deliberately wrong",
        expectation="the sRGB, Rec.2020 and ST.2084 conversions gone; the two fetches kept"),
}


SH = "src/shaders.hlsl"

# Hypotheses for w2, taken from its own ISA and nowhere else. RGA on the shipped PSMain reports
# 372 instructions with 3 v_sqrt_f32, 7 v_rcp_f32 and 9 v_rsq_f32: the source computes a length
# and then divides by it, and the compiler did not fuse those into a reciprocal square root.
W2_TRANSFORMS = {
    # length(v) then v / length(v): one sqrt and a divide, where a single rsqrt and a multiply do
    # the same work. fDist is still needed for the distance falloff, so it is recovered as
    # fDistSq * rsqrt(fDistSq).
    "rsqrt_dist": dict(
        kind="alu_strength_reduction",
        edits=[(SH,
                b"    float fDist = length(vLightToPixelUnNormalized);\n",
                b"    float fDistSq = dot(vLightToPixelUnNormalized, vLightToPixelUnNormalized);\n"
                b"    float fInvDist = rsqrt(fDistSq);\n"
                b"    float fDist = fDistSq * fInvDist;\n"),
               (SH,
                b"    float3 vLightToPixelNormalized = vLightToPixelUnNormalized / fDist;\n",
                b"    float3 vLightToPixelNormalized = vLightToPixelUnNormalized * fInvDist;\n")],
        equivalence="sqrt(x) and x/sqrt(x) replaced by rsqrt(x) and x*rsqrt(x). Mathematically "
                    "identical; not bitwise identical, since the rounding differs.",
        expectation="one sqrt and one divide fewer per light"),

    # vLightDir is a per-light constant that the shader normalises inside the per-pixel loop.
    # dot(a, b/|b|) == dot(a,b) * rsqrt(dot(b,b)) - one rsqrt instead of a sqrt and a divide.
    "light_dir_norm": dict(
        kind="alu_strength_reduction",
        edits=[(SH,
                b"    float fCosAngle = dot(vLightToPixelNormalized, vLightDir / length(vLightDir));\n",
                b"    float fCosAngle = dot(vLightToPixelNormalized, vLightDir)\n"
                b"                    * rsqrt(dot(vLightDir, vLightDir));\n")],
        equivalence="dot(a, b/|b|) == dot(a,b)/|b| == dot(a,b) * rsqrt(dot(b,b)). Mathematically "
                    "identical, not bitwise.",
        expectation="one sqrt and a three-component divide fewer per light"),
}
W2_TRANSFORMS["both"] = dict(
    kind="stack",
    edits=W2_TRANSFORMS["rsqrt_dist"]["edits"] + W2_TRANSFORMS["light_dir_norm"]["edits"],
    equivalence="the two above together; measured, not assumed to compose",
    expectation="not assumed to be the sum")

CH = "src/Common.hlsli"
PS = "src/ShadowsAndScenePass.hlsl"

# Hypotheses for w4, taken from its own ISA and nowhere else. RGA on the shipped PSMain
# (gfx1030, root signature reconstructed from VariableRateShadingScene::CreateRootSignatures)
# reports 23 VGPRs, no scratch, ~237 instructions and 6 image_sample. Four of those six are one
# cluster: the 2x2 PCF taps, all through sampleClamp, which the C++ creates as
# D3D12_FILTER_MIN_MAG_MIP_POINT. Four point samples of one 2x2 texel quad is exactly what a
# single gather4 returns.
W4_TRANSFORMS = {
    "gather_pcf": dict(
        kind="texture_instruction_reduction",
        edits=[(CH,
                b"""        vShadowDepths.x = shadowMap.Sample(sampleClamp, vShadowTexCoord).x;
        vShadowDepths.y = shadowMap.Sample(sampleClamp, vShadowTexCoord + float2(vTexelUnits.x, 0.0f)).x;
        vShadowDepths.z = shadowMap.Sample(sampleClamp, vShadowTexCoord + float2(0.0f, vTexelUnits.y)).x;
        vShadowDepths.w = shadowMap.Sample(sampleClamp, vShadowTexCoord + vTexelUnits).x;
""",
                b"""        // One gather4 in place of four point samples of the same 2x2 texel quad.
        // Gather's footprint is the bilinear footprint of its address, the quad starting at
        // floor(uv*dims - 0.5); offsetting the address by half a texel makes that quad start
        // at floor(uv*dims), which is the texel the first point sample reads. Gather returns
        // (-,+), (+,+), (+,-), (-,-) in x, y, z, w.
        float4 vGathered = shadowMap.Gather(sampleClamp, vShadowTexCoord + 0.5f * vTexelUnits);
        vShadowDepths.x = vGathered.w;
        vShadowDepths.y = vGathered.z;
        vShadowDepths.z = vGathered.x;
        vShadowDepths.w = vGathered.y;
""")],
        equivalence="the same four texels, read by one instruction instead of four and assigned "
                    "to the same components, so every arithmetic operation downstream is "
                    "unchanged. Exact if and only if the half-texel-offset address selects the "
                    "same quad as the four original addresses; that is what the byte-exact "
                    "oracle tests. The sampler is POINT, so no filtering is being replaced.",
        expectation="6 image_sample down to 3 image instructions in the pixel shader"),

    # CalcLightingColor returns vLightColor * fNDotL * fDistFalloff, and both scalars come out
    # of a saturate, so lightPass is exactly +0 for every pixel the light cannot reach: facing
    # away, or past the end of the distance falloff. The shadow term - two 4x4 transforms, a
    # perspective divide, four texture taps and the bilinear weights, the largest single block
    # in this shader's ISA - then multiplies that zero. Skipping it is bit-exact for every
    # finite shadow term, and a non-finite one would show up in the byte-exact oracle as a
    # changed pixel rather than pass unnoticed.
    "zeroskip_shadow": dict(
        kind="early_out_on_exact_zero",
        pattern_provenance="transferred from phase 2P, not derived from w4's ISA alone; counted "
                           "separately in the report for that reason",
        edits=[("src/ShadowsAndScenePass.hlsl",
                b"""        if (sampleShadowMap && i == 0)
""",
                b"""        if (sampleShadowMap && i == 0 && any(lightPass != 0.0f))
""")],
        equivalence="0 * x == 0 for every finite x, so the result is bit-identical wherever the "
                    "shadow term is finite. Where it would not be, the images differ and the "
                    "byte-exact oracle rejects: the rule is not being assumed away.",
        expectation="the shadow block skipped on every wave whose lanes are all unlit"),

    "vs_lightspace": dict(
        kind="hoist_uniform_transform_to_vertex_stage",
        targets_block="shadow address math",
        block_share_of_ceiling_pct=58,
        predicted_delta_pct=[-3.0, -1.8],
        predicted_correctness="FAIL tier A and tier B: the shadow depth test is a hard "
                              "comparison and interpolating the light-space position flips it on "
                              "boundary pixels",
        edits=[(PS,
                b"""    float3 normal : NORMAL;
    float3 tangent : TANGENT;
""",
                b"""    float3 normal : NORMAL;
    float3 tangent : TANGENT;
    float4 lightspacepos : TEXCOORD1;
"""),
               (PS,
                b"""    result.uv = uv;
    result.normal = normal;
    result.tangent = tangent;
""",
                b"""    result.uv = uv;
    result.normal = normal;
    result.tangent = tangent;

    // lights[0].view and lights[0].projection are uniform for the whole draw, so this is a
    // linear function of the world position and perspective-correct interpolation reproduces it
    // at every pixel - to within floating-point rounding, which is the whole question.
    result.lightspacepos = mul(mul(result.worldpos, lights[0].view), lights[0].projection);
"""),
               (PS,
                b"""            lightPass *= CalcUnshadowedAmountPCF2x2(i, input.worldpos);
""",
                b"""            lightPass *= CalcUnshadowedAmountPCF2x2LightSpace(input.lightspacepos);
"""),
               # The pixel-side half, one replacement inside the LF region of the file. The
               # original signature stays, delegating through a forward declaration, so
               # Glass.hlsl - which includes this header and calls it - is unaffected.
               (CH,
                b"""float4 CalcUnshadowedAmountPCF2x2(int lightIndex, float4 vPosWorld)
{
    // Compute pixel position in light space.
    float4 vLightSpacePos = vPosWorld;
    vLightSpacePos = mul(vLightSpacePos, lights[lightIndex].view);
    vLightSpacePos = mul(vLightSpacePos, lights[lightIndex].projection);

    vLightSpacePos.xyz /= vLightSpacePos.w;
""",
                b"""float4 CalcUnshadowedAmountPCF2x2LightSpace(float4 vLightSpacePos);

float4 CalcUnshadowedAmountPCF2x2(int lightIndex, float4 vPosWorld)
{
    float4 vLightSpacePos = vPosWorld;
    vLightSpacePos = mul(vLightSpacePos, lights[lightIndex].view);
    vLightSpacePos = mul(vLightSpacePos, lights[lightIndex].projection);
    return CalcUnshadowedAmountPCF2x2LightSpace(vLightSpacePos);
}

float4 CalcUnshadowedAmountPCF2x2LightSpace(float4 vLightSpacePos)
{
    vLightSpacePos.xyz /= vLightSpacePos.w;
""")],
        equivalence="mathematically identical: the composition of two uniform matrices applied to "
                    "a position that is itself linearly interpolated. Not bitwise identical, and "
                    "the difference lands on a hard comparison.",
        expectation="two 4x4 transforms out of the pixel shader, four interpolants in"),

    # ---------------------------------------------------------------- ceiling decomposition
    # DIAGNOSTICS, never candidates. Each removes one block of the hot pixel shader and keeps
    # the others alive, so the shares add up to something that can be compared with ablate_ps.

    # Block B: the normal map fetch and the tangent frame. pixelNormal stays a unit vector so
    # the lighting math downstream is unchanged in shape.
    "abl_normalmap": dict(
        kind="diagnostic_block", candidate=False,
        edits=[(PS,
                b"""    float3 pixelNormal = CalcPerPixelNormal(input.uv, input.normal, input.tangent);
""",
                b"""    float3 pixelNormal = normalize(input.normal);
""")],
        equivalence="none: diagnostic",
        expectation="removes 1 image_sample, 3 rsq and the 3x3 tangent-to-world transform"),

    # Block C: the per-light distance and N.L math. pixelNormal is still consumed, so block B
    # cannot be dead-coded along with it.
    "abl_lightmath": dict(
        kind="diagnostic_block", candidate=False,
        edits=[(PS,
                b"""        float4 lightPass = CalcLightingColor(lights[i].position, lights[i].direction, lights[i].color, lights[i].falloff, input.worldpos.xyz, pixelNormal);
""",
                b"""        float4 lightPass = lights[i].color * saturate(pixelNormal.y);
""")],
        equivalence="none: diagnostic",
        expectation="removes the length, the reciprocal, the two falloffs and the N.L dot"),

    # Block D: the whole shadow term - two 4x4 transforms, a perspective divide, four texture
    # taps and the bilinear weights.
    "abl_shadow": dict(
        kind="diagnostic_block", candidate=False,
        edits=[(PS,
                b"""        if (sampleShadowMap && i == 0)
        {
            lightPass *= CalcUnshadowedAmountPCF2x2(i, input.worldpos);
        }
""",
                b"""""")],
        equivalence="none: diagnostic",
        expectation="removes 4 image_sample and roughly 60 VALU"),

    # Block D split: the four taps removed, the address math that feeds them kept alive by
    # consuming the transformed depth. Separates texture cost from transform cost inside D.
    "abl_shadow_taps": dict(
        kind="diagnostic_block", candidate=False,
        edits=[("src/Common.hlsli",
               b"""        vShadowDepths.x = shadowMap.Sample(sampleClamp, vShadowTexCoord).x;
        vShadowDepths.y = shadowMap.Sample(sampleClamp, vShadowTexCoord + float2(vTexelUnits.x, 0.0f)).x;
        vShadowDepths.z = shadowMap.Sample(sampleClamp, vShadowTexCoord + float2(0.0f, vTexelUnits.y)).x;
        vShadowDepths.w = shadowMap.Sample(sampleClamp, vShadowTexCoord + vTexelUnits).x;
""",
               b"""        vShadowDepths = (float4)saturate(vLightSpaceDepth);
""")],
        equivalence="none: diagnostic",
        expectation="removes 4 image_sample, keeps both 4x4 transforms and the divide"),

    # DIAGNOSTIC, not a candidate: the entire lighting body removed, so the pass keeps its
    # geometry, its rasterisation and its one diffuse fetch and loses everything a source
    # transformation could ever touch. Its image is deliberately wrong.
    "ablate_ps": dict(
        kind="diagnostic_upper_bound",
        candidate=False,
        edits=[("src/ShadowsAndScenePass.hlsl",
                b"""    float4 diffuseColor = diffuseMap.Sample(sampleWrap, input.uv);
    float3 pixelNormal = CalcPerPixelNormal(input.uv, input.normal, input.tangent);
    float4 totalLight = ambientColor;

    for (int i = 0; i < NUM_LIGHTS; i++)
    {
        float4 lightPass = CalcLightingColor(lights[i].position, lights[i].direction, lights[i].color, lights[i].falloff, input.worldpos.xyz, pixelNormal);
        if (sampleShadowMap && i == 0)
        {
            lightPass *= CalcUnshadowedAmountPCF2x2(i, input.worldpos);
        }
        totalLight += lightPass;
    }

    return diffuseColor * saturate(totalLight);
""",
                b"""    float4 diffuseColor = diffuseMap.Sample(sampleWrap, input.uv);
    return diffuseColor;
""")],
        equivalence="none: the image is deliberately different. This measures a ceiling, not a "
                    "candidate.",
        expectation="the largest speed-up any change to this shader's body could produce"),
}


UA_PS = "src/shader_mesh_dynamic_indexing_pixel.hlsl"

# U-A's ceiling probe, and nothing else yet: the 2U preregistration runs the probe before any
# hypothesis and closes the workload if the ceiling is under 3 %.
UB_TRANSFORMS = {
    "shadow_tmax": dict(
        kind="ray_extent_reduction",
        targets_block="shadow ray",
        block_share_of_ceiling_pct=55,
        predicted_delta_pct=[-20.0, -5.0],
        predicted_correctness="tier A PASS; conditional on the scene, not algebraic",
        edits=[(UB_HLSL,
                b"""    rayDesc.TMin = 0;
    rayDesc.TMax = 10000;

    // Initialize shadow ray payload.
""",
                b"""    rayDesc.TMin = 0;
    // The shadow ray is aimed at the light and only asks whether anything blocks it, so nothing
    // beyond the light can shadow this point. Its origin is the hit position, by construction at
    // both call sites.
    rayDesc.TMax = length(g_sceneCB.lightPosition.xyz - ray.origin);

    // Initialize shadow ray payload.
""")],
        equivalence="conditional, not algebraic: identical image if and only if no geometry lies "
                    "between the light and t = 10000 along any shadow ray. abl_shadowray is the "
                    "positive control that the oracle sees this flag at all.",
        expectation="shadow-ray traversal bounded by the light distance instead of 10000"),

    "hitpos_reuse": dict(
        kind="cse_across_traceray",
        targets_block="closest-hit arithmetic",
        block_share_of_ceiling_pct=1,
        predicted_delta_pct=[0.0, 2.0],
        predicted_correctness="tier A PASS, bit-exact by construction",
        edits=[(UB_HLSL,
                b"""    float checkers = AnalyticalCheckersTexture(HitWorldPosition(), triangleNormal, g_sceneCB.cameraPosition.xyz, g_sceneCB.projectionToWorld);
""",
                b"""    float checkers = AnalyticalCheckersTexture(hitPosition, triangleNormal, g_sceneCB.cameraPosition.xyz, g_sceneCB.projectionToWorld);
"""),
               (UB_HLSL,
                b"""        Ray reflectionRay = { HitWorldPosition(), reflect(WorldRayDirection(), triangleNormal) };
""",
                b"""        Ray reflectionRay = { hitPosition, reflect(WorldRayDirection(), triangleNormal) };
"""),
               (UB_HLSL,
                b"""        Ray reflectionRay = { HitWorldPosition(), reflect(WorldRayDirection(), attr.normal) };
""",
                b"""        Ray reflectionRay = { hitPosition, reflect(WorldRayDirection(), attr.normal) };
""")],
        equivalence="bit-exact: HitWorldPosition() is a pure function of intrinsics DXR restores "
                    "after a TraceRay, so every evaluation returns the same value",
        expectation="three redundant evaluations removed, more live state across TraceRay"),

    "ablate_ch": dict(
        kind="diagnostic_ceiling", candidate=False,
        edits=[(UB_HLSL,
                b"""void MyClosestHitShader_Triangle(inout RayPayload rayPayload, in BuiltInTriangleIntersectionAttributes attr)
{
""",
                b"""void MyClosestHitShader_Triangle(inout RayPayload rayPayload, in BuiltInTriangleIntersectionAttributes attr)
{
    rayPayload.color = l_materialCB.albedo; return;
"""),
               (UB_HLSL,
                b"""void MyClosestHitShader_AABB(inout RayPayload rayPayload, in ProceduralPrimitiveAttributes attr)
{
""",
                b"""void MyClosestHitShader_AABB(inout RayPayload rayPayload, in ProceduralPrimitiveAttributes attr)
{
    rayPayload.color = l_materialCB.albedo; return;
""")],
        equivalence="none: diagnostic",
        expectation="everything a source change to the shading could ever give up"),

    "abl_shadowray": dict(
        kind="diagnostic_block", candidate=False,
        edits=[(UB_HLSL,
                b"""    bool shadowRayHit = TraceShadowRayAndReportIfHit(shadowRay, rayPayload.recursionDepth);

    float checkers""",
                b"""    bool shadowRayHit = false;

    float checkers"""),
               (UB_HLSL,
                b"""    bool shadowRayHit = TraceShadowRayAndReportIfHit(shadowRay, rayPayload.recursionDepth);

    // Reflected component.""",
                b"""    bool shadowRayHit = false;

    // Reflected component.""")],
        equivalence="none: diagnostic",
        expectation="one TraceRay per hit removed"),

    "abl_reflection": dict(
        kind="diagnostic_block", candidate=False,
        edits=[(UB_HLSL,
                b"""    if (l_materialCB.reflectanceCoef > 0.001 )
""",
                b"""    if (false)
"""),
               (UB_HLSL,
                b"""    if (l_materialCB.reflectanceCoef > 0.001)
""",
                b"""    if (false)
""")],
        equivalence="none: diagnostic",
        expectation="the recursive radiance ray removed"),

    "abl_phong": dict(
        kind="diagnostic_block", candidate=False,
        edits=[(UB_HLSL,
                b"""    float4 phongColor = CalculatePhongLighting(l_materialCB.albedo, triangleNormal, shadowRayHit, l_materialCB.diffuseCoef, l_materialCB.specularCoef, l_materialCB.specularPower);
""",
                b"""    float4 phongColor = l_materialCB.albedo * (shadowRayHit ? 0.5f : 1.0f);
"""),
               (UB_HLSL,
                b"""    float4 phongColor = CalculatePhongLighting(l_materialCB.albedo, attr.normal, shadowRayHit, l_materialCB.diffuseCoef, l_materialCB.specularCoef, l_materialCB.specularPower);
""",
                b"""    float4 phongColor = l_materialCB.albedo * (shadowRayHit ? 0.5f : 1.0f);
""")],
        equivalence="none: diagnostic",
        expectation="the Phong evaluation gone, both secondary rays kept"),
}

UA_TRANSFORMS = {
    "ablate_ps": dict(
        kind="diagnostic_ceiling", candidate=False,
        edits=[(UA_PS,
                b"""    float3 diffuse = g_txDiffuse.Sample(g_sampler, input.uv).rgb;
    float3 mat = g_txMats[materialConstants.matIndex].Sample(g_sampler, input.uv).rgb;
    return float4(diffuse * mat, 1.0f);
""",
                b"""    return float4(input.uv.x, input.uv.y, 0.5f, 1.0f);
""")],
        equivalence="none: diagnostic, the image is deliberately wrong",
        expectation="both texture samples and the multiply gone; the ceiling on anything this "
                    "pixel shader could ever give up"),
}

TRANSFORM_SETS = {"w1": {}, "w2": W2_TRANSFORMS, "w3": {}, "w4": W4_TRANSFORMS,
                  "ua": UA_TRANSFORMS, "ub": UB_TRANSFORMS,
                  "uc": UC_TRANSFORMS}

WORKLOAD = "w1"
OUT = ROOT / "research/49_2t_w1"
DIRS = {"w1": "research/49_2t_w1", "w2": "research/50_2t_w2",
        "w3": "research/51_2t_w3", "w4": "research/52_2t_w4", "w5": "research/53_2t_w5",
        "ua": "research/53_2u_ua", "ub": "research/54_2u_ub", "uc": "research/55_2u_uc"}
TRANSFORMS = {}


def select(w):
    global WORKLOAD, OUT, TRANSFORMS
    G.require(w in WORKLOADS or w in DIRS, f"unknown workload {w}")
    WORKLOAD, OUT = w, ROOT / DIRS[w]
    TRANSFORMS = TRANSFORM_SETS.get(w, {})


def W():
    return WORKLOADS[WORKLOAD]


SDK_DXC = Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe")


def dxc():
    """The compiler the workload's own project uses, never a convenient one.

    Phase 2R lost two preregistrations to compiling with the wrong dxc; the workload says which.
    """
    if W().get("dxc") == "sdk":
        return SDK_DXC
    return (Path(os.environ["TEMP"]) /
            "claude/src/nbody/src/packages/Microsoft.Direct3D.DXC.1.8.2505.32/build/native/bin/x64/dxc.exe")


def dxil_from_header(path, var):
    """The bytes of a DXIL library embedded in a generated C header.

    The header also carries the disassembly inside an `#if 0` block, which is full of hex, so the
    array has to be located by its variable name and not by the first `=` in the file.
    """
    import re
    text = Path(path).read_text(errors="replace")
    m = re.search(re.escape(var) + r"\[\]\s*=\s*\{(.*?)\};", text, re.S)
    G.require(m is not None, f"{path}: no array {var}")
    return bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", m.group(1)))


def stage_pristine():
    """One pristine copy per workload, never built in, with the NuGet packages it needs.

    Most samples want the packages beside their project. A workload can instead declare `stage`,
    a list of repository-relative paths to copy with their layout preserved, for a project that
    resolves packages further up the tree.
    """
    dst = PRISTINE / W()["dir"]
    if dst.exists():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    if W().get("stage"):
        repo = SAMPLES.parents[1]
        for rel in W()["stage"]:
            shutil.copytree(repo / rel, dst / rel)
    else:
        shutil.copytree(SAMPLES / W()["dir"], dst)
        shutil.copytree(PKG_SRC, dst / "src/packages", dirs_exist_ok=True)
    return dst


def shader_root():
    """The directory the shader sources are addressed relative to: the primary shader's own."""
    first = next(iter(W()["shaders"].values()))[2]
    return Path(first).parent


def staged(rel):
    """Where a shader source lives inside a staging directory, keeping its subdirectories."""
    return Path(rel).relative_to(shader_root())


def source_rels():
    """Every source file a build may touch: shader entry points and the headers they include."""
    return {r for _, _, r in W()["shaders"].values()} | set(W().get("aux", []))


def variant_source(label, root):
    out = {}
    if label == "base":
        return out
    for rel, old, new in TRANSFORMS[label]["edits"]:
        src = out.get(rel) or (root / rel).read_bytes()
        out[rel] = once(src, old, new, f"{label}: anchor in {rel}")
    return out


def compile_shaders(root, stage, label):
    """Preregister every shader's bytecode with the compiler the project itself uses."""
    hashes = {}
    stage.mkdir(parents=True, exist_ok=True)
    patched = variant_source(label, root)
    for cso, (target, entry, rel) in W()["shaders"].items():
        src = stage / staged(rel)
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(patched.get(rel) or (root / rel).read_bytes())
        others = {r for _, _, r in W()["shaders"].values()} - {rel}
        for other in others | set(W().get("aux", [])):
            o = stage / staged(other)
            o.parent.mkdir(parents=True, exist_ok=True)
            if not o.exists():
                o.write_bytes(patched.get(other) or (root / other).read_bytes())
        cmd = [dxc(), "-nologo", f"-T{target}"]
        if entry:
            cmd.append(f"-E{entry}")
        cmd += [str(a) for a in W().get("shader_flags", [])]
        cmd += ["-Fo", stage / cso, src]
        G.run_checked(cmd, stage, stage / f"dxc_{cso}.log", timeout=300)
        hashes[cso] = G.sha(stage / cso)
    return hashes


def instrument(work):
    for e in W()["edits"]:
        rel, old, new = e if len(e) == 3 else (W()["main"], e[0], e[1])
        f = work / rel
        # Bytes, not text: one of U-B's sources is Windows-1252, and an instrumentation pass has
        # no business re-encoding a file it is only inserting a line into.
        f.write_bytes(once(f.read_bytes(), old, new, f"instrumentation {rel}"))
    # next to every file that includes it, whatever the project layout is
    for rel in {e[0] if len(e) == 3 else W()["main"] for e in W()["edits"]}:
        shutil.copy2(ROOT / "tools/t_probe.h", (work / rel).parent / "TProbe.h")
    # Debug info out of the shader blobs so their hashes are the shaders and nothing else.
    proj = work / W()["proj"]
    # Bytes again: the project file keeps whatever encoding and BOM it shipped with.
    proj.write_bytes(proj.read_bytes().replace(b" -Zi -Qembed_debug", b""))
    return [dict(path=str(p), sha256=G.sha(p)) for p in sorted(work.rglob("*"))
            if p.is_file() and p.suffix.lower() in (".cpp", ".h", ".hlsl", ".hlsli", ".vcxproj")]


def prepare(criteria):
    OUT.mkdir(exist_ok=False)
    root = stage_pristine()
    eid = f"T_{WORKLOAD.upper()}_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(os.environ["TEMP"]) / "claude" / eid
    shutil.copytree(root, work)
    expected = {}
    for label in ["base"] + sorted(TRANSFORMS):
        expected[label] = compile_shaders(root, OUT / "preregistered" / label, label)
    rows = instrument(work)
    with (OUT / "instrumented_source_hashes.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "sha256"]); w.writeheader(); w.writerows(rows)
    (OUT / "baseline_sources").mkdir()
    for rel in source_rels():
        dst = OUT / "baseline_sources" / staged(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(work / rel, dst)
    G.save_json(OUT / "experiment_manifest.json", dict(
        experiment_id=eid, created_at=datetime.now().astimezone().isoformat(), phase="2T",
        workload=WORKLOAD, workload_name=W()["name"], workspace=str(work),
        original_source=str(root), dxc=str(dxc()), msbuild=str(MSBUILD),
        configuration="Release/x64/v145", regions=W()["regions"],
        primary_region=W()["primary_region"], expected_bytecode=expected,
        transforms={k: {kk: vv for kk, vv in v.items() if kk != "edits"}
                    for k, v in TRANSFORMS.items()},
        transform_edits={k: [[rel, old.decode(), new.decode()] for rel, old, new in v["edits"]]
                         for k, v in TRANSFORMS.items()},
        preregistered_criteria=criteria))
    print("prepared", work, flush=True)


def preregister():
    """Add expected bytecode for transforms declared after this workload's prepare.

    Append-only: an entry already in the manifest is never rewritten, so the gate a build is
    judged against cannot be moved after the fact.
    """
    m = manifest()
    root = stage_pristine()
    added = []
    for label in sorted(TRANSFORMS):
        if label in m["expected_bytecode"]:
            continue
        m["expected_bytecode"][label] = compile_shaders(root, OUT / "preregistered" / label, label)
        m.setdefault("transforms", {})[label] = {k: v for k, v in TRANSFORMS[label].items()
                                                 if k != "edits"}
        m.setdefault("transform_edits", {})[label] = [[rel, old.decode(), new.decode()]
                                                      for rel, old, new in TRANSFORMS[label]["edits"]]
        m.setdefault("preregistered_at", {})[label] = datetime.now().astimezone().isoformat()
        added.append(label)
    G.require(added, "nothing new to preregister")
    keep = OUT / "experiment_manifest.prepare.json"
    if not keep.exists():
        shutil.copy2(OUT / "experiment_manifest.json", keep)
    (OUT / "experiment_manifest.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    for label in added:
        print(label + ": " + " ".join(f"{k}={v[:8]}"
                                      for k, v in m["expected_bytecode"][label].items()), flush=True)


def manifest():
    return json.loads((OUT / "experiment_manifest.json").read_text())


def build(label):
    m = manifest()
    work = Path(m["workspace"]).resolve(strict=True)
    G.require(work.name == m["experiment_id"]
              and work.parent == (Path(os.environ["TEMP"]) / "claude").resolve(),
              "workspace is not this experiment's own copy")
    for rel in source_rels():
        (work / rel).write_bytes((OUT / "baseline_sources" / staged(rel)).read_bytes())
    try:
        for rel, data in variant_source(label, work).items():
            (work / rel).write_bytes(data)
            snap = OUT / "source_revisions" / label / staged(rel)
            snap.parent.mkdir(parents=True, exist_ok=True)
            if snap.exists():
                G.require(snap.read_bytes() == data, "variant source changed since first build")
            else:
                snap.write_bytes(data)
        # the output directory follows the project, not the solution
        proj_dir = (work / W()["proj"]).parent
        out = proj_dir / "bin/x64/Release"
        art = W().get("artifact")
        if art:
            # The library is compiled into a header and linked in, so the stale artefact to
            # remove is the header, not a .cso.
            h = proj_dir / art["rel"]
            if h.exists():
                h.unlink()
        elif out.exists():
            for f in out.glob("*.cso"):
                f.unlink()
        (OUT / "build_logs").mkdir(exist_ok=True)
        n = 1
        while (OUT / "build_logs" / f"{label}.{n}.log").exists():
            n += 1
        G.run_checked([MSBUILD, work / W()["proj"], "/p:Configuration=Release", "/p:Platform=x64",
                       "/p:PlatformToolset=v145", "/v:minimal", "/nologo"],
                      proj_dir, OUT / "build_logs" / f"{label}.{n}.log", timeout=1800)
        if art:
            data = dxil_from_header(proj_dir / art["rel"], art["var"])
            got = {cso: G.sha_bytes(data) for cso in W()["shaders"]}
        else:
            got = {cso: G.sha(out / cso) for cso in W()["shaders"]}
        for cso, h in got.items():
            G.require(h == m["expected_bytecode"][label][cso],
                      f"{label}/{cso}: {h[:12]} != preregistered "
                      f"{m['expected_bytecode'][label][cso][:12]}")
        exe = next(out.glob("*.exe"))
        home = OUT / "builds" / label
        if home.exists():
            shutil.rmtree(home)
        shutil.copytree(out, home)
        artifact = dict(variant=label, executable=str(home / exe.name),
                        executable_sha256=G.sha(home / exe.name), shaders=got)
        rec = OUT / f"build_{label}.json"
        if rec.exists():
            G.require(json.loads(rec.read_text())["shaders"] == got, "rebuild changed a shader")
            rec.unlink()
        G.save_json(rec, artifact)
        print(f"{label}: " + " ".join(f"{k}={v[:8]}" for k, v in got.items())
              + f" exe {artifact['executable_sha256'][:12]}", flush=True)
    finally:
        for rel in source_rels():
            (work / rel).write_bytes((OUT / "baseline_sources" / staged(rel)).read_bytes())


def run(label, rep, iters, warm):
    m = manifest()
    a = json.loads((OUT / f"build_{label}.json").read_text())
    G.require(G.sha(a["executable"]) == a["executable_sha256"], "executable changed since build")
    folder = OUT / "runs" / f"{label}_r{rep}"
    folder.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("T_", "ME_", "NB_", "AMD_"))}
    env.update(T_DIR=str(folder), T_ITERS=str(iters), T_WARM=str(warm))
    proc = G.run_checked([a["executable"]] + list(W().get("args", [])),
                         Path(a["executable"]).parent,
                         folder / "process.log", env=env, timeout=1800)
    G.require((folder / "summary.json").is_file(), "run produced no summary")
    s = json.loads((folder / "summary.json").read_text())
    G.save_json(folder / "run.json", dict(variant=label, rep=rep, pid=proc["pid"], summary=s,
                                          target_sha256=G.sha(folder / "target.bin")
                                          if (folder / "target.bin").exists() else None,
                                          shaders=a["shaders"]))
    r = m["primary_region"]
    print(f"{label}_r{rep}: region{r} median {s[f'region{r}_median_ns']:.0f} ns"
          + (f", target {G.sha(folder / 'target.bin')[:12]}"
             if (folder / "target.bin").exists() else ""), flush=True)


def compare_target(a_tag, b_tag):
    import numpy as np
    x, y = [np.fromfile(OUT / "runs" / t / "target.bin", dtype=np.uint8) for t in (a_tag, b_tag)]
    G.require(x.shape == y.shape, "target shape mismatch")
    d = np.abs(x.astype(np.int16) - y.astype(np.int16))
    return dict(pair=[a_tag, b_tag], identical=bool(np.array_equal(x, y)),
                bytes=int(x.size), differing=int(np.count_nonzero(d)),
                max_abs_delta=int(d.max()),
                differing_fraction=float(np.mean(d != 0)))


def nearest(base_seq, ts):
    """The base run closest in wall-clock time to a variant run."""
    return min(base_seq, key=lambda p: abs(p[0] - ts))[1]


def analyse():
    m = manifest()
    r = m["primary_region"]
    data, timed = {}, {}
    for b in sorted(OUT.glob("build_*.json")):
        label = b.name[len("build_"):-len(".json")]
        vals, seq = [], []
        for rep in range(1, 40):
            f = OUT / "runs" / f"{label}_r{rep}" / "run.json"
            if f.is_file():
                vals.append(json.loads(f.read_text())["summary"][f"region{r}_median_ns"])
                seq.append((f.stat().st_mtime, vals[-1]))
        if vals:
            data[label], timed[label] = vals, seq
    line = "=" * 90
    print(line)
    print(f"1. {m['workload_name']}: region {r} = {m['regions'][str(r)]}, ns per frame")
    print(line)
    for label, v in data.items():
        print(f"   {label:16s} " + ", ".join(f"{x:.0f}" for x in v)
              + f"   median {statistics.median(v):.0f}")
    thr = None
    if "base" in data and len(data["base"]) > 1:
        v = [y for _, y in timed["base"]]
        pw = [abs(a - b) / ((a + b) / 2) * 100
              for i, (ta, a) in enumerate(timed["base"]) for tb, b in timed["base"][i + 1:]
              if abs(ta - tb) < 3600]
        thr = max(1.0, 3 * max(pw))
        print(f"\n   A/A on base: " + ", ".join(f"{x:.2f}%" for x in pw)
              + f"  -> N95 {max(pw):.2f}%, accept threshold {thr:.2f}%")
    print("\n" + line)
    print("2. RESPONSE, paired against base, and correctness")
    print(line)
    verdicts = {}
    for label, v in data.items():
        if label == "base" or "base" not in data:
            continue
        # Pair each run with the base run nearest to it in time. Rep numbers are not a pairing:
        # base_r1 and gather_r1 can be sessions apart, and this workload's base moved 1.2 %
        # between sessions.
        paired = [(y - nearest(timed["base"], ts)) / nearest(timed["base"], ts) * 100
                  for ts, y in timed[label]]
        k = len(paired)
        med = statistics.median(paired)
        perf = thr is not None and med <= -thr and all(p < 0 for p in paired) and k >= 3
        corr = None
        if (OUT / f"runs/{label}_r1/target.bin").exists() and (OUT / "runs/base_r1/target.bin").exists():
            corr = compare_target("base_r1", f"{label}_r1")
            corr["passed"] = corr["identical"]
        final = ("ACCEPTED" if perf and corr and corr["passed"] else
                 "REJECTED (correctness)" if corr and not corr["passed"] else
                 "REJECTED (performance)" if not perf else "incomplete")
        verdicts[label] = dict(median_pct=med, per_process=paired, performance_accepted=perf,
                               correctness=corr, final=final)
        print(f"   {label:16s} median {med:+7.2f} %   " + ", ".join(f"{p:+.2f}%" for p in paired)
              + (f"   image identical={corr['identical']}" if corr else "")
              + f"   -> {final}")
    G.save_json(OUT / f"analysis_{datetime.now().strftime('%H%M%S')}.json",
                dict(workload=m["workload_name"], region=m["regions"][str(r)],
                     medians_ns=data, threshold_pct=thr, verdicts=verdicts))
    print("\nwrote analysis json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "preregister", "build", "run", "analyse"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--workload", default="w1")
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--iters", type=int, default=500)
    ap.add_argument("--warm", type=int, default=200)
    a = ap.parse_args()
    select(a.workload)
    if a.action == "prepare":
        prepare(dict(
            provenance="every build is gated on the preregistered SHA-256 of every shader the "
                       "project compiles; the pristine sources are restored on every exit path",
            correctness="the sample's own render target after a fixed frame count, compared byte "
                        "for byte against the baseline's. Baseline vs baseline must be identical "
                        "first or nothing is judged against it",
            performance="median of the primary timestamp region, several independent processes, "
                        "counterbalanced order, paired against base",
            acceptance="median <= -max(1 %, 3 x N95) from this workload's own A/A control, every "
                       "paired process negative, and correctness passing"))
    elif a.action == "preregister":
        preregister()
    elif a.action == "build":
        build(a.name)
    elif a.action == "run":
        run(a.name, a.rep, a.iters, a.warm)
    else:
        analyse()
