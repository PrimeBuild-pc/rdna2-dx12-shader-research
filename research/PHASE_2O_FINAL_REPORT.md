# Phase 2O — final report

**Closed 2026-09-06.** Six preregistered cycles, all six executed, plus an independent clean-room
replication of the three results that carry a conclusion. This report supersedes the running
commentary in `PLAN.md` and `AUTONOMOUS_LOG.md` for everything concerning 2O.

**Question 2O was created to answer:** phase 2N had classified `Render Color` — 48.7 % of the
MiniEngine ModelViewer frame — as *texture-unit throughput bound*, on the strength of a
`TexUnitBusy` of 94.6 %. The handoff audit found that claim unobtainable with the instrumentation
that produced it. 2O had to establish what the pass is actually limited by, with every step
gated.

---

## 1. The gate

Every build in this phase passed through one fail-closed chain:

```
HLSL source → verified DXC invocation → generated header/bytecode
           → SHA-256 preregistered offline BEFORE any build ran
           → hash of the bytecode the build produced
           → hash of the PSO the running process actually created
           → baseline restored on every exit path
```

A mismatch anywhere aborts. The chain caught, among others: four defective builds in O2 (a
`CommandContext::Flush` that silently invalidated GPA registration, an incomplete-pass path, a
missing include path, a missing header); a manifest that could not be overwritten; and an
`experiment_id` that no longer matched its workspace and would have had every O6 build rejected.
**None of those produced a number.** The gate's value is exactly that: it stopped plausible-looking
measurements from existing.

## 2. The six cycles

| cycle | question | verdict |
|---|---|---|
| **O1** | does the chain source → bytecode → PSO → image actually propagate, fail-closed and reversible | **PASS** — canary A/B/A2 |
| **O2** | what do the raw counters mean, and is the workload identical frame to frame | **PASS** — aggregation validated against the SDK |
| **O3** | do the material texture samples explain the pass | **no** — 2.1 % of texture instructions, 13.9 % of TA cycles |
| **O4** | is it texture *filtering* throughput | **falsified** |
| **O5** | is it cache or memory | **falsified** (within the bounds of §5) |
| **O6** | does the pass scale with the texture instruction count | **replicated** |

### O2 — counter semantics, measured rather than read

- `TexUnitBusy%` is the **maximum over the 80 CUs**, not a mean or a sum:
  `max(TA_BUSY)/GPUBusyCycles·100`, verified exact against the SDK. The 94.6 % of 2N describes
  the busiest CU; the mean is 93.2 %.
- **Workload identity decomposed**: aggregate work counters are **bit-identical** across a
  5-pass session (40 different frames); per-instance counters and timing are not (`GPUTime`
  varies 19.9 % frame to frame). Multipass is therefore admissible for aggregate work, never for
  single timing values. The preregistered 0.1 %-on-every-counter identity criterion **failed** and
  is reported as failed: it was too coarse, mixing three different kinds of counter.
- Baseline: 39 214 PS waves, `WAVES_32 = 0` → **the pixel shader runs wave64**; 6.12 M texture
  instructions; Σ`TA_BUSY` 89.0 M; `GPUBusyCycles` 1.19 M.

### O3 — the material samples are not the pass

Dose measured, not assumed: 1.06 / 2.07 / 3.34 texture instructions removed per wave, out of
**155.9**. The three material samples are **2.1 % of the pixel shader's texture instructions**;
the other ~153 are the light and shadow-map fetches of `ShadeLights`. Response: Δ`TA_BUSY`
−2.33 / −5.71 / **−13.91 %**.

**So the three material samples cost 13.9 % of the texture unit's busy cycles while being 2.1 %
of its instructions** — instruction counts are a poor proxy for addresser cost, here by a factor
of about seven. `mat3` also removed 11.3 % of VALU work (the TBN maths dies with the sample), so
it cannot arbitrate; `mat1` is the clean point (texture −0.68 %, ALU **+0.55 %**, time −1.53 %).

