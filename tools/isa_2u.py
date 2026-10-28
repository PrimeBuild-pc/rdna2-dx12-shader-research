"""Native ISA for phase 2U variants, so a measured delta can be checked against what the
transformation actually did to the machine code rather than to the source.

Compiles each preregistered variant's pixel shader with RGA for gfx1030, through a root
signature reconstructed from the workload's own C++, and reports register use plus the opcode
mix that matters here: image instructions, transcendentals, and everything else.

    python -B tools/isa_2u.py w4 [variant ...]      # all preregistered variants if none named
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G

ROOT = Path(__file__).resolve().parents[1]
RGA = ROOT / ("RadeonDeveloperToolSuite-2026-05-28-1806/"
              "RadeonDeveloperToolSuite-2026-05-28-1806/rga.exe")

# One entry per workload: where its preregistered sources land, which file and entry point is the
# hot pixel shader, and the root signature and PSO its C++ builds. The root signatures are
# reconstructed by reading that C++, and are used for offline ISA generation only.
WORKLOADS = {
    "w4": dict(
        out="research/52_2t_w4",
        ps="ShadowsAndScenePass.hlsl", entry="PSMain", model="ps_6_0",
        rs_macro="W4RS",
        rs='''// Root signature reconstructed from VariableRateShadingScene::CreateRootSignatures,
// RootSignature::ScenePass (5 parameters). Offline ISA generation only.
#define W4RS \\
    "RootFlags(ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT|DENY_DOMAIN_SHADER_ROOT_ACCESS|DENY_HULL_SHADER_ROOT_ACCESS|DENY_GEOMETRY_SHADER_ROOT_ACCESS)," \\
    "DescriptorTable(SRV(t0, numDescriptors=2, flags=DATA_STATIC), visibility=SHADER_VISIBILITY_PIXEL)," \\
    "CBV(b0, flags=DATA_STATIC)," \\
    "CBV(b1, flags=DATA_STATIC)," \\
    "DescriptorTable(SRV(t2, numDescriptors=2), visibility=SHADER_VISIBILITY_PIXEL)," \\
    "DescriptorTable(Sampler(s0, numDescriptors=2), visibility=SHADER_VISIBILITY_PIXEL)"
''',
        gpso='''# schemaVersion
1.0

# InputLayoutNumElements
4

# InputLayout
{ "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 0, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 }
{ "NORMAL", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 12, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 }
{ "TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 24, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 }
{ "TANGENT", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 32, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 }

#PrimitiveTopologyType
D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE

# NumRenderTargets
1

# RTVFormats
{ DXGI_FORMAT_R8G8B8A8_UNORM }
'''),
}

TRANSCENDENTAL = ("v_rcp_", "v_rsq_", "v_sqrt_", "v_log_", "v_exp_", "v_sin_", "v_cos_",
                  "v_rcp_iflag_")
# Lines RGA emits that are metadata, not instructions.
NOT_INSTRUCTIONS = {"s_code_end", "wave_size", "vgpr_count", "sgpr_count", "type", "s_version"}


def opcodes(isa_path):
    ops = Counter()
    for line in isa_path.read_text().splitlines():
        m = re.match(r"\s+([a-z][a-z0-9_]*)\s", line)
        if m and m.group(1) not in NOT_INSTRUCTIONS:
            ops[m.group(1)] += 1
    return ops


def summarise(ops):
    return dict(
        instructions=sum(ops.values()),
        image=sum(n for o, n in ops.items() if o.startswith("image_")),
        image_sample=sum(n for o, n in ops.items() if o.startswith("image_sample")),
        image_gather=sum(n for o, n in ops.items() if o.startswith("image_gather")),
        valu=sum(n for o, n in ops.items() if o.startswith("v_")),
        salu=sum(n for o, n in ops.items() if o.startswith("s_")),
        transcendental=sum(n for o, n in ops.items() if o.startswith(TRANSCENDENTAL)),
        interp=sum(n for o, n in ops.items() if o.startswith("v_interp")),
        branch=sum(n for o, n in ops.items() if o.startswith(("s_cbranch", "s_branch"))),
    )


def run(workload, wanted):
    w = WORKLOADS[workload]
    out = ROOT / w["out"]
    stage = Path(__import__("os").environ["TEMP"]) / f"claude/isa_2u_{workload}"
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "rs.hlsl").write_text(w["rs"])
    (stage / "pso.gpso").write_text(w["gpso"])

    labels = wanted or sorted(d.name for d in (out / "preregistered").iterdir() if d.is_dir())
    report = {}
    for label in labels:
        src = out / "preregistered" / label
        G.require(src.is_dir(), f"{label}: no preregistered sources")
        d = stage / label
        d.mkdir(exist_ok=True)
        for f in src.glob("*.hlsl*"):
            (d / f.name).write_bytes(f.read_bytes())
        for f in d.glob("gfx1030_*"):
            f.unlink()
        proc = subprocess.run(
            [str(RGA), "-s", "dx12", "-c", "gfx1030",
             "--ps", str(d / w["ps"]), "--ps-entry", w["entry"], "--ps-model", w["model"],
             "--rs-macro", w["rs_macro"], "--rs-hlsl", str(stage / "rs.hlsl"),
             "--gpso", str(stage / "pso.gpso"), "--isa", str(d / "isa.txt"),
             "-a", str(d / "stats.txt"), "-I", str(d)],
            capture_output=True, text=True, timeout=900, cwd=d)
        isa = next(d.glob("*isa_pixel.txt"), None)
        stats = next(d.glob("*stats_pixel.txt"), None)
        G.require(isa and stats, f"{label}: RGA produced no ISA ({proc.stdout[-300:]})")
        st = {m.group(1): int(m.group(2))
              for m in (re.match(r"\s*-\s*([\w.]+)\s*=\s*(\d+)", l)
                        for l in stats.read_text().splitlines()) if m}
        report[label] = dict(
            vgpr=st["resourceUsage.numUsedVgprs"], sgpr=st["resourceUsage.numUsedSgprs"],
            scratch=st["resourceUsage.scratchMemUsageInBytes"], **summarise(opcodes(isa)))

    G.save_json_over(out / "isa_2u.json", report)
    cols = ["vgpr", "sgpr", "instructions", "valu", "salu", "image", "image_sample",
            "image_gather", "transcendental", "interp", "branch"]
    print(f"{'variant':18s}" + "".join(f"{c:>14s}" for c in cols))
    base = report.get("base")
    for label, r in sorted(report.items()):
        print(f"{label:18s}" + "".join(f"{r[c]:>14d}" for c in cols))
    if base:
        print(f"\n{'delta vs base':18s}" + "".join(f"{c:>14s}" for c in cols))
        for label, r in sorted(report.items()):
            if label != "base":
                print(f"{label:18s}" + "".join(f"{r[c] - base[c]:>+14d}" for c in cols))


if __name__ == "__main__":
    G.require(len(sys.argv) > 1 and sys.argv[1] in WORKLOADS, "usage: isa_2u.py <workload> [variant ...]")
    run(sys.argv[1], sys.argv[2:])
