"""O1 only: prepare, then A -> B -> A2. No timing collection or GPA.

python -B tools/run_o1.py prepare
python -B tools/run_o1.py A   (also a same-binary image repeat)
python -B tools/run_o1.py B
python -B tools/run_o1.py A2
"""
import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil

import buildv as G

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/24_phase2o_build_gate"
ORIGINAL = Path(os.environ["TEMP"]) / "claude/src/dxs"
DXC = Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe")
PS_REL = "MiniEngine/Model/Shaders/ModelViewerPS.hlsl"
CANARY_FROM, CANARY_TO = b"mrt.Color = colorSum;", b"mrt.Color = colorSum + float3(0.125, 0.0, 0.0);"
BASELINE_REPEATS = 3
# Single source of truth for the capture frame: the probe header the app is built with.
CAPTURE_FRAME = int(re.search(r"kCaptureFrame = (\d+)",
                              (ROOT / "tools/o1_probe.h").read_text(encoding="utf-8"))[1])


def precompile(dxc, stage):
    """Preregister, offline, the exact bytecode each stage must produce.

    Without this, stage B accepts *any* bytecode that merely differs from A, and the audit's
    "unexpected hash must be rejected" is never exercised by the experiment itself.
    """
    src = ORIGINAL / PS_REL
    baseline = src.read_bytes()
    G.require(baseline.count(CANARY_FROM) == 1, "canary match ambiguous")
    expected = {}
    for label, text in [("A", baseline), ("B", baseline.replace(CANARY_FROM, CANARY_TO))]:
        d = stage / label
        shutil.copytree(src.parent, d / "Shaders")
        (d / "Shaders" / src.name).write_bytes(text)
        (d / "Output/Model/CompiledShaders").mkdir(parents=True)
        G.run_checked([dxc, "-nologo", "-E", "main", "-T", "ps_6_2", "-D", "_GAMING_DESKTOP=1",
                       "-Fh", d / "Output/Model/CompiledShaders/ModelViewerPS.h",
                       "-Vn", "g_pModelViewerPS", "-HV", "2021", d / "Shaders" / src.name],
                      d / "Shaders", stage / f"dxc_{label}.log", timeout=120)
        expected[label] = G.shader_artifact(d)
    G.require(expected["A"]["bytecode_sha256"] != expected["B"]["bytecode_sha256"],
              "canary does not change the bytecode")
    return expected


def replace_once(path, old, new, out=None):
    # Preserve every pre-edit revision in the experiment, never delete or overwrite it.
    out = OUT if out is None else out
    b = path.read_bytes()
    text = b.decode("utf-8-sig")
    if "\r\n" in text:  # raw decode keeps CRLF: match and insert in the file's own ending
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    G.require(text.count(old) == 1, f"patch not unique: {path}: {old[:70]}")
    backup = out / "source_revisions" / (path.name + "." + G.sha(path))
    backup.parent.mkdir(exist_ok=True)
    if not backup.exists():
        backup.write_bytes(b)
    path.write_text(text.replace(old, new), encoding="utf-8", newline="")


