# Phase 1B — Mappatura del package driver AMD

Package analizzato: `whql-amd-software-adrenalin-edition-26.9.1-win11-a/` — **mai modificato**,
tutte le letture in sola lettura, nessuna copia scritta al suo interno.

Script: [`tools/drivermap.py`](../../tools/drivermap.py) (walk + SHA-256 + PE + INF),
[`tools/classify.py`](../../tools/classify.py) (classificazione con evidenza).
Output: `driver_files.csv` (724 righe), `driver_map.json`, `component_classification.csv`,
`pe_metadata.json`, `inf_map.json`, `dependency_graph.json`, `installed_vs_package.csv`.

## 1. Composizione del package

| | |
|---|---:|
| File totali | 724 |
| Dimensione | 2.7 GB |
| File PE (MZ) | 219 |
| Firmati Authenticode (sigcheck) | 322 |
| INF | 41 (41 `.cat` corrispondenti) |
| DLL / SYS / EXE | 158 / 25 / 36 |

Un solo INF è di classe **Display**: `Packages/Drivers/Display/WT6A_INF/u0203729.inf`,
DriverVer `08/27/2026, 32.0.21045.9003`, catalogo `u0203729.cat`, 142 sezioni, 154 file
referenziati. Tutto il percorso DirectX vive lì dentro. Gli altri 40 INF sono audio (17),
NPU/AI Vitis-XRT (2, ma 176+346 MB di payload), ISP/camera (7), USB/LED/UCSI/PCI (4) e
componenti software (amdocl, amdwin, amdfdans, amdxe, amdfendr, amdafd).

**Il 64% del package (NPU + audio + camera) è irrilevante per questo progetto.**

## 2. Evidenza usata per classificare

Nessuna classificazione deriva dal nome del file. Le fonti, in ordine di forza:

### 2.1 Chiavi di registro WDDM nell'INF Display (evidenza `confirmed`)

`UserModeDriverName` è un `REG_MULTI_SZ` indicizzato per versione del runtime D3D
(`[D3D9, D3D10, D3D11, D3D12]`). Riga 4265 di `u0203729.inf`:

```
HKR,,UserModeDriverName,%REG_MULTI_SZ%,
    %13%\B026432\atidx9loader64.dll,   <- D3D9
    %13%\B026432\amdxx64.dll,          <- D3D10
    %13%\B026432\amdxx64.dll,          <- D3D11
    %13%\B026432\amdxc64.dll           <- D3D12   <<<
```

Altre chiavi rilevanti:

| riga | chiave | valore |
|---:|---|---|
| 4264 | `OpenGLDriverName` | `atig6pxx.dll` (loader) → `atio6axx.dll` (riga 8685) |
| 4266 | `UserModeDriverNameWow` | `atidx9loader32.dll, amdxx32.dll, amdxx32.dll, amdxc32.dll` |
| 4272 | `VulkanDriverName` | `amd-vulkan64.json` → `amdvlk64.dll` |
| 4280 | `UserModeDriverNameWsl` | `amdxc64.so` (D3D12 per WSL) |
| 4285 | `D3DVendorName` | `amdxn64.dll, amdxn64.dll, amdxx64.dll, amdxx64.dll` |
| 4287 | `InstalledDisplayDrivers` | `amdxc64, amdxc32, amdxn64, amdxx64, amdxn32, amdxx32, atiumdva, atiumd6a` |
| 8521 | `VulkanDriverNameNexus` | `amdvlk_nexus.cab` |
| **4201** | **`Parameters\DXCTuningsFileName`** | **`amdxc64z.dll;amdxc32z.dll`** |
| **4202** | **`Parameters\ABCDTuningsFileName`** | **`amdxc64d.dat;amdxc32d.dat;amdxc64b.dat;amdxc32b.dat`** |

### 2.2 Entry point esportati (evidenza `strong`)

| binario | export non decorati |
|---|---|
| `amdxc64.dll` | `OpenAdapter12`, **`D3D12OpenCompilerDDI`**, `AmdExtD3DCreateInterface`, `AmdGetDxcModuleHandle`, `DxcExternalFunc1`, **`GetSettingsBlobsAll`**, **`GetSettingsBlobsAllDecoded`**, `OpenShimInterface` |
| `amdxx64.dll` | `OpenAdapter10`, `OpenAdapter10_2`, `AmdD3D11CreateDevice*`, **`AmdDxGsaCompileShader`**, `AmdDxGsaFreeCompiledShader`, `AmdDxExtCreate11`, `GetSettingsBlobsAll`, `MmTelemetryParser` |
| `amdn1b64.dll` | `OpenAdapter10`, `OpenAdapter10_2`, `AmdDxGsaCompileShader`, `AmdDxShimQueryInterface`, `XdxInitXopServices` |
| `amdxcstub64.dll` | solo `AmdExtD3DCreateInterface`, `AmdGetDxcModuleHandle` (142 KB — è uno stub) |
| `amdxcffx64.dll` | solo `UpdateFfxApiProvider` |
| `amdvlk64.dll` | `vk_icdGetInstanceProcAddr`, `vk_icdNegotiateLoaderICDInterfaceVersion`, `GetSettingsBlobsAll` |
| `atio6axx.dll` | `DrvPresentBuffers`, `DrvSwapBuffers`, `Drv*`, `egl*`, `GetSettingsBlobsAll` |
| `amdihk64.dll` | `NotifyGraphicsApi`, `NotifyComputeApi`, `NotifyFidelityFXStatus` |

