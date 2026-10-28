# Phase 1A — Inventario software (verificato 2026-09-03)

Generato da [`tools/inventory.py`](../../tools/inventory.py).
Dati grezzi: `hardware_info.json`, `windows_info.json`, `gpu_info.json`, `project_tree.txt`.

## Sistema

| | |
|---|---|
| CPU | AMD Ryzen 7 5800X3D, 8C/16T, base 3400 MHz, L3 96 MB |
| Motherboard | MSI MPG X570 GAMING EDGE WIFI (MS-7C37) rev 1.0 |
| RAM | 32 GB |
| GPU | AMD Radeon RX 6950 XT — `PCI\VEN_1002&DEV_73A5&SUBSYS_05041043&REV_C0` (Navi 21) |
| Display | 2560 × 1440 |
| OS | Windows 11 Pro 25H2, build **10.0.26200.9168**, x64 |
| Piano energetico | `zoic's ultimate performance(amd)` |
| **HAGS** (`HwSchMode`) | **2 = abilitato** |
| Game DVR | 0 (disabilitato) |
| Defender real-time | **attivo** (`DisableRealtimeMonitoring = False`) |

Due voci contano per il resto della ricerca:

- **HAGS attivo** cambia chi fa lo scheduling delle command queue: la Fase 1G (GPUView/ETW) va
  letta sapendolo, e un eventuale A/B su HAGS è un esperimento a sé.
- **Defender real-time attivo** è rumore di fondo sia per i benchmark sia, soprattutto, per la
  futura analisi ProcMon della shader cache: intercetta gli accessi ai file.

## Driver grafico

| | |
|---|---|
| Driver **installato** | **32.0.21045.5002** (17-Aug-2026) |
| INF installato | `u0203303.inf_amd64_e5876a26758f154c`, sottocartella binari `B026363` |
| Package **nel progetto** | Adrenalin 26.9.1, DriverVer `32.0.21045.9003` (27-Aug-2026) |
| INF del package | `u0203729.inf`, sottocartella binari `B026432` |

**Non sono la stessa revisione.** Confronto hash in
[`research/01_driver_map/installed_vs_package.csv`](../01_driver_map/installed_vs_package.csv):
tutti e 7 i binari grafici confrontati differiscono, e 4 di essi hanno **dimensione identica al
byte ma contenuto diverso** — `amdxc64.dll` incluso, che per giunta dichiara la stessa
FileVersion (8.18.10.0500) in entrambe. Per identificare una revisione serve l'hash.

## Strumenti nel progetto

| Tool | Versione | Percorso |
|---|---|---|
| Radeon GPU Profiler | 2.7.0.32 | `RadeonDeveloperToolSuite-2026-05-28-1806/.../RadeonGPUProfiler.exe` |
| Radeon GPU Analyzer | 2.14.2.8 | `.../RadeonGPUAnalyzer.exe` (+ `rga.exe`) |
| Radeon Developer Panel / Service | RDTS 2026-05-28 | `.../RadeonDeveloperPanel.exe`, `RadeonDeveloperService.exe` |
| RGD / RMV / RRA | RDTS 2026-05-28 | `.../rgd.exe`, `RadeonMemoryVisualizer.exe`, `RadeonRaytracingAnalyzer.exe` |
| Process Monitor | 4.1 | `ProcessMonitor/Procmon64.exe` |
| Sigcheck | 2.91 | `Sigcheck/sigcheck64.exe` |
| Ghidra | 12.1.3 PUBLIC (build 2026-08-17) | `ghidra_12.1.3_PUBLIC_20260817/ghidra_12.1.3_PUBLIC/ghidraRun.bat` |
| Package AMD estratto | Adrenalin 26.9.1 (2.7 GB, 724 file) | `whql-amd-software-adrenalin-edition-26.9.1-win11-a/` |

Nella RDTS sono presenti anche `amd_comgr_3.dll` e `amdgpu_dis.dll`: il **disassemblatore ISA
AMD GPU** e il compiler-manager. Serviranno per interpretare l'ISA estratto da RGP/RGA.

## Strumenti di sistema

| Tool | Versione | Percorso |
|---|---|---|
| PresentMon CLI | **2.5.1** | `C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication\PresentMon-2.5.1-x64.exe` |
| PresentMon GUI + service | 2.x | `C:\Program Files\Intel\PresentMon\PresentMonApplication\` |
| Windows Performance Toolkit | 10.0.26100 | `C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\` (`wpa.exe`, `xperf.exe`) |
| WPR | in-box | `C:\Windows\System32\wpr.exe` |
| Python | 3.11 | `C:\Users\Lorenzo\AppData\Local\Programs\Python\Python311\python.exe` |

Altre installazioni di PresentMon presenti sul sistema (**da non usare**, per non mescolare
versioni nei dati): CapFrameX 2.4.1, RTSS 1.10.0 / 2.3.1.

Pacchetti Python: `pandas`, `numpy`, `scipy`, `matplotlib 3.10.9` già presenti;
**installati in questa fase**: `pefile 2024.8.26`, `lief 1.0.0`, `capstone 5.0.7`.

## Dati sperimentali già raccolti

| Cartella | Contenuto |
|---|---|
| `research/fortnite_DX12_PerformanceMode/` | 7 run PresentMon, ~15 MB ciascuno, + `-stats.csv` |
| `research/3DMark_SteelNomad_DX12/{1..7}/` | 7 run PresentMon + screenshot risultato 3DMark |
| `C:\Users\Lorenzo\Documents\PresentMon\Captures\` | 4 capture COD preesistenti (AFMF / FSR3-FG / cap 120 / uncapped) — **non** usate in questa analisi |

## Non ancora disponibile

- **Black Myth: Wukong Benchmark**: non installato. Blocca la Fase 1F.