def prepare():
    OUT.mkdir(exist_ok=False)
    eid = "O1_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(os.environ["TEMP"]) / "claude" / eid
    work.mkdir(exist_ok=False)
    expected = precompile(DXC, OUT / "preregistered")
    manifest = dict(expected_bytecode={k: v["bytecode_sha256"] for k, v in expected.items()},
                    expected_artifacts=expected,
                    experiment_id=eid, created_at=datetime.now().astimezone().isoformat(),
                    original_source=str(ORIGINAL), workspace=str(work), dxc_selected=str(DXC),
                    historical_custom_hash="52CE6C5E64AB2E82",
                    sequence=["A", "B", "A2"], capture_frame_index=CAPTURE_FRAME,
                    baseline_repeats=BASELINE_REPEATS,
                    canary="mrt.Color = colorSum + float3(0.125, 0.0, 0.0);",
                    workload=f"Sponza 1920x1080; capture at frame {CAPTURE_FRAME} "
                             "(after all 128 light shadow slices); no performance verdict",
                    configuration="Profile/x64/v145",
                    # Confirmed nondeterminism in the baseline: FillLightGridCS.hlsli assigns
                    # per-tile light slots with InterlockedAdd, and Lighting.hlsli accumulates
                    # colorSum in that order, so the float sum order varies between runs. The
                    # baseline is therefore CHARACTERISED, not gated at 1 ULP; the canary must
                    # stand far above the measured baseline spread.
                    oracle_policy={"baseline_repeats":BASELINE_REPEATS,
                                   "canary_min_changed_pixel_fraction":0.10,
                                   "canary_min_ratio_over_baseline_spread":20.0,
                                   "canary_min_positive_red_fraction":0.10,
                                   "canary_max_baseline_changed_pixel_fraction":0.005,
                                   "finite_only":True},
                    gpu_perf_api=False, timing_export=False,
                    workspace_budget_bytes=8_000_000_000,
                    source_modification_policy="instrumented copy only; original clone and build unchanged")
    G.save_json(OUT/"experiment_manifest.json", manifest)
    # Copies, not hardlinks/junctions: runtime or build cannot write historical files.
    with (OUT/"input_hashes.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["source", "copy", "bytes", "sha256"])
        total = 0
        for area in ["MiniEngine", "Packages", "vcpkg", "vcpkg_installed"]:
            for source in sorted((ORIGINAL/area).rglob("*")):
                if not source.is_file() or (area == "MiniEngine" and
                    source.relative_to(ORIGINAL/area).parts[0] == "Build"):
                    continue
                # Not needed by the Profile app; don't copy vcpkg build trees/debug libraries.
                if area == "vcpkg_installed" and any(x in source.parts for x in ["debug", "tools"]):
                    continue
                target = work/source.relative_to(ORIGINAL)
                h = G.sha(source)  # before copying any binary/resource
                total += source.stat().st_size
                G.require(total < 3_000_000_000, "input copy budget exceeded")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                G.require(G.sha(target) == h, "copy integrity failure")
                w.writerow([str(source), str(target), source.stat().st_size, h])
        shutil.copy2(ORIGINAL/"vcpkg.json", work/"vcpkg.json")
        for p in [ORIGINAL/"vcpkg.json", ROOT/"tools/buildv.py", ROOT/"tools/run_o1.py", ROOT/"tools/o1_probe.h"]:
            w.writerow([str(p), "", p.stat().st_size, G.sha(p)])
    instrument(work, OUT)
    finish_prepare(work, OUT)
def instrument(work, out, o2=False):
    """Apply the frozen-workload instrumentation to a workspace copy. Shared by O1 and O2."""
    R = lambda *a: replace_once(*a, out=out)
    me = work/"MiniEngine"
    props = me/"PropertySheets/Build.props"
    old = "$(SolutionDir)..\\Build\\$(Platform)\\$(Configuration)"
    # All five output/include locations are project-specific under the stage root.
    text = props.read_text(encoding="utf-8-sig")
    G.require(text.count(old) == 4, "unexpected Build.props output layout")
    (out/"Build.props.before").write_bytes(props.read_bytes())
    props.write_text(text.replace(old, "$(O1BuildRoot)"), encoding="utf-8", newline="")
    model = me/"Model/Model.vcxproj"
    R(model, '<FxCompile Include="Shaders\\ModelViewerPS.hlsl">',
                 '<FxCompile Include="Shaders\\ModelViewerPS.hlsl">\n      <ExcludedFromBuild>true</ExcludedFromBuild>')
    # Observe PSO per command context; getter also verifies native cached identity.
    cc = me/"Core/CommandContext.h"
    R(cc, '    void SetPipelineState( const PSO& PSO );',
        '    void SetPipelineState( const PSO& PSO );\n'
        '    const PSO* GetObservedPSO() const { return m_ObservedPSO &&\n'
        '        m_ObservedPSO->GetPipelineStateObject() == m_CurPipelineState ? m_ObservedPSO : nullptr; }')
    R(cc, '    ID3D12PipelineState* m_CurPipelineState;',
                 '    ID3D12PipelineState* m_CurPipelineState;\n    const PSO* m_ObservedPSO = nullptr;')
    R(cc, '    ID3D12PipelineState* PipelineState = PSO.GetPipelineStateObject();',
                 '    m_ObservedPSO = &PSO;\n    ID3D12PipelineState* PipelineState = PSO.GetPipelineStateObject();')
    shutil.copy2(ROOT/"tools/o1_probe.h", me/"Core/O1Probe.h")
    sponza = me/"Model/SponzaRenderer.cpp"
    R(sponza, '#include "SponzaRenderer.h"', '#include "SponzaRenderer.h"\n#include "O1Probe.h"')
    R(sponza, '        gfxContext.DrawIndexed(indexCount, startIndex, baseVertex);',
        '        gfxContext.DrawIndexed(indexCount, startIndex, baseVertex);\n'
        '        if (gfxContext.GetObservedPSO() == &m_ModelPSO || gfxContext.GetObservedPSO() == &m_CutoutModelPSO)\n'
        '            O1Probe::Draw(gfxContext, indexCount);')
    R(sponza,
        '                RenderObjects( gfxContext, camera.GetViewProjMatrix(), camera.GetPosition(), Sponza::kCutout );',
        '                RenderObjects( gfxContext, camera.GetViewProjMatrix(), camera.GetPosition(), Sponza::kCutout );\n'
        '                O1Probe::Capture(gfxContext);')
    viewer = me/"ModelViewer/ModelViewer.cpp"
    R(viewer, '    SSAO::Enable = true;',
        '    SSAO::Enable = true;\n'
        '    if (getenv("ME_O1_DIR")) {\n'
        '        TemporalEffects::EnableTAA = false; MotionBlur::Enable = false;\n'
        '        PostEffects::EnableAdaptation = false; SSAO::AsyncCompute = false;\n    }')
    R(viewer, '    m_CameraController->Update(deltaT);',
                 '    if (!getenv("ME_O1_DIR")) m_CameraController->Update(deltaT);\n'
                 '    else m_Camera.Update();')
    # Full-precision diagnostic target for phase 2Q, selected at runtime. Off by default, so
    # every earlier cycle's behaviour is unchanged; with ME_Q_R32 the scene colour buffer is
    # created as R32G32B32A32_FLOAT and the probe captures float32 instead of a quantised
    # R11G11B10 image.
    R(me/"Core/BufferManager.cpp",
      '        g_SceneColorBuffer.Create( L"Main Color Buffer", bufferWidth, bufferHeight, 1, DefaultHdrColorFormat, esram );',
      '        g_SceneColorBuffer.Create( L"Main Color Buffer", bufferWidth, bufferHeight, 1,\n'
      '            getenv("ME_Q_R32") ? DXGI_FORMAT_R32G32B32A32_FLOAT : DefaultHdrColorFormat, esram );')
    game = me/"Core/GameCore.cpp"
    R(game, '#include "GameCore.h"', '#include "GameCore.h"\n#include "O1Probe.h"')
    R(game, '        float DeltaTime = Graphics::GetFrameTime();',
                 '        float DeltaTime = O1Probe::Enabled() ? 1.0f / 60.0f : Graphics::GetFrameTime();')
    R(game, '        GameInput::Update(DeltaTime);\n        EngineTuning::Update(DeltaTime);',
                 '        if (!O1Probe::Enabled()) { GameInput::Update(DeltaTime); EngineTuning::Update(DeltaTime); }')
    R(game, '        game.RenderScene();',
                 '        game.RenderScene();\n'
                 '        if (O1Probe::TargetFrame()) { O1Probe::Save(); return false; }')
    R(game, '        GpaProfiler::Initialize(g_CommandManager.GetCommandQueue());',
                 '        if (!O1Probe::Enabled()) GpaProfiler::Initialize(g_CommandManager.GetCommandQueue());')
    if o2:
        # O2 hooks. Everything below is inert unless ME_O2_DIR is set at run time, so a binary
        # built with them behaves exactly like the O1 one when it is not.
        shutil.copy2(ROOT / "tools/o2_gpa.h", me / "Core/O2Gpa.h")
        # The GPA include directory is declared only in Core.vcxproj; Model and ModelViewer
        # also compile O2Gpa.h now, so put it in the property sheet all four projects import.
        gpa_inc = Path(os.environ["TEMP"]) / "claude/gpa/4_4/include"
        R(props, '<AdditionalIncludeDirectories>..\Core;%(AdditionalIncludeDirectories)',
          f'<AdditionalIncludeDirectories>..\Core;{gpa_inc};%(AdditionalIncludeDirectories)')
        R(viewer, '#include "SponzaRenderer.h"', '#include "SponzaRenderer.h"\n#include "O2Gpa.h"')
        R(game, '#include "O1Probe.h"', '#include "O1Probe.h"\n#include "O2Gpa.h"')
        R(game,
          '        if (!O1Probe::Enabled()) GpaProfiler::Initialize(g_CommandManager.GetCommandQueue());',
          '        if (!O1Probe::Enabled() && !O2Gpa::Enabled())\n'
          '            GpaProfiler::Initialize(g_CommandManager.GetCommandQueue());\n'
          '        O2Gpa::Initialize(g_CommandManager.GetCommandQueue());')
        R(game, '        if (O1Probe::TargetFrame()) { O1Probe::Save(); return false; }',
          '        if (O1Probe::TargetFrame()) { O1Probe::Save(); return false; }\n'
          '        if (O2Gpa::EndFrame()) return false;')
        R(game,
          '        float DeltaTime = O1Probe::Enabled() ? 1.0f / 60.0f : Graphics::GetFrameTime();',
          '        float DeltaTime = (O1Probe::Enabled() || O2Gpa::Enabled())\n'
          '            ? 1.0f / 60.0f : Graphics::GetFrameTime();')
        R(game,
          '        if (!O1Probe::Enabled()) { GameInput::Update(DeltaTime); EngineTuning::Update(DeltaTime); }',
          '        if (!O1Probe::Enabled() && !O2Gpa::Enabled())\n'
          '        { GameInput::Update(DeltaTime); EngineTuning::Update(DeltaTime); }')
        # Same frozen scene as O1: no TAA jitter, no motion blur, no exposure adaptation.
        R(viewer, '    if (getenv("ME_O1_DIR")) {',
          '    if (getenv("ME_O1_DIR") || getenv("ME_O2_DIR")) {')
        R(viewer, '    if (!getenv("ME_O1_DIR")) m_CameraController->Update(deltaT);',
          '    if (!getenv("ME_O1_DIR") && !getenv("ME_O2_DIR")) m_CameraController->Update(deltaT);')
        R(viewer, '    GraphicsContext& gfxContext = GraphicsContext::Begin(L"Scene Render");',
          '    GraphicsContext& gfxContext = GraphicsContext::Begin(L"Scene Render");\n'
          '    O2Gpa::OnContextBegin(gfxContext);')
        # gfxContext.Finish() appears twice in this file (Scene Update and Scene Render).
        # Anchor on the last statement of the render path so the wrong context is not closed.
        R(viewer, '        MotionBlur::RenderObjectBlur(gfxContext, g_VelocityBuffer);\n\n    gfxContext.Finish();',
          '        MotionBlur::RenderObjectBlur(gfxContext, g_VelocityBuffer);\n\n'
          '    O2Gpa::OnContextEnd(gfxContext);\n    gfxContext.Finish();')
        R(sponza, '#include "O1Probe.h"', '#include "O1Probe.h"\n#include "O2Gpa.h"')
        R(sponza, '                ScopedTimer _prof2(L"Render Color", gfxContext);',
          '                ScopedTimer _prof2(L"Render Color", gfxContext);\n'
          '                O2Gpa::Scope _o2gpa(gfxContext);')
    return me


def finish_prepare(work, out):
    """Freeze the baseline HLSL and hash every instrumented source, for both O1 and O2."""
    me = work / "MiniEngine"
    # Immutable baseline bytes for the only HLSL edit in this experiment.
    (out/"baseline_ModelViewerPS.hlsl").write_bytes((work/PS_REL).read_bytes())
    with (out/"instrumented_source_hashes.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["path", "sha256"])
        for q in sorted(me.rglob("*")):
            if q.is_file() and q.suffix in [".cpp", ".h", ".hlsl", ".hlsli", ".props", ".vcxproj"]:
                w.writerow([str(q), G.sha(q)])
    print("Prepared", work, flush=True)


def runtime(work, tag, artifact, manifest):
    folder = OUT/"runs"/tag
    folder.mkdir(parents=True, exist_ok=False)
    # The process that runs must be the exact binary build() verified, not a later relink.
    G.require(G.sha(artifact["executable"]) == artifact["executable_sha256"],
              "executable changed between build and run")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("ME_", "AMD_", "SC_"))}
    env["ME_O1_DIR"] = str(folder)
    process = G.run_checked([artifact["executable"]], work/"MiniEngine/ModelViewer",
                            folder/"process.log", env=env, timeout=300)
    frame = manifest["capture_frame_index"]
    rows = G.verify_runtime(folder/"runtime.csv", artifact)
    G.require(all(int(r["pid"]) == process["pid"] and int(r["frame"]) == frame for r in rows),
              "wrong process/frame in runtime inventory")
    image = json.loads((folder/"image.json").read_text())
    G.require(image["pid"] == process["pid"] and image["frame_index"] == frame and
              image["dxgi_format"] == 26 and image["width"] == 1920 and image["height"] == 1080 and
              (folder/"color.bin").stat().st_size == image["width"]*image["height"]*4,
              "image metadata/data mismatch")
    return dict(tag=tag, pid=process["pid"], draws=len(rows), image=image,
                image_sha256=G.sha(folder/"color.bin"), runtime_custom_hash=artifact["custom_hash"])