`OpenAdapter12` è **la** prova che `amdxc64.dll` è lo user-mode driver D3D12: è l'entry point
che il runtime D3D12 cerca nella DLL indicata da `UserModeDriverName[3]`. Le due evidenze
(INF e export) sono indipendenti e concordi.

### 2.3 Version-info PE (evidenza `probable` da sola, qui concorde con le altre)

`amdxc64.dll` → FileDescription **"AMD DX12 UMD"**, ProductName "Advanced Micro Devices, Inc.
Radeon DirectX 12 Driver", FileVersion 8.18.10.0500, firmato "Advanced Micro Devices".

### 2.4 Cosa NON è stato possibile classificare

562 file su 724 restano senza componente: sono `.xclbin` (80, binari NPU), `.dat` di
firmware/video (46), `.qm` di traduzione, icone, XML e testi. Non ho tentato di indovinare:
figurano come `NaN` in `component_classification.csv`. 30 PE hanno solo la descrizione
dichiarata dal file (`declared:...`, confidenza *probable*) perché nessun INF li nomina in una
chiave funzionale.

## 3. Scoperta strutturale: il compilatore shader è dentro il UMD

Grafo delle dipendenze (`dependency_graph.json`, 153 archi intra-package):

- `amdxc64.dll` importa **6 sole DLL, tutte di Windows**: `kernel32`, `ntdll`, `advapi32`,
  `user32`, `version`, `winmm`. **Zero dipendenze AMD.**
- `amdxx64.dll` (DX10/11) e `amdxn64.dll` (DX9): stesso quadro, 8 import di sistema.
- Gli unici cluster di dipendenze interne del package riguardano lo stack NPU/AI
  (`xrt_coreutil`, `xir`, `runner`, `onnxruntime`, `vitis-ai-runtime2`) — irrilevante qui.
- `amdxcffx64.dll` è l'unico binario grafico con dipendenze CRT/`dxgi`/`wintrust`.

**Non esiste una "DLL del compilatore shader" separata da attaccare.** Il compilatore è
linkato staticamente dentro gli 82 MB di `amdxc64.dll`. Lo confermano i 310 export decorati C++
del file, che sono serializzatori Boost delle strutture del **compilatore AMD (SC)**:

```
_SC_SHADERSTATE                        _SC_COMPILE_FLAGS
_E_SC_SI_OPT_MINIMIZE_VGPRS_STRATEGY   _E_SC_SI_OPT_THREAD_LATENCY_STRATEGY
_E_SC_SI_OPT_USE_MORE_D16_SELECTOR     _E_SC_SI_OPT_IR_MODE_SELECTOR
_E_SC_SI_OPT_NPI_DISABLE               _SC_LAUNCH_MODE_FLAGS
_SC_CACHE_POLICY / _READ / _WRITE / _ATOMIC / _CONTROL
_SC_PS_EXPORT_INFO                     _SC_PRIMSHADER_CONTROL_FLAGS
_SC_CPS_CONFIG                         _SC_SI_GLC_CONTROL / _SC_SI_SLC_CONTROL
```

Sono **esattamente le manopole del compilatore che contano per questo progetto**: strategia di
minimizzazione VGPR (→ occupancy), strategia di latenza dei thread, uso di D16, politiche di
cache GLC/SLC. Il tipo di archivio è `sc_xml_oarchive`: queste strutture sono
serializzate/deserializzate **in XML**.

Collegando questo alla riga 4201 dell'INF (`DXCTuningsFileName = amdxc64z.dll;amdxc32z.dll`):
il UMD DX12 ha un meccanismo documentato per caricare un file di tuning esterno.
**`amdxc64z.dll`, `amdxc64d.dat` e `amdxc64b.dat` NON sono presenti nel package** (verificato:
`ls B026432/` non li contiene). La chiave punta a file che non vengono installati.

> Classificazione: **relazione probable**. Ho l'evidenza che (a) l'INF definisce la chiave,
> (b) il binario contiene serializzatori XML per le opzioni del compilatore. **Non ho ancora
> l'evidenza** che `amdxc64.dll` legga effettivamente quella chiave a runtime né che il formato
> atteso sia quello di `sc_xml_oarchive`. Va verificato con analisi statica mirata (stringhe +
> xref su `DXCTuningsFileName`) prima di trattarlo come una superficie reale.

