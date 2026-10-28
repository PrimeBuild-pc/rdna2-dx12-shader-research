# Phase 2U — preregistration

**Written 2026-09-07, before any new workload was opened and before any 2U measurement.**

Phase 2T measured the frozen pipeline's hit rate: **0 of 4 workloads, 5 transformations built,
none accepted**. The stated goal of 2U is to raise that rate. That goal is dangerous, because a
hit rate is trivially raised by choosing the denominator after seeing the numerator. Everything
below exists to stop that.

## The three changes to the pipeline, and why each is legitimate

2T's own results say where the pipeline lost, and each change answers one of those losses. No
change touches the acceptance rule for a transformation.

### 1. Ceiling probe promoted to a gate, run **before** any hypothesis

2T spent zero attempts on W1 and W3 and was right to: a 5.76 µs dispatch and a 480 ns draw cannot
be improved by changing a shader. It reached that conclusion from the profile. W4 showed the
better instrument: **ablate the candidate shader's body and measure what the workload loses**.
That number is the ceiling on everything the pipeline could ever do there.

- The probe runs on every workload, immediately after the baseline, before any hypothesis.
- **Ceiling < 3 % of the primary region → the workload is closed as `NO_HEADROOM`.** No attempts
  are spent. Its reason is recorded and it **stays in the denominator of the primary hit rate**.
- The probe is a diagnostic, never a candidate: its image is deliberately wrong and it is never
  counted as an attempt.

**Both hit rates are always reported**, and the primary one is the strict one:

- **primary** = hit workloads ÷ workloads attempted — directly comparable to 2T's 0/4.
- **conditional** = hit workloads ÷ workloads whose ceiling passed the 3 % gate. This one may only
  ever be quoted next to the primary and with its denominator spelled out.

### 2. Ceiling decomposition, so a hypothesis has to name its target

2T's W4 had a 16.6 % ceiling and the pipeline took 0.3 % of it, because both candidates were
aimed by instinct at whatever the ISA made most visible. In 2U, a qualifying workload's ceiling is
first **decomposed**: the shader body is ablated in sub-blocks, one at a time, and each block's
share of the ceiling is measured, the way phase 2O's dose–response did.

Then, **before it is built**, every candidate transformation must declare in the manifest:

1. which measured sub-block it targets,
2. that block's measured share of the ceiling,
3. its predicted Δ, as a number, derived from that share.

The prediction is recorded and scored against the measurement afterwards, hit or miss. A
hypothesis that targets no measured block is not built.

### 3. A two-tier correctness rule, both tiers fixed here

2T's byte-exact rule rejected 3 of 5 candidates. It was preregistered and it stays, but it is
also stricter than what phase 2Q established as sound. So both tiers are declared now, before any
2U measurement, and **every result is reported under both**:

- **Tier A — exact.** The render target is byte-identical to the baseline's. Unchanged from 2T.
- **Tier B — bounded.** Declared acceptable only if **all** of: no NaN, no Inf, no new negative
  zero; **≤ 2 ULP** per component in a float32 capture where one exists, or ≤ 1 LSB per component
  in a quantised capture; **and ≤ 0.01 %** of pixels differ at all. A transformation whose
  difference is a *different texel*, a *different branch* or a *different sample*, rather than a
  rounding of the same arithmetic, fails tier B regardless of how few pixels it touches — 2T's
  `gather_pcf` (43 pixels, max delta 41) is the worked example of a tier-B failure.

A transformation is **ACCEPTED** only at tier A. Tier B verdicts are reported as
`ACCEPTED_TIER_B` and counted in a separate column. **The headline hit rate uses tier A only.**

## The acceptance rule for a transformation — unchanged from 2P and 2T

Median Δ of the primary region ≤ −max(1 %, 3 × N95) with N95 from that workload's own A/A control,
**every** paired process negative, and correctness passing. Runs are paired with the base run
nearest in wall-clock time, never by rep number — the defect 2T found and fixed. Never fewer than
4 paired processes per variant.

## Measurement memory

Every transformation ever measured by this project — 2K, 2L, 2M, 2P, 2R, 2T and 2U — is collected
into `research/MEASUREMENT_MEMORY.csv`, one row per measured variant, with: phase, workload,
shader, transformation kind, the ISA deltas (instructions, VGPR, texture instructions,
transcendentals), the predicted Δ where one was recorded, the measured Δ, the correctness tier and
the verdict. It is written from the existing artefacts, not from recollection; a row whose source
artefact cannot be found is not written.