def decode(channel, bits):
    """One R11G11B10_FLOAT channel to float32: unsigned, 5-bit exponent, bias 15."""
    import numpy as np
    mbits = bits - 5
    e = (channel >> mbits).astype(np.int32)
    m = (channel & ((1 << mbits) - 1)).astype(np.float32) / (1 << mbits)
    return np.where(e == 0, np.ldexp(m, -14), np.ldexp(1.0 + m, e - 15)).astype(np.float32)


def image_diff(a, b):
    import numpy as np
    x, y = [np.fromfile(OUT/"runs"/tag/"color.bin", dtype="<u4") for tag in [a, b]]
    G.require(x.shape == y.shape and len(x) == 1920*1080, "image shape mismatch")
    maxima, positive, changed, delta = [], [], [], []
    for shift, bits in [(0, 11), (11, 11), (22, 10)]:
        xc, yc = [(z >> shift) & ((1 << bits)-1) for z in [x, y]]
        G.require(not np.any((xc >> (bits-5)) == 31) and not np.any((yc >> (bits-5)) == 31),
                  "nonfinite image channel")
        d = yc.astype(np.int32) - xc.astype(np.int32)
        maxima.append(int(np.max(np.abs(d))))
        positive.append(float(np.mean(d > 0)))
        changed.append(float(np.mean(d != 0)))
        # Decoded magnitude, so the canary is checkable as a value and not only as a bit flip.
        # Dark pixels only: above ~1.0 a single ULP of this format already exceeds 0.125.
        fx, fy = decode(xc, bits), decode(yc, bits)
        sel = (d != 0) & (fx < 1.0)
        delta.append(float(np.median((fy - fx)[sel])) if sel.any() else 0.0)
    return dict(pair=[a, b], changed_pixels=int(np.count_nonzero(x != y)),
                changed_fraction=float(np.mean(x != y)), max_channel_ulp=maxima,
                positive_channel_fraction=positive, changed_channel_fraction=changed,
                median_decoded_delta_dark=delta)