## 4. Il package NON è il driver installato

| binario | size installato | size package | SHA-256 installato | SHA-256 package | stesso size | stesso hash |
|---|---:|---:|---|---|:---:|:---:|
| `amdkmdag.sys` | 102 772 744 | 102 772 744 | `f7783eb80812…` | `1b6d668b6349…` | sì | **no** |
| `amdxc64.dll` | 82 422 960 | 82 422 960 | `6aaade81651f…` | `6c42f438658e…` | sì | **no** |
| `amdxcffx64.dll` | 14 509 352 | 14 509 352 | `32faef8521fa…` | `7ffc9d306068…` | sì | **no** |
| `atio6axx.dll` | 64 289 808 | 64 289 808 | `e70a5a327a55…` | `dd86e51129cf…` | sì | **no** |
| `amdvlk64.dll` | 102 732 296 | 102 722 576 | `d4a9e509e02d…` | `5c1581fb8c14…` | no | no |
| `amdxx64.dll` | 50 424 200 | 50 423 688 | `9931c1db9a91…` | `78980bcb9534…` | no | no |
| `amdxcstub64.dll` | 142 736 | 142 728 | `a4cbb621180c…` | `8960b192f673…` | no | no |

- **Installato**: INF `u0203303`, cartella `B026363`, `amdkmdag.sys` v32.0.21045.**5002**
  (`C:\Windows\System32\DriverStore\FileRepository\u0203303.inf_amd64_e5876a26758f154c`).
- **Package nel progetto**: INF `u0203729`, cartella `B026432`, v32.0.21045.**9003**.

Due conseguenze operative importanti:

1. **`amdxc64.dll` ha la stessa dimensione al byte e la stessa FileVersion (8.18.10.0500) nelle
   due revisioni, ma contenuto diverso.** La stringa di versione dell'UMD DX12 non identifica la
   revisione: **serve l'hash**.
2. Qualsiasi analisi statica va fatta sulla **copia installata** (`B026363`), non su quella del
   package, altrimenti si studia un driver che non è quello che gira. Le due copie vanno tenute
   distinte e sempre etichettate con l'hash.

Nota aggiuntiva: `C:\Windows\System32\amdxc64.dll` è **142 736 byte** con lo stesso SHA-256 di
`amdxcstub64.dll` nel DriverStore. Il file in System32 chiamato "amdxc64.dll" **è lo stub**, non
il driver: l'UMD vero da 82 MB sta solo nel DriverStore. È una trappola facile da prendere.

## 5. Shortlist — i binari da guardare per DirectX 12

Ordine di priorità, con il motivo. Tutti i path si riferiscono alla **copia installata**
(`.../u0203303.inf_amd64_e5876a26758f154c/B026363/`), che è quella che gira.

