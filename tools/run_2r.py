"""Phase 2R: does the method work on a second, structurally different D3D12 workload?

Workload: DirectX-Graphics-Samples / D3D12nBodyGravity. Chosen against criteria written down
before it was inspected (see SELECTION in the manifest): an O(N^2) compute simulation with LDS
tiling and no textures, which is the opposite of MiniEngine's per-light pixel-shading loop.

Same discipline as 2O/2P: a fail-closed build gate on a bytecode SHA-256 preregistered from an
offline DXC compile before any build runs, the pristine source restored on every exit path, and
a correctness oracle that is measured rather than argued - here the particle state after a fixed
number of deterministic simulation steps, compared at float32.

    python -B tools/run_2r.py prepare  [--cycle r1]
    python -B tools/run_2r.py build   <variant>
    python -B tools/run_2r.py run     <variant> [--rep R] [--iters N] [--warm N]
    python -B tools/run_2r.py analyse
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
ORIGINAL = Path(os.environ["TEMP"]) / "claude/src/nbody"
# The project compiles its shaders with the DXC that ships in its own NuGet package
# (1.8.2505.32), not the Windows SDK one (1.8.2502.11). Preregistering with the SDK compiler
# produced a different blob and the gate rejected the build - which is exactly what the gate is
# for; the preregistration now uses the same compiler the build uses.
DXC = ORIGINAL / "src/packages/Microsoft.Direct3D.DXC.1.8.2505.32/build/native/bin/x64/dxc.exe"
MSBUILD = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\amd64\MSBuild.exe")
CS_REL = "src/nBodyGravityCS.hlsl"
CYCLE_DIR = {"r1": "research/43_2r_workload", "r2": "research/44_2r_cycle2",
             "r3": "research/45_2r_cycle3", "r4": "research/46_2r_cycle4"}
CYCLE = "r1"
OUT = ROOT / CYCLE_DIR[CYCLE]

SELECTION = dict(
    written_before_choosing=True,
    criteria=[
        "open source, D3D12, buildable with the toolchain already verified here (MSVC v145 and "
        "the Windows SDK 10.0.26100) without installing anything new",
        "a repeatable workload: deterministic, or fixable to a deterministic step count",
        "no anti-cheat, sources modifiable",
        "GPU-bound enough that the pass under study is measurable on an RX 6950 XT",
        "structurally different from ModelViewer/Sponza: NOT a forward-plus per-light pixel "
        "shading loop over a static mesh scene",
        "small enough to build, instrument and measure inside this session's budget",
        "chosen WITHOUT first checking whether it contains a shader already known to be easy to "
        "optimise",
    ],
    rejected=dict(
        too_small_or_not_gpu_bound="D3D12HelloWorld, Fullscreen, Bundles, DynamicIndexing, "
                                   "PipelineStateCache, PredicationQueries, SmallResources, "
                                   "ReservedResources, Residency, 11On12, On7, HDR, "
                                   "DepthBoundsTest, LinkedGpus, xGPU, HeterogeneousMultiadapter, "
                                   "StateObjectDatabase, AdvancedShaderDelivery, SM6WaveIntrinsics",
        not_structurally_different="D3D12Raytracing/D3D12RaytracingMiniEngineSample - it is "
                                   "MiniEngine again",
        too_large_for_the_budget="the other D3D12Raytracing samples, and the FidelityFX-SDK "
                                 "sample framework (the local clone is sparse and has no host)",
        closed_source="3DMark Steel Nomad, which is installed and would otherwise qualify on "
                      "GPU load"),
    chosen="Samples/Desktop/D3D12nBodyGravity",
    why="an O(N^2) n-body simulation: one compute shader, 10 000 particles, LDS tiling, no "
        "textures, no lighting, no light grid. Deterministic given a fixed step count. The "
        "closest thing to the opposite of the workload 2O and 2P studied.")

CS = CS_REL

# Cycle r2. Hypotheses come from the ISA of the shipped shader (RGA, gfx1030): 85 VGPR, 2 KB LDS,
# no scratch, and per interaction roughly 3 subtracts, 3 multiplies, 5 fused multiply-adds and
# **one v_rsq_f32**. Two things the ISA settles before any of this was written:
#   - `1.0f / sqrt(distSqr)` is already emitted as a single `v_rsq_f32`. The compiler does that
#     strength reduction itself, so there is nothing to win there - checked, not assumed.
#   - the softening add is already folded into `v_fmaak_f32` with the constant inline.
# What is left is arithmetic the compiler cannot legally move, and shapes that cost registers.
R2_TRANSFORMS = {
    # The particle mass is a compile-time constant and multiplies every interaction. Summation
    # distributes over it: sum(r_i * mass * c_i) == mass * sum(r_i * c_i). One multiply per
    # interaction disappears - about 128 per tile per thread - and one appears at the end.
    # The compiler cannot do this itself: it changes the order of rounding.
    "mass_hoist": dict(
        kind="alu_reassociation",
        edits=[(CS,
                b"    float s = mass * invDistCube * particles;\n",
                b"    float s = invDistCube * particles;\n"),
               (CS,
                b"    vel.xyz += accel.xyz * g_paramf.x;        //deltaTime;\n",
                b"    accel *= mass;\n"
                b"    vel.xyz += accel.xyz * g_paramf.x;        //deltaTime;\n")],
        equivalence="mass factors out of every term of the sum, including the negative-count "
                    "correction term, so the two forms are mathematically identical. They are "
                    "NOT bitwise identical: the rounding happens in a different order, which is "
                    "exactly why the compiler is not allowed to do it.",
        expectation="removes one VALU multiply from each of the ~10 000 interactions per thread"),

    # sharedPos is a float4 but only .xyz is ever read. Storing float3 cuts the LDS footprint
    # from 2048 to 1536 bytes per group and removes a dword from every tile store.
    "lds_float3": dict(
        kind="lds_footprint",
        edits=[(CS, b"groupshared float4 sharedPos[blocksize];\n",
                b"groupshared float3 sharedPos[blocksize];\n"),
               (CS, b"void bodyBodyInteraction(inout float3 ai, float4 bj, float4 bi, float mass, int particles) \n",
                b"void bodyBodyInteraction(inout float3 ai, float3 bj, float4 bi, float mass, int particles) \n"),
               (CS, b"    float3 r = bj.xyz - bi.xyz;\n", b"    float3 r = bj - bi.xyz;\n"),
               (CS, b"        sharedPos[GI] = oldPosVelo[tile * blocksize + GI].pos;\n",
                b"        sharedPos[GI] = oldPosVelo[tile * blocksize + GI].pos.xyz;\n"),
               (CS, b"    bodyBodyInteraction(accel, float4(0, 0, 0, 0), pos, mass, -tooManyParticles);\n",
                b"    bodyBodyInteraction(accel, float3(0, 0, 0), pos, mass, -tooManyParticles);\n")],
        equivalence="only the xyz components of sharedPos were ever read; w was written and never "
                    "used. The same values reach the same arithmetic in the same order, so the "
                    "result must be bit-identical.",
        expectation="25 % less LDS per group and one fewer dword written per tile"),

    # 85 VGPR is a lot for this shader, and the eight-wide unrolled body is where the live values
    # come from. Halving the unroll keeps the interaction order identical and should trade a
    # little instruction-level parallelism for registers.
    "unroll4": dict(
        kind="register_pressure",
        edits=[(CS,
                b"        for (uint counter = 0; counter < blocksize; counter += 8 ) \n"
                b"        {\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+1], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+2], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+3], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+4], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+5], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+6], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+7], pos, mass, 1);\n"
                b"        }\n",
                b"        for (uint counter = 0; counter < blocksize; counter += 4 ) \n"
                b"        {\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+1], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+2], pos, mass, 1);\n"
                b"            bodyBodyInteraction(accel, sharedPos[counter+3], pos, mass, 1);\n"
                b"        }\n")],
        equivalence="the same 128 interactions in the same order; only how many of them the "
                    "compiler sees at once changes. Bit-identical.",
        expectation="fewer live values, so fewer VGPRs and more waves in flight"),
}

# All three together, since none of them is expected to interact with the others.
R2_TRANSFORMS["all3"] = dict(
    kind="stack",
    edits=(R2_TRANSFORMS["mass_hoist"]["edits"] + R2_TRANSFORMS["lds_float3"]["edits"]
           + R2_TRANSFORMS["unroll4"]["edits"]),
    equivalence="the three above applied together; measured, never assumed to compose",
    expectation="not assumed to be the sum of the three")

CYCLES = {"r1": {}, "r2": R2_TRANSFORMS, "r3": R2_TRANSFORMS, "r4": R2_TRANSFORMS}
TRANSFORMS = {}


def select(cycle):
    global CYCLE, OUT, TRANSFORMS
    G.require(cycle in CYCLE_DIR, f"unknown cycle {cycle}")
    CYCLE, OUT = cycle, ROOT / CYCLE_DIR[cycle]
    TRANSFORMS = CYCLES.get(cycle, {})


def variant_source(label, root=None):
    root = root or ORIGINAL
    out = {}
    if label == "base":
        return out
    for rel, old, new in TRANSFORMS[label]["edits"]:
        src = out.get(rel) or (root / rel).read_bytes()
        if b"\r\n" in src:
            old, new = old.replace(b"\n", b"\r\n"), new.replace(b"\n", b"\r\n")
        G.require(src.count(old) == 1, f"{label}: anchor not unique in {rel}")
        out[rel] = src.replace(old, new)
    return out


def compile_cs(source, out_cso, log):
    """The project's own compute-shader command, minus -Zi/-Qembed_debug so the blob is the
    shader and nothing else, and its hash does not depend on where it was built."""
    G.run_checked([DXC, "-nologo", "-Tcs_6_0", "-ECSMain", "-Fo", out_cso, source],
                  Path(source).parent, log, timeout=180)
    return G.sha(out_cso)


def instrument(work):
    """Timing, correctness dump and headless benchmark mode. Inert unless NB_DIR is set."""
    cpp = work / "src/D3D12nBodyGravity.cpp"
    text = cpp.read_bytes()

    def once(old, new):
        nonlocal text
        G.require(text.count(old) == 1, f"instrumentation anchor not unique: {old[:60]!r}")
        text = text.replace(old, new)

    once(b'#include "D3D12nBodyGravity.h"',
         b'#include "D3D12nBodyGravity.h"\r\n#include "NbProbe.h"')
    # VSync off while benchmarking, untouched otherwise.
    once(b'ThrowIfFailed(m_swapChain->Present(1, 0));',
         b'ThrowIfFailed(m_swapChain->Present(NbProbe::Enabled() ? 0 : 1, 0));')
    # Timestamp pair around the simulation dispatch, and the buffer it writes.
    once(b'    pCommandList->Dispatch(static_cast<int>(ceil(ParticleCount / 128.0f)), 1, 1);',
         b'    NbProbe::SetTarget(pUavResource);\r\n'
         b'    NbProbe::BeforeDispatch(pCommandList);\r\n'
         b'    pCommandList->Dispatch(static_cast<int>(ceil(ParticleCount / 128.0f)), 1, 1);\r\n'
         b'    NbProbe::AfterDispatch(pCommandList);')
    # One iteration is complete once the compute fence has been waited on.
    once(b'        WaitForSingleObject(m_threadFenceEvents[threadIndex], INFINITE);',
         b'        WaitForSingleObject(m_threadFenceEvents[threadIndex], INFINITE);\r\n'
         b'        NbProbe::EndIteration((UINT64)ParticleCount * sizeof(Particle));')
    once(b'    ID3D12Fence* pFence = m_threadFences[threadIndex].Get();',
         b'    ID3D12Fence* pFence = m_threadFences[threadIndex].Get();\r\n'
         b'    NbProbe::Init(m_device.Get(), pCommandQueue);')
    cpp.write_bytes(text)
    shutil.copy2(ROOT / "tools/nb_probe.h", work / "src/NbProbe.h")

    # Debug info out of the compute shader blob, so its hash is the shader and nothing else.
    proj = work / "src/D3D12nBodyGravity.vcxproj"
    t = proj.read_text(encoding="utf-8-sig")
    old = 'dxc.exe -nologo -Tcs_6_0 -E"CSMain" -Zi -Qembed_debug -Fo"$(OutDir)%(Filename).cso" "%(FullPath)"'
    G.require(t.count(old) == 4, "unexpected compute-shader build commands")
    t = t.replace(old, 'dxc.exe -nologo -Tcs_6_0 -E"CSMain" -Fo"$(OutDir)%(Filename).cso" "%(FullPath)"')
    proj.write_text(t, encoding="utf-8")

    rows = []
    for p in sorted(work.rglob("*")):
        if p.is_file() and p.suffix.lower() in (".cpp", ".h", ".hlsl", ".vcxproj"):
            rows.append(dict(path=str(p), sha256=G.sha(p)))
    return rows


def prepare():
    OUT.mkdir(exist_ok=False)
    eid = "R_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    work = Path(os.environ["TEMP"]) / "claude" / eid
    shutil.copytree(ORIGINAL, work)
    (OUT / "preregistered").mkdir()
    expected = {}
    for label in ["base"] + sorted(TRANSFORMS):
        d = OUT / "preregistered" / label
        d.mkdir()
        shutil.copy2(ORIGINAL / CS_REL, d / "nBodyGravityCS.hlsl")
        for rel, data in variant_source(label).items():
            (d / Path(rel).name).write_bytes(data)
        expected[label] = compile_cs(d / "nBodyGravityCS.hlsl", d / "nBodyGravityCS.cso",
                                     d / "dxc.log")
    # A transformation that compiles to bytecode identical to another variant is a finding, not
    # an error: it means DXC already normalises the difference away. Recorded and measured once.
    duplicates = {}
    seen = {}
    for label, h in expected.items():
        if h in seen:
            duplicates[label] = seen[h]
        else:
            seen[h] = label

    rows = instrument(work)
    with (OUT / "instrumented_source_hashes.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "sha256"])
        w.writeheader()
        w.writerows(rows)
    (OUT / "baseline_sources").mkdir()
    shutil.copy2(work / CS_REL, OUT / "baseline_sources/nBodyGravityCS.hlsl")

    G.save_json(OUT / "experiment_manifest.json", dict(
        experiment_id=eid, created_at=datetime.now().astimezone().isoformat(), phase="2R",
        cycle=CYCLE, workspace=str(work), original_source=str(ORIGINAL),
        workload="DirectX-Graphics-Samples / Samples/Desktop/D3D12nBodyGravity",
        selection=SELECTION, dxc=str(DXC), msbuild=str(MSBUILD),
        configuration="Release/x64/v145", particle_count=10000, threads_per_group=128,
        expected_bytecode=expected, identical_bytecode_to=duplicates,
        transforms={k: {kk: vv for kk, vv in v.items() if kk != "edits"}
                    for k, v in TRANSFORMS.items()},
        transform_edits={k: [[rel, old.decode(), new.decode()] for rel, old, new in v["edits"]]
                         for k, v in TRANSFORMS.items()},
        criteria=dict(
            provenance="every build is gated on the compute shader's preregistered bytecode "
                       "SHA-256; the pristine source is restored on every exit path",
            correctness="the particle buffer after a fixed number of deterministic simulation "
                        "steps, compared at float32 against the baseline's. Baseline vs baseline "
                        "must be byte-identical first, or nothing can be judged",
            performance="median dispatch time from a timestamp pair on the compute queue, "
                        "recorded per iteration after a warm-up, with several independent "
                        "processes and counterbalanced order",
            acceptance="median delta <= -max(1 %, 3 x N95) with N95 from the baseline A/A "
                       "control measured in the cycle, every paired process negative, and "
                       "correctness passing")))
    print("prepared", work, flush=True)


def manifest():
    return json.loads((OUT / "experiment_manifest.json").read_text())


def build(label):
    m = manifest()
    work = Path(m["workspace"]).resolve(strict=True)
    G.require(work.name == m["experiment_id"]
              and work.parent == (Path(os.environ["TEMP"]) / "claude").resolve()
              and ORIGINAL.resolve() not in [work, *work.parents],
              "workspace path is not this experiment's own copy")
    baseline = (OUT / "baseline_sources/nBodyGravityCS.hlsl").read_bytes()
    (work / CS_REL).write_bytes(baseline)
    with (OUT / "instrumented_source_hashes.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if Path(row["path"]) != work / CS_REL:
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
        out = work / "src/bin/x64/Release"
        for stale in ("nBodyGravityCS.cso", "D3D12nBodyGravity.exe"):
            (out / stale).unlink(missing_ok=True)
        (OUT / "build_logs").mkdir(exist_ok=True)
        attempt = 1
        while (OUT / "build_logs" / f"{label}.{attempt}.log").exists():
            attempt += 1
        G.run_checked([MSBUILD, work / "src/D3D12nBodyGravity.vcxproj", "/p:Configuration=Release",
                       "/p:Platform=x64", "/p:PlatformToolset=v145", "/v:minimal", "/nologo"],
                      work / "src", OUT / "build_logs" / f"{label}.{attempt}.log", timeout=1800)
        cso, exe = out / "nBodyGravityCS.cso", out / "D3D12nBodyGravity.exe"
        G.require(cso.is_file() and exe.is_file(), "build produced no shader or executable")
        got = G.sha(cso)
        G.require(got == m["expected_bytecode"][label],
                  f"{label}: compute shader is {got[:12]}, preregistered {m['expected_bytecode'][label][:12]}")
        # Copy the WHOLE output tree, not just its files: the Agility SDK lives in a D3D12        # subdirectory and the app sets D3D12SDKPath to it, so a files-only copy produces an
        # executable that cannot create a device.
        home = OUT / "builds" / label
        if home.exists():
            shutil.rmtree(home)
        shutil.copytree(out, home)
        artifact = dict(variant=label, executable=str(home / "D3D12nBodyGravity.exe"),
                        executable_sha256=G.sha(home / "D3D12nBodyGravity.exe"),
                        cs_sha256=got, cs_bytes=cso.stat().st_size)
        record = OUT / f"build_{label}.json"
        if record.exists():
            prev = json.loads(record.read_text())
            G.require(prev["cs_sha256"] == artifact["cs_sha256"],
                      "rebuild produced a different compute shader")
            record.unlink()
        G.save_json(record, artifact)
        print(f"{label}: cs {got[:12]} ({artifact['cs_bytes']} B), exe "
              f"{artifact['executable_sha256'][:12]}", flush=True)
    finally:
        (work / CS_REL).write_bytes(baseline)


def run(label, rep, iters, warm):
    m = manifest()
    a = json.loads((OUT / f"build_{label}.json").read_text())
    G.require(G.sha(a["executable"]) == a["executable_sha256"], "executable changed since build")
    folder = OUT / "runs" / f"{label}_r{rep}"
    folder.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("NB_", "ME_", "AMD_"))}
    env.update(NB_DIR=str(folder), NB_ITERS=str(iters), NB_WARM=str(warm))
    proc = G.run_checked([a["executable"]], Path(a["executable"]).parent,
                         folder / "process.log", env=env, timeout=1800)
    G.require((folder / "summary.json").is_file() and (folder / "particles.bin").is_file(),
              "run produced no summary or particle dump")
    s = json.loads((folder / "summary.json").read_text())
    G.save_json(folder / "run.json", dict(variant=label, rep=rep, pid=proc["pid"],
                                          iters=iters, warm=warm, summary=s,
                                          particles_sha256=G.sha(folder / "particles.bin"),
                                          cs_sha256=a["cs_sha256"]))
    print(f"{label}_r{rep}: median {s['dispatch_ns_median']:.0f} ns over {s['recorded']} "
          f"iterations, particles {G.sha(folder / 'particles.bin')[:12]}", flush=True)


def compare_particles(a_tag, b_tag):
    import numpy as np
    x, y = [np.fromfile(OUT / "runs" / t / "particles.bin", dtype="<f4") for t in (a_tag, b_tag)]
    G.require(x.shape == y.shape, "particle dump shape mismatch")
    xb, yb = [v.view(np.int32).astype(np.int64) for v in (x, y)]
    mono = lambda b: np.where(b < 0, np.int64(-2147483648) - b, b)
    finite = np.isfinite(x) & np.isfinite(y)
    ulp = np.where(finite, np.abs(mono(xb) - mono(yb)), 0)
    d = np.where(finite, np.abs(y - x), 0.0)
    rel = np.where(finite & (x != 0), d / np.maximum(np.abs(x), np.finfo(np.float32).tiny), 0.0)
    return dict(pair=[a_tag, b_tag], identical=bool(np.array_equal(xb, yb)),
                values=int(x.size), differing=int(np.count_nonzero(xb != yb)),
                max_ulp=int(ulp.max()), max_abs=float(d.max()), max_rel=float(rel.max()),
                rms=float(np.sqrt(np.mean(d.astype(np.float64) ** 2))),
                nonfinite_a=int(np.count_nonzero(~np.isfinite(x))),
                nonfinite_b=int(np.count_nonzero(~np.isfinite(y))))


def analyse():
    m = manifest()
    labels = [p.name.replace("build_", "").replace(".json", "")
              for p in sorted(OUT.glob("build_*.json"))]
    data = {}
    for label in labels:
        vals = []
        for rep in range(1, 12):
            f = OUT / "runs" / f"{label}_r{rep}" / "run.json"
            if f.is_file():
                vals.append(json.loads(f.read_text())["summary"]["dispatch_ns_median"])
        if vals:
            data[label] = vals
    line = "=" * 88
    print(line)
    print("1. DISPATCH TIME - median per process, ns")
    print(line)
    for label, vals in data.items():
        print(f"   {label:16s} " + ", ".join(f"{v:.0f}" for v in vals)
              + f"   median {statistics.median(vals):.0f} ns")
    n95 = thr = None
    if "base" in data and len(data["base"]) > 1:
        v = data["base"]
        pw = [abs(a - b) / ((a + b) / 2) * 100 for i, a in enumerate(v) for b in v[i + 1:]]
        n95, thr = max(pw), max(1.0, 3 * max(pw))
        print(f"\n   A/A on base: " + ", ".join(f"{x:.2f}%" for x in pw)
              + f"  -> N95 {n95:.2f}%, accept threshold {thr:.2f}%")
    print("\n" + line)
    print("2. RESPONSE, paired against base")
    print(line)
    verdicts = {}
    for label, vals in data.items():
        if label == "base" or "base" not in data:
            continue
        k = min(len(vals), len(data["base"]))
        paired = [(vals[i] - data["base"][i]) / data["base"][i] * 100 for i in range(k)]
        med = statistics.median(paired)
        ok = thr is not None and med <= -thr and all(p < 0 for p in paired) and k >= 3
        verdicts[label] = dict(median_pct=med, per_process=paired, performance_accepted=ok)
        print(f"   {label:16s} median {med:+7.2f} %   per process "
              + ", ".join(f"{p:+.2f}%" for p in paired)
              + f"   {'ACCEPT' if ok else 'reject'}")
    print("\n" + line)
    print("3. CORRECTNESS - particle state after the same number of steps")
    print(line)
    corr = {}
    if (OUT / "runs/base_r1/particles.bin").is_file() and (OUT / "runs/base_r2/particles.bin").is_file():
        c = compare_particles("base_r1", "base_r2")
        corr["base_vs_base"] = c
        print(f"   base vs base   identical={c['identical']}  differing={c['differing']} "
              f"(determinism check, must be identical)")
    for label in data:
        if label == "base" or not (OUT / f"runs/{label}_r1/particles.bin").is_file():
            continue
        c = compare_particles("base_r1", f"{label}_r1")
        c["passed"] = c["max_ulp"] <= 1 and c["nonfinite_b"] == 0
        corr[label] = c
        print(f"   {label:16s} identical={str(c['identical']):5s} differing={c['differing']:8d}"
              f"  max_ulp={c['max_ulp']}  max_rel={c['max_rel']:.3e}"
              f"  -> {'PASS' if c['passed'] else 'FAIL'}")
    G.save_json(OUT / f"analysis_{datetime.now().strftime('%H%M%S')}.json",
                dict(experiment_id=m["experiment_id"], dispatch_ns=data, n95=n95, threshold=thr,
                     verdicts=verdicts, correctness=corr))
    print("\nwrote analysis json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prepare", "build", "run", "analyse"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--iters", type=int, default=1000)
    ap.add_argument("--warm", type=int, default=200)
    ap.add_argument("--cycle", default="r1")
    a = ap.parse_args()
    select(a.cycle)
    if a.action == "prepare":
        prepare()
    elif a.action == "build":
        build(a.name)
    elif a.action == "run":
        run(a.name, a.rep, a.iters, a.warm)
    else:
        analyse()