Instrumentation defect found and fixed: per-shader-engine `SQ` counters return **corrupted** on
SE0/SE2 in some sessions — one event's value under another event's name, bit-identical to a
different session. `tools/sq_validity.py` now rejects such a session.

### O4 — filtering falsified

Five builds, **one pixel shader bytecode** (`52CE6C5E64AB2E82`), only the static sampler changed
in C++. ALU held fixed by construction *and verified*: `INSTS_VALU`, `INST_CYCLES_VALU`,
`ITEM_CYCLES_VALU`, `INSTS_TEX_LOAD`, `WAVES` unchanged to **0.07 %**.

Dose: aniso histogram **collapsed**, mean 1.2181 → 1.0000, −17.9 % filtering cycles.
Response: Δ`TA_BUSY` −2.73 / −3.50 / −3.54 %, Δ`GPUBusyCycles` −2.20 / −2.63 / −2.78 %.

**Turning anisotropy off entirely, or dropping to the cheapest filter the hardware has, moves the
pass by at most ~3 % while `TexUnitBusy` stays ~94 %.** The texture unit is busy, but not busy
*filtering*. Reported failures: the upward arm produced only +0.71 % of dose (the content rarely
asks for more than 8×), so bidirectionality was formally present and experimentally ineffective;
and 3.50/13.91 = 25 % is **not** a cost partition, since O3 and O4 are different interventions and
additivity was never measured.

### O5 — cache and memory falsified; stage attribution closed

- **Stage attribution needed a control to close.** `SQ_VS*` reads zero, which alone cannot
  distinguish "the vertex stage issues no texture instruction" from "the vertex stage does not run
  under that mask". Sweeping all eight shader masks: the vertex work runs under **`GS`** (the NGG
  primitive shader) and *does* issue texture instructions — **0.47 %** of the total, 3.007 per
  wave, i.e. a three-stream vertex attribute fetch. **99.53 % of the scope's texture work is
  pixel-stage**, so every ratio in O2/O3/O4 stands to within 0.47 %.
- **L0 back-pressure**: Σ`TCP_TA_REQ_STALL` / Σ`TA_BUSY` = **0.24 %** against a preregistered
  "not the cache" band of ≤ 10 %. The counter is live: the sampler intervention moves it as its
  meaning requires (TCP requests −12 %, L0 misses −30 %, stalls −24 %) while `TA_BUSY` barely
  notices.
- **L0 miss traffic**: hit rate **97.66 %**, 0.21 misses per texture instruction.
- **DRAM**: **31.88 MB = 39.6 GB/s**, against 555–621 GB/s that 2N measured on other passes of
  this same frame. Validated by a cross-check worth more than either number alone: L2 misses ×
  64 B = 31.90 MB against 31.88 MB computed independently from `EA_RDREQ_{32,64,96,128}B` —
  **0.06 % apart**.
- Derived: **156.0 texture instructions per PS wave**, **14.51 `TA_BUSY` cycles each**, 9.07 L0
  requests each, TA duty cycle **93.25 %**.

### O6 — replication at fixed bytecode

Lever: the number of lights surviving tile culling, C++ data only, four builds carrying **one**
pixel shader bytecode. Dose measured, never inferred from the stride: 155.99 → 100.86 → 49.92 →
33.40 texture instructions per wave, wave count constant to 0.19 %.

| variant | Δ tex | Δ`TA_BUSY` | Δ`GPUBusyCycles` | Δ`TA_BUSY`/Δtex | cycles per removed instruction |
|---|---:|---:|---:|---:|---:|
| `L64` | −35.37 % | −33.09 % | −32.48 % | **0.94** | **13.58** |
| `L32` | −68.05 % | −61.57 % | −60.20 % | **0.90** | **13.13** |
| `L16` | −78.63 % | −71.06 % | −69.37 % | **0.90** | **13.12** |