| # | binario | size | ruolo (evidenza) | perché merita approfondimento |
|---:|---|---:|---|---|
| 1 | **`amdxc64.dll`** | 82.4 MB | **UMD D3D12** — INF `UserModeDriverName[3]` + export `OpenAdapter12` (*confirmed*) | È **il** driver DX12. Contiene il compilatore shader statically-linked, la gestione PSO, la pipeline cache e il `D3D12OpenCompilerDDI`. Ogni ipotesi del progetto passa da qui. |
| 2 | **`amdxc64.dll` → `GetSettingsBlobsAll` / `GetSettingsBlobsAllDecoded`** | — | export (*strong*) | Espone i **blob di impostazioni del driver** in forma decodificabile. È la via più diretta per enumerare cosa è configurabile nell'UMD **senza modificare nulla**: si può chiamare l'export su una copia e leggere l'elenco. Priorità alta e rischio zero. |
| 3 | **`amdxc64z.dll` / `amdxc64d.dat` / `amdxc64b.dat`** | assenti | `HKR,Parameters,DXCTuningsFileName` / `ABCDTuningsFileName` (*probable*) | Hook di tuning dichiarato dall'INF ma **non installato**. Se il UMD lo legge davvero, è una superficie di tuning che non tocca né i binari né il catalogo. Da verificare staticamente prima di qualsiasi altra cosa. |
| 4 | **`amdxcffx64.dll`** | 14.5 MB | "DX12 AMD Driver Based FidelityFX Library", export `UpdateFfxApiProvider`, importa `dxgi`+`wintrust` (*strong*) | Percorso FidelityFX **lato driver** per DX12: upscaling/frame-gen iniettati dal driver. Attivo o meno, è codice DX12-specifico che può stare nel path di rendering. `wintrust` suggerisce una verifica di firma sull'applicazione: da capire. |
| 5 | **`amdkmdag.sys`** | 102.8 MB | KMD, classe Display (*strong*) | Scheduling, submission delle command queue, gestione memoria. Rilevante per capire i risultati ETW/GPUView della Fase 1G. **Solo lettura**: qualsiasi modifica è fuori dai vincoli. |
| 6 | **`amdxcstub64.dll`** (in System32 come `amdxc64.dll`) | 143 KB | export `AmdExtD3DCreateInterface`, `AmdGetDxcModuleHandle` (*strong*) | Piccolo, leggibile in poche ore, ed è il punto in cui un'applicazione ottiene le estensioni AMD per D3D12. Ottimo primo bersaglio Ghidra perché è minuscolo e definisce l'interfaccia verso l'UMD grande. |
| 7 | **`amdxx64.dll`** | 50.4 MB | UMD D3D10/D3D11 — INF `UserModeDriverName[1..2]` + `OpenAdapter10_2` (*confirmed*) | Non è il target, **ma** esporta `AmdDxGsaCompileShader`: una API di compilazione shader esposta. Confronto utile per capire l'interfaccia del compilatore, su un binario con la stessa base di codice ma senza il DDI D3D12. |
| 8 | `amdn1b64.dll` | 20.3 MB | ProductName "Radeon DirectX 11 Driver", export `AmdDxGsaCompileShader`, `XdxInitXopServices` (*strong*) | Stessa API GSA in un modulo molto più piccolo. Candidato per capire il formato di input/output del compilatore shader con meno rumore. |
| 9 | `amdihk64.dll` | 257 KB | "Radeon Settings: Host Service", export `NotifyGraphicsApi`, `NotifyComputeApi`, `NotifyFidelityFXStatus` (*strong*) | È il ponte tra il driver e Radeon Settings: dice **quali eventi grafici il driver notifica all'esterno**. Piccolo, e può rivelare hook osservabili senza injection. |
| 10 | `atiadlxx.dll` / `amdadlx64.dll` | 2.2 / 5.2 MB | ADL / ADLX (*probable*, da version-info) | API pubblica e documentata per leggere stato/clock/limiti GPU. Utile come **fonte di telemetria migliore di PresentMon** (che campiona a 10 Hz e ha tutte le colonne `*Limited` a NA). Nessun rischio. |
| 11 | `amdxc64.so` | 125.7 MB | `UserModeDriverNameWsl` (*confirmed*) | Stesso UMD D3D12 in formato **ELF, non firmato**. Per la sola analisi statica è più comodo (simboli ELF) e non è coperto dal catalogo. Da usare come mappa, **verificando** però che corrisponda alla build Windows. |
| 12 | `amdvlk64.dll` | 102.7 MB | ICD Vulkan (*confirmed*) | Fuori dal percorso primario per policy, ma è l'unico componente il cui **sorgente è pubblico** (AMDVLK/PAL/LLPC). Serve come *Rosetta stone* per interpretare le strutture `_SC_*` e il sistema di settings blob trovati in `amdxc64.dll`. |

Esclusi esplicitamente dalla shortlist: tutto lo stack NPU/Vitis/XRT/ONNX (522 MB), audio,
camera/ISP, LED, UCSI. Nessuna evidenza di coinvolgimento nel percorso DX12.

## 6. Vincolo firma/catalogo — conferma

`u0203729.inf` dichiara `CatalogFile = u0203729.cat`, e la sezione `[SignatureAttributes]`
dell'INF elenca esplicitamente i file soggetti a PETrust (`amdxc64.dll=SignatureAttributes.PETrust`,
`amdxx64.dll`, `amdxcffx64.dll`, `amdn1b64.dll`, `amdihk64.dll`, …).

Modificare **un solo byte** di uno di questi file invalida l'hash nel catalogo e con esso la firma
del package. Il vincolo del progetto è quindi confermato dal package stesso, non solo dalla
documentazione Microsoft. Le tre vie che **non** toccano file firmati:

1. impostazioni/registry esposte dal driver (`GetSettingsBlobsAll`, chiavi `HKR,UMD,*`);
2. file di tuning **non firmati e non presenti** (`amdxc64z.dll`, `*.dat`) — *se* il driver li legge;
3. tutto ciò che sta a livello di applicazione/OS e non nel package.

## 7. Cosa resta aperto in 1B

- **Nessuna evidenza runtime.** Non so ancora quali di questi binari vengano effettivamente
  caricati dal processo di gioco: serve la Fase 1K (module list del processo o ProcMon), che è
  fuori dallo scope autorizzato per questo giro.
- Non è verificato se `amdxc64.dll` legga davvero `DXCTuningsFileName`.
- Non ho aperto Ghidra: nessuna decompilazione, come richiesto.
- `amdvlk_nexus.cab` (71.5 MB) non è stato estratto né analizzato.
