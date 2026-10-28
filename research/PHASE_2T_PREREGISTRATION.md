# Phase 2T — preregistration

**Written 2026-09-07, before any of the workloads below was inspected.** The question is not
whether the pipeline can be made to win again. It is:

> Run the frozen pipeline, unchanged, on workloads chosen before looking at them. **How often does
> it produce an accepted transformation, how many attempts does each one cost, and how large are
> the gains when they happen?**

## The metrics, defined before measuring

- **Hit rate** = workloads with at least one ACCEPTED transformation ÷ workloads **attempted**.
  A workload that fails to build, or turns out to have no measurable GPU pass, stays in the
  denominator with its reason recorded. **It is not swapped for an easier one.**
- **Cost in attempts** = transformations built and measured ÷ transformations accepted, counted
  over the whole phase.
- **Quality of gains** = for each accepted transformation, Δ of the target pass and, where the
  workload has a frame, Δ of the GPU frame, together with its correctness class.
- **Failure taxonomy**, every one counted: build failure, no measurable pass, no hypothesis found,
  compiler already does it, correctness rejected, performance rejected.

## Selection criteria, applied before inspection

1. In `microsoft/DirectX-Graphics-Samples`, `Samples/Desktop/*` — same repository, same toolchain
   (MSVC v145, Windows SDK 10.0.26100, the NuGet packages already fetched), nothing new installed.
2. Does real GPU work every frame, rather than demonstrating an API call once.
3. Needs no hardware feature this RX 6950 XT lacks.
4. Structurally distinct from each other and from the two already done.
5. **Chosen by directory name and the repository's own one-line description only.** No shader, no
   source file, no ISA was opened before this list was fixed.
6. Order of attempt is fixed here and followed.

## The workloads, in the order they will be attempted

| # | workload | why it was picked, from the name alone | expected structure |
|---|---|---|---|
| **W1** | `D3D12ExecuteIndirect` | GPU-driven submission: a compute shader culls and writes an indirect argument buffer | compute + indirect draws |
| **W2** | `D3D12Multithreading` | a shadowed scene recorded from several threads | shadow map + lit geometry |
| **W3** | `D3D12MeshShaders` | the mesh-shader pipeline, which RDNA2 supports | amplification/mesh stage |
| **W4** | `D3D12VariableRateShading` | a scene whose shading rate varies per region | pixel shading with VRS |
| W5 | `D3D12SM6WaveIntrinsics` | wave-intrinsic visualisation, a full-screen pixel shader | reserve, only if one of W1–W4 cannot be attempted at all |

Already done, reported separately and **not** counted in this phase's hit rate: MiniEngine
ModelViewer (**hit**, −41.4 %) and `D3D12nBodyGravity` (**miss**, no accepted transformation).

## The pipeline, frozen and not to be altered

```
profile → hot pass → shader identified by bytecode hash → ISA inspection
        → hypothesis → build gate on a preregistered SHA-256 → correctness oracle
        → paired A/B on the real workload, several processes, counterbalanced order
        → verdict
```

Acceptance, unchanged from 2P: median Δ ≤ −max(1 %, 3 × N95) with N95 from that workload's own
A/A control, **every** paired process negative, and correctness passing. Correctness rule per
workload is declared in that workload's manifest before its first measurement.

**No transformation is proposed from memory of what worked before.** Hypotheses must come from
that workload's own ISA and source.

## Budget and stopping

Ten cycles. A workload that consumes its share without producing a hypothesis is closed as a
miss and the phase moves on. The phase ends at ten cycles or when W1–W4 are closed, whichever
comes first.
