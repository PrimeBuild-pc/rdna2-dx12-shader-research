# Rebuilding the environment and the missing data

The original workstation was wiped on 2026-10-28. Everything that could be published is in git
or in the [v1.0-archive release](https://github.com/PrimeBuild-pc/rdna2-dx12-shader-research/releases/tag/v1.0-archive).
This page lists **everything else**, where to get it, and how to regenerate it. A machine-readable
copy is in [data/manifests/environment.json](../data/manifests/environment.json); an AI agent can
follow it step by step.

## 1. Restore the published data

Some paths are longer than Windows' 260-character limit: enable long paths or clone into a short folder.

```powershell
git config --global core.longpaths true
git clone https://github.com/PrimeBuild-pc/rdna2-dx12-shader-research C:
dna2
cd C:dna2
gh release download v1.0-archive          # or download the 5 assets from the release page
# unzip/extract every asset at the repository root (paths inside start with research/ or preserved_temp_claude_20260909/)
7z x large-measurement-data.zip; 7z x wpr-etw-event-exports.zip
7z x oracle-frame-dumps.7z; 7z x msbuild-diagnostic-logs.7z; 7z x extra-analysis-data.7z
pip install -r requirements.txt
```

Every extracted file can be checked against
[data/manifests/release_data_files.csv](../data/manifests/release_data_files.csv) (see
[data/README.md](../data/README.md)).

## 2. Reference system

| Item | Value during the measurements | Notes |
|---|---|---|
| GPU | AMD Radeon RX 6950 XT, Navi 21, PCI `1002:73A5` rev C0 | any RDNA2 card can reuse the methods |
| CPU / RAM / board | Ryzen 7 5800X3D / 32 GB / X570 | |
| OS | Windows 11 Pro 25H2, build 26200 | HAGS on (`HwSchMode=2`), display 2560×1440 |
| Driver, Sep 2026 (all baselines, 2O–2U, Cyberpunk 60–63) | **32.0.21045.5002** (Adrenalin 26.8.1, INF `u0203303.inf`) | do not pool numbers across drivers |
| Driver, mid-Oct 2026 (phases 64–68) | 32.0.21045.11001 | |
| Driver at archive time | 32.0.21045.16010 (Adrenalin 26.10.1) | adds FSR 4.1 on RX 6000 |
| Driver package analysed in phase 1B | `whql-amd-software-adrenalin-edition-26.9.1-win11-a.exe`, 986,362,744 bytes, SHA-256 `b06cd91e9a22078d7f10b7a19530e0bdb51214b10693da2577fd3f0617db2bdb` | **not** the installed driver; AMD no longer hosts old installers reliably, check the SHA-256 if you find one |

Old AMD drivers: <https://www.amd.com/en/support/download/previous-drivers.html>.

## 3. Tools to install

| Tool | Version used | Where to get it | Used by |
|---|---|---|---|
| Python | 3.11 + numpy, pandas, scipy, matplotlib, pefile 2024.8.26, lief 1.0.0, capstone 5.0.7 | python.org, `requirements.txt` | all `tools/*.py` |
| PowerShell | 7 | `winget install Microsoft.PowerShell` | `tools/capture_etw.ps1` |
| PresentMon | **2.5.1** for all historical captures (2.6.0 later) | <https://github.com/GameTechDev/PresentMon/releases> | frame capture, `tools/pmparse.py` |
| Windows Performance Toolkit (WPR/xperf/WPA) | Windows SDK 10.0.26100 | Windows SDK / ADK | `tools/capture_etw.ps1`, phase 1.5A, 63 |
| Windows SDK (DXC, `dxil.dll`, validator) | 10.0.26100.0; dxcompiler/dxil 1.8.2502.11 | Windows SDK | build gates, `tools/dxil_roundtrip.cpp` |
| Visual Studio 2026 Build Tools | MSVC 14.51.36231, toolset v145 | visualstudio.microsoft.com | MiniEngine, D3D12 samples, C++ tools |
| Radeon Developer Tool Suite | 2026-05-28-1806: RGA 2.14.2, RGP 2.7, RDP 3.5.0, RMV 1.15, RGD 1.6.3, RRA 1.11 | <https://gpuopen.com/tools/> | ISA dumps (RGA), RGP traces |
| GPUPerfAPI | 4.4.5 | <https://github.com/GPUOpen-Tools/gpu_performance_api/releases> | hardware counters (phases 2N–2U) |
| Ghidra | 12.1.3 (build 2026-08-17) | <https://github.com/NationalSecurityAgency/ghidra/releases> | static driver analysis (optional) |
| Sysinternals Process Monitor / Sigcheck | 4.1 / 2.91 | <https://learn.microsoft.com/sysinternals/> | phase 1B, 1C |
| ReShade | 6.8.0 "Full Add-on" x64; setup SHA-256 `afe4c8f13048306307983b8b3d41d5bf00a86820440b0e57dea10950e1176445`; SDK API 20, commit `18deaa52de0c425a78b329e9cb3c497281cd00ec` | <https://reshade.me> | Cyberpunk loader (phases 66–68) only |
| 3DMark (Steel Nomad DX12 v1) | — | Steam / UL | machine-state control |

## 4. Source workloads

| Workload | Exact source | Notes |
|---|---|---|
| MiniEngine ModelViewer + D3D12 samples | <https://github.com/microsoft/DirectX-Graphics-Samples> at commit `213dd4fd4918ea009dd8f35adee1aff1f2ecaba4` | apply `preserved_temp_claude_20260909/dxs-tracked-changes.patch` and copy `dxs-untracked/` (instrumentation, GPA profiler, shader inventory); see its README |
| FidelityFX-SDK (2K corpus) | <https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK> at commit `60f4ea81909200d8542eca14dccb2628b763a9a3` | shallow + sparse clone was enough |
| Cyberpunk 2077 | GOG, **game version 2.31** for every measurement | the game is now at 2.5 (Oct 2026): shaders and performance changed, so phases 60–69 must be re-baselined |
| Fortnite | Epic, DX12 Performance Mode, Sep 2026 build | anti-cheat: passive capture only |

## 5. Missing artifacts and how to regenerate them

The SHA-256 of every original file is in
[data/manifests/excluded_files.csv](../data/manifests/excluded_files.csv). Regenerated files will
**not** match those hashes when driver, game or toolchain versions differ; that is expected.

| Missing artifact | Why it is missing | How to get it back |
|---|---|---|
| WPR traces `research/63_*/**/*.etl` (21 GB Cyberpunk run, smoke run) | too large, and a system-wide trace contains private data of the original machine (all processes, command lines, paths) | Re-capture: follow [research/C2077_OPERATOR_PROCEDURE.md](../research/C2077_OPERATOR_PROCEDURE.md), run `pwsh tools/capture_etw.ps1` around the built-in benchmark (1440p fullscreen, RT/upscaling/FG off), then `python tools/c2077_native.py` to align and `tools/etl_extract.cpp` + `tools/c2077_etw_offline.py` / `c2077_gpu_queue.py` to re-derive the offline outputs. Fortnite ETLs were already deleted in Sep 2026 (derived CSVs kept). |
| Cyberpunk shader caches (`research/64_*/copies/`, repacked caches in `65_*`) | game content (CD PROJEKT RED) | Copy `engine\shader_final.cache` and `engine\staticshader_final.cache` from your own install (game 2.31 hashes: `339145371a3b…3ccfa` and `bff160947aba…59ff`), then run `research/64_*/probe_containers.py`. |
| Extracted DXIL / LLVM IR (`*.dxil`, `*.ll` in 64, 65, 68) and the add-on payload header | game content | Re-extract with the offsets in each phase's `extraction.json` / `artifact_manifest.json`, then disassemble with DXC (`dxc -dumpbin`). |
| Our build outputs: `.exe`, `.dll`, `.obj`, `.lib`, `.pdb`, `.cso`, `.addon64` | rebuildable, some embed game bytecode | MiniEngine variants: `tools/buildv.py` (forces `-t:Rebuild`, checks the compiled shader header hash against the preregistered SHA-256 in each phase). C++ tools: build commands are in each phase's `build/*.log` / `*.command.json`. |
| Third-party binaries (AMD package, RDTS, GPUPerfAPI DLLs, ReShade DLL/setup, Ghidra, Sysinternals, PresentMon 2.5.1 copy) | redistribution not allowed or pointless | Download from section 3 and compare the SHA-256 in the excluded manifest. |
| Microsoft public PDBs / symcache (`63_*/symbols`, `symcache`) | Microsoft content | Microsoft symbol server: `_NT_SYMBOL_PATH=srv*C:\symbols*https://msdl.microsoft.com/download/symbols`. |
| SHA-named backup files in phase 66–68 rollback folders | copies of game / ReShade files | not needed; the loader's own manifest lists them. |

## 6. What a contributor will most likely need to redo

1. Install the tools in section 3 on an RDNA2 machine and run the self-checks in
   [CONTRIBUTING.md](../CONTRIBUTING.md).
2. Re-baseline Cyberpunk on the current game and driver: five runs of the built-in benchmark
   with PresentMon (procedure above), before any shader experiment.
3. Re-extract the shader caches from your install and redo the phase-68 back-buffer catalogue on
   the current game version (shader hashes almost certainly changed with 2.5), then continue with
   phase 69 as described in [ROADMAP.md](ROADMAP.md).

## Notes for AI agents

- Treat [environment.json](../data/manifests/environment.json) as the install list. Never run the
  ReShade loader in a game with anti-cheat; never modify signed driver files.
- Paths in old reports and scripts point at `C:\Users\Lorenzo\Downloads\driver mod` and `E:\GOG\Cyberpunk 2077`.
  Replace them; most tools take paths as arguments, some hard-code them at the top of the file.
