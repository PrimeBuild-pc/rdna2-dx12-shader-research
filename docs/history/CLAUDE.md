# AMD RDNA2 Driver Optimization Research

Ricerca sul software stack grafico AMD su Windows per capire **dove** si può
realisticamente ottimizzare il percorso shader/pipeline DX12 su questo sistema.
Fase 1 = **solo analisi**. Nessuna modifica al driver.

## Sistema target (verificato 2026-09-03)

| | |
|---|---|
| GPU | AMD Radeon RX 6950 XT (Navi 21, RDNA2) |
| Driver installato | 32.0.21045.5002 (17-Aug-2026) |
| CPU / RAM | Ryzen 7 5800X3D / 32 GB |
| MB | X570 |
| OS | Windows 11 Pro 10.0.26200 |
| API primaria | DirectX 12 |

## Target applicativi

1. **Fortnite** (DX12) — `E:\Fortnite`
2. **Call of Duty / Warzone** — `E:\Call of Duty` (cod25)
3. **Black Myth: Wukong Benchmark** — workload controllato, *non ancora installato*

Gli esperimenti invasivi si fanno **solo** sul workload controllato (Wukong),
mai su Fortnite/Warzone.

## Vincoli permanenti

- Niente modifiche a `.sys` / `.dll` / `.cat` / `.inf`; niente sostituzione di file di cache.
- Niente DLL injection, hooking DX, patch degli eseguibili nei giochi con anti-cheat.
- Niente bypass/interferenza anti-cheat. Se una tecnica lo richiede → si testa su Wukong.
- Niente driver sperimentali, niente modifiche a boot/security di Windows.
- Modifiche persistenti al Registry solo con approvazione esplicita.
- Analisi binaria sempre su **copie**; SHA-256 prima di toccare qualsiasi file.
- Non ottimizzare le impostazioni GUI Adrenalin (già configurate a mano).
- Linux/Mesa/RADV/Vulkan non sono il percorso di ricerca primario.
- Un solo byte modificato in un file coperto dal catalogo invalida la firma del package.

## Layout progetto

```
driver mod/
├── whql-amd-software-adrenalin-edition-26.9.1-win11-a[.exe]   package AMD estratto (READ-ONLY)
│   └── Packages/Drivers/{AMDISP,Display,Audio,AMDNPUMCDM,AMDNPUWDF,RadeonLED,SBDrv}
├── RadeonDeveloperToolSuite-2026-05-28-1806/   RGP, RGA, RGD, RMV, RRA, RDP
├── ProcessMonitor/  Procmon64.exe
├── Sigcheck/        sigcheck64.exe
├── ghidra_12.1.3_PUBLIC_20260817/
└── research/        output (creato per fase)
```

## Strumenti (percorsi verificati)

| Tool | Percorso |
|---|---|
| PresentMon 2.5.1 CLI | `C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication\PresentMon-2.5.1-x64.exe` |
| PresentMon output | `C:\Users\Lorenzo\Documents\PresentMon\Captures\` (contiene già capture COD) |
| Process Monitor | `.\ProcessMonitor\Procmon64.exe` |
| Sigcheck | `.\Sigcheck\sigcheck64.exe` |
| RGP / RGA / RDS | `.\RadeonDeveloperToolSuite-.../Radeon{GPUProfiler,GPUAnalyzer,DeveloperService}.exe` |
| WPR / WPA / xperf | `C:\Windows\System32\wpr.exe`, `C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\` |
| Ghidra | `.\ghidra_12.1.3_PUBLIC_20260817\ghidra_12.1.3_PUBLIC\ghidraRun.bat` |
| Python 3.11 | `C:\Users\Lorenzo\AppData\Local\Programs\Python\Python311\python.exe` — pandas/numpy/scipy OK, **lief/pefile/capstone da installare** |

## Cache AMD (stato baseline 2026-09-03)

`%LOCALAPPDATA%\AMD\`

| Dir | File | Size | Note |
|---|---:|---:|---|
| `DxCache` | 63 | 1.9 MB | `.parc`, nome = 4 campi hex `<a>.<b>.<c>.<d>.<n>.parc` |
| `DxcCache` | 48 | 515 MB | il grosso del volume: candidato principale |
| `DX9Cache` | 10 | 136 KB | irrilevante per i target |

I due campi centrali si ripetono su molti file (probabile driver/device ID);
il primo campo varia per file → probabile hash pipeline/shader. **Da confermare.**

## Regole di lavoro

- Ogni claim di performance richiede varianza run-to-run misurata prima.
- Mai solo FPS medi: p95/p99 frametime, 1% e 0.1% low, conteggio stutter con definizione scritta.
- Ogni esperimento ha un experiment ID e metadata (driver, cache state, versione gioco, config).
- Le classificazioni (componente driver, tipo di file) richiedono **evidenza**, mai il solo filename.
- Le correlazioni hanno un livello di confidenza: confirmed / strong / probable / speculative.
  Timestamp vicini ≠ correlazione.
- Aggiorna sempre `PLAN.md` a fine fase.
