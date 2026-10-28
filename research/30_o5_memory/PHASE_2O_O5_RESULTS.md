# Phase 2O — cycle O5: stage attribution and cache/memory classification of `Render Color`

**Date:** 2026-09-06 · cycle **5 of 6** · `classification` — no image claim, no accepted
optimisation. Criteria and bands were written into `experiment_manifest.json` **before any
counter was read**.

O3 and O4 established what the pass is *not* limited by: filtering. Two prerequisites for any
positive claim were still unmeasured, and O5 closes both.

**No new build.** The five O4 executables are reused, their pixel shader bytecode still pinned
to the O1 baseline (`52CE6C5E64AB2E82`) and their SHA-256 re-verified at prepare and at every
run. Only the counter sets change — which turns O4's sampler variants into a **memory-traffic
lever at byte-identical bytecode**.

Sets and their pass counts were measured offline with `gpaenum_hw.exe` before running:
`stage_tex` 16 counters / 2 passes, `stage_all` 56 / 7, `tcp_ta` 320 / **1**, `l1l2` 96 / **1**,
`dram` 144 / **1**. Timing is **not** re-measured here — mixing a derived counter into a raw set
costs an extra pass, and O4 measured `GPUTime`/`GPUBusyCycles` on these exact executables.

---

## A. Stage attribution — closed, and it needed a control to close it

`SQ` counters carry a shader mask. The preregistered prediction was that the vertex stage issues
**< 1 %** of the texture instructions in this scope, because `ModelViewerVS.hlsl` contains no
texture object and no `Sample` call.

The `SQ_VS*` counters read **zero waves and zero texture instructions**. That alone proves
nothing: on RDNA2 a plain vertex shader is compiled into the NGG primitive-shader stage, so a
zero under the `VS` mask is equally consistent with "the vertex stage never ran under that
mask". A mid-cycle control swept **all eight shader masks** (`stage_all`, 7 passes):

| mask | waves | texture instructions | share |
|---|---:|---:|---:|
| `PS` | 39 171 | **6 109 550** | 99.53 % |
| `GS` | 9 596 | **28 852** | 0.47 % |
| `VS`, `ES`, `HS`, `LS`, `CS`, `ALL` | 0 | 0 | — |

The vertex work is there, under the `GS` mask, exactly as the NGG mapping predicts — and it does
issue texture instructions, **3.007 per wave**, which is what a three-stream vertex attribute
fetch looks like (`INSTS_TEX_LOAD` counts buffer loads, not only filtered samples). The `GS`
figures are **bit-identical across all three processes**.

**Verdict: PASS on the preregistered prediction (0.47 % < 1 %), but not for the reason the
source-level reading suggested.** Every texture ratio in O2, O3 and O4 that divided a whole-block
`TA` counter by `SQ_PS INSTS_TEX_LOAD` is sound to within **0.47 %**. Across-process spread of
the `PS` count is 0.038 %, well inside O2's ±0.4 % emulation band, and the total (6.11 M) matches
O2's independently measured baseline (6 115 386) to 0.09 %.

Had the control not been run, "VS share = 0 %" would have been reported as a clean confirmation
of a claim the data could not actually support.

## B. The texture addresser is not waiting on the L0 cache

`tcp_ta`, single pass, so `TCP_PERF_SEL_TCP_TA_REQ_STALL` and `TA_PERF_SEL_TA_BUSY` are read on
the same frames. Median of 3 independent processes, order interleaved.

| variant | TCP requests | L0 misses | L0 hit | TA stall cycles | `TA_BUSY` | stall / busy |
|---|---:|---:|---:|---:|---:|---:|
| `s_base` | 55 403 333 | 1 299 197 | **97.66 %** | 209 154 | 88 700 482 | **0.24 %** |
| `s_aniso1` | 50 486 806 | 1 173 330 | 97.68 % | 166 450 | 86 299 986 | 0.19 % |
| `s_point` | 48 641 822 | 912 842 | 98.12 % | 158 614 | 85 629 318 | 0.19 % |
| `s_bilinear` | 48 879 938 | 941 732 | 98.07 % | 159 125 | 85 602 065 | 0.19 % |

**0.24 % against a preregistered "not the cache" band of ≤ 10 %.** The L0 vector cache holds the
texture addresser back for roughly one cycle in four hundred.

The counter is not dead, and this is the reason to believe the 0.24 %. The sampler intervention —
byte-identical bytecode, point filtering reading one texel per quad instead of four — moves it in
exactly the direction its meaning predicts:

| vs `s_base` | Δ TCP req | Δ L0 miss | Δ TA stall | Δ `TA_BUSY` | stall/busy |
|---|---:|---:|---:|---:|---|
| `s_aniso1` | −8.87 % | −9.69 % | −20.42 % | −2.71 % | 0.24 → 0.19 % |
| `s_point` | −12.20 % | −29.74 % | −24.16 % | −3.46 % | 0.24 → 0.19 % |
| `s_bilinear` | −11.77 % | −27.51 % | −23.92 % | −3.49 % | 0.24 → 0.19 % |

