# PHASE 1 — STATUS

Aggiornato: **2026-09-03** · Fasi completate: **1A, 1B, 1E** (baseline su dati esistenti).
Nessuna modifica a driver, shader cache, file AMD, registry o configurazione di sistema.
Nessuna injection, nessun hooking. `%LOCALAPPDATA%\AMD\DxCache` **non toccato**.
Tutti i CSV raw dei benchmark sono intatti.

---

## 1. Cosa ho verificato

### Parser e strumentazione
- Le 14 catture PresentMon hanno **header identico** (66 colonne, md5 `6f207fcf…`): un solo parser.
- **38 colonne popolate al 100%**, 2 al 50%, **26 sempre NA** — fra cui *tutte* le
  `GPU*Limited` (power/thermal/current limit **non verificabili** su questa GPU),
  `CPUPower`, `CPUTemperature` e le bandwidth di memoria.
- **Nessuna colonna `Dropped`** in questo loadout; 0 frame senza display change su 14/14 file
  → **0 dropped frame**.
- Frequenza di campionamento telemetria **misurata**: GPU clock/power/util ~10 Hz,
  CPU clock/util ~1 Hz, VRAM ~0.05 Hz. A 620 FPS **un campione copre ~60 frame**.
- Parser validato contro i `-stats.csv` di PresentMon su tutti e 14 i file:
  frame count identico, deviazione massima **0.053%** su avg FPS, **0.0001%** sui percentili.
  Cross-check indipendente con la GUI 3DMark: 41.38 vs 41.385 FPS (run 3).
- `pmparse` ha un self-check eseguibile (`python tools/pmparse.py`) che verifica le due
  definizioni di 1% low e i quattro casi limite del rilevatore di spike.

### Baseline Fortnite (7 run, DX12 Performance Mode, uncapped, Hardware Independent Flip)
- **616.2 avg FPS**, frametime medio 1.623 ms, 0 dropped frame, 0 frame generati.
- **CPU-bound**: `MsCPUBusy` 1.529 ms > `MsGPUBusy` 1.373 ms in 7/7 run, GPU util **73.9%**,
  headroom GPU **15.3%**, CPU a 4.44 GHz.
- `baseline noise ≈ ±1.3%` (CV avg FPS) → MDD 7v7 = **2.17%**. Senza il run anomalo: ±0.62%, MDD 1.11%.
- 81 spike totali. **In 81/81 il lavoro GPU non aumenta** (`MsGPUBusy` +0.26 ms mediano):
  gli spike sono interamente CPU-side, e `MsGPUWait` alto è la *conseguenza*.

### Baseline Steel Nomad (7 run)
- **41.41 avg FPS**, **99.0% GPU util**, `MsGPUBusy` = 99.9% del frametime, `MsGPUWait` 13 µs.
- **Zero spike, zero dropped frame** su tutti e 7 i run.
- `baseline noise ≈ ±0.11%` → MDD 7v7 = **0.17%**. È ~12× più preciso di Fortnite.

### Package driver (724 file, 2.7 GB)
- 219 PE, 322 firmati, 41 INF di cui **uno solo di classe Display** (`u0203729.inf`).
- **`amdxc64.dll` = UMD DirectX 12**, con doppia evidenza indipendente:
  INF `UserModeDriverName[3]` **e** export `OpenAdapter12`. Esporta anche
  `D3D12OpenCompilerDDI`, `GetSettingsBlobsAll`, `GetSettingsBlobsAllDecoded`.
- **Il compilatore shader è dentro l'UMD**: `amdxc64.dll` importa 6 sole DLL, tutte di Windows,
  zero dipendenze AMD. I suoi 310 export decorati sono serializzatori Boost/XML delle strutture
  del compilatore AMD: `_SC_COMPILE_FLAGS`, `_E_SC_SI_OPT_MINIMIZE_VGPRS_STRATEGY`,
  `_E_SC_SI_OPT_THREAD_LATENCY_STRATEGY`, `_SC_CACHE_POLICY`, `_SC_PS_EXPORT_INFO`…