def stage(label):
    manifest = json.loads((OUT/"experiment_manifest.json").read_text())
    policy, expect = manifest["oracle_policy"], manifest["expected_bytecode"]
    work = Path(manifest["workspace"]).resolve(strict=True)
    # Stage B writes to the workspace source. Refuse to run anywhere but this experiment's own
    # copy, so a mangled manifest or a swapped junction cannot reach the original clone.
    G.require(work.name == manifest["experiment_id"]
              and work.parent == (Path(os.environ["TEMP"])/"claude").resolve()
              and ORIGINAL.resolve() not in [work, *work.parents]
              and not work.is_symlink(), "workspace path is not this experiment's own copy")
    used = sum(p.stat().st_size for p in [*work.rglob("*"), *OUT.rglob("*")] if p.is_file())
    G.require(used + 2_500_000_000 < manifest["workspace_budget_bytes"],
              f"output budget: {used} bytes used, another build does not fit")
    previous = {"B": "A", "A2": "B"}.get(label)
    if previous:
        G.require((OUT/f"{previous}_result.json").is_file(), "previous stage not verified")
    source = work/PS_REL
    baseline = (OUT/"baseline_ModelViewerPS.hlsl").read_bytes()
    G.require(source.read_bytes() == baseline, "workspace source not restored")
    # The preregistered HLSL edit is the ONLY thing allowed to differ between stages.
    with (OUT/"instrumented_source_hashes.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if Path(row["path"]) != source:
                G.require(G.sha(row["path"]) == row["sha256"],
                          f"instrumented source changed since prepare: {row['path']}")
    try:
        if label == "B":
            G.require(baseline.count(CANARY_FROM) == 1, "canary match ambiguous")
            source.write_bytes(baseline.replace(CANARY_FROM, CANARY_TO))
        snapshot = OUT/"source_revisions"/f"{label}_ModelViewerPS.hlsl"
        if snapshot.exists():  # a retry after a failed build must present the same source
            G.require(snapshot.read_bytes() == source.read_bytes(), "stage source differs from the recorded revision")
        else:
            with snapshot.open("xb") as f:
                f.write(source.read_bytes())
        # A stage directory is never reused; a failed attempt keeps its logs under its own name.
        attempt = 1
        while (work/"build"/f"{label}.{attempt}").exists() or (OUT/"build_logs"/f"{label}.{attempt}").exists():
            attempt += 1
        artifact = G.build(work/"MiniEngine", work/"build"/f"{label}.{attempt}",
                           OUT/"build_logs"/f"{label}.{attempt}",
                           Path(manifest["dxc_selected"]),
                           expected=expect["B"] if label == "B" else expect["A"],
                           different=expect["A"] if label == "B" else None)
        runs = [runtime(work, label, artifact, manifest)]
        if label == "A":
            runs += [runtime(work, f"A_repeat{i}", artifact, manifest)
                     for i in range(1, policy["baseline_repeats"])]
            diffs = [image_diff("A", r["tag"]) for r in runs[1:]]
            spread = max(d["changed_fraction"] for d in diffs)
            G.save_json(OUT/"baseline_spread.json", dict(spread=spread, diffs=diffs))
            # Not a determinism claim: this measures how far the same binary moves, so the
            # canary can be required to stand far above it.
            G.require(spread <= policy["canary_max_baseline_changed_pixel_fraction"],
                      f"baseline spread too large to resolve the canary: {spread}")
            diff = diffs[0]
        else:
            diff = image_diff("A", label)
            spread = json.loads((OUT/"baseline_spread.json").read_text())["spread"]
            if label == "A2":
                G.require(diff["changed_fraction"] <=
                          policy["canary_max_baseline_changed_pixel_fraction"],
                          f"restored baseline outside measured baseline spread: {diff}")
            else:
                G.require(diff["changed_fraction"] >= policy["canary_min_changed_pixel_fraction"]
                          and diff["changed_fraction"] >=
                              policy["canary_min_ratio_over_baseline_spread"] * spread
                          and diff["positive_channel_fraction"][0] >=
                              policy["canary_min_positive_red_fraction"],
                          f"canary not detected above measured baseline noise: {diff}")
        result = dict(stage=label, status="PASS", build=artifact, runs=runs,
                      image_diff=diff, baseline_spread=spread)
        G.save_json(OUT/f"{label}_result.json", result)
        print(json.dumps(result, indent=2), flush=True)
    except BaseException as e:
        G.save_json(OUT/f"{label}_failure_{datetime.now().strftime('%H%M%S')}.json",
                    dict(stage=label, status="FAIL", reason=str(e)))
        raise
    finally:
        if source.read_bytes() != baseline:
            source.write_bytes(baseline)
        G.require(source.read_bytes() == baseline, "baseline source restoration failed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare","A","B","A2"])
    action = ap.parse_args().action
    prepare() if action=="prepare" else stage(action)