Less traffic, fewer misses, proportionally fewer stalls — and `TA_BUSY` barely notices. The unit
caveat registered before measuring (TCP and TA are different blocks' cycle counters) is answered
by this: the ratio responds as its meaning requires, and it is two orders of magnitude away from
the decision band, so no plausible unit correction changes the verdict.

## C. Where the fetches land

`l1l2` and `dram`, single pass each, median of 3 processes.

| variant | L1 (GL1C) req | L1 hit | L2 (GL2C) req | L2 hit | DRAM read |
|---|---:|---:|---:|---:|---:|
| `s_base` | 1 765 866 | 52.52 % | 851 743 | 41.47 % | **31.88 MB** |
| `s_aniso1` | 1 644 180 | 52.91 % | 787 650 | 39.23 % | 29.45 MB |
| `s_point` | 1 356 680 | 47.07 % | 731 501 | 36.38 % | 28.73 MB |
| `s_bilinear` | 1 407 748 | 47.28 % | 755 487 | 37.37 % | 28.72 MB |

**Self-consistency check, not assumed:** L2 misses × 64 B = 31.90 MB against 31.88 MB of DRAM
read bytes computed independently from `GL2C_PERF_SEL_EA_RDREQ_{32,64,96,128}B` —
**0.06 % apart**. Two different counter groups describing the same traffic agree, which is the
evidence that this hierarchy read is trustworthy.

31.88 MB over the pass's 804.5 µs is **39.6 GB/s**. Phase 2N measured 555–621 GB/s on other
passes of this same frame on this same GPU. `Render Color` is running at about **6 %** of the
memory bandwidth the machine demonstrably delivers.

## D. The numbers that matter

| quantity | value |
|---|---:|
| pixel-stage texture instructions in the scope | 6 111 703 |
| ... per pixel-shader wave | **156.0** |
| **`TA_BUSY` cycles per texture instruction** | **14.51** |
| TCP (L0) requests per texture instruction | 9.07 |
| L0 misses per texture instruction | 0.21 |
| `TA_BUSY` per CU | 1 108 756 |
| **TA duty cycle** (per-CU busy / `GPUBusyCycles`) | **93.25 %** |
| DRAM read | 31.88 MB = 39.6 GB/s |

The 93.25 % agrees with O2's `TexUnitBusy` of 94.63 %, which O2 showed is the *maximum* over the
80 CUs; the mean is 93.25 %. The texture unit really is saturated.

## E. What is left standing

Four candidate causes for a texture unit at 93 % duty, and the measurements that dispose of them:

| candidate | measurement | verdict |
|---|---|---|
| texture **filtering** throughput | O4: aniso off entirely (−17.9 % filter cycles) moves the pass ≤ 3 % | **falsified** |
| L0 cache back-pressure on the addresser (`TCP→TA` request stall) | stall / busy = **0.24 %**, band ≤ 10 % | **falsified** |
| L0 miss traffic | L0 hit **97.66 %**, 0.21 misses per texture instruction | **falsified** |
| DRAM bandwidth **saturation** | **39.6 GB/s** against 555–621 GB/s reached elsewhere in this frame | **falsified** |

Each verdict is bounded by what was measured: what is excluded is bandwidth *saturation* and the
`TCP→TA` request back-pressure specifically — **not** memory latency in general, for which no
counter was collected here.

What survives is **the sheer number of texture instructions the pixel shader issues — 156 per
wave — each occupying the addresser for about 14.5 cycles, with the data essentially always
resident in L0.** Within the texture path, the cost is *instruction* throughput in the addresser:
not filtering, not cache, not memory.

**Correction, added after O6:** this section originally listed only texture-path candidates and
so read as if the texture path had been established as *the* limiter. It has not. Pixel-shader
ALU is a fifth candidate and it was not tested here. O6 measured it: at this baseline the VALU
issue duty is **96.6 %** against the addresser's 93.6 %, so the two are co-saturated and this
cycle cannot rank them. What O5 does establish stands unchanged — filtering, L0 stalls, L0 miss
traffic and DRAM bandwidth are all eliminated by measurement.

Stated as a falsifiable claim, which is O6's job:

> `TA_BUSY` in this scope is set by the count of pixel-stage texture instructions. Removing a
> texture instruction of the dominant (shadow / light-buffer) kind removes on the order of
> 14 cycles of `TA_BUSY`, and the pass's GPU time follows `TA_BUSY` with the damped slope O3
> measured (0.59–0.82).

**Caveat carried into O6, from O3:** the cost per instruction is *not* uniform. O3's `mat1`
removed 0.68 % of the texture instructions and 2.33 % of `TA_BUSY` — the three material samples
are anisotropically filtered and cost about 3.4× the average. The ~153 shadow and light fetches
per wave are the cheap majority, and it is their marginal cost that O6 must measure. If they are
nearly free, this cycle's conclusion is wrong.

## F. Limits and defects

- **`stage_all` is a 7-pass session.** O2 established that aggregate work counters are
  bit-identical across passes and that timing counters are not; only aggregate work counters are
  used here, and the `GS` values are in fact bit-identical across three processes.
- **`stage_tex` is inherently 2-pass**: the `PS` and `VS` masks of one `SQ` event cannot share a
  hardware pass. Registered as a caveat before measuring.
- The `TCP`/`TA` ratio is an indicator across two blocks, not an identity (§B).
- L1 and L2 requests include clients other than the texture path (depth, colour export), so
  their hit rates characterise the pass, not the texture path alone. The L0 figures are texture-
  path specific; the L2 → DRAM chain is validated by the 0.06 % cross-check.
- Timing is inherited from O4 rather than re-measured (declared in the manifest before running).
- `TCP_PERF_SEL_REQ` at 9.07 requests per texture instruction is measured but **not explained**.
  No claim is built on it.

## G. Artifacts

`experiment_manifest.json` (preregistration), `sets/{stage_tex,stage_all,tcp_ta,l1l2,dram}.txt`,
`build_s_*.json` (inherited from O4, hashes re-verified), `runs/` (42 runs), `o5_analysis.json`,
`tools/run_o5.py`.

- **Budget:** cycle **5 of 6**.
- **Preservation:** no builds, no deletes, no Clean; driver, cache, Registry, security and game
  files untouched.