Both preregistered bands met — ratio ∈ [0.75, 1.25] and marginal cost ∈ [10, 19] against O5's
independent forecast of 14.5. **REPLICATED.**

OLS over all four arms: `GPUBusyCycles` = 0.170523 × tex + 136 696, R² = 0.99963, intercept
CI95 [98 292, 175 099] → **≈ 88 % of the pass lies on the sloped part**, ~12 % is fixed cost the
light loop does not touch.

## 3. The correction that reshaped the conclusion

While writing O6 I had divided `INST_CYCLES_VALU` by **320** SIMDs — the GCN layout. RDNA2 has
**2 SIMD32 per CU**, so Navi 21 has **160**. The arithmetic check that exposes it: ÷80 would give
an impossible 193 % duty cycle. The independent reviewer found the same error separately, citing
the RDNA2 ISA document.

| variant | TA duty | VALU issue duty (corrected) |
|---|---:|---:|
| `L128` | 93.61 % | **96.64 %** |
| `L64` | 92.76 % | 91.11 % |
| `L32` | 90.39 % | 79.87 % |
| `L16` | 88.45 % | 71.82 % |

Divisor-free: 1 144 278 VALU issue cycles per SIMD and 1 108 364 `TA_BUSY` cycles per CU against
1 184 031 GPU busy cycles — both within 7 % of the pass duration.

**At the baseline the pass is co-saturated, with the ALU marginally the higher of the two.** The
first draft claimed the texture addresser could be ranked above the ALU because it stayed
saturated while the ALU drained. That was wrong and is retracted.

## 4. Conclusion

> **`Render Color` is dominated by the per-light shading loop in `ShadeLights`.** About **88 % of
> the pass's GPU busy cycles lie on a line in that loop's work** (R² = 0.9996 across four arms),
> and at the baseline the loop leaves **both** the pixel-shader VALU (96.6 %) **and** the texture
> addresser (93.6 %) near saturation.

Four alternative explanations were eliminated by measurement rather than by argument:

| candidate | measurement | verdict |
|---|---|---|
| texture **filtering** throughput | anisotropy off at byte-identical bytecode: pass moves ≤ 3 % | falsified |
| L0 back-pressure on the addresser (`TCP→TA` stall) | 0.24 %, band was ≤ 10 % | falsified |
| L0 miss traffic | 97.66 % hit, 0.21 misses per texture instruction | falsified |
| DRAM bandwidth **saturation** | 39.6 GB/s against 555–621 GB/s in the same frame | falsified |

## 5. What Phase 2O does **not** establish

- **Which of the two saturated units binds at the baseline.** They are three points apart and
  every O6 arm moves both. The entire cycle is consistent with an ALU-bound pass in which each
  removed loop iteration happens to carry a stable 13.1 cycles of addresser work, and with the
  fact that removing iterations also shortens the waves. O4 is the only arm in the phase that
  moved one alone — texture, at verified-fixed ALU — and it is worth 2.6 %. Settling this needs
  the mirror of O4, an arm that moves ALU alone, ideally a factorial ALU × texture design. It was
  not run.
- **Memory latency in general.** What is excluded is bandwidth *saturation* and the `TCP→TA`
  request back-pressure specifically. No latency counter was collected.
- **Any optimisation.** Every 2O intervention is `diagnostic_only`: each one changes the image.
- **Anything about Fortnite or Warzone.** The workload is MiniEngine ModelViewer / Sponza.

## 6. Clean-room replication

All of 2O was measured with the user's ordinary desktop session running. The three results that
carry a conclusion were repeated on a machine verified idle (1.69 % total GPU, compositor only):