- **L'INF dichiara un hook di tuning che non viene installato**:
  `HKR,Parameters,DXCTuningsFileName = "amdxc64z.dll;amdxc32z.dll"` e
  `ABCDTuningsFileName = "amdxc64d.dat;…"`. Nessuno di quei file esiste nel package.
- **Il package NON è il driver installato**: installato `u0203303`/`B026363` v…**5002**,
  package `u0203729`/`B026432` v…**9003**. `amdxc64.dll` ha **dimensione identica al byte e
  stessa FileVersion** nelle due revisioni ma **hash diverso**.
- `C:\Windows\System32\amdxc64.dll` (142 736 B) **è lo stub** `amdxcstub64.dll`, non l'UMD.
- L'INF elenca esplicitamente i file soggetti a PETrust: il vincolo "un byte modificato invalida
  il catalogo" è confermato dal package stesso.

### Sistema
- Windows 11 25H2 build 26200.9168; **HAGS abilitato** (`HwSchMode = 2`);
  Defender real-time **attivo**; piano energetico `zoic's ultimate performance(amd)`.

---

## 2. Cosa rimane incerto

| Aperto | Perché |
|---|---|
| **Nessuna evidenza runtime** su quali binari AMD carichi il gioco | richiede ProcMon / module list — fuori scope in questo giro |
| `amdxc64.dll` legge davvero `DXCTuningsFileName`? | serve analisi statica mirata (stringhe + xref), non ancora fatta |
| Formato e semantica dei settings blob (`GetSettingsBlobsAllDecoded`) | non ancora invocato né decodificato |
| Contenuto di `DxCache`/`DxcCache` | non ancora ispezionato: la forensics della cache è la prossima fase |
| Confini del percorso Creative dentro le catture Fortnite | **non determinabili**: il CSV non contiene marker di scena. Documentato, non indovinato |
| Causa del degrado di `fortnite_r4` | nessuna nota sui processi in background per quel run |
| Causa della crescita VRAM in Steel Nomad | correlazione certa, meccanismo ignoto |
| Direzione causale spike ↔ calo clock GPU | telemetria a 10 Hz: risoluzione insufficiente |
| `amdvlk_nexus.cab` (71.5 MB) | non estratto |
| Black Myth: Wukong | **non installato** → Fase 1F bloccata |

---

## 3. Anomalie nei benchmark

1. **`fortnite_r4`** — unico run fuori distribuzione, flaggato (MAD z>3.5) su 8 metriche
   indipendenti. Prima metà normale (616 FPS), **seconda metà a 582 FPS (−5.5%)** mentre negli
   altri 6 run la seconda metà è *più veloce* (+1.9…+5.0%). Crollo netto da ~610 a ~545 FPS da
   t≈44 s, con 15 dei suoi 28 spike concentrati lì. **Non è throttling**: power più *bassa*
   (234.5 W vs 239–240 W), temp identica, GPU util più bassa; il costo cresce solo su
   `MsCPUBusy` (1.573 vs 1.514 ms) a lavoro GPU invariato. Coerente con un consumatore di CPU
   esterno o una variazione di percorso. → tenuto nei dati, **escluso dalle baseline**.
2. **Steel Nomad: VRAM crescente monotòna** su 7 esecuzioni identiche consecutive:
   6 463 → 6 996 MB, **+533 MB (+8.2%), ~80 MB per run**, senza alcun effetto sulle
   performance (FPS piatto entro 0.31%). Un gap di ~4 min non l'ha resettata.
3. **`steelnomad_r1` è troncato di ~5 s**: la cattura è partita in ritardo, il run è però
   completo (3DMark: 4139 punti, in linea con r3 = 4137). Da non confondere con un run diverso.
4. **Spike di 363–448 ms a t≈0.45 s in 7/7 run Fortnite**: artefatto di aggancio della cattura,
   non del gioco. Escluso dal warm-up trim di 2 s.
5. Lo **0.1% low di Steel Nomad poggia su 2 frame**: metrica non significativa, da non usare.