Its use in 2U is declared here in advance: **it ranks hypothesis kinds by measured median Δ, and
nothing else.** It never overrides the ISA, never proposes a transformation on its own, and a
hypothesis drawn from it is labelled `memory` in the manifest and counted separately, exactly as
2T counted `zeroskip_shadow`.

## Workloads

**W4 `D3D12VariableRateShading` is carried forward from 2T.** It is the only workload in the
project with a proven ceiling (16.6 %), a byte-exact oracle stable over 14 processes and two
sessions, and an A/A of 0.44 %. Re-attempting it is not cherry-picking as long as it is reported
as a re-attempt: **its 2T miss stands in the record and is not erased by a 2U hit.**

New workloads, **chosen now by directory name and one-line description only**, from the same
repository and toolchain, in this order:

| # | workload | why, from the name alone |
|---|---|---|
| **U-A** | `D3D12DynamicIndexing` | per-draw material indexing into a descriptor array: a pixel shader that does real per-pixel work |
| **U-B** | `D3D12Raytracing` | DXR, which this RX 6950 XT supports; a ray-generation and hit-shader pipeline is structurally unlike everything attempted so far |
| **U-C** | `D3D12HDR` | a full-screen tone-mapping pixel shader, i.e. a pass that is by construction pixel-shader bound |
| U-D | FidelityFX SDK sample | reserve, used only if two of U-A..U-C cannot be built or have no measurable pass |

Same rules as 2T: a workload that fails to build, or has no measurable pass, or fails the ceiling
gate, **stays in the denominator with its reason recorded and is not swapped for an easier one.**

## Budget and stopping

**Twelve cycles.** The phase ends at twelve, or when W4 and U-A..U-C are closed, whichever comes
first. A workload that consumes four cycles without an accepted transformation is closed as a
miss and the phase moves on.

## What is out of scope for 2U, and stays out

No modification to driver, cache, Registry, security settings or games. No injection, no hooking,
no patching of any executable. The controlled workloads are open-source samples built from source
on this machine; nothing else is modified.

---

# Milestone C2077 — preregistration (separate, starts only after 2U)

Cyberpunk 2077 is **not installed** as of writing; GOG Galaxy is. The milestone is written now so
its scope cannot expand after the first measurement looks interesting.

## What this milestone can and cannot be

The frozen pipeline **rebuilds a shader from source**. Cyberpunk ships no shader source and its
files are not to be modified. **The transformation pipeline therefore cannot run on Cyberpunk, and
no part of this milestone will claim it did.** What can run is the half of the pipeline that comes
before the hypothesis: profile, attribute, classify the limit, and state what the method would
have to be able to reach in order to matter here.

## Scope, fixed here

1. **Non-invasive measurement only**: PresentMon 2.5.1 (ETW consumer, no injection), Windows
   ETW/WPR, the game's own built-in benchmark, and AMD's own driver-side capture (RGP via the
   Radeon Developer Panel) **only if it works without modifying the game**. If any tool requires
   injecting into or altering the game, it is not used.
2. **The game is launched by the operator, by hand, through GOG**, never by a script.
3. **No modification of any game file, no config change beyond the game's own in-game settings
   menu, no Registry change, no environment-variable injection into the game process** in this
   milestone. The `AMD_SC_OPTIONS` surface found in phase 1.5B stays untouched here; if it is ever
   used it will be preregistered separately, with its own risk statement.
4. Deliverable: run-to-run variance measured **before** any claim, the frame-time distribution
   (p95/p99, 1 % and 0.1 % low, stutter count by the written definition in `METHOD.md`), a CPU/GPU
   bound classification, and an honest answer to one question: **is there a shader-side ceiling
   here at all that a source-level method could address, and how would we ever know without the
   source?**

## Performance controls, not targets

3DMark Steel Nomad (installed, `E:\3DMark`) and Unigine Superposition (not installed) are
**controls**: they establish that the machine is in the same state between Cyberpunk sessions.
**Neither is a modification target.** Any 3DMark action needing its GUI is delegated to the
operator; nothing in 3DMark or Superposition is modified, patched or scripted into.

## Fortnite / Warzone

**Not opened by this milestone.** It may be proposed only after Cyberpunk is closed, as a separate
milestone, and it is limited in advance to passive profiling and to changes made through the
games' own settings. No injection, no hooking, no anti-cheat interference, no modification of any
protected game file — a limit that does not move regardless of what the Cyberpunk result is.
