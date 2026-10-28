"""Native ISA and register statistics for every 2P variant, so a speed-up cannot be attributed
to ALU issue cost when it might be occupancy, register pressure or scratch.

Compiles each variant's pixel shader with RGA for gfx1030, through a root signature
reconstructed from `Renderer::m_RootSig`, and reports VGPR/SGPR/scratch plus the opcode mix of
the three per-light loops.

    python -B tools/isa_2p.py <cycle>          # p1, p2, ...
"""
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G
import run_o1 as O1
import run_2p as P

ROOT = Path(__file__).resolve().parents[1]
RGA = ROOT / "RadeonDeveloperToolSuite-2026-05-28-1806/RadeonDeveloperToolSuite-2026-05-28-1806/rga.exe"

RS = b'''// Root signature reconstructed from MiniEngine Renderer::m_RootSig (Model/Renderer.cpp),
// parameter order from Renderer.h. Offline ISA generation only.
#define MVRS \\
    "RootFlags(ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT)," \\
    "CBV(b0, space=0, visibility=SHADER_VISIBILITY_VERTEX)," \\
    "CBV(b0, space=0, visibility=SHADER_VISIBILITY_PIXEL)," \\
    "DescriptorTable(SRV(t0, numDescriptors=10), visibility=SHADER_VISIBILITY_PIXEL)," \\
    "DescriptorTable(Sampler(s0, numDescriptors=10), visibility=SHADER_VISIBILITY_PIXEL)," \\
    "DescriptorTable(SRV(t10, numDescriptors=10), visibility=SHADER_VISIBILITY_PIXEL)," \\
    "CBV(b1)," \\
    "SRV(t20, visibility=SHADER_VISIBILITY_VERTEX)," \\
    "StaticSampler(s10, filter=FILTER_ANISOTROPIC, maxAnisotropy=8, visibility=SHADER_VISIBILITY_PIXEL)," \\
    "StaticSampler(s11, filter=FILTER_COMPARISON_MIN_MAG_LINEAR_MIP_POINT, comparisonFunc=COMPARISON_GREATER_EQUAL, addressU=TEXTURE_ADDRESS_CLAMP, addressV=TEXTURE_ADDRESS_CLAMP, addressW=TEXTURE_ADDRESS_CLAMP, visibility=SHADER_VISIBILITY_PIXEL)," \\
    "StaticSampler(s12, filter=FILTER_ANISOTROPIC, maxAnisotropy=8, visibility=SHADER_VISIBILITY_PIXEL)"
'''

GPSO = b"""# schemaVersion
1.0

# InputLayoutNumElements
2

# InputLayout
{ "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 0, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA,0 },
{ "COLOR", 0, DXGI_FORMAT_R32G32B32A32_FLOAT, 0, 12, D3D12_INPUT_CLASSIFICATION_PER_VERTEX_DATA, 0 }

#PrimitiveTopologyType
D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE

# NumRenderTargets
2

# RTVFormats
{ DXGI_FORMAT_R11G11B10_FLOAT, DXGI_FORMAT_R16G16B16A16_FLOAT }
"""

TRANSCENDENTAL = {"v_log_f32", "v_exp_f32", "v_rcp_f32", "v_rsq_f32", "v_sqrt_f32",
                  "v_sin_f32", "v_cos_f32"}


def loops(lines):
    """The per-light loops: a backward s_branch marks the end, its target the start."""
    labels = {}
    for i, l in enumerate(lines):
        m = re.match(r"^(label_[0-9A-Fa-f]+):", l.strip())
        if m:
            labels[m.group(1)] = i
    out = []
    for i, l in enumerate(lines):
        m = re.search(r"s_branch\s+(label_[0-9A-Fa-f]+)", l)
        if m and labels.get(m.group(1), i + 1) < i:
            out.append((labels[m.group(1)], i))
    return sorted(out)


def opcodes(lines):
    c = Counter()
    for l in lines:
        m = re.match(r"^\s+([a-z][a-z0-9_]*)\s", l)
        if m and m.group(1) not in ("s_code_end",):
            c[m.group(1)] += 1
    return c