---

## 4. Qualità e ripetibilità delle baseline

| | Steel Nomad | Fortnite |
|---|---:|---:|
| CV avg FPS | **0.105%** | 1.329% (0.620% senza r4) |
| MDD 7v7 su avg FPS | **0.17%** | 2.17% (1.11% senza r4) |
| CV 1% low | 0.598% | 7.243% |
| CV 0.1% low | 0.779% (2 frame: non usare) | **22.28%** |
| CV conteggio spike | — (0 spike) | **67.3%** |
| Allineamento fra run | deterministico | correlazione tracce FPS/s 0.55 medio |

```
Steel Nomad :  baseline noise ≈ ±0.11%  ->  reale un guadagno ≥ 0.2%  (prudente ≥ 0.5%)
Fortnite    :  baseline noise ≈ ±1.3%   ->  reale un guadagno ≥ 2.2%  (prudente ≥ 3%)
Fortnite 1% low   : ±7%   -> serve ≥ 12%
Fortnite 0.1% low : ±22%  -> inutilizzabile come metrica decisionale con 7 run
```

**Steel Nomad è lo strumento, Fortnite è la verifica di realtà.** Fortnite non è un banco di
misura: i run seguono lo stesso percorso ma non sono allineati frame-per-frame, e il CSV non
contiene marker per isolare il percorso. Per stringere la sua soglia servono più run (la MDD
scala come 1/√n: da 7 a 20 run si passa da ~2.2% a ~1.2%), non run più lunghi.

Qualità complessiva: **alta e utilizzabile**. Zero dropped frame, un solo present mode stabile,
nessun frame generato, parser validato contro due strumenti indipendenti.

---

## 5. Componenti AMD più promettenti

Elenco completo con evidenza in
[`research/01_driver_map/component_analysis.md`](01_driver_map/component_analysis.md).
I primi cinque, in ordine di rapporto valore/rischio:

| # | componente | perché |
|---:|---|---|
| 1 | **`amdxc64.dll` — export `GetSettingsBlobsAll` / `GetSettingsBlobsAllDecoded`** | Enumera le impostazioni dell'UMD in forma decodificabile, **chiamando un export su una copia**: nessuna modifica, nessun rischio, e dice subito cosa è configurabile senza toccare binari firmati. Miglior primo passo in assoluto. |
| 2 | **Hook `DXCTuningsFileName` (`amdxc64z.dll`, `amdxc64*.dat`)** | L'INF lo dichiara, i file non vengono installati, e il binario contiene serializzatori XML per le opzioni del compilatore (VGPR, latency, D16, cache policy). Se il driver lo legge davvero, è una superficie di tuning **fuori dal catalogo firmato**. Da verificare staticamente prima di crederci. |
| 3 | **`amdxc64.dll` — corpo dell'UMD D3D12** | Contiene compilatore shader, gestione PSO e pipeline cache, tutto statically-linked (82 MB, zero dipendenze AMD). È il bersaglio finale di ogni ipotesi, ma è anche il più costoso: va aggredito **solo** dopo aver ristretto con evidenza runtime. |
| 4 | **`amdxcffx64.dll`** — FidelityFX driver-based per DX12 | 14.5 MB di codice DX12-specifico nel path di rendering, con `UpdateFfxApiProvider` e import di `dxgi`+`wintrust`. Capire se e quando è attivo cambia l'interpretazione di qualsiasi misura. |
| 5 | **`amdxcstub64.dll`** (143 KB) + **`atiadlxx.dll`/`amdadlx64.dll`** | Lo stub è minuscolo e definisce l'interfaccia estensioni verso l'UMD: primo bersaglio Ghidra sensato. ADL/ADLX è telemetria GPU documentata, **migliore di PresentMon** che qui campiona a 10 Hz e ha tutte le colonne `*Limited` a NA. |

Menzione a parte: **`amdvlk64.dll`** non è nel percorso di ricerca per policy, ma il suo
sorgente è pubblico (AMDVLK/PAL/LLPC) ed è l'unico modo realistico di interpretare le strutture
`_SC_*` e il sistema di settings blob trovati dentro `amdxc64.dll`. Usarlo come dizionario, non
come target.

