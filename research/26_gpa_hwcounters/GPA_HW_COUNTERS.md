# Raw GPA counters on Navi 21 — option (a). **The useful counters exist.**

**Date:** 2026-09-06 · No build of the app, no rendering, no benchmark, no measurement of any
workload. Counter *enumeration* and *pass-count* queries only.

Answers the open question left by [`../25_gpa_validity/GPA_VALIDITY.md`](../25_gpa_validity/GPA_VALIDITY.md),
which established that none of the 145 **derived** counters can separate texture-filter rate
from cache/latency or from pixel-stage ALU, and flagged as an **inference** — explicitly not
verified — that `kGpaOpenContextEnableHardwareCountersBit` might expose raw `SQ`/`TA` events.

**That inference is now verified, and it is correct.**

---

## 1. What the flag exposes

| Context | Counters |
|---|---:|
| `kGpaOpenContextDefaultBit` (what phase 2N used) | **145**, all derived |
| `kGpaOpenContextEnableHardwareCountersBit` | **4001** — 3855 additional raw hardware counters |

Confirmed **twice, independently**:

- **Offline**, through the counter library's virtual context
  (`GpaCounterLibOpenCounterContext`, DX12 / discrete counters, device `1002:73A5:C0`) —
  no D3D12 device, no GPU work. Tool: `gpaenum_hw.cpp` → `counters_hardware.csv`.
- **Live**, on the real RX 6950 XT through a real DX12 context reported by GPA as
  *"AMD Radeon RX 6950 XT"*, GPUPerfAPI 4.4.5. Tool: `gpaenum_live_hw.cpp` →
  `counters_live_hardware.csv`.

The two name sets are **identical**: 4001 = 4001, zero only-offline, zero only-live. The
offline tables are not a fiction of the SDK; the installed driver really exposes these.

Raw counters added, by hardware block:

```
TA 1120   SQ 768   TCP 480   TD 320   DB 240   SPI 216   CB 160   GL2C 144   SC 144
SX  80    GL1C 64  EA  32    GESE 24  PA  52   TIMESTAMP 6   GRBM 2   GEDIST 2   CPF 1
```

## 2. The pixel-stage ALU counters that the derived set lacks

`SQ` counters carry a **shader mask**, and 96 of them are scoped to `PS` — 24 distinct events
across the 4 shader engines (`SQ_PS0..PS3`):

| Event | What it answers |
|---|---|
| `PERF_SEL_INSTS_VALU` | vector-ALU instructions issued **by the pixel shader** |
| `PERF_SEL_INST_CYCLES_VALU` | cycles those instructions occupied |
| `PERF_SEL_ITEM_CYCLES_VALU` | per-item VALU cycles |
| `PERF_SEL_INSTS_SALU` | scalar-ALU instructions |
| `PERF_SEL_INSTS_TEX_LOAD` / `_TEX_STORE` | **texture instructions issued by the PS** |
| `PERF_SEL_WAVES`, `_WAVES_32`, `_LEVEL_WAVES` | wave count, wave32 share, occupancy level |
| `PERF_SEL_INSTS_LDS` / `_FLAT` / `_GDS` / `_SMEM`, `PERF_SEL_WAIT_INST_LDS` | other issue classes |
| `SQC_PERF_SEL_{I,D}CACHE_{REQ,HITS,MISSES}`, `LDS_BANK_CONFLICT` | instruction/scalar cache |

This is exactly the measurement `PHASE_2N_RESULTS.md` did not have when it excluded ALU by
argument. `PSBusy` says pixel-shader work exists; `SQ_PSn_PERF_SEL_INST_CYCLES_VALU` says how
much of it was arithmetic.

## 3. The filter-cost counters — in `TA`, not `TD`

`TA` (texture addresser): **14 distinct events × 80 instances** (one per CU on Navi 21).

- `PERF_SEL_TA_BUSY`
- `PERF_SEL_ANISO_{1,2,4,6,8,10,12,14,16}_CYCLE_QUADS`
- `PERF_SEL_MIP_{1,2}_CYCLE_QUADS`
- `PERF_SEL_VOL_{1,2}_CYCLE_QUADS`

The `*_CYCLE_QUADS` events bucket quads by **how many cycles their filtering cost**, so
`Σ N · ANISO_N_CYCLE_QUADS` is the cycle cost the texture pipe spent filtering — directly
comparable against `TA_BUSY`. That is the separation `TexUnitBusy` cannot give, because its
own documentation says it includes *"all extra fetches and any cache or memory effects"*.

