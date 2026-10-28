# Contributing

Thanks for picking this up. The project is paused, so you do not need permission to fork it and
carry on. Pull requests and issues are welcome; a short note on what you measured, on which
GPU/driver, is the most useful thing you can add.

## Start here

1. [README.md](README.md) — findings in five minutes.
2. [HANDOFF.md](HANDOFF.md) — detailed state, rules, and the exact point where work stopped.
3. [docs/ROADMAP.md](docs/ROADMAP.md) — what to do next, ranked.
4. [docs/PHASES.md](docs/PHASES.md) — which `research/` folder holds what.

## Environment

The measurements were taken on Windows 11 + RX 6950 XT. Anything RDNA2 on Windows should reuse the
methods; absolute numbers will differ.

| Need | Version used | Notes |
|---|---|---|
| Python | 3.11 | `pip install -r requirements.txt` |
| PowerShell | 7 (`pwsh`) | for `tools/capture_etw.ps1` |
| PresentMon | 2.5.1 (later 2.6.0) | frame capture; CSV schema handled by `tools/pmparse.py` |
| Windows Performance Toolkit | Windows SDK 10 | `wpr`, `xperf`, WPA |
| Visual Studio / MSBuild | toolset v145 | MiniEngine and C++ tools |
| DXC + DXIL validator | Windows SDK | used by `tools/dxil_roundtrip.cpp` |
| Radeon GPU Analyzer (RGA) | from Radeon Developer Tool Suite | ISA dumps (`--offline`/DX12 mode) |
| GPUPerfAPI | 4.4.5 | hardware counters in MiniEngine |
| ReShade | 6.8.0 Full Add-on x64 | only for the Cyberpunk loader phases |

Workloads used: [DirectX-Graphics-Samples](https://github.com/microsoft/DirectX-Graphics-Samples)
(MiniEngine and the D3D12 samples), [FidelityFX-SDK](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK),
3DMark Steel Nomad, Fortnite, Cyberpunk 2077 (GOG). Our MiniEngine instrumentation patch is in
[preserved_temp_claude_20260909/](preserved_temp_claude_20260909/README.md).

## Self-checks you can run without a GPU

```powershell
pwsh -NoProfile -File tools/test_capture_etw.ps1
python -B tools/c2077_native.py              # alignment parser self-test
python -B tools/etw_analyze.py --selfcheck
python -B tools/pmparse.py                   # PresentMon parser self-check
python -B tools/c2077_shader_loader.py selfcheck
```

All of these pass on a fresh clone (checked 2026-10-28). `tools/test_buildv.py` (17 build-gate
failure modes) also needs DXC from Windows SDK 10.0.26100 and a DirectX-Graphics-Samples clone at
`%TEMP%\claude\src\dxs` (paths are hard-coded at the top of the script; change them to match your
setup). Many other scripts hard-code paths from the original machine in the same way.

## Ground rules (why the numbers here can be trusted)

These were the project's rules. Please keep them if you want your results to be comparable.

- **Measure noise first.** Every performance claim needs run-to-run variance (A/A) measured
  beforehand. Report p95/p99 frame time and 1%/0.1% lows, not only mean FPS.
- **Preregister.** Write the hypothesis, metric and acceptance threshold *before* building
  variants. Do not move thresholds after seeing data; a near-miss is a negative result.
- **Prove provenance.** Gate every build on the SHA-256 of the compiled shader bytecode, and check
  the PSO that actually ran. MSBuild can silently skip recompiling.
- **Prove correctness.** Bit-exact or a declared ULP bound, checked by an oracle that has passed a
  positive control.
- **Label confidence.** confirmed / strong / probable / speculative. Close timestamps are not
  correlation. Classify components by evidence (exports, INF, runtime), never by file name.
- **Keep negatives and failed attempts.** They are in the tree on purpose.

## Safety and legal limits

- Do not modify or redistribute signed driver files (`.sys`, `.dll`, `.cat`, `.inf`), shader caches,
  or game files. One changed byte invalidates the driver package signature.
- **Never** use injection, hooking or the ReShade loader in games with anti-cheat (Fortnite,
  Call of Duty/Warzone, any online game). The loader work was done only on single-player
  Cyberpunk 2077, with backups, manifests and verified restore.
- Do not commit game-derived data (shader caches, extracted DXIL, disassembly) or third-party
  binaries. Reference them by SHA-256 instead, like
  [data/manifests/excluded_files.csv](data/manifests/excluded_files.csv).

## Repository conventions

- One folder per phase under `research/NN_name/`, holding a preregistration, raw data,
  `STATUS.md`/results, and hashes.
- Paths in old reports point at the original machine (`C:\Users\Lorenzo\Downloads\driver mod`,
  game on `E:`). Adjust them; most tools take paths as arguments.
- New docs in English, please. Existing Italian reports can stay as they are.
