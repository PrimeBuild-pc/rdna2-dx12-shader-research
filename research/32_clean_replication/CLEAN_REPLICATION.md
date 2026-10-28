# Clean-room replication of Phase 2O's decisive results — **PASS**

**Date:** 2026-09-06 · **Experiment ID:** `R_20260906_195446` · cycle **1 of 10** of this session.
Criteria, tolerances and the historical values to beat were written into
`experiment_manifest.json` **before the first run**.

The whole of Phase 2O was measured while the user's ordinary desktop session was running. This
cycle repeats only the three results that carry a conclusion, on a machine verified idle
(`environment_snapshot.md`: no browser, no Discord, no game, no encoder; **1.69 % total GPU**,
desktop compositor only; live CPU under 0.5 %). No application was closed to achieve this.

**No build.** The executables come from the O4 and O6 build records, SHA-256 re-verified at
prepare and again at every run, pixel shader bytecode still `52CE6C5E64AB2E82`. Old and new
numbers are never pooled — the criteria compare them.

## Arm A — null / baseline

| quantity | clean | historical | Δ | tolerance | |
|---|---:|---:|---:|---:|---|
| `TA_BUSY` (Σ 80 CU) | 88 701 626 | 88 700 482 | **+0.00 %** | ±2 % | OK |
| PS texture instructions | 6 112 392 | 6 111 703 | **+0.01 %** | ±2 % | OK |
| `GPUBusyCycles` | 1 186 280 | 1 189 003 | **−0.23 %** | ±5 % | OK |

`GPUTime` per process: 793 700 / 711 300 / 796 880 ns — the same first-process clock excursion
seen in O6, so the clock-regime artefact is **not** caused by background load either.

## Arm B — sampler at byte-identical bytecode (`s_point` vs `s_base`)

| metric | clean | historical | |diff| | tolerance | |
|---|---:|---:|---:|---:|---|
| Δ`TA_BUSY` | −3.76 % | −3.50 % | 0.26 pt | 1.75 pt | OK |
| Δ`GPUBusyCycles` | −2.56 % | −2.63 % | 0.07 pt | 1.31 pt | OK |

O4's conclusion survives: dropping to the cheapest filter the hardware has moves the pass ~2.6 %.

## Arm C — light-count dose-response (`L32` vs `L128`)

| metric | clean | historical | |diff| | tolerance | |
|---|---:|---:|---:|---:|---|
| Δ texture instructions (dose) | −68.05 % | −68.05 % | 0.00 pt | 5 pt | OK |
| Δ`TA_BUSY` | −61.75 % | −61.57 % | 0.18 pt | 5 pt | OK |
| Δ`GPUBusyCycles` | −60.00 % | −60.20 % | 0.20 pt | 5 pt | OK |
| marginal cycles per removed instruction | **13.11** | 13.13 | — | band [10, 19] | OK |

## Verdict

**CLEAN_REPLICATION = PASS**, on every arm, with margins one to two orders of magnitude inside
the tolerances. The work counters are effectively identical (+0.00 %, +0.01 %) and even the
timing agrees to 0.23 %.

**Consequence:** background desktop load was not driving any Phase 2O conclusion, and the
`GPUTime` instability documented in O4/O6 is intrinsic to this machine's clock behaviour rather
than contention. Phase 2O's results stand as written, and 2P may proceed.

Artifacts: `experiment_manifest.json`, `environment_snapshot.md`, `build_*.json`, `sets/`,
`runs/` (31 runs), `clean_replication.json`, `tools/run_clean.py`.