`TD` on this ASIC exposes **only** ray-tracing BVH events
(`PERF_SEL_RAY_TRACING_BVH4_*`, 4 events × 80). Not useful here — the filter question lives in
`TA`.

## 4. Pass counts — measured, not assumed

`GpaCounterLibGetPassCount`, offline, on the hardware-enabled context:

| Set | Counters | Passes |
|---|---:|---:|
| all 36 `SQ_PS*` ALU/wave/texture-instruction counters | 36 | **1** |
| `TA_BUSY` on all 80 CUs | 80 | **1** |
| `TA_BUSY` + one `ANISO_N` bucket, all 80 CUs | 160 | **1** |
| full `TA` aniso+mip+vol distribution, any instance count (1, 4 or 80) | 14…1120 | **7** |
| `SQ_PS*` + `TA_BUSY` | 116 | 2 |
| `SQ_PS*` + `TA_BUSY` + `GPUTime` (a derived counter) | 117 | 3 |
| all 4001 counters | 4001 | 38 |

Two structural facts fall out:

1. **Pass count is driven by events per block, not by instance count.** 1, 4 or 80 TA
   instances of the same 14 events all cost 7 passes. Per-CU coverage is therefore free.
2. **`TA` holds 2 events per pass** on this ASIC — the cumulative sweep goes
   1,1,2,2,3,3,4,4,5,5,6,6,7,7 as events are added.

Mixing a derived counter into a raw set costs an extra pass, so raw and derived should be
captured separately.

## 5. What this changes

**`GPA_VALIDITY.md` stands as written** — it was scoped to the 145 derived counters of the
default context, and within that scope its conclusion is right. What changes is the
consequence drawn from it:

- ~~"O5 as preregistered is not executable"~~ → **O5 is executable**, with raw counters.
  Not with the derived set, and not with the instrumentation phase 2N used.
- The ALU alternative that 2N excluded by argument can now be **measured**, single-pass.
- Option **(c)** — dropping the causal claim and doing only time-based ablations — is **not**
  needed. Recorded per the instruction "if no useful counters emerge, go straight to (c)".

## 6. Multipass validity (finding A03) — now testable rather than assumed

Each half of the discriminator is single-pass, so the pair can be captured as two independent
single-pass sessions instead of one multipass session.

More usefully: the O1 harness is already the frozen workload the SDK's multipass rule requires
— camera frozen, TAA / motion blur / exposure adaptation disabled, fixed 1/60 timestep, all
128 shadow slices resolved before the capture frame. Cycle O1 showed that configuration
produces **bit-identical images across three independent processes**. So the question
"do successive frames present an identical `Render Color` workload?" is now a cheap, decisive
experiment (compare the capture at frame *N* and frame *N+1*) instead of an assumption. That
belongs in **O2**, and it gates whether any multipass set may be used at all.

## 7. Limits — what is NOT established here

- Enumeration and scheduling only. **No counter has been read from any workload.** Nothing here
  says anything about `Render Color`, texture throughput, or ALU in this application.
- Raw counters are per-instance events with no derived normalisation. Their semantics
  (units, whether they count quads, cycles or instructions, per-SIMD versus per-CU aggregation)
  must be pinned down against AMD documentation before any number is interpreted. Guessing
  their meaning would repeat the mistake this phase exists to correct.
- `GpaEnableCounterByName` on the *live* session, sample begin/end around the right scope, and
  the ten unchecked GPA return paths listed in `GPA_VALIDITY.md` §6 all still need fixing
  before a capture is trustworthy. Enumerating a counter is not the same as sampling it
  correctly.
- The 4001-counter context may behave differently from the 145-counter one with respect to
  clock modes and stability; the flag values for clock mode are independent bits and were left
  at default in this enumeration.

## Files

`gpaenum_hw.cpp` (offline virtual context; `passes <file>` mode queries a named set) ·
`gpaenum_live_hw.cpp` (live DX12 context) · `build.cmd` ·
`counters_default.csv` (145) · `counters_hardware.csv` (4001, with block/instance/event/mask) ·
`counters_live_hardware.csv` (4001, live) · `set_*.txt` (the candidate sets measured above)