def analyse_isa(path):
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    out = dict(total_instructions=sum(opcodes(lines).values()), loops=[])
    for a, b in loops(lines):
        c = opcodes(lines[a:b + 1])
        vmem = sum(v for k, v in c.items() if k.startswith(("buffer_load", "image_")))
        trans = sum(v for k, v in c.items() if k in TRANSCENDENTAL)
        out["loops"].append(dict(first_line=a + 1, last_line=b + 1,
                                 instructions=sum(c.values()), vmem=vmem,
                                 transcendental=trans,
                                 # wave64 on SIMD32: 2 cycles per VALU op, 8 for a quarter-rate
                                 # transcendental. A cost estimate, not a measurement.
                                 est_valu_cycles=2 * (sum(c.values()) - vmem - trans) + 8 * trans,
                                 top=dict(c.most_common(8))))
    return out


def main(cycle):
    P.select(cycle)
    m = json.loads((P.OUT / "experiment_manifest.json").read_text())
    stage = P.OUT / "isa"
    stage.mkdir(exist_ok=True)
    (stage / "rs.hlsl").write_bytes(RS)
    (stage / "pso.gpso").write_bytes(GPSO)
    report = {}
    for label in P.VARIANTS:
        d = stage / label
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree((O1.ORIGINAL / O1.PS_REL).parent, d)
        for rel, data in P.variant_source(label).items():
            (d / Path(rel).name).write_bytes(data)
        cmd = [str(RGA), "-s", "dx12", "-c", "gfx1030",
               "--ps", str(d / "ModelViewerPS.hlsl"), "--ps-entry", "main",
               "--ps-model", "ps_6_2", "--rs-macro", "MVRS",
               "--rs-hlsl", str(stage / "rs.hlsl"), "--gpso", str(stage / "pso.gpso"),
               "--isa", str(d / "isa.txt"), "-a", str(d / "stats.txt"),
               "-I", str(d), "-D", "_GAMING_DESKTOP=1"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        isa = next(d.glob("*isa_pixel.txt"), None)
        stats = next(d.glob("*stats_pixel.txt"), None)
        G.require(isa is not None and stats is not None,
                  f"{label}: RGA produced no ISA ({proc.stdout[-300:]})")
        st = {}
        for line in stats.read_text().splitlines():
            mm = re.match(r"\s*-\s*([\w.]+)\s*=\s*(\d+)", line)
            if mm:
                st[mm.group(1)] = int(mm.group(2))
        report[label] = dict(stats=st, isa=analyse_isa(isa),
                             bytecode=m["expected_bytecode"][label])
    G.save_json(P.OUT / "isa_report.json", report)

    print(f"{'variant':12s} {'VGPR':>5s} {'SGPR':>5s} {'scratch':>8s} {'instr':>7s}"
          f" {'loops':>6s} {'loop instr':>11s} {'loop vmem':>10s} {'loop trans':>11s}"
          f" {'est cycles':>11s}")
    for label, r in report.items():
        L = r["isa"]["loops"]
        print(f"{label:12s} {r['stats'].get('resourceUsage.numUsedVgprs', 0):5d}"
              f" {r['stats'].get('resourceUsage.numUsedSgprs', 0):5d}"
              f" {r['stats'].get('resourceUsage.scratchMemUsageInBytes', 0):8d}"
              f" {r['isa']['total_instructions']:7d} {len(L):6d}"
              f" {sum(x['instructions'] for x in L):11d}"
              f" {sum(x['vmem'] for x in L):10d}"
              f" {sum(x['transcendental'] for x in L):11d}"
              f" {sum(x['est_valu_cycles'] for x in L):11d}")
    print("\nper-loop detail (instructions / vmem / transcendental / estimated VALU cycles)")
    for label, r in report.items():
        print(f"   {label:12s} " + "  ".join(
            f"[{x['instructions']}/{x['vmem']}/{x['transcendental']}/{x['est_valu_cycles']}]"
            for x in r["isa"]["loops"]))
    print("\nwrote", P.OUT / "isa_report.json")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "p1")
