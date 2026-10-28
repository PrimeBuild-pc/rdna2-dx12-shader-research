# Third-party notices

This repository contains research outputs that include or quote small amounts of third-party
material. Each item stays under its original license; the MIT / CC BY 4.0 licenses of this
repository do not apply to it.

| Material | Where | License / status |
|---|---|---|
| Microsoft DirectX-Graphics-Samples (MiniEngine, D3D12 samples): HLSL sources and headers copied as experiment baselines and variants; MiniEngine instrumentation patch | `research/*/baseline_sources/`, `research/*/preregistered/`, `preserved_temp_claude_20260909/` | MIT, © Microsoft. https://github.com/microsoft/DirectX-Graphics-Samples |
| AMD FidelityFX-SDK compute shaders used in the 2K corpus | `research/20_real/` | MIT, © Advanced Micro Devices. https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK |
| Intel PresentMon reference text | `research/63_c2077_wpr_attribution/fs1440_r1/offline_20261016/sources/` | MIT, © Intel. https://github.com/GameTechDev/PresentMon |
| ReShade 6.8.0 add-on API | used by `tools/c2077_*.cpp` (headers not included) | BSD-3-Clause, © Patrick Mours. https://github.com/crosire/reshade |
| AMD driver metadata (file lists, hashes, PE version info, exported symbol and option names) | `research/00_inventory/`, `01_driver_map/`, `09_umd_settings/`, `10_sc_probe/`, `13_scoptions_static/` | Facts extracted for interoperability research. No AMD binaries or code are included. |
| Short DXIL excerpts and hashes of Cyberpunk 2077 shaders | reports in `research/64_*`–`69_*` | Quoted minimally for research. No game files, caches or full shaders are included. © CD PROJEKT RED. |

Excluded entirely (see [data/README.md](data/README.md)): AMD driver package and installer, Radeon
Developer Tool Suite, Ghidra, Sysinternals, ReShade binaries and source copies, RenoDX and
REDmod/WolvenKit files, GPUPerfAPI binaries, Microsoft PDBs, Cyberpunk 2077 shader caches and
extracted shaders.

All trademarks belong to their owners. This project is not affiliated with or endorsed by AMD,
Microsoft, Intel, CD PROJEKT RED, Epic Games, Activision or UL.