| arm | clean | historical | |
|---|---:|---:|---|
| A — baseline `TA_BUSY` | 88 701 626 | 88 700 482 (**+0.00 %**) | OK |
| A — baseline PS texture instructions | 6 112 392 | 6 111 703 (**+0.01 %**) | OK |
| A — baseline `GPUBusyCycles` | 1 186 280 | 1 189 003 (−0.23 %) | OK |
| B — Δ`TA_BUSY` (`s_point`) | −3.76 % | −3.50 % | OK |
| B — Δ`GPUBusyCycles` (`s_point`) | −2.56 % | −2.63 % | OK |
| C — Δ`TA_BUSY` (`L32`) | −61.75 % | −61.57 % | OK |
| C — Δ`GPUBusyCycles` (`L32`) | −60.00 % | −60.20 % | OK |
| C — marginal cycles per instruction | 13.11 | 13.13 | OK |

**CLEAN_REPLICATION = PASS.** Background load was driving none of it, and the `GPUTime` clock
excursion documented in O4/O6 reappears on the idle machine, so it is intrinsic to this GPU's
clock behaviour, not contention. → [`32_clean_replication/CLEAN_REPLICATION.md`](32_clean_replication/CLEAN_REPLICATION.md)

## 7. Independent adversarial review

Two audits by a second agent (Codex, driven through Herdr), each recomputing the tables from the
raw CSVs with its own scripts. Every figure reproduced. Findings adopted, all of which **weakened**
a claim:

- O4: `CubeMapSamplerDesc` is copy-initialised from the modified sampler, so `s12` changed too
  (out of scope, no number affected, but the manifest's invariant text was false); `defaultSampler`
  is also used by out-of-scope passes and can leave the caches differently warmed; identical DXIL
  does not guarantee identical native ISA, since the driver sees the root signature at PSO
  creation (answered by the measured ALU control); bidirectionality failed; the 25 %/75 % partition
  is invalid.
- O5/O6: the SIMD divisor (found independently); the 13.1 figure is addresser unit-cycles summed
  over 80 TAs, **not** pass-duration cycles (that coefficient is 0.171 `GPUBusyCycles`); R² is not
  causation, the dose being collinear with VALU work and loop length; an ALU-bound account
  survives all of O6; the `TCP→TA` result bounds that back-pressure only. The reviewer also
  verified positively that the TCP counter is live (80/80 instances non-zero, GPA's own numerator
  for `MemUnitStalledCycles`) and that `Render Shadow Map` does not read `radiusSq`.

Preserved: `29_o4_sampler/audit/`, `31_o6_lightcount/codex_audit_o5_o6.txt`.

## 8. Artifacts

`24_phase2o_build_gate/` (O1) · `25_gpa_validity/` · `26_gpa_hwcounters/` (4001 raw counters) ·
`27_o2_counters/` (O2) · `28_o3_material_ablation/` · `29_o4_sampler/` · `30_o5_memory/` ·
`31_o6_lightcount/` · `32_clean_replication/` · superseded prepares preserved beside their cycles.
Runners: `tools/run_o1.py`, `run_o2.py`, `run_o4.py`, `run_o5.py`, `run_o6.py`, `run_clean.py`,
`buildv.py` (the gate), `sq_validity.py`, `o2_analyse.py`, `o4_analyse.py`.

---

## FINAL VERDICT — Phase 2O

**The bottleneck of `Render Color` is the per-light shading loop of `ShadeLights`, not the
driver.** No driver setting, compiler flag, sampler state or cache configuration is the lever:
filtering, cache back-pressure, miss traffic and memory bandwidth were each eliminated by
measurement. Phases 2E–2K had already shown that no codegen lever is reachable from outside the
driver; 2O adds that on this workload the reachable cost was never in codegen to begin with. It
is in the shading algorithm — and both the ALU and the texture addresser are saturated by it,
with no evidence able to rank them.

## NEXT RECOMMENDED ACTION

**Phase 2P: reduce the real cost of the per-light loop with semantics-preserving transformations**
— common subexpression elimination the compiler is not performing, hoisting of terms invariant
across lights or across PCF taps, algebraic restructuring — judged end-to-end on `Render Color`
in the real workload, with the same build gate and correctness oracle, and with the quality of the
image explicitly not reduced.