---

## 6. Prossimi cinque esperimenti consigliati

In ordine. Tutti non distruttivi tranne dove indicato.

1. **Enumerare le impostazioni dell'UMD DX12 senza toccare nulla.**
   Copiare `amdxc64.dll` (dalla cartella **installata** `B026363`) in una directory di lavoro,
   caricarla in un processo host minimale e chiamare `GetSettingsBlobsAllDecoded`; in parallelo,
   `strings` + xref su `DXCTuningsFileName` / `ABCDTuningsFileName` per stabilire **se il driver
   legge davvero quell'hook**. Esito: la lista concreta delle manopole esistenti.
   *Rischio: nullo. Costo: basso. È il passo che decide se esiste una via non invasiva.*

2. **Forensics della shader cache a cache calda, poi a cache fredda.**
   Baseline hash/size/mtime di `DxCache` e `DxcCache` (**515 MB in DxcCache**: è lì il volume),
   poi ProcMon su un avvio Fortnite e su Steel Nomad. Rispondere a: chi scrive, quando, quanto,
   e se il nome file correla col contenuto. La cancellazione della cache resta **manuale e
   dell'operatore**, mai automatica.
   *Precondizione: backup della cache (copia, non spostamento).*

3. **Attribuire il millisecondo e mezzo di CPU di Fortnite.**
   Trace WPR/ETW attorno a un run Fortnite e a uno Steel Nomad, analisi in WPA:
   quanto di `MsCPUBusy` è codice del gioco e quanto è `amdxc64.dll` / `amdkmdag.sys`.
   Con HAGS attivo, guardare anche le code GPU in GPUView. È **l'unico modo** per sapere se
   l'overhead CPU del driver è una superficie reale o solo un'ipotesi.

4. **Installare Black Myth: Wukong Benchmark e caratterizzarlo.**
   Serve un workload controllato **aperto** (Steel Nomad è chiuso e a cache già calda): N run
   baseline per stimarne CV e MDD, poi verificare che RGP riesca a catturarlo. È la
   precondizione di tutta la Fase 1F e dell'unica catena che vale davvero,
   `shader hash → cache blob → ISA → costo GPU`.

5. **Chiudere le due anomalie aperte con un esperimento ciascuno.**
   (a) Ripetere 10 run Steel Nomad consecutivi campionando la VRAM e annotando riavvii del
   processo: la crescita di ~80 MB/run è del driver o dell'applicazione?
   (b) Ripetere 10 run Fortnite **registrando i processi in background** per capire se `r4` è
   riproducibile. Serve anche a portare la MDD di Fortnite da 2.2% a ~1.2%.

**Non consigliato ora**: aprire Ghidra su `amdxc64.dll`. 82 MB senza evidenza runtime e senza
sapere se esiste una via via-impostazioni sono settimane spese male. L'esperimento 1 costa
un pomeriggio e può renderlo superfluo.

---

## 7. File prodotti in questo giro

```
research/
├── 00_inventory/    project_tree.txt, software_versions.md,
│                    hardware_info.json, windows_info.json, gpu_info.json
├── 01_driver_map/   driver_files.csv (724), driver_map.json, component_analysis.md,
│                    component_classification.csv, pe_metadata.json, inf_map.json,
│                    dependency_graph.json, installed_vs_package.csv, _sigcheck.csv
├── 04_benchmarks/analysis/
│                    METHOD.md, fortnite_baseline.md, steelnomad_baseline.md,
│                    baseline_comparison.md, fortnite_runs.csv, steelnomad_runs.csv,
│                    frametime_outliers.csv, correlations.csv, run_to_run_variance.csv,
│                    parser_validation.csv, charts/ (18 PNG)
└── PHASE_1_STATUS.md

tools/  pmparse.py (+self-check), validate.py, analyze.py, drivermap.py, classify.py, inventory.py
```
