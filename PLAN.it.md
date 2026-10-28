# PLAN — Roadmap Fase 1

> **Stato corrente 2026-09-26:** partire da [HANDOFF.md](HANDOFF.md). Claude non disponibile; presa in carico Codex. Baseline e scaling fullscreen conclusi. Recuperata la cattura WPR reale già eseguita l'8 settembre: allineamento nativo e controllo perdite PASS; resta l'attribuzione offline CPU/driver/code GPU. I riepiloghi storici sotto non sono il backlog corrente.

Aggiornato: **2026-09-07 — 2U CHIUSA: hit rate 0 su 4 (2T era 0 su 4); 1 hit su 9 workload in tutto il programma**. Milestone C2077 preparata e pronta, in attesa che il gioco sia installato.
> **2U in una riga:** tre modifiche alla pipeline — **ceiling gate**, **decomposizione del ceiling**, **regola di correttezza a due livelli** — tutte hanno funzionato e **nessuna ha prodotto un hit**. Due workload chiusi dal gate prima di ogni ipotesi (ceiling −0,38% e +0,22%). Il candidato migliore, `shadow_tmax` su un workload DXR, e' **byte-identico, replicato, con separazione completa a −1,8/−2,2%** — e la soglia preregistrata lo rifiuta. **Il collo di bottiglia non e' generare idee: sono l'esattezza e la soglia.** Report: [`research/PHASE_2U_RESULTS.md`](research/PHASE_2U_RESULTS.md) · procedura Cyberpunk: [`research/C2077_OPERATOR_PROCEDURE.md`](research/C2077_OPERATOR_PROCEDURE.md).
> 2T: hit rate del metodo misurato, 0 su 4 workload. 2O, 2P, 2Q, 2R complete; review avversariale eseguita; PoC CONGELATO.
> **2T in una riga:** la pipeline congelata, girata su 4 workload D3D12 dichiarati prima di guardarli, ha prodotto **zero trasformazioni accettate su 5 tentate**. Due workload chiusi prima di ogni ipotesi perche' il pass non e' migliorabile (dispatch da 5,76 us, draw da 480 ns). W4 ha **16,6% di frame dentro il pixel shader** — il tetto c'e' — e la pipeline non ne ha preso niente: il candidato veloce non era esatto, quello esatto non era veloce. Contando 2P e 2R, il metodo sta a **1 hit su 6 workload**. Report: [`research/PHASE_2T_RESULTS.md`](research/PHASE_2T_RESULTS.md). Stato: **gate build validato; O1 PASS (1/6);
O2 PASS (2/6): semantica e aggregazione dei counter raw validate contro l'SDK, identità del
workload misurata, baseline `Render Color` acquisita senza ablazioni; O3 PASS (3/6): dose-risposta
sui sample dei materiali, 2,1% delle istruzioni texture = 13,9% dei cicli TA; O4 PASS (4/6):
ablazione del solo sampler a bytecode invariato — **l'ipotesi "texture-filter-throughput bound"
di 2N è falsificata**; O5 PASS (5/6): attribuzione di stage chiusa (99,53% pixel) e cache/memoria
eliminate per misura (stallo L0 0,24%, hit 97,66%, 39,6 GB/s); O6 PASS (6/6): **replicato** che
l'88% dei cicli del pass scala col conteggio di istruzioni texture, a 13,1 cicli ciascuna, ma la
correzione del divisore SIMD mostra il pass **co-saturo** VALU 96,6% / TA 93,6% e quindi le due
unità **non sono classificabili** alla baseline. **2P: primo guadagno end-to-end reale** — `stack3_scalar` porta `Render Color` a −41,4% e il frame GPU a −24,5% misurato, in 68 righe di HLSL applicativo. **2Q: equivalenza float32 verificata** (≤7 ULP, `SCALAR_BRANCH` bit-identico, `fresnel5` provato più accurato su tutto il suo dominio, data contract misurato). **2R: metodo portato su un secondo workload D3D12, nessuna trasformazione accettata**. **Review avversariale eseguita: ha rotto la canary del data contract, che e' stata ricostruita e dotata di controllo positivo**; 2P/2Q/2R sono ora **congelate** come PoC validato (`research/POC_FROZEN.md`). Prossima fase proposta, una sola: **2T, misurare l'hit rate del metodo** su 3–5 workload D3D12 dichiarati prima di guardarli**.
Le fasi 1A, 1B, 1E, 1.5, 2A–2N hanno report storici; “completata” non certifica tutte le loro conclusioni.

> **ERRATA CORRENTE — prevale sulle voci storiche sotto.**
> Audit: [`research/CODEX_HANDOFF_AUDIT.md`](research/CODEX_HANDOFF_AUDIT.md).
> **RISOLTO** — la catena `sorgente → bytecode → binario linkato → PSO eseguito → immagine` è ora
> dimostrata fail-closed e reversibile:
> [`research/24_phase2o_build_gate/PHASE_2O_O1_RESULTS.md`](research/24_phase2o_build_gate/PHASE_2O_O1_RESULTS.md).
> **RISOLTO NEGATIVAMENTE (O4)** — “Render Color texture-**filter**-throughput bound” è ora
> **falsificata per misura**: spegnere del tutto l'anisotropico (−17,9% di cicli aniso) o scendere
> al filtro point, con il bytecode del pixel shader **byte-identico** e l'ALU verificata invariata
> entro 0,07%, muove il pass **al massimo del ~3%** mentre `TexUnitBusy` resta ~94%.
> → [`research/29_o4_sampler/PHASE_2O_O4_RESULTS.md`](research/29_o4_sampler/PHASE_2O_O4_RESULTS.md).
> Restava vero che con la strumentazione di 2N la tesi **non era ottenibile**. Fra i 145 counter derivati non esiste alcun
> counter VALU/SALU/occupancy per lo stage pixel, e `TexUnitBusy` include per documentazione gli
> effetti di cache e memoria. Il set di 31 counter di 2N richiede **13 passate** (misurato offline).
> → [`research/25_gpa_validity/GPA_VALIDITY.md`](research/25_gpa_validity/GPA_VALIDITY.md).
> **RISOLTO in parte** — `kGpaOpenContextEnableHardwareCountersBit` espone **4001 counter invece
> di 145** (verificato offline **e su contesto DX12 vivo**, insiemi identici). Ci sono i counter
> `SQ` mascherati `PS` per l'ALU del pixel shader (`INSTS_VALU`, `INST_CYCLES_VALU`,
> `INSTS_TEX_LOAD`, waves) — **1 passata** per tutti e 36 — e i counter `TA` per il costo di
> filtraggio (`TA_BUSY`, `ANISO_*_CYCLE_QUADS`) — `TA_BUSY` su 80 CU in **1 passata**.
> → [`research/26_gpa_hwcounters/GPA_HW_COUNTERS.md`](research/26_gpa_hwcounters/GPA_HW_COUNTERS.md).
> **O5 torna eseguibile**, con i counter raw.
> **CORREZIONE MISURATA (O2)** — `TexUnitBusy` è il **massimo su 80 CU**, non una media né una
> somma: `TexUnitBusy% = max(TA_BUSY)/GPUBusyCycles·100`, verificato esatto contro l'SDK. Il
> 94,6% di 2N riguarda *la CU più carica*, non le texture unit nel complesso (qui l'imbalance
> misurata è però solo 1,013). `TexAveAnisotropy` e `GPUBusyCycles` validati esatti.
> **Identità del workload (O2)** — i counter di **lavoro aggregato** sono bit-identici anche su
> una sessione a 5 passate; i counter **per-instance** e quelli di **timing** no
> (`GPUTime` varia del 19,9% fra frame). Il multipass è quindi ammissibile per il lavoro
> aggregato, mai per valori singoli di timing.
> → [`research/27_o2_counters/PHASE_2O_O2_RESULTS.md`](research/27_o2_counters/PHASE_2O_O2_RESULTS.md).
> `PSPixelsOut ≈ 2× schermo` conta due MRT, non dimostra overdraw 2×.
> Le A/B 2L–2M senza provenienza runtime restano non valide per conclusioni causali.
> Oracolo immagine: **ora esiste e funziona**, ma solo per il punto di cattura di O1
> (`g_SceneColorBuffer` dopo `Render Color`, prima di particelle e post-effetti).
> I 28,90 draw/frame di 2M sono **una** delle due componenti dello scope: al runtime se ne
> osservano **34** su 2 PSO nativi.
> Il numero 2.5× di 2K richiede ricalcolo: best/oracle includono varianti scartate per correttezza.
Vedi [`research/PHASE_1_STATUS.md`](research/PHASE_1_STATUS.md) e
[`research/PHASE_1_5_DECISION_GATE.md`](research/PHASE_1_5_DECISION_GATE.md).
Legenda: `[ ]` da fare · `[~]` in corso · `[x]` fatto · `[!]` bloccato

---

## Blocchi prima di partire

- [!] **Black Myth: Wukong Benchmark non installato** → blocca la 1F. Scaricarlo.
- [x] `pip install pefile lief capstone` — fatto (pefile 2024.8.26, lief 1.0.0, capstone 5.0.7).
- [~] Scenario Fortnite ripetibile: i 7 run seguono lo stesso percorso ma **non sono allineati
  frame-per-frame** (correlazione tracce FPS/s 0.55) e il CSV non ha marker di scena. Serve
  registrare anche i processi in background (vedi anomalia r4).

---

## 1A — Inventory → `research/00_inventory/` ✔ COMPLETA
- [x] `project_tree.txt`, `software_versions.md`, `hardware_info.json`, `windows_info.json`, `gpu_info.json`
- Trovato: **HAGS attivo** (`HwSchMode=2`), Defender real-time attivo, Win 11 25H2 26200.9168,
  display 2560x1440, GPU `DEV_73A5` (Navi 21).
- **Il package nel progetto (v…9003, INF u0203729) NON è il driver installato (v…5002, INF u0203303).**

## 1B — Mappa package driver → `research/01_driver_map/` ✔ COMPLETA
- [x] Walk + SHA-256 + PE metadata + sigcheck su tutti i 724 file (219 PE, 322 firmati)
- [x] Parsing dei 41 INF → **un solo INF di classe Display**, `u0203729.inf`
- [x] `driver_files.csv`, `driver_map.json`, `component_analysis.md`, `dependency_graph.json`
- [x] Shortlist di 12 binari con evidenza (INF + export + version-info), nessuna dal filename
- Risultati chiave:
  - **`amdxc64.dll` = UMD DX12** (INF `UserModeDriverName[3]` + export `OpenAdapter12`), esporta
    anche `D3D12OpenCompilerDDI`, `GetSettingsBlobsAll`, `GetSettingsBlobsAllDecoded`.
  - **Il compilatore shader è statically-linked dentro l'UMD**: 6 import, tutti Windows, zero
    dipendenze AMD. Export = serializzatori Boost/XML di `_SC_COMPILE_FLAGS`,
    `_E_SC_SI_OPT_MINIMIZE_VGPRS_STRATEGY`, `_SC_CACHE_POLICY`…
  - **`HKR,Parameters,DXCTuningsFileName = amdxc64z.dll`** dichiarato dall'INF ma **il file non
    è nel package**. Superficie di tuning potenziale fuori dal catalogo firmato — *da verificare*.
  - `C:\Windows\System32mdxc64.dll` è lo **stub** (143 KB), non l'UMD.
- [ ] Non fatto: estrazione di `amdvlk_nexus.cab`; nessuna evidenza runtime (→ 1K).

## 1C — Forensics shader cache → `research/02_shader_cache/`
- [ ] Baseline hash+size+mtime di `DxCache`/`DxcCache` (**prima** di qualunque run)
- [ ] Procmon su Fortnite: chiuso → avvio → menu → gameplay → uscita
- [ ] `cache_before.csv`, `cache_after.csv`, `file_activity.csv`, `cache_diff.md`
- [ ] Rispondere: quali file letti/scritti/creati, da quale processo, quando, quanti byte
- [ ] Verificare stabilità tra due avvii identici e se il filename correla col contenuto
- Ipotesi da testare: `DxcCache` (515 MB) è il vero store; `DxCache` (1.9 MB) è indice/metadata.

## 1D — Rebuild controllato cache → `research/03_cache_rebuild/`
- [ ] Backup completo della cache (copia, non move)
- [ ] Procedura **manuale** scritta; la cancellazione la esegue l'operatore umano
- [ ] Run cold-cache vs warm-cache: timestamp, sequenza creazione file, size, CPU/GPU, frametime

## 1E — Harness benchmark → `research/04_benchmarks/analysis/` ✔ COMPLETA (analisi)
- [x] Parser `tools/pmparse.py` con self-check eseguibile; `analyze.py` produce metriche,
  varianza, spike, correlazioni e 18 grafici
- [x] Validato contro i `-stats.csv` di PresentMon su 14/14 file (max 0.053% su avg FPS) e
  contro la GUI 3DMark (41.38 vs 41.385)
- [x] Definizioni scritte in `METHOD.md`: 1% / 0.1% low **time-integrated** (primaria) e
  **percentile** (secondaria), spike = `ft > 2x mediana mobile (21 frame) AND +>=2 ms`
- [x] **Baseline noise: Steel Nomad ±0.11% (MDD 0.17%) · Fortnite ±1.3% (MDD 2.17%)**
- [x] Fortnite è **CPU-bound** (CPUBusy 1.53 > GPUBusy 1.37 ms, GPU util 74%);
  Steel Nomad è **GPU-bound al 99.9%**
- [ ] Da fare: wrapper di *lancio* PresentMon + `experiment_metadata.json` per i run futuri
  (finora i run li ha lanciati l'operatore a mano)

## 1F — Wukong: profiling controllato → `research/05_rgp/`
- [!] bloccato dall'installazione del benchmark
- Nota: Steel Nomad copre il ruolo di *strumento di misura* (CV 0.11%) ma è chiuso e gira a cache
  già calda: non espone il percorso di compilazione shader. Wukong resta necessario.
- [ ] Config grafica fissa + N run baseline → deviazione standard → soglia di differenza "reale"
- [ ] Capture RGP; se riesce: event timing, occupancy, VGPR/SGPR/LDS, shader costosi, hash
- [ ] `expensive_shaders.csv`, `pipeline_notes.md`, `shader_analysis/`
- [ ] Verificare interoperabilità RGP → RGA su pipeline estratte

## 1G — Scheduling Windows → `research/06_etw/`
- [ ] Trace WPR attorno al benchmark controllato; analisi WPA/GPUView
- [ ] Classificare il limite: GPU exec / CPU submission / sync / shader / memoria / present / unknown

## 1H — Baseline Fortnite
- [ ] ≥5 run comparabili, solo strumenti non invasivi
- [ ] Varianza run-to-run **prima** di qualsiasi claim; cold vs warm cache separati

## 1I — Warzone shader investigation
- [ ] Procmon sulla fase di preloading shader
- [ ] Classificare i dati trovati: testo, DXIL/DXBC, cache driver AMD, metadata, archivio, unknown
- Nota: `E:\Call of Duty\_retail_\cod25` — i `.ff` sono archivi del gioco, non shader.

## 1J — Correlazione → `research/07_correlation/shader_cache_map.json`
- [ ] Catena: shader/pipeline → hash → attività cache → blob → evento render → costo frametime
- [ ] Ogni relazione etichettata confirmed / strong / probable / speculative; gap = "unknown"

## 1K — Candidati analisi driver
- [ ] Elenco UMD effettivamente caricati nel workload controllato (evidenza runtime, non filename)
- [ ] Per candidato: path, versione, firma, processo, exports/imports, ruolo probabile, rilevanza shader/PSO/cache
- [ ] Solo dopo la shortlist: Ghidra mirato. Nessuna decompilazione a tappeto.

## Fase 1.5 — attribution CPU + settings UMD  (al decision gate)

### 1.5A — ETW/WPR attribution su Fortnite → `research/08_etw_fortnite/`
- [x] Harness di cattura `tools/capture_etw.ps1` (WPR CPU+GPU filemode + PresentMon + snapshot background)
- [x] Sampling a 8 kHz verificato: `xperf -setprofint 1221` → 16 300 campioni/s contro 1 677 di default
- [x] Analizzatore `tools/etw_analyze.py` in streaming (niente dump da 1.45 GB), validato su dry-run:
  attribuzione per modulo senza simboli, RVA corretti, path del modulo caricato risolto
- [x] Soglia decisionale fissata **prima** dei dati: >=15% campioni in `amdxc64.dll` = ramo forte, <3% = ramo chiuso
- [x] **3 catture Fortnite eseguite** (2026-09-04, 3 x 13.5 GB) e analizzate: 8.4 M campioni,
  2.9 miliardi di righe evento → `research/08_etw_fortnite/RESULTS.md`
- [x] `cpu_module_attribution.csv`, `hot_threads.csv`, `amdxc64_hot_offsets.csv`, `summary_3runs.csv`
- [x] **`amdxc64.dll` = 0.151 core-equiv = ~151 ms CPU/s ≈ 0.24 ms/frame**, CV 1.95% su 3 run;
  81% su un solo thread di submission (TID 15168, 26.9% del thread)
- [x] **Codice caldo dell'UMD in sole 204 pagine da 4 KB**; top-10 (40 KB) = 29.4% del costo
- [x] **Run 4 con PresentMon valido** (24 695 frame): thread del percorso critico identificato
  quantitativamente → `amdxc64.dll` = **2.1%** ≈ 0.03 ms/frame, identico su 4 run e 2 sessioni
- [x] **RAMO A CHIUSO**: sotto la soglia del 3% pre-registrata. Il percorso critico e' all'84%
  `ntoskrnl.exe` (3 pagine = 50% del tempo kernel), non driver AMD
- [x] Bug dello script trovato e corretto: `Start-Process -ArgumentList` non quota gli spazi in
  "driver mod" → PresentMon usciva con exit 1. **Non** era PresentMonService ne' WPR (entrambi
  verificati innocenti). Aggiunti pre-flight fail-fast, try/finally, `-ValidateOnly`
- [x] ETL cancellati dopo l'analisi (~50 GB liberati); CSV derivati conservati

### 1.5B — Settings/tunings dell'UMD → `research/09_umd_settings/` ✔ COMPLETA
- [x] Istanza reale identificata da registro: `...ȃ303.inf_amd64_...\B026363mdxc64.dll`,
  sha256 `6aaade81…`; analisi su copia
- [x] **`GetSettingsBlobsAllDecoded` = stub vuoto** (`xor eax,eax; ret`) → niente probe standalone
- [x] `GetSettingsBlobsAll` = `uint32_t f(void* buf, uint32_t size)`, query-size-then-fill, dipende da
  un globale popolato solo dall'init driver → inutile da un host che fa solo LoadLibrary
- [x] **`DXCTuningsFileName` è del KMD**: stringa solo in `amdkmdag.sys`, chiave viva sotto
  `Servicesmduw23g-203303-6af680f4\Parameters`, file inesistenti → **strada chiusa**
- [x] **Trovata l'interfaccia vera**: `AMD_SC_OPTIONS`, `AMD_SC_CFG_FILE`/`amdsc.ini`,
  `AMD_DXCP_TEST_OPTIONS`, `AMD_CONFIG_DIR`, `EnableGlobalSettingsDumping`/`GlobalSettingsDumpFile`,
  parser boost::program_options, **272 opzioni `SCOption_*`** + opzioni di dump ISA per shader hash
- [ ] Da chiarire: se siano attive in retail, la sintassi, e il `cmp eax,1` che protegge il dump

## Fase 2 — shader compiler / codegen (workload: Steel Nomad)

### 2A/2B/2C — parser SC → `research/10_sc_probe/` ✔ PARSER ATTIVO
- [x] **`AMD_SC_OPTIONS` e `AMD_SC_CFG_FILE` sono consumate dalla build retail** (confirmed):
  nome valido -> OK, typo di una lettera -> backend DX12 fallisce
- [x] Sintassi file ricostruita: `#` commento (`;` no), `chiave=valore` senza `--`,
  spazi ammessi, nomi validati, niente sezioni. boost::program_options::parse_config_file
- [x] **Primo dump riuscito**: `dump-prefix` + `dump-all=true` produce XML `SC_INPUT` per
  shader hash + dump testuale con ISA, Shader Stats (VGPR/SGPR/spill), Optimization Report,
  SCML Model Decision Stats, Scheduler stats
- [x] Catena ottenuta: `shader hash -> SC_INPUT XML -> ISA RDNA2 -> statistiche`, senza
  toccare file firmati, registro, cache o iniettare nulla
- Strumento: **RGA in modalita' DX12** (usa il driver installato, headless, pochi secondi).
  3DMark non usabile per il canary: build Epic su JVM, non parte se lanciata da script;
  ProcMon senza filtri e' inutilizzabile (2.1 GB in 8 min). `tools/sc_probe.ps1` rimosso,
  sostituito da `tools/sc_canary.sh`
- [ ] **Non fatto**: nessuna opzione di ottimizzazione attivata; nessun dump su Steel Nomad
  (serve far ereditare l'ambiente al launcher Epic)

### 2D — catalogo 272 SCOption ✔ (parziale)
- [x] Tabella di puntatori contigua a RVA `0x2722060`, stride 8: **l'indice e' l'ID opzione**
  (`SCOption_MINIMIZE_VGPRS` = #20). 62 candidate RDNA2
- [ ] datatype/default/range non determinati

### 2E — Compiler Optimization Lab → `research/11_compiler_experiments/` ✔ CHIUSA (negativa)
- [x] Baseline 6 shader controllati (VGPR 8..144, inst 80..1994, branch fino a 40): `baseline.csv`
- [x] **Le 272 `SCOption_*` NON sono impostabili**: i soli `options_description` nel binario sono
  "CompilerControl options" e "Dump options" (8 opzioni dump). `u32SCOptions[0] = 0x%08X` prova
  che la tabella dei nomi serve al *reporting* di una bitmask, non all'input
- [x] 12 varianti di naming testate con l'oracolo: tutte KO
- [x] `AMD_DXCP_TEST_OPTIONS` scartata: accetta nomi arbitrari ma le settings note sono feature
  Adrenalin (Chill/Boost/RIS/Anti-Lag/FSR), non codegen
- [x] Controllo negativo: 24 compilazioni con le opzioni disponibili, **0 cambiano l'ISA**
- [x] **Ranking vuoto**: nessuna leva di codegen accessibile. Non inventate candidate
- Correzioni: `AMD_SC_OPTIONS` funziona (splitta sugli **spazi**, il mio path con "driver mod" si
  spezzava); default `dump-prefix` = `amdsc` nella CWD; le dump-* sono `typed_value<bool>`
  (serve `=valore`); esiste sintassi per-shader `<hash>.<opzioni>`

### 2F — banco D3D12 con timestamp query → `research/12_d3d12_microbench/` ✔ FUNZIONANTE
- [x] `bench.cpp` (MSVC/O2): D3D12 nativo, timestamp query @100 MHz, warm-up 10, 25 misure,
  8 dispatch/misura, mediana/media/p95/sd/CV. Nessun rendering, nessun VSync
- [x] **Bug di correttezza trovato e corretto**: buffer SRV non inizializzato -> gli shader
  leggevano denormali/NaN. `s3_mem` CV **68.7% -> 0.09%**
- [x] **Varianza del banco misurata prima di tutto** (3 run indipendenti, mediane):
  s2 ±0.02%, s3 ±0.28%, s5 ±0.22%, **s4 ±2.32%** (il piu' rumoroso)
- [x] **Wave32 vs Wave64 su 4 shader**: `[WaveSize(32)]` produce ISA **byte-identico** alla
  baseline (il driver sceglie gia' wave32); **wave64 sempre piu' lento**: +7.6% (s4), +14.6%
  (s5), +16.3% (s2), +18.4% (s3)
- [x] **Contro-esempio importante**: `s4_pressure` w64 ha VGPR 144->116 e inst 691->678, ed e'
  **+7.6% piu' lento**. Meno registri e meno istruzioni != piu' veloce. (I VGPR wave64 valgono
  il doppio in file registri: 116 w64 ~ 232 w32-equivalenti -> occupancy peggiore)
- [x] **Classifica: nessuna variante piu' veloce della baseline.** Non inventate candidate
- [x] Catena chiusa: HLSL -> DXC -> DXIL -> compilatore AMD -> ISA -> **tempo GPU reale in ns**
- [ ] Non fatto (fermata richiesta): numthreads, unroll/loop, riscritture di s4, verifica di
  correttezza numerica dell'output fra varianti

### Ricognizione `AmdExtD3DCreateInterface` / AGS ✔ (solo statica)
- [x] Lo stub in System32 e' un **forwarder puro**: 2 export, nessuna GUID, nessuna stringa
- [x] 59 simboli `AmdExt*` nel UMD: **intrinsics** (atomiche 32/64/float, wave ops
  ballot/scan/reduce, constant load, thread id) via `AmdExtD3DShaderIntrinsicsUAV`
- [x] **Nessun compiler control**: niente flag, ottimizzazioni, register allocation, scheduling.
  Non riapre le leve chiuse in 2E

### 2G — Automated Shader Optimizer → `research/14_optimizer/` ✔ FUNZIONANTE
- [x] **Verifica di correttezza numerica** aggiunta al banco (readback di 65 536 float4,
  tolleranza relativa 1e-4); validata: due run dello stesso shader danno output bit-identico
- [x] Ciclo automatico: genera HLSL -> DXC -> RGA (ISA/VGPR/inst) -> bench 3 run -> verifica ->
  conserva/scarta. 16 varianti one-variable-at-a-time, dedup per SHA del sorgente
- [x] **La verifica ha respinto 3 falsi positivi**: `L2_unroll4/8/12` erano le piu' veloci
  (-57%, -61%) ma con **errore relativo 1.5-2.0** = risultato semanticamente diverso
- [x] Criterio di accettazione **corretto in corsa**: soglia = max(rumore shader, spread
  variante, spread baseline). Da 5 "accettate" a **3 realmente valide**
- [x] **Top 3** (corrette, spread <0.3% su 3 run):
  `L3_loop` **-30.03%**, `all_loop` -29.87%, `L2_loop` -14.54%
- [x] Nuovi contro-esempi alle metriche statiche: `L2_loop` ha **piu' VGPR** (152 vs 144) ed e'
  -14.5%; `L3_loop` ha **piu' istruzioni** (719 vs 691) ed e' -30%
- [ ] Non fatto (fermata richiesta): esplorazione con i migliori come parent; access pattern
  (cambiano i dati letti -> output diverso, servirebbe un criterio di correttezza diverso)

### Ramo statico `u32SCOptions` → `research/13_scoptions_static/` ✔ CHIUSO
- [x] Non e' servito reverse engineering: **il dump elenca i flag attivi per shader**
  (`//!option SCOption_X = 1`)
- [x] Su Navi 21: **34 attive su 272** (22 sempre attive, 12 shader-dipendenti, 238 mai attive)
- [x] Delle 12 shader-dipendenti, **11 sono workaround hardware** (NSA, prefetch, LDS+VMEM,
  FP atomic denorm): l'input le induce, ma per **correttezza**, non per prestazioni
- [x] `MINIMIZE_VGPRS`, `PBQP`, `LIVENESS_BASED_SCHEDULING`, `FORCE_WAVE32/64`, `SUBVECTOR`,
  `ML_MODEL_FOR_PS_WAVESIZE`: **mai viste attive** e non raggiungibili
- Conclusione: l'ipotesi "induco l'euristica dall'input" e' vera come meccanismo ma **inutile
  come leva di ottimizzazione**

### 2H — Robustezza e causa → `research/15_robustness/`, `16_corpus/`, `17_rgp/` ✔ COMPLETA
- [x] **Corregge 2G alla radice**: la "baseline" di 2G aveva `[unroll]` esplicito scritto da me.
  Il **default di DXC** (nessun attributo) produce gia' il codice veloce: `dxc_default` e
  `L3_loop` coincidono entro 0.5% su tutti i 20 dataset e tutte e 15 le scale.
  **Contro il compilatore il guadagno e' zero.** La frase di 2G "il default di DXC (unroll
  completo) e' una scelta sbagliata" e' **falsa** e va cancellata
- [x] **Due difetti di misura del banco trovati e corretti**: warm-up a iterazioni invece che a
  tempo (fino a **5.2x** di errore su shader corti) e duty cycle basso (una submission+fence per
  misura -> clock GPU giu'). Ora tutte le `reps` misure sono in **una sola command list**.
  Ripetibilita' fra processi: 0.3-0.6% (prima fino a 419%)
- [x] Set 2G rimisurato: `L3_loop` **-16.31%** (non -30%), `all_loop` -16.65%,
  **`L2_loop` -1.63% -> RESPINTA**. La baseline `[unroll]` ha spread 12.7% ed e' **bimodale**
- [x] **Correttezza forte**: 20 dataset deterministici x 3 workload, output **completo**
  (1 048 576 float), max abs/max rel/RMS/RMS rel/NaN-Inf divergenti. Le varianti **superano
  1e-4 su 7 dataset su 20** — ma **`dxc_default` fallisce sugli stessi 7 con gli stessi
  errori**: e' lo shader a essere mal condizionato, non la trasformazione. RMS rel 1e-7 ovunque.
  `wave64` e' l'unica bit-identica, ed e' la piu' lenta
- [x] **Reference CPU** in float32 sugli stessi bit letti dalla GPU: RMS rel 1e-5 su ds0. Lo
  scarto GPU-CPU (4.6e-01) e' 3 ordini piu' grande di quello fra varianti GPU (1.2e-03)
- [x] **Scala**: guadagno fra -12.2% e -32.0% su 45 combinazioni (3 dataset x 3 workload x
  5 dpm x 5 run). Piu' grande sui workload piccoli
- [x] **Causa (confidenza: strong)**. Occupancy **identica** (144 VGPR entrambe), scratch 0,
  nessun branch: `[loop]` non impedisce lo srotolamento nell'ISA. Cambia lo **scheduling delle
  load**: `s_waitcnt` 23 vs 14, `s_clause` 1 vs 3, distanza load->wait mediana 3 vs 8,
  **12 load su 24 stallano entro 2 istruzioni** contro 1 su 24, gruppi di load 1.5 vs 6.0
- [x] **Tre controlli**: (nullo) `pressure24_nomem`, stessa aritmetica senza load -> la penalita'
  sparisce (+34.5% -> -4.4%); (negativo) `mem_gather` con indirizzi seriali -> ISA cambia
  uguale, guadagno +0.01%; (positivo) sweep del working set -> penalita' **-0.31% a 4 KB,
  +25.77% a 1 MB, +0.13% a 16 MB**: non monotona, esiste solo dove la latenza conta ma non
  domina
- [x] **Generalizzazione, 20 shader / 65 varianti / 5 run**: `[loop]` e' un **no-op** (0 meglio,
  0 peggio, 20 uguale). La variabile che conta e' `[unroll]`: **9 meglio, 3 peggio, 8 uguale**,
  mediana -3.08%, migliore -65.89%, **peggior regressione +40.69%** (`lds_reduce`)
- [x] Classe identificata: `[unroll]` danneggia i cicli il cui corpo tiene vivo fra le iterazioni
  un array indicizzato alimentato dalla memoria (`pressure24` +34.5%, `pressure48` +31.0%,
  `lds_reduce` +40.7%); aiuta dove il corpo e' piccolo e le operazioni sono indipendenti
- [x] **Pavimento del banco misurato: ~3.15 us** (solo store di 4 MB). `alu_ilp4__all_unroll`
  e `alu_chain_dep` sono **al pavimento**: i loro delta sono limitati dalla banda, non dal calcolo
- [x] RGP: due tracce catturate con `RadeonDeveloperPanelCLI --rgp-auto-capture=dispatch` +
  instruction tracing (`research/17_rgp/*.rgp`). **Non leggibili da CLI** (solo GUI), quindi
  **nessun contatore di stall misurato** — la causa resta *strong*, non *confirmed*
- [x] Progetto di **Phase 2I** scritto e non implementato: `15_robustness/PHASE_2I_DESIGN.md`

### 2I — AI-guided shader search → `research/18_ai_search/` ✔ COMPLETA (positiva)
- [x] **Self-check del banco reso bloccante** (`tools/bench_selfcheck.py`): al primo tentativo
  ha **fallito** (riproducibilita' 2.72% vs soglia 1%), quindi ho ridisegnato la statistica
  invece di allentare la soglia
- [x] **Confronto appaiato** con doppio riferimento (default misurato in prima E ultima
  posizione, media delle due) e ordine mescolato: cancella la deriva di clock, misurata a
  **+0.35%** sulla seconda posizione. Rumore del nullo appaiato: **SE 0.049%** -> un 1% e' 20 SE
- [x] Soglie fissate prima: candidato < -0.5%; accettato < **-1.0%** su **tutte e 3** le combo
  (workload, dataset) **e** media+2SE < 0, 10 processi per combo
- [x] **Deduplica a 3 livelli** (HLSL normalizzato / DXIL / ISA): 2 varianti eliminate senza
  misurarle, entrambe informative. `p24__load_then_scale` -> **ISA identica** al default;
  `bdiv__select` -> **DXIL identico** (DXC canonicalizza gia' if/else in select)
- [x] Correttezza a due livelli su 5 dataset: **1 eliminata** (`trig__unroll4`, max rel 4.4e-4)
- [x] **9 varianti su 23 battono il default REALE**, tutte su 3/3 combo:
  `bdiv__hoist_parity` **-69.5%**, `bdiv__hoist_parity_batch` -49.7%, `trig__unroll` -25.4%
  (**bit-exact**), `ldsred__wave` -14.5%, `ldsred__tree` -14.4%, `mix__unroll` -6.2%,
  `dot__unroll` -5.8%, `dot__acc4` -5.8%, `dot__acc4_unroll` -1.2%
- [x] Il vincitore e' **strict** (max rel 4e-7): non e' una vittoria comprata con la precisione
- [x] **Su `p24` nessuna variante batte il default**: 7 trasformazioni, 0 accettate. Il
  compilatore su quello shader e' gia' a posto
- [x] **Causa isolata con 5 controlli, ipotesi iniziale falsificata.** Non e' il parallelismo
  di memoria: raddoppiare le load senza ramo da' **-4.3%** (peggiora). `hoist_seq` ha la
  **stessa aritmetica** del default (128 v_sin, 128 v_cos) e solo 32->2 branch divergenti,
  95->2 operazioni su exec mask: **-67.0%**. Il backend AMD ricava 32 rami divergenti da una
  select, scelta che non paga mai quando la condizione divide sempre il wave
- [x] **Lo staging LDS coalescente e' il peggior risultato della fase**: +109.8% / +99.9% /
  +93.0% su tre shader. Il costo in occupancy supera il guadagno in coalescenza
- [x] Prodotti `search_history.csv`, `accepted_variants.csv`, `rejected_correctness.csv`,
  `accepted_correctness.csv`, `isa_dedup.csv`, `confirm_detail.csv`, `causal_bdiv.csv`,
  `best_variants.md`
- [ ] Non fatto: generazione automatica delle trasformazioni (in 2I le propongo io); predittore
  su regioni divergenti / waitcnt per op di memoria / byte LDS per gruppo

### 2J - Feature-Guided Transformation Predictor -> `research/19_predictor/` COMPLETA (positiva)
- [x] **Le trasformazioni ora sono meccaniche**: lo shader e' un IR (`tools/ir2j.py`), ogni
  trasformazione e' una funzione IR->IR, l'HLSL lo genera il programma. Verifica: l'emettitore
  riproduce `bdiv__hoist_parity` di 2I meccanicamente. **17 trasformazioni, 10 regole**
- [x] Split dichiarato PRIMA delle regole: **6 dev** (gia' misurati in 2H/2I) + **8 validation**
  mai usati per costruirle, di cui 3 trappole deliberate
- [x] Feature separate: 21 sorgente (dall'IR) + 9 DXIL (`dxc -Fc`) + 15 ISA (RGA) + occupancy
  stimata. Il predittore vede **solo la baseline**
- [x] **RISPOSTA: si', ~4x meno tentativi.** Guidato con budget **2** (-37.18%) batte random
  con budget **8** (-35.03%). Con budget 5 trova **l'ottimo esatto su 7 shader su 8**, e su
  quei 7 random non lo batte mai (P=0.000 su 4000 estrazioni). Hit rate 62.5% vs 36.5%
- [x] **Il merito NON e' delle regole**: solo regole = 80.1% dell'oracolo contro il **77.7% di
  random**. Con l'evidenza misurata dai dev: **96.9%**. Il sistema funziona perche' ricorda
  misure, non perche' ragiona
- [x] **Apprendimento online = zero** (C identico a B): con 8 shader e budget 5 non c'e'
  abbastanza trasferimento. Negativo pulito
- [x] Le due sconfitte sono lo stesso errore, **regole dedotte ragionando invece che misurando**:
  R2 ("condizione uniforme -> sollevare inutile") e' FALSA, su `v_cond_uniform` hoist vale
  **-46.26%**; R5 ("array vivo -> niente unroll") vale a n=24/48 ma **non a n=16**, dove unroll
  vale -16.16% (`v_pipe16`, unico shader dove random batte il guidato)
- [x] Controllo "ordine di catalogo" (97.4%) riportato ma **dichiarato non valido**: quell'ordine
  l'ho scritto io e contiene gli stessi prior
- [x] **La correttezza ha trovato 10 bug MIEI su 112 varianti**, nessuno del compilatore: indice
  di staging LDS errato; `tg32/tg128` **semanticamente non valida** quando la condizione legge
  `gid.x`; sollevamento con modulo 4 emesso con 2 rami invece di 4. Dopo le correzioni 112/112
- [x] Deduplica a 3 livelli: 14 varianti su 140 eliminate prima di misurarle
- [x] Prodotti `shader_features.csv`, `transform_proposals.csv`, `search_history.csv`,
  `validation_results.csv`, `budget_sweep.csv`, `correctness.csv`, `dedup.csv`,
  `predictor_vs_random.md`
- [ ] Non fatto: shader reali catturati da un workload DX12; `v_pipe16` resta irrisolto (non ho
  aggiustato le regole per farlo passare, sarebbe stato fitting sulla validation)

### 2K - Generalizzazione su shader REALI + memoria delle misure -> `research/20_real/` COMPLETA
- [x] **Corpus reale**: DirectX-Graphics-Samples (Microsoft) + FidelityFX-SDK (AMD), clonati
  shallow+sparse. 476 file HLSL -> 66 entry point compute che compilano standalone -> 64 unici
  -> **64/64 eseguibili** -> 58 misurabili -> **34 dev / 24 REAL_VALIDATION** (split per hash,
  fissato prima di qualunque ranking)
- [x] **Banco generico nuovo** (`bench2.cpp`): root signature **sintetizzata dalla tabella dei
  binding letta nel DXIL**, risorse fittizie tipizzate per slot (Texture2D/2DArray, CBV,
  sampler, buffer strutturati/raw/con contatore). Dump di verifica esteso alla RWTexture2D,
  senza il quale la correttezza sarebbe stata vuota per la maggior parte di questi shader
- [x] **Memoria delle misure** persistente: `measurement_memory.csv`, 216 righe con feature
  baseline, trasformazione, parametri, correttezza a due livelli, Delta%, SE, workload,
  dataset, hash DXIL, VGPR/SGPR/LDS/branch/waitcnt/load-use/clause, validita'
- [x] Predittore **solo evidenza**: kNN (k=5) sulle feature normalizzate, media pesata dei
  Delta osservati sui dev simili. Nessuna regola scritta a mano
- [x] **RISPOSTA: si', ~2.5x.** Memoria con budget **2** (-7.02%) = random con budget **5**.
  A budget 1: memoria **-6.57%** contro random **+1.59%** (in media una regressione)
- [x] **Vantaggio piu' piccolo che sul sintetico (2J: 4x), per motivo strutturale**: su HLSL
  arbitrario restano meccanicamente sicure solo attributi di ciclo, wave size e numthreads ->
  **3.6 trasformazioni per shader** contro ~11 sull'IR. Le trasformazioni strutturali che in
  2I/2J valevano -30%/-70% richiedono un AST HLSL vero: **non implementate**, non omesse
- [x] **Errore di metodo trovato e corretto**: `tg*` dava -50% falsi su shader
  `numthreads(1,1,1)` con scritture idempotenti. Il gate di correttezza **non poteva**
  catturarlo (risultato identico, lavoro diverso). Aggiunto invariante meccanico: la
  trasformazione deve **conservare il numero totale di thread**. 9 misure invalidate
- [x] **Il corpus sintetico aveva insegnato una cosa falsa**: in 2F/2H `wave64` era **sempre**
  peggiore (+7%..+20%). Su shader reali e' la trasformazione **piu' spesso accettata**
  (23/51, migliore **-49.86%**); `wave32` resta un no-op (0/51)
- [x] **Guadagni reali su codice Microsoft/AMD non modificato**, tutti correttezza *strict*:
  `BitonicPreSortCS` **-77.43%** con `[unroll(4)]`, `ParticleSpawnCS` **-49.86%** con wave64,
  `DoFPass2CS` -17.85%, `DebugDrawHistogramCS` -15.27%. **12 shader su 24** con almeno una
  variante accettata; scarto per correttezza 4.7%
- [x] Baseline "solo regole" (-8.47% a budget 2-3) **dichiarato non valido**: l'ordine l'ho
  scritto io dopo aver visto 2J. Il solo baseline pulito e' random
- [x] Prodotti `REAL_GENERALIZATION.md`, `measurement_memory.csv`, `shader_features.csv`,
  `transform_proposals.csv`, `validation_results.csv`, `corpus.csv`, `probe.csv`,
  `PHASE_2L_DESIGN.md` (progettata, **non eseguita**)
- [ ] Non fatto: AST HLSL per le trasformazioni strutturali; dati reali al posto delle risorse
  fittizie; dedup a livello ISA sulle varianti (costo RGA)

### 2L - Ottimizzazione end-to-end su workload reale -> `research/21_workload/` COMPLETA (negativa)
- [x] **Workload reale costruito da sorgente**: MiniEngine ModelViewer (DirectX-Graphics-Samples),
  scena Sponza, MSBuild toolset v145, configurazione Profile. Criterio di scelta dichiarato
  PRIMA del profiling; 51 dei 58 shader del corpus 2K vengono da MiniEngine
- [x] **Strumentazione aggiunta all'app**: modalita' benchmark headless, export CSV dell'albero
  dei timer GPU, media su TUTTI i frame (StatHistory media solo sugli ultimi 64), VSync off con
  passo temporale fisso a 1/60. **Spread run-to-run del frame da 18.03% a 1.13%**
- [x] Baseline: **GPU frame 1.0680 ms**, 2000 frame dopo 400 di warm-up, 7 run
- [x] **Ranking per costo reale**: `Render Color` **48.71%** del frame (pixel/vertex, FUORI dal
  corpus 2K che e' solo compute). I pass compute raggiungibili sommano ~33%
- [x] **RISPOSTA: no, guadagno end-to-end zero.** Due integrazioni: set `bitonic`
  (micro -79.9%/-51.2%) -> pass **+1.24%**, frame **-0.27%**; set `culling` (micro -76.4%/-65.8%)
  -> pass **+1.83%**, frame **+0.35%**. Entrambe dentro il rumore, entrambe col pass PEGGIORATO
- [x] **Causa 1: ottimizzati shader che l'app non esegue.** `BitonicPreSortCS`/-77% viene da
  `D3D12RaytracingFallback`, non da MiniEngine; `Sort()` e' chiamata con
  `IsPartiallyPreSorted=true` (PreSort mai dispatchato); e uno `ScopedTimer` dentro
  `BitonicSort::Sort` **non compare mai** nel profilo: la scena usa il percorso tiled rendering
- [x] **Causa 2: le bocciature di correttezza di 2K erano FALSI NEGATIVI.** Lo **stesso `.cso`
  misurato due volte** da' output diverso su `ParticleBinCullingCS` (max rel 0.38),
  `ParticleLargeBinCullingCS` (0.18), `ParticlePreSortCS`: sono **non deterministici** (append
  buffer/atomiche). Il gate di 2K misurava la loro nondeterminatezza, non la trasformazione
- [x] **Causa 3: il guadagno si inverte.** Micro a ~1 M thread con risorse finte contro
  `DispatchIndirect` con conteggi derivati dai dati e poche particelle: -76% -> +1.83%
- [x] **Anche l'oracolo immagine cade**: la build NON modificata da' **2 hash distinti su 6 run**.
  I miei test precedenti (3 e 4 run) erano troppo corti. Tutti i verdetti "immagine diversa" di
  questa fase sono ininterpretabili
- [x] Amdahl calcolato prima di ogni integrazione; `[WaveSize]` non testabile perche' l'app
  compila a SM 6.2 e serve 6.6
- [x] Prodotti `PHASE_2L_RESULTS.md`, `baseline_profile.csv`, `pass_ranking.csv`,
  `ab_bitonic.csv`, `ab_culling.csv`
- [ ] Le tre correzioni da fare prima di rifare la fase: costruire il corpus dagli shader che il
  workload **esegue** con i loro **veri** dispatch; testare la determinatezza della baseline
  prima di qualunque gate numerico; riprodurre nel microbenchmark il dispatch reale

### 2M - Runtime-First Hot Shader Optimization -> `research/22_runtime/` COMPLETA (negativa, informativa)
- [x] **Ambiente pulito verificato** (Chrome/Discord chiusi, 0 processi rumorosi). Spread del
  GPU frame 0.5-1.4% su 5-7 run
- [x] **Inventario runtime nell'app** (`Core/ShaderInventory.{h,cpp}`): scope -> PSO -> hash
  FNV-1a del bytecode VS/PS/CS -> chiamate/frame -> dimensioni reali di dispatch/draw.
  **40 istanze shader realmente eseguite, 40/40 mappate al sorgente**
- [x] **La mappatura va fatta per HASH, non per nome**: il PSO di `Render Color` si chiama
  "Sponza: Depth PSO" perche' MiniEngine fa `m_ModelPSO = m_DepthPSO` e la copia porta il nome.
  Solo l'hash identifica `ModelViewerPS` (12 612 byte, confermato compilando con DXC)
- [x] **Ranking reale**: `Render Color` **48.71%** del frame (PS `ModelViewerPS` + VS
  `ModelViewerVS`, 28.90 draw/frame); i primi 7 pass fanno il **76%**
- [x] Optimizer esteso ai **pixel shader**: `Lighting.hlsli` (22 cicli, incluso SOLO da
  `ModelViewerPS`), trasformazioni applicate, app ricompilata, A/B pulito
- [x] **RISPOSTA: no.** `all_unroll4` **+0.61%** su Render Color, `all_loop` **+0.36%**.
  Nessun guadagno
- [x] **Il perche', misurato non ipotizzato.** Due sonde di Amdahl: togliere tutte le 128 luci
  locali -> **+0.36%**; azzerare **l'intero pixel shader** (`mrt.Color = 0`, bytecode da 12 612
  a ~4 900 byte) -> **+0.66%**. **`Render Color` non e' limitato dall'ALU del pixel shader.**
  Confronto: `Opaque` disegna la stessa geometria con gli stessi 28.90 draw senza PS e costa
  0.032 ms contro 0.520 ms — ma quel 16x non sta nel codice dello shader
- [x] **Difetto mio (a)**: dopo aver cambiato il layout della classe `PSO`, la build
  incrementale lasciava Model/ModelViewer non ricompilati -> access violation. Serve
  `-t:Rebuild` dopo ogni modifica a un header condiviso
- [x] **Difetto mio (b)**: l'oracolo d'immagine introdotto in 2L **e' rotto** — col PS forzato
  a nero il dump e' byte-identico al baseline. **Tutti i verdetti "immagine identica/diversa"
  di 2L e 2M vanno scartati.** Non ho una verifica di correttezza a livello di frame; lo dichiaro
  invece di inventarne una
- [x] Prodotti `PHASE_2M_RESULTS.md`, `runtime_inventory.csv`, `shader_map.csv`, `hot_ranking.csv`
- [ ] Non fatto: compute replay con i dispatch reali (i dati ci sono in `runtime_inventory.csv`);
  capire con contatori hardware cosa limiti davvero `Render Color` (banda render target? ROP?
  texture?); riparare l'oracolo di correttezza end-to-end

### 2N - Classificazione dei colli di bottiglia hardware -> `research/23_bottleneck/` COMPLETA
- [x] **Counter ENUMERATI, non indovinati**: `gpaenum.exe` apre un contesto GPUPerfAPI DX12 e
  trova **145 counter reali su Navi 21** in 13 gruppi. Ne sono stati abilitati 31 (13 passate)
- [x] **GPUPerfAPI 4.4.5 integrato nell'applicazione** (`Core/GpaProfiler.{h,cpp}`), agganciato
  agli scope del profiler e al ciclo di vita delle command list. RGP resta inutilizzabile da CLI
- [x] **CLASSIFICAZIONE**:
  `Render Color` 48.7% -> **texture-unit throughput bound**;
  `Resolve Image` 9.5% -> **memory bandwidth bound**;
  `Render Shadow Map` 4.5% e `Z PrePass` 3.0% -> **raster/geometry bound**;
  `Culling & Sorting` 4.4% -> **latency/serialization bound**;
  `Sharpen or Copy` 3.3% -> **bandwidth bound**; `Generate SSAO` -> **memory latency bound**
- [x] `Render Color` e' texture-bound e non altro, per esclusione dai numeri: TexUnit **94.6%**
  busy con solo **0.4%** di stall; ROP `PSExportStalls` 0.01% e `WriteUnitStalled` 0.00%;
  raster `PAStalledOnRasterizer` 0.2% (contro 49-52% dei pass davvero raster-bound); banda
  **73 GB/s** contro i 555 e 621 GB/s di altri pass dello stesso frame. Con L0 al 97.6% il
  limite e' il **rate di filtraggio**, non il trasporto dei byte
- [x] **BUG GRAVE TROVATO NEI MIEI STRUMENTI**: verificando l'hash dell'eseguibile ho scoperto
  che una build con shader modificato produceva **binario identico e stesso mtime** — MSBuild
  saltava la ricompilazione in silenzio (granularita' dei timestamp). Si misurava due volte lo
  stesso binario
- [x] **Correzioni retroattive a 2M**: (a) «azzerare il pixel shader non cambia Render Color» ha
  **evidenza invalida**, ma la conclusione *non e' ALU-bound* e' confermata indipendentemente dai
  counter; (b) «l'oracolo d'immagine e' rotto» e' **RITRATTATA**: il dump identico si spiegava col
  binario identico
- [x] Rimedio: `tools/buildv.py` con `-t:Rebuild` e verifica sull'hash dell'**header dello shader
  compilato** (deterministico; quello dell'eseguibile no, cambia a ogni link)
- [x] **Circa il 12% del frame (raster + serializzazione) non e' raggiungibile da nessuna
  trasformazione di shader.** Il 48.7% di Render Color lo e', ma solo riducendo il **numero di
  operazioni di sampling** — non con gli attributi di ciclo, l'unica cosa che il catalogo sa fare
- [ ] Non fatto: i controlli di ablazione (PS vuoto / senza texture / un solo render target)
  falliscono la compilazione con `-t:Rebuild` e la causa non e' diagnosticata; `HDR Tone Mapping`
  non produce dati (scope non registrato dall'aggancio GPA); `CSBusy`/`CSVALUUtilization` non
  erano nel set abilitato

## 2O — Audit handoff e ablation gate (2026-09-05)

- [x] Audit read-only di sorgenti/dati, storia, toolchain e clone reali; output in
  `research/CODEX_HANDOFF_AUDIT.md` e `research/handoff_audit_20260905/`.
- [x] Mapping offline: 40/40 associazioni scope/stage/hash del CSV storico corrispondono
  agli header attuali; non è ancora una prova di propagazione di una variante nuova.
- [x] Piano preregistrato in 8 passi, massimo 6 cicli, §7 dell'audit.
- [x] **Gate build — SUPERATO** (2026-09-06). `tools/test_buildv.py`: 17 modi di fallimento su 17
  rifiutati senza GPU (errore processo, header assente/ambiguo, hash invariato, hash inatteso,
  bytecode corrotto, PSO runtime sbagliato). Ricompilando il PS attraverso la catena si riottiene
  l'artefatto storico: **12 612 byte, `52CE6C5E64AB2E82`**.
- [!] **Gate GPA — non superabile con la strumentazione di 2N.** Quel set richiede 13 passate;
  fra i 145 counter *derivati* nessuno discrimina il rate di filtraggio da cache/latenza/ALU e
  non ne esiste alcuno per l'ALU dello stage pixel. `25_gpa_validity/GPA_VALIDITY.md`.
- [x] **Opzione (a) eseguita — counter raw disponibili** → `research/26_gpa_hwcounters/`.
  `kGpaOpenContextEnableHardwareCountersBit`: **145 → 4001 counter**, verificato offline (contesto
  virtuale, device `1002:73A5:C0`) **e live** (contesto DX12 reale, RX 6950 XT); i due insiemi di
  nomi sono identici. **96 counter `SQ` mascherati `PS`** (`INSTS_VALU`, `INST_CYCLES_VALU`,
  `ITEM_CYCLES_VALU`, `INSTS_SALU`, `INSTS_TEX_LOAD/STORE`, `WAVES`/`WAVES_32`/`LEVEL_WAVES`) e
  **14 eventi `TA` × 80 CU** (`TA_BUSY`, `ANISO_{1..16}_CYCLE_QUADS`, `MIP`, `VOL`). `TD` espone
  solo ray-tracing BVH. **Pass count misurati:** 36 `SQ_PS*` = **1**; `TA_BUSY` × 80 CU = **1**;
  distribuzione `TA` completa = 7 (`TA` regge 2 eventi/passata); `SQ`+`TA_BUSY` = 2; +`GPUTime` = 3.
  Il costo dipende dagli eventi per blocco, **non** dalle instance → copertura per-CU gratuita.
  **Opzione (c) non necessaria.** Nessun counter è ancora stato letto da un workload.
- [ ] Da correggere prima di qualunque cattura: 10 return code GPA ignorati, ordine
  `Begin`/`OnContextBegin`, `ComputeContext::Begin` che non registra mai, `Shutdown()` mai
  chiamata. E fissare la semantica dei counter raw sulla documentazione AMD prima di
  interpretarne i numeri.

### O1 — propagazione build ✔ **PASS** (ciclo 1/6) → `research/24_phase2o_build_gate/`

- [x] `O1_20260906_010146`. A baseline → B canary → A2 ripristino, tutte con SHA-256 del bytecode
  **preregistrato prima della build**.
- [x] Bytecode presente **esattamente una volta** in `Model.lib` e `ModelViewer.exe`;
  **34 draw** di `Render Color` con hash PSO atteso su 2 PSO nativi, 836 757 indici.
- [x] Canary rilevata **come valore**: 100,00% dei pixel, solo canale R, tutti positivi,
  delta decodificato mediano **+0,124268** (= +0,125 quantizzato in R11). G e B invariati al bit.
- [x] A2 riproduce immagine **bit-identica** ad A con eseguibile di SHA-256 diverso → la build è
  avvenuta davvero. Controllo diretto del difetto 2N “MSBuild saltava la ricompilazione”.
- [x] Spread di baseline **misurato 0 su 3 processi**. Registrato come spread misurato, **non**
  come determinismo: `FillLightGridCS.hlsli:163` usa `InterlockedAdd`, il meccanismo esiste.
- [x] Cattura al frame 140: `RenderLightShadows` copia **una** slice su `MaxLights=128` per frame.
- [x] **14 difetti eliminati prima del ciclo.** Il tlog `CL.read.1.tlog` non può contenere l'header
  generato (FileTracker esclude output e Packages: **è questa la causa dell'anomalia
  `dxc.write.1.tlog`, non i timestamp**); `-MD` mette DXC in modalità solo-dipendenze;
  regex che troncava `.hlsli`; `inline constexpr` in build C++14. Elenco completo nel report.
- [x] **3266 file del clone originale riverificati, 0 modificati.** Nessun delete, nessun Clean.

### O2 — semantica, identità del workload, baseline ✔ **PASS** (ciclo 2/6) → `research/27_o2_counters/`

- [x] `O2_20260906_014011`. Shader **non modificato** (stesso SHA-256 di O1), nessuna ablazione,
  nessun verdetto di prestazione. 4 sessioni: `sq_ps` (32 counter, 1 passata), `ta_busy` (80, 1),
  `crosspass` (85, 2), `aniso` (721, 5); 8 sample su frame consecutivi dal 140.
- [x] **Aggregazione validata misurando, non leggendo**: `CPF_STAT_BUSY`=`GPUBusyCycles` esatto;
  `TexAveAnisotropy`=media pesata esatta (1,2181); `TexUnitBusyCycles` **non è la somma** dei 80
  `TA_BUSY` ma il **massimo**, e `TexUnitBusy%`=`max/GPUBusyCycles·100` esatto (94,627017).
- [x] **Identità del workload**: totali dei bucket aniso **bit-identici su una sessione a
  5 passate** (40 frame); `ITEM_CYCLES_VALU` esatto ovunque. Cross-pass `Σ TA_BUSY`: 0,43% di
  differenza contro 1,72% di rumore frame-a-frame → **PASS**.
- [x] Criterio di identità preregistrato (0,1% su ogni counter) **FALLITO** e riportato come
  tale: era troppo grossolano, mescolava lavoro aggregato, lavoro per-instance e timing.
- [x] **Baseline**: PS waves 39 214, **`WAVES_32`=0 → pixel shader in wave64**, VALU 71,0 M inst /
  183,2 M cicli, `INSTS_TEX_LOAD` 6,12 M, `Σ TA_BUSY` 89,0 M, `GPUTime` 802 µs (±19,9%),
  11,22 M quad aniso con media 1,2181 sample/quad. 14,56 cicli TA per istruzione texture PS.
- [ ] Non stabilito: `TA_BUSY` **non è attribuito a uno stage** (serve una sessione con
  `SQ_VS*_PERF_SEL_INSTS_TEX_LOAD`); il legame `INSTS_TEX_LOAD`↔quad↔`TA_BUSY` non è un'identità
  pulita; i counter `{emulated}` valgono ±0,4%.
### O3 — ablazione del campionamento materiali ✔ (`research/28_o3_material_ablation/`)
- [x] 4 build (`mat0..mat3`), ognuna gated su uno SHA-256 di bytecode **preregistrato offline
  prima** che girasse qualunque build. Sostituzioni type-preserving al sito di sample.
- [x] **Dose esatta**: 1,06 / 2,07 / 3,34 istruzioni texture rimosse per wave PS su **155,9**.
  I tre sample dei materiali sono il **2,1%** delle istruzioni texture del pixel shader; gli
  altri ~153 sono i fetch di luci e shadow map di `ShadeLights`. Chi si aspettava che "le texture
  dei materiali" dominassero questo pass sbagliava di un fattore ~50.
- [x] **Confondente quantificato, non assunto**: `mat3` non è un'ablazione solo-texture — toglie
  2,1% di texture e **11,3% di VALU**, perché muore anche la matematica TBN che consumava i
  valori. `mat1` è il punto utile: texture giù, ALU **su** dello 0,55%.
- [x] Risposta monotona: Δ`TA_BUSY` −2,33 / −5,71 / **−13,91%**, Δ`GPUTime` −1,53 / −3,39 /
  −11,43%, con soglia A/A max(2%, 3×1,03%) = 3,09%. **I 3 sample materiale costano il 13,9% dei
  cicli busy della texture unit pur essendo il 2,1% delle sue istruzioni.**
- [x] **Difetto di strumentazione trovato**: i counter SQ per-shader-engine sono a volte
  corrotti (SE0 e SE2: valori di un evento sotto il nome di un altro, bit-identici a una sessione
  diversa). Gate nuovo `tools/sq_validity.py`; le dosi O3 usano solo SE1+SE3. Nessuna conclusione
  precedente ne è toccata (la sessione `sq_ps` di O2 passa il gate; i counter TA sono sani).
- [x] Non stabilisce "texture-filter-throughput bound": stabilisce che una riduzione verificata
  di lavoro della texture unit dà una riduzione di tempo **proporzionale ma smorzata** (0,59–0,82).

### O4 — ablazione del solo sampler ✔ (`research/29_o4_sampler/`) — **falsifica 2N**
- [x] 5 build (`s_base`, `s_aniso1`, `s_aniso16`, `s_point`, `s_bilinear`): cambia **solo** il
  sampler statico in C++, il bytecode del pixel shader è **byte-identico** in tutte
  (`52CE6C5E64AB2E82`) e il gate lo impone. Scope verificato nel sorgente: dentro `Render Color`
  girano solo i draw Sponza opachi+cutout, che campionano **esclusivamente** via `defaultSampler`.
- [x] **ALU tenuta ferma e verificata**, non solo argomentata: `INSTS_VALU`, `INST_CYCLES_VALU`,
  `ITEM_CYCLES_VALU`, `INSTS_TEX_LOAD`, `WAVES` invariati entro **0,07%**, con tutti e 4 gli
  shader engine sani sotto il gate di O3.
- [x] Dose: istogramma aniso **collassato** (media 1,2181 → 1,0000), **−17,9%** di cicli aniso,
  quad costanti allo 0,06%.
- [x] Risposta: Δ`TA_BUSY` −2,73 / −3,50 / −3,54%, Δ`GPUBusyCycles` −2,20 / −2,63 / −2,78%,
  Δ`GPUTime` −2,31 / −2,86 / −2,52%. Soglie per-metrica dal controllo A/A: `GPUBusyCycles` 2,00%
  (passano), `GPUTime` 3,88% (**non** passa). Verdetto co-primario conservativo: **riduzione di
  `TA_BUSY` e `GPUBusyCycles` stabilita, riduzione del tempo suggestiva ma non confermata.**
- [x] **RISULTATO**: spegnere del tutto l'anisotropico — e in `s_point` scendere al filtro più
  economico dell'hardware — muove `Render Color` **al massimo del ~3%**. L'ipotesi di 2N
  «`Render Color` è texture-filter-throughput bound» prevedeva un effetto grande: **non è
  supportata**. La texture unit è occupata al 94%, ma non a *filtrare*.
- [x] **Bidirezionalità fallita e dichiarata tale**: il braccio verso l'alto (`s_aniso16`) produce
  solo +0,71% di dose perché il contenuto non chiede quasi mai più di 8×. Il suo nullo non
  falsifica nulla; valgono solo i bracci verso il basso.
- [x] **Nessuna partizione di costo O3/O4**: 3,50/13,91 = 25% è il confronto di due interventi
  **diversi**, non una scomposizione «25% filtraggio / 75% resto»: additività mai misurata.
- [x] Difetti trovati e riportati: `CubeMapSamplerDesc` è copia di `DefaultSamplerDesc` quindi
  cambiava anche `s12` (fuori scope, nessun numero toccato, ma l'invariante scritta era falsa);
  `defaultSampler` è usato anche da `DepthViewerPS`/`SkyboxPS` fuori scope e può scaldare la
  cache diversamente; **DXIL identico non garantisce ISA nativa identica** (il driver vede la
  root signature alla creazione del PSO) — a cui risponde la misura ALU sopra.
- [x] **Audit indipendente da Codex** (via herdr): dose e risposta ricalcolate da zero dai CSV
  grezzi e riprodotte; i tre difetti sopra, la bocciatura della bidirezionalità e il rifiuto
  della partizione 25/75 vengono da lì e sono stati adottati. Conservati in `29_o4_sampler/audit/`.
- [ ] Non misurato: counter TCP/TCC/cache. Parte del −3,5% può essere traffico di memoria
  ridotto invece che filtraggio. O4 misura il costo dell'intero percorso sampler.

### O5 — attribuzione di stage + classificazione cache/memoria ✔ (`research/30_o5_memory/`)
- [x] **Nessuna build**: riusati i 5 eseguibili di O4 (SHA-256 riverificato a prepare e a ogni run),
  cambiano solo i set di counter. Le varianti sampler di O4 diventano così una **leva di traffico
  di memoria a bytecode byte-identico**. Passate misurate offline prima di correre:
  `tcp_ta` 320 counter/**1 passata**, `l1l2` 96/**1**, `dram` 144/**1**, `stage_tex` 16/2, `stage_all` 56/7.
- [x] **Attribuzione di stage chiusa, ma è servito un controllo per chiuderla.** `SQ_VS*` legge
  zero waves e zero texture: da solo non distingue "il vertex stage non campiona" da "il vertex
  stage non gira sotto quella maschera". Sweep di **tutte e 8 le maschere**: il lavoro vertex sta
  sotto `GS` (NGG primitive shader), 9 596 waves, e **emette 28 852 istruzioni texture = 0,47%**
  (3,007 per wave: un attribute fetch a 3 stream — `INSTS_TEX_LOAD` conta anche i buffer load).
  Predizione preregistrata <1% → **PASS**; tutti i rapporti texture di O2/O3/O4 reggono entro 0,47%.
- [x] **Non è la cache L0**: `Σ TCP_TA_REQ_STALL / Σ TA_BUSY` = **0,24%** contro una banda
  preregistrata «non è la cache» di ≤10%. Il counter non è morto: l'intervento sampler lo muove
  come il suo significato impone (TCP req −12%, L0 miss −30%, stall −24%).
- [x] **Non è il traffico di miss né la DRAM**: hit L0 **97,66%**, 0,21 miss per istruzione
  texture; **31,88 MB letti = 39,6 GB/s**, contro i 555–621 GB/s che 2N misura su altri pass
  dello stesso frame. **Cross-check**: L2 miss × 64 B = 31,90 MB contro 31,88 MB calcolati
  indipendentemente da `EA_RDREQ_*` → **0,06% di scarto**, ed è questa la prova che la lettura
  della gerarchia è affidabile.
- [x] Numeri chiave: **156,0 istruzioni texture per wave PS**, **14,51 cicli di `TA_BUSY` per
  istruzione**, 9,07 richieste L0 per istruzione, **duty cycle TA 93,25%** (coerente con il
  `TexUnitBusy` 94,63% di O2, che è il *massimo* sulle 80 CU).
- [x] **Correzione aggiunta dopo O6**: la sezione «cosa resta in piedi» elencava solo candidati del
  percorso texture, e si leggeva come se il percorso texture fosse *il* limite. Non lo è: l'ALU del
  pixel shader era un quinto candidato mai testato lì.

### O6 — replica/falsificazione a bytecode fisso ✔ (`research/31_o6_lightcount/`)
- [x] Leva: **numero di luci che sopravvivono al culling**, dato C++ in `CreateRandomLights`
  (`radiusSq = 0` per stride di indice, così il mix sfera/cono/cono-ombreggiato resta
  proporzionale e le luci superstiti sono bit-identiche). 4 build, 4 eseguibili distinti,
  **un solo bytecode** (`52CE6C5E64AB2E82`) imposto dal gate.
- [x] **Dose misurata, non dedotta dallo stride**: istruzioni texture per wave 155,99 → 100,86 →
  49,92 → 33,40 (−35,4 / −68,1 / −78,6%), con le waves costanti allo 0,19%. Il 155,99 riproduce
  esattamente il 156,0 di O5 da build e sessione diverse.
- [x] **REPLICATO su entrambe le bande preregistrate**: Δ`TA_BUSY`/Δtex = **0,94 / 0,90 / 0,90**
  (banda [0,75–1,25]) e **13,6 / 13,1 / 13,1 cicli** per istruzione rimossa (banda [10–19],
  predizione di O5: 14,5). Il pass scende del **−32,5 / −60,2 / −69,4%** di `GPUBusyCycles`.
- [x] Fit lineare: `GPUBusyCycles` = 0,1710 × (istruzioni texture) + 139 365 → **l'88,2% dei cicli
  del pass scala col conteggio di istruzioni**; per `TA_BUSY` il 90,4%.
- [x] **ERRORE MIO TROVATO E CORRETTO NELLA STESSA STESURA**: avevo diviso `INST_CYCLES_VALU` per
  320 SIMD (layout GCN) invece che per **160** (RDNA2 ha 2 SIMD32 per CU). Il duty VALU non è
  48,3% ma **96,64%**. Controllo che lo smaschera: ÷80 darebbe un impossibile 193%.
- [x] **Conseguenza, che indebolisce la conclusione**: alla baseline il pass è **co-saturo** —
  VALU 96,64% e texture addresser 93,61%, con l'ALU *marginalmente più alta*. O6 **non può
  classificare** texture sopra ALU: entrambe scendono con lo stesso loop. Man mano che il loop si
  accorcia divergono (VALU 96,6→71,8%, TA 93,6→88,5%).
- [x] `GPUTime` inaffidabile qui (N95 13,99%): il primo processo di ogni batch gira a clock più
  basso (1,476 vs 1,688 cicli/ns) mentre `GPUBusyCycles` si muove <0,7%. Conclusioni su
  `GPUBusyCycles` e `TA_BUSY`.
- [x] Due `prepare` rifiutati e conservati (`_SUPERSEDED_prepare_01/02`): manifest non
  sovrascrivibile (gate che funziona) e `experiment_id` non coincidente col nome del workspace
  (che avrebbe fatto fallire ogni build). **Nessuno dei due ha costruito o misurato nulla.**

- [x] **Audit indipendente di Codex (via herdr)**: dose, elasticità (0,935/0,905/0,904), costo
  marginale (13,576/13,132/13,117) e il fit OLS a 4 punti riprodotti fino alla sesta cifra. Ha
  trovato **da solo lo stesso errore del divisore SIMD** (citando l'ISA RDNA2) e ha aggiunto
  quattro correzioni adottate: i 13,1 cicli sono cicli-unità sommati su 80 TA e **non** cicli di
  durata del pass (quello è 0,171 `GPUBusyCycles`/istruzione); R²=0,9996 dice che i bracci stanno
  su una retta, **non** che le texture causino la durata; un'ipotesi ALU-bound sopravvive a tutto
  O6 per due meccanismi concreti (ogni iterazione porta con sé un lavoro TA stabile; togliere
  iterazioni accorcia le wave); il risultato `TCP→TA` esclude *quella* back-pressure, non la
  latenza di memoria in generale. Conservato in `31_o6_lightcount/codex_audit_o5_o6.txt`.


**CONCLUSIONE DI FASE 2O.** `Render Color` è dominato dal **loop per-luce di `ShadeLights`**:
l'**88% dei cicli GPU del pass sta su una retta nel lavoro di quel loop** (R²=0,9996 su 4 bracci),
e alla baseline quel loop lascia **sia** la VALU del pixel shader (96,6%) **sia** il texture
addresser (93,6%) vicini alla saturazione. Quattro spiegazioni alternative eliminate **per misura**,
ciascuna nell'ambito dichiarato: filtraggio texture (O4, ≤3%), back-pressure `TCP→TA` (0,24%),
traffico di miss L0 (hit 97,66%), **saturazione** di banda DRAM (39,6 GB/s su 555–621). Resta
esclusa la saturazione di banda, **non** la latenza di memoria in generale: nessun counter la misura.
**Non stabilito:** quale delle due unità sature sia quella vincolante alla baseline — distano 3
punti e ogni braccio di O6 le muove insieme, quindi tutto O6 è compatibile con un pass ALU-bound
in cui ogni iterazione rimossa porta con sé 13,1 cicli di addresser. O4 è l'unico braccio della
fase che ne ha mossa una sola (texture, a ALU fissa) e vale il 3,5%. Servirebbe lo specchio di O4,
un braccio che muova solo l'ALU — idealmente un disegno fattoriale ALU × texture: non è stato
eseguito.
**Cosa significa per la domanda iniziale:** il costo localizzabile è il **numero di operazioni
texture e ALU che l'algoritmo di shading emette per pixel** (il kernel PCF a 10 tap di
`GetDirectionalShadow`, i fetch per-luce di `ShadeLights`). È una proprietà dell'applicazione,
**non** un'impostazione driver, un flag del compilatore, uno stato sampler o una configurazione di
cache. 2E–2K avevano già stabilito che nessuna leva di codegen è raggiungibile da fuori il driver;
2O aggiunge che su questo workload il costo raggiungibile non era in codegen fin dall'inizio.

### 2P — ottimizzatore del loop per-luce ✔ COMPLETA (`research/33..39`, 8 cicli)
- [x] **Replica clean-room di 2O** su macchina verificata inattiva (GPU 1,69%): counter di lavoro
  a **+0,00%** e **+0,01%**, bracci O4 e O6 dentro tolleranza di uno-due ordini di grandezza.
  **CLEAN_REPLICATION = PASS**: il carico di background non guidava nessuna conclusione di 2O.
- [x] Ipotesi dall'ISA reale (RGA gfx1030, root signature ricostruita): `(gloss+2)/8` è **già**
  sollevata dal compilatore; `pow(x,5)` di `FSchlick` **no** — esce come `v_log`+`v_mul`+`v_exp`.
- [x] **Quattro trasformazioni accettate**, tutte con immagine **bit-identica**: `fresnel5`
  (−3,17%), `shadowskip` (−5,48%), `falloffskip` (**−27,59%**), `scalar` (−3,84%, abilita il
  percorso `SCALAR_BRANCH` che il motore spediva disattivato).
- [x] **Migliore variante `stack3_scalar`: `Render Color` −41,60%** (cicli GPA) / **−40,34%**
  (timer del motore, strumento indipendente), **frame GPU −24,39%** (≈−21,7% al netto di un
  effetto di clock quantificato), **immagine byte-identica**. 68 righe di diff, un solo file HLSL.
- [x] **Il braccio mancante di 2O è stato fornito**: `fresnel5` muove l'ALU a texture fissa
  (−0,08%) e il pass segue del −3,17%; O4 muoveva la texture a ALU fissa e il pass seguiva del
  −2,6%. **Entrambe le unità sature sono sul percorso critico, nessuna domina.**
- [x] Correttezza: `ndotlskip` **rifiutata** dal criterio preregistrato; il criterio stesso era
  però irrealizzabile (1 ULP di R11G11B10 vale ~1,6% relativo) e viene sostituito **in avanti**,
  senza toccare il verdetto già emesso. Controllo nullo `base_pad` (bytecode diverso, stesso
  lavoro): **+0,01%**.
- [x] Generalità misurata: a un quarto delle luci il guadagno **scende a −20,19%** ma resta.
- [ ] Non separato: quanto del guadagno venga dall'occupancy invece che dal lavoro rimosso — due
  tentativi falliti (`LEVEL_WAVES` restituisce un valore impossibile identico su ogni build; il
  padding viene rimaterializzato dal compilatore). Argomento residuo: tre varianti nello stesso
  bucket VGPR vanno da −3% a −37%.
- [ ] Non dimostrato: equivalenza a piena precisione (l'oracolo è un target quantizzato) e
  generalità oltre questa scena. → `research/PHASE_2P_FINAL_REPORT.md`

### 2Q — equivalenza a piena precisione ✔ COMPLETA (`research/40..42`)
- [x] Cattura diagnostica in `R32G32B32A32_FLOAT` (env-gated, `ME_Q_R32`): determinismo float32
  verificato, poi ogni trasformazione giudicata da sola.
- [x] `SCALAR_BRANCH` **bit-identico in float32**; il resto entro **7 ULP** e **4,4e-7** relativo,
  **zero NaN/Inf/−0**.
- [x] `fresnel5` verificato **esaustivamente su tutti i 1 065 353 217 float32 del suo dominio**:
  mai oltre **3 ULP** dal valore vero (riferimento in doppia precisione) contro **8 388 608 ULP**
  di `pow(x,5)` — la trasformazione è **più accurata** di ciò che sostituisce.
- [x] Data contract **misurato** con una canary: mai scattata su nessuna luce di nessun pixel.
- [x] Replica finale a 7 processi: `Render Color` **−41,43%**; frame GPU **−24,47% misurato** /
  **−21,78% stima clock-corretta**, mai mescolati.
- [ ] Nessuna review indipendente (reviewer esaurito).

### 2R — generalizzazione su un secondo workload ✔ COMPLETA, esito negativo (`research/43..44`)
- [x] Criteri di scelta scritti prima; scelto `D3D12nBodyGravity` (n-body O(N²), compute, LDS).
- [x] Costruito, strumentato, gated; **A/A N95 0,05%**, oracolo esatto (stato particelle
  byte-identico su 5 processi).
- [x] Tre trasformazioni guidate dall'ISA: `unroll4` **già fatta dal compilatore**, `lds_float3`
  bit-identica ma **+1,28% più lenta**, `mass_hoist` **−3,58% ma rifiutata dalla correttezza**
  (somma mal condizionata, 164 301 ULP dopo **un solo passo**).
- [x] **Nessuna trasformazione accettata.** Risultato negativo ottenuto con lo stesso metodo.
- [ ] Bottleneck classificato con un modello, non con counter hardware.

### Review avversariale + congelamento ✔ (`research/POC_FROZEN.md`, `47..48`)
- [x] Review su quattro bersagli dichiarati: ULP/sweep **REGGE CON RISERVA**, canary **ROTTO**,
  conditioning **ROTTO nella formulazione**, occupancy **REGGE CON RISERVA**.
- [x] **Canary ricostruita** (Q4): la v1 scriveva il sentinella dentro il valore poi moltiplicato
  per zero, quindi era cieca proprio sui percorsi degli early-out. La v2 propaga una maschera
  impostata prima di ogni moltiplicazione: **0 pixel su 2 073 600**. Controllo positivo (Q5):
  **2 073 600 su 2 073 600** — il silenzio della v2 e' evidenza, non artefatto.
- [x] Buco di provenienza dello sweep chiuso; ogni campo riprodotto identico con host tracciato.
- [x] **Audit di provenienza:** 64 build, 422 run, 22 cicli, **zero discrepanze**.
- [x] **2P/2Q/2R congelate** come PoC validato, con i limiti dichiarati. Nessuna ulteriore
  ottimizzazione su ModelViewer.

### 2S — consolidamento infrastruttura
- [ ] Non avviata; assorbita nella prossima fase proposta.

### 2T — hit rate del metodo (proposta, una sola)
- [ ] 3–5 workload D3D12 open source dichiarati **prima** di guardarli, pipeline congelata e non
  modificata, e la domanda: **quante volte produce una trasformazione accettata?** Negativi
  compresi. E' l'unica cosa che trasforma "ha funzionato una volta e non due" in una proprieta'
  misurata del metodo.

**Prossima azione:** scrivere `research/PHASE_1_REPORT.md` — le 14 domande e la tabella ranked
delle superfici di ottimizzazione, che ora può essere compilata con evidenza invece che con
ipotesi. I percorsi strategici e il log seguenti sono storici.

## Report finale
- [ ] `research/PHASE_1_REPORT.md` — 14 domande + tabella ranked delle superfici di ottimizzazione

---

## Percorso a più alto valore (fare per primo)

1E harness → 1C forensics cache → 1D cold/warm → 1F RGP su Wukong.
L'obiettivo è la catena `shader hash → cache blob → ISA → costo GPU`.
Se si costruisce anche solo in parte, vale più di mesi di decompilazione del driver.
1B/1K servono a preparare il terreno, non a produrre risultati da soli.

## Log

- **2026-09-03 (1)** — Ricognizione: tool e percorsi verificati, GPU/driver/OS confermati, baseline
  cache censita (63/48/10 file). Scritti CLAUDE.md e PLAN.md. Wukong benchmark mancante.
- **2026-09-03 (3)** — Fase 1.5. Pipeline ETW costruita e validata (8 kHz, attribuzione per
  modulo e RVA senza simboli); catture Fortnite in attesa dell'operatore. Analisi statica mirata
  dell'UMD installato: due strade chiuse con evidenza (`GetSettingsBlobsAllDecoded` stub,
  `DXCTuningsFileName` lato KMD) e una aperta e molto più promettente (config del compilatore
  shader via env var/file, 272 `SCOption_*`, dump ISA per shader hash).
  Prodotto `research/PHASE_1_5_DECISION_GATE.md`. **Nessuna modifica a driver, cache, registro
  o ambiente.**
- **2026-09-03 (2)** — Fasi **1A + 1B + 1E** completate su 7 run Fortnite + 7 run Steel Nomad
  forniti dall'operatore. Parser validato contro PresentMon e 3DMark. Baseline noise stabilito
  (±0.11% / ±1.3%). Package driver mappato con evidenza (724 file). Scoperto che il package non
  è la revisione installata e che l'UMD DX12 contiene il compilatore shader.
  Prodotti `research/PHASE_1_STATUS.md`, `01_driver_map/component_analysis.md`,
  `04_benchmarks/analysis/{METHOD,fortnite_baseline,steelnomad_baseline,baseline_comparison}.md`.
  **Nessuna modifica a driver, cache, registry o sistema.**
- **2026-09-04 (8)** — Fase **2H**. Trovato che il "−30%" di 2G era misurato contro una baseline
  con `[unroll]` scritta da me: contro il **default di DXC** il guadagno è **zero**. Corretti due
  difetti di misura del banco (warm-up a iterazioni, duty cycle) che valevano fino a 5.2×; il set
  2G rimisurato dà −16.3% e fa cadere il terzo vincitore. Correttezza forte su 20 dataset ×
  3 workload con output completo: le varianti escono da 1e-4 su 7 dataset, ma **anche il default
  di DXC**, quindi è lo shader a essere mal condizionato. Causa determinata con tre controlli
  (nullo/negativo/positivo): è lo **scheduling delle load**, non occupancy né pressione registri;
  confidenza *strong*, contatori di stall non misurati (RGP leggibile solo da GUI). Corpus di
  20 shader: `[loop]` è un no-op, `[unroll]` migliora 9 volte e peggiora 3, peggior regressione
  **+40.7%**. Prodotti `15_robustness/PHASE_2H_RESULTS.md` e `PHASE_2I_DESIGN.md`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-04 (9)** — Fase **2I**. Prima risposta positiva del progetto: **9 varianti su 23
  battono il default reale di DXC/AMD**, tutte su 3/3 combinazioni di workload/dataset con
  10 processi ciascuna. La migliore, `bdiv__hoist_parity`, è **−69.5%** ed è **strict**
  (max rel 4e−7). Reso bloccante il self-check del banco: è fallito al primo giro e ha portato
  a sostituire il confronto fra mediane indipendenti (rumore 1.1–1.3%) con un **confronto
  appaiato a doppio riferimento** (SE 0.049%). La causa è stata isolata con 5 controlli e la
  mia ipotesi iniziale — parallelismo di memoria — è stata **falsificata**: è il numero di
  regioni divergenti (32 → 2). Su `pressure24` nessuna variante batte il default: 7 provate,
  0 accettate. Lo staging LDS coalescente è il peggior risultato della fase (fino a +109.8%).
  Prodotto `research/18_ai_search/best_variants.md`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-05 (10)** — Fase **2J**. Automatizzata la *proposta* delle trasformazioni: shader
  come IR, trasformazioni come funzioni IR→IR, predittore interpretabile su feature
  sorgente/DXIL/ISA. **Il guidato con 2 benchmark batte random con 8** (~4× meno tentativi), e
  con budget 5 trova l'ottimo esatto su 7 shader di validazione su 8. Ma il risultato che conta
  è un altro: **le regole scritte a mano da sole valgono 80.1% dell'oracolo contro il 77.7% di
  random** — tutto il vantaggio viene dall'evidenza misurata (96.9%). Le due regole dedotte
  ragionando invece che misurando sono esattamente quelle che hanno fatto danni. Il gate di
  correttezza ha respinto 10 varianti su 112, tutte per bug nelle mie trasformazioni, incluso
  un caso in cui `tg32/tg128` è semanticamente invalida. Prodotto
  `research/19_predictor/predictor_vs_random.md`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-05 (11)** — Fase **2K**. Il sistema esce dal corpus sintetico: 24 shader compute
  **reali** di DirectX-Graphics-Samples e FidelityFX-SDK, mai visti, eseguiti con un banco
  generico che sintetizza la root signature dai binding DXIL. **La memoria delle misure con 2
  benchmark equivale a random con 5** (~2.5×); a budget 1 trova −6.57% dove random in media
  peggiora (+1.59%). Trovati guadagni veri su codice Microsoft non modificato, tutti *strict*:
  `BitonicPreSortCS` −77.43%, `ParticleSpawnCS` −49.86%. Due risultati scomodi: (a) su HLSL
  arbitrario restano solo 3.6 trasformazioni meccanicamente sicure per shader contro ~11
  sull'IR, ed è questo a comprimere il vantaggio; (b) il corpus sintetico aveva insegnato che
  `wave64` è sempre peggiore — sui shader reali è la trasformazione più spesso accettata.
  Trovato e corretto un artefatto che la correttezza non poteva catturare (`numthreads` che
  cambia il lavoro senza cambiare il risultato). Prodotti
  `research/20_real/REAL_GENERALIZATION.md` e `PHASE_2L_DESIGN.md`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-05 (12)** — Fase **2L**. Catena end-to-end percorsa per intero: MiniEngine
  ModelViewer costruito da sorgente, strumentato, profilato (frame GPU 1.068 ms, spread portato
  da 18% a 1.13%), shader ottimizzati integrati e ricompilati, A/B misurato. **Il guadagno
  end-to-end è zero**: −0.27% e +0.35%, entrambi dentro il rumore, con il pass bersaglio
  peggiorato in entrambi i casi. Le cause sono state isolate e sono tutte concrete: (1) i
  microbench più grossi erano su shader che l'app **non esegue**; (2) le bocciature di
  correttezza di 2K erano **falsi negativi** — quegli shader sono non deterministici, lo stesso
  binario dà output diversi; (3) dove le trasformazioni sono state applicate a shader eseguiti,
  il −76% è diventato **+1.83%**, perché il microbench dispatcha 1M thread con dati finti e
  l'app usa DispatchIndirect data-dependent. Cade anche l'oracolo immagine: la build non
  modificata dà 2 hash su 6 run. Prodotto `research/21_workload/PHASE_2L_RESULTS.md`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-05 (13)** — Fase **2M**. Applicata la regola "profile first": inventario runtime
  dentro l'app (scope → PSO → hash bytecode → chiamate → dispatch reali), **40/40 shader
  eseguiti mappati al sorgente per hash**. Identificato senza ambiguità il vero collo di
  bottiglia: `Render Color` = **48.71%** del frame, pixel shader `ModelViewerPS`. Optimizer
  esteso ai pixel shader e A/B pulito: nessun guadagno (+0.61% / +0.36%). Ma la sonda di Amdahl
  dà il risultato che conta: **azzerare l'intero pixel shader cambia il pass dello +0.66%** —
  quel pass non è limitato dall'ALU dello shader, quindi nessuna trasformazione sorgente può
  aiutarlo. Trovati due difetti miei: build incrementale incoerente dopo il cambio di layout di
  `PSO` (access violation, serve `-t:Rebuild`) e **oracolo d'immagine rotto** — col PS forzato a
  nero il dump è byte-identico, quindi tutti i verdetti sull'immagine di 2L e 2M vanno scartati.
  Prodotto `research/22_runtime/PHASE_2M_RESULTS.md`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-05 (14)** — Fase **2N**. Enumerati i **145 counter hardware reali** della Navi 21 e
  integrato GPUPerfAPI dentro MiniEngine. Classificati i pass: **`Render Color` (48.7% del frame)
  è texture-unit throughput bound** — TexUnit 94.6% busy con 0.4% di stall, ROP e raster fermi,
  e appena 73 GB/s contro i 555–621 GB/s di altri pass dello stesso frame. `Resolve Image` è
  bandwidth bound, `Z PrePass` e `Render Shadow Map` raster bound, `Culling & Sorting`
  latency/serialization bound. Trovato inoltre un **bug grave nei miei strumenti**: MSBuild
  saltava in silenzio la ricompilazione quando il sorgente veniva scritto nello stesso secondo
  della build precedente, quindi si misurava due volte lo stesso binario. Questo **invalida
  l'evidenza** dell'ablazione di 2M e **fa ritrattare** la conclusione «oracolo d'immagine rotto».
  Rimedio in `tools/buildv.py`. Prodotto `research/23_bottleneck/PHASE_2N_RESULTS.md`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-05 (15) — AUDIT HANDOFF.** Ricostruita la storia e conservati inventory/hash/diff/tlog.
  Trovati gate build non fail-closed e runner non integrati, requisito GPA di workload identico
  non soddisfatto, interpretazione MRT/overdraw errata e scoring 2K contaminato dai rifiuti.
  La classificazione texture-throughput di 2N torna ipotesi da testare; root cause del tracking
  DXC ancora da diagnosticare. Stop al gate come da brief: **0/6 cicli, nessuna build o misura**.
  Piano 2O e criteri in `research/CODEX_HANDOFF_AUDIT.md`; log e session report prodotti.
  Nessuna modifica a sorgenti operativi, driver, cache, Registry, security o giochi;
  nessun file eliminato né applicazione personale chiusa.
- **2026-09-06 (16)** — **2O cicli O3 e O4.** O3: dose-risposta sui tre sample dei materiali,
  con la dose misurata (1,06 / 2,07 / 3,34 istruzioni texture per wave su 155,9) invece che
  assunta, e il confondente ALU quantificato (`mat3` toglie anche l'11,3% di VALU). Risultato:
  quei tre sample sono il **2,1% delle istruzioni texture ma il 13,9% dei cicli busy della
  texture unit**; gli altri ~153 fetch per wave sono luci e shadow map. Trovato un difetto di
  strumentazione — i counter SQ per-shader-engine tornano a volte **corrotti** su SE0/SE2, con
  il valore di un evento sotto il nome di un altro — e aggiunto il gate `tools/sq_validity.py`.
  O4: la stessa domanda senza il confondente, cambiando **solo il sampler statico in C++** con
  il bytecode del pixel shader byte-identico e l'ALU verificata invariata entro 0,07%.
  **Spegnere del tutto l'anisotropico, o scendere al filtro point, muove `Render Color` al
  massimo del ~3%**: l'ipotesi «texture-filter-throughput bound» ereditata da 2N è **falsificata**.
  Riportati come falliti anche il braccio bidirezionale (`s_aniso16` produce solo +0,71% di dose)
  e la tentazione di dedurre una partizione 25/75 fra filtraggio e resto (additività mai
  misurata). Codex, via herdr, ha ricalcolato dose e risposta da zero dai CSV grezzi
  confermandoli, e le sue tre obiezioni metodologiche sono state adottate nel report.
  Prodotti `research/28_o3_material_ablation/PHASE_2O_O3_RESULTS.md`,
  `research/29_o4_sampler/PHASE_2O_O4_RESULTS.md`, `tools/o4_analyse.py`, `tools/sq_validity.py`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-06 (17)** — **2O cicli O5 e O6: fase chiusa, 6/6.** O5 senza costruire nulla: riusati
  gli eseguibili di O4 e cambiati solo i counter, il che trasforma le varianti sampler in una leva
  di traffico di memoria a bytecode identico. Chiusa l'attribuzione di stage, e per chiuderla è
  servito un controllo: `SQ_VS*` legge zero, ma solo perché su RDNA2 il vertex shader gira sotto
  la maschera `GS` — sweep di tutte e 8 le maschere, **99,53% del lavoro texture è pixel**, lo
  0,47% è l'attribute fetch del primitive shader. Eliminate per misura tre spiegazioni: stallo
  della cache L0 sull'addresser **0,24%** (banda ≤10%), hit L0 **97,66%**, **39,6 GB/s** di DRAM
  contro i 555–621 disponibili — con un cross-check che vale più dei singoli numeri: L2 miss × 64 B
  = 31,90 MB contro 31,88 MB calcolati da counter diversi, **0,06% di scarto**.
  O6 ha messo alla prova il coefficiente che restava: variando **il numero di luci** (dato C++,
  bytecode byte-identico, 4 build gated sullo stesso hash) le istruzioni texture per wave scendono
  da 156 a 33 e **`TA_BUSY` le segue a 13,1 cicli ciascuna** — la predizione di O5 era 14,5, e
  l'88% dei cicli del pass scala col conteggio. **REPLICATO** su entrambe le bande preregistrate.
  Ma nella stessa stesura ho trovato un mio errore che *indebolisce* la conclusione: avevo diviso
  `INST_CYCLES_VALU` per 320 SIMD invece che per 160 (RDNA2 ha 2 SIMD32 per CU), quindi il duty
  VALU non è 48% ma **96,6%**. Alla baseline il pass è **co-saturo**, VALU 96,6% e texture
  addresser 93,6%: O6 non può classificare l'una sopra l'altra, e l'unico braccio che ne ha mossa
  una sola resta O4 (texture a ALU fissa, 3,5%). Corretti di conseguenza il report O6 e la sezione
  «cosa resta in piedi» di O5. Conclusione di fase: il costo sta nel **loop per-luce di
  `ShadeLights`** — una proprietà dell'applicazione, non del driver, del compilatore, del sampler
  o della cache. Prodotti `research/30_o5_memory/PHASE_2O_O5_RESULTS.md`,
  `research/31_o6_lightcount/PHASE_2O_O6_RESULTS.md`, `tools/run_o5.py`, `tools/run_o6.py`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-06 (18)** — **Fase 2P, 8 cicli, primo guadagno end-to-end reale del progetto.** Prima
  replicata la 2O a macchina verificata inattiva (counter di lavoro a +0,00%/+0,01%): il carico di
  background non guidava nulla. Poi attaccato il loop per-luce di `ShadeLights` con trasformazioni
  semanticamente equivalenti, ipotizzate leggendo l'**ISA reale** e non il sorgente: il compilatore
  solleva già `(gloss+2)/8` ma **non** riduce `pow(x,5)`, che esce come log+mul+exp. Quattro
  trasformazioni accettate con **immagine bit-identica**; la migliore, `stack3_scalar`, vale
  **−41,60% di `Render Color`** (confermato al −40,34% da uno strumento indipendente) e
  **−24,39% di frame GPU**, in 68 righe di diff su un solo file HLSL. Fornito anche il braccio che
  mancava a 2O — ALU mossa a texture fissa — che chiude la domanda: **entrambe le unità sature
  sono sul percorso critico, nessuna domina**. Un criterio di correttezza preregistrato si è
  rivelato irrealizzabile e **è stato sostituito in avanti** senza toccare il verdetto già emesso;
  due controlli sull'occupancy sono falliti e sono riportati come tali; la review del candidato
  finale non è stata ottenuta perché il reviewer ha esaurito il limite d'uso. Prodotti
  `research/PHASE_2P_FINAL_REPORT.md`, `PHASE_2P_WORKLOG.md`, `PHASE_2P_MEASUREMENT_MEMORY.csv`,
  `tools/run_2p.py`, `tools/isa_2p.py`, `tools/run_clean.py`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-07 (19)** — **Sessione notturna autonoma: fasi 2Q e 2R, 5 cicli su 12.** 2Q chiude il
  dubbio lasciato da 2P: catturando in `R32G32B32A32_FLOAT`, `SCALAR_BRANCH` è **bit-identico anche
  in float32** e il resto dello stack differisce al massimo di **7 ULP** e 4,4e-7 relativo, senza
  NaN/Inf/−0; `fresnel5` è stato verificato **esaustivamente su tutti i 1 065 353 217 valori del suo
  dominio** e risulta **più accurato** di `pow(x,5)` (3 ULP contro 8 388 608 dal valore vero); il
  data contract degli early-out è stato **misurato** con una canary che non è mai scattata. Replica
  finale a 7 processi: `Render Color` **−41,43%**, frame GPU **−24,47% misurato** / −21,78%
  clock-corretto. 2R porta lo stesso metodo su `D3D12nBodyGravity` (n-body O(N²), compute, LDS):
  baseline con A/A N95 **0,05%** e oracolo esatto, tre trasformazioni provate, **nessuna accettata**
  — una era già fatta dal compilatore, una bit-identica ma più lenta, e `mass_hoist` (−3,58%,
  algebricamente esatta) è stata **rifiutata dalla correttezza** perché la somma delle forze ha
  condizionamento ~1e5. Il gate ha fermato cinque difetti prima che producessero numeri, fra cui
  **due preregistrazioni compilate col DXC sbagliato**. Nessuna review indipendente: il reviewer
  aveva esaurito il limite d'uso. Prodotti `research/OVERNIGHT_FINAL_REPORT.md`,
  `OVERNIGHT_SESSION_LOG.md`, `PHASE_2R_MEASUREMENT_MEMORY.csv`, `tools/fp32_sweep/`,
  `tools/nb_probe.h`, `tools/run_2r.py`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-07 (20)** — **Review avversariale di 2Q/2R e congelamento del PoC.** Il reviewer ha
  **rotto la canary del data contract**: scriveva il sentinella dentro il valore poi moltiplicato
  per zero, quindi era cieca esattamente sui percorsi che gli early-out saltano. Ricostruita out
  of band con una maschera propagata e impostata prima di ogni moltiplicazione (**0 pixel su
  2 073 600**) e dotata del **controllo positivo** che alla v1 mancava (**2 073 600 su 2 073 600**),
  cosi' che il silenzio sia evidenza. Corretta anche la quantificazione del conditioning in 2R
  (amplificazione ~20 epsilon mediana, non κ≈1e5) e chiuso il buco di provenienza dello sweep.
  Audit completo: **64 build, 422 run, 22 cicli, zero discrepanze**. **2P/2Q/2R congelate** come
  proof of concept validato con i limiti dichiarati; nessuna ulteriore ottimizzazione.
  Prodotto `research/POC_FROZEN.md`. Prossima fase proposta, una sola: **2T, misurare l'hit rate
  del metodo** su 3–5 workload D3D12 dichiarati prima di guardarli.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-07 (21)** — **Fase 2T chiusa: misurato l'hit rate del metodo, 7 cicli su 10.** La
  pipeline congelata, senza modificarla, su 4 workload D3D12 scelti per nome prima di aprirne una
  riga: **0 hit su 4**, **5 trasformazioni costruite e misurate, nessuna accettata**. W1
  `D3D12ExecuteIndirect` e W3 `D3D12MeshShaders` chiusi **prima di ogni ipotesi** e a ragione — un
  dispatch di 5,76 us (0,03% del picco aritmetico) e un draw di **480 ns**, 48 tick del contatore,
  non si migliorano cambiando uno shader; W1 non ha nemmeno un oracolo, il back buffer cambia a
  ogni run perche' l'animazione legge il wall clock. W2 `D3D12Multithreading`: 3 ipotesi dall'ISA,
  tutte sotto soglia (−0,99% / −0,22% / −1,22% contro 2,88%). **W4 `D3D12VariableRateShading` e' il
  miss che informa**: baseline con oracolo byte-identico su 14 processi in due sessioni, A/A N95
  0,44%, e una **sonda di Amdahl che dà −16,59%** — a differenza di 2M il tetto c'è. La pipeline
  non ne ha preso niente. `gather_pcf`, dedotta dall'ISA di W4 (4 dei 6 `image_sample` sono i tap
  PCF 2x2 e il sampler è POINT, quindi un `gather4` li rende tutti), ha fatto esattamente quello
  che prometteva — 6 `image_sample` → 2 + 1 `image_gather4_lz` — e **dimezzare le istruzioni
  texture vale lo 0,5% del pass**: qualunque cosa sia quel 16,6%, non è throughput di texture. È
  stata **rifiutata dalla correttezza**, e non per rumore di arrotondamento: l'offset di mezzo
  texel cade su un texel diverso su 43 pixel di 921 600, con delta fino a 41. `zeroskip_shadow` è
  l'unica del progetto oltre a 2P a tornare **byte-identica** — l'argomento `0 * finito == 0`
  regge — e vale **+0,13%**, cioè niente: con una sola luce puntiforme quasi nessuna wave è
  interamente non illuminata. La sua provenienza è **dichiarata**: il pattern viene da 2P, non
  dall'ISA di W4, ed è contato a parte proprio perché un hit non andasse accreditato alla pipeline
  ISA-only. **Il gate ha fermato due difetti prima che producessero numeri**: gli header in `aux`
  non venivano mai salvati né ripristinati (workspace sporco dopo una build che tocca
  `Common.hlsli`, preso dall'hash preregistrato di `Glass_PSMain`), e l'analizzatore accoppiava le
  run per numero di rep — con la base scivolata dell'1,2% fra le due sessioni avrebbe scorato
  `gather_pcf` a ~−1,5% e **fabbricato un'accettazione**. Entrambi corretti alla radice e W1–W3
  rianalizzati (verdetti invariati). **Lettura onesta: contando 2P e 2R il metodo sta a 1 hit su 6
  workload, e il −41% di 2P somiglia più a un outlier che a un tasso.** Prodotti
  `research/PHASE_2T_RESULTS.md`, `research/52_2t_w4/verdict.json`, `tools/run_2t.py`
  (azione `preregister`, `source_rels()`, pairing temporale).
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-07 (22)** — **Fase 2U chiusa, 12 cicli: hit rate 0 su 4, e ora sappiamo perche'.**
  Tre modifiche preregistrate alla pipeline, tutte hanno fatto il loro lavoro, nessuna ha prodotto
  un hit. **(1) Ceiling gate**: si misura il tetto ablando il corpo dello shader *prima* di ogni
  ipotesi, e sotto il 3% il workload si chiude senza spendere tentativi. Ha chiuso **U-A
  `D3D12DynamicIndexing` (ceiling −0,38%)** e **U-C `D3D12HDR` (+0,22%)** in un ciclo ciascuno:
  cancellare l'intero pixel shader non sposta niente, sono limitati da draw call e da fetch, non
  dallo shading. Restano nel denominatore. **(2) Decomposizione del ceiling**: su W4 il 72% del
  tetto e' il termine ombra e solo il 14% di quello sono i tap texture — il che spiega a
  posteriori perche' `gather_pcf` di 2T valeva 0,5%; su U-B `D3D12Raytracing/ProceduralGeometry`
  (**tetto −79%**) sono **raggi ombra −43,5% e raggi riflessi −26,9%, mentre il Phong e' l'1%**,
  quindi qualunque trasformazione ALU era inutile *prima* di costruirla. **(3) Regola di
  correttezza a due livelli**: non e' servita, perche' **due candidati su tre sono tornati
  byte-identici**. **Il quasi-successo del progetto**: `shadow_tmax` limita il TMax del raggio
  ombra alla distanza della luce — **immagine byte-identica**, −2,18%, replicato a 2000
  frame/processo a **−1,81% con separazione completa** (ogni processo variante piu' veloce di ogni
  processo base) — e la soglia preregistrata (4,02%, 2,76% nella replica) **lo rifiuta**. La
  replica e' stata fatta *perche'* era un quasi-successo, e' dichiarato, e **non l'ha salvato**.
  Due credenze standard misurate false: sollevare il lavoro uniforme al vertex stage costa
  **+4,31%** su W4 (attribuito per regione, con il pass depth-only a **+7,24%** e il postprocess
  fermo a +0,14% come controllo negativo, previsione **sbagliata nel segno**), e il PERFORMANCE TIP
  di Microsoft sul non portare valori attraverso `TraceRay` vale **−0,09%**. Costruita la
  **memoria delle misure** (`MEASUREMENT_MEMORY.csv`, 39 righe, solo da artefatti): il −41,6% di 2P
  su MiniEngine contro **−2,18% come miglior risultato di tutto il resto** — quel regime e' un
  outlier, non un tasso. **Sei difetti fermati dal gate** prima di produrre numeri, fra cui
  l'accoppiamento per numero di rep che avrebbe **fabbricato un'accettazione**. Preparata la
  milestone Cyberpunk: `tools/capture_game.py` **validato su processo DX12 vivo** (11 030 frame,
  exit 0), `pmparse.py` esteso ai tre schemi CSV con **le 14 baseline esistenti identiche** dopo
  la modifica, procedura operativa scritta. **Superposition scaricato, firma UNIGINE verificata,
  installato in silent su E: con uninstaller** — ma e' DX11/OpenGL/Vulkan, non DX12: vale come
  controllo di stato macchina, non come workload. Prodotti `research/PHASE_2U_RESULTS.md`,
  `PHASE_2U_PREREGISTRATION.md`, `PHASE_2U_W4_CEILING.md`, `C2077_OPERATOR_PROCEDURE.md`,
  `MEASUREMENT_MEMORY.csv`, tre `verdict.json`, `tools/isa_2u.py`, `tools/memory.py`,
  `tools/capture_game.py`.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-08 (23) — Cyberpunk fullscreen scaling, rianalisi v2 completata.**
  Rigenerate `native_analysis_v2` per fs1440_r1/fs1080_r1/fs720_r1/fs1440_r2:
  **112,368 / 163,965 / 185,826 / 111,905 FPS**, deriva delle ancore −0,411%.
  Corrette durata N-intervalli e diagnostica allineamento in `tools/c2077_native.py`;
  il localizzatore proposto dalla sola durata QPC è stato smentito, non adottato.
  Il 720p mantiene uno scarto di un frame fra blocchi: finestra globale 6415–18356,
  incertezza +/-1 esplicita e sensibilità verificata, non identità esatta dei frame.
  GPUBusy/CPUBusy/GPUWait 720p = **4,172 / 5,230 / 1,107 ms**: GPU dominante a 1440p
  (strong), limite non-GPU/CPU-submission a 720p (probable); CPU vs driver non isolati.
  Nessun tetto rigido a 186 FPS né speedup shader dimostrato. Test sintetici/reali PASS,
  33 hash storici invariati. Check riproducibile: `tools/c2077_scaling_check.py`.
  Report: `research/62_c2077_fullscreen_scaling/VERDICT_V2.md`; dati in
  `scaling_analysis_v2.json` nella stessa directory. Nessuna nuova cattura necessaria
  per questo verdetto; WPR separato serve solo per attribuire gioco vs driver/sync.
  **Nessuna modifica a driver, cache, registry o giochi.**
- **2026-09-08 (24) — WPR CPU+GPU Cyberpunk: harness corretto, acquisizione benchmark in attesa del click.**
  `capture_etw.ps1` ora preserva il sampling di default, usa QPC in ms, verifica exit/timeout,
  non ferma sessioni altrui e salva l'ETL incompleto invece di cancellarlo. Test puro e smoke
  reale PASS: zero eventi/buffer persi, stack CPU e code DxgKrnl presenti, sampling 1 ms.
  Cyberpunk avviato normalmente, settings salvati 1440p fullscreen invariati; nessuna cattura
  benchmark ancora effettuata, nessuna attribuzione conclusa. Serve solo preparare il menu
  e il click manuale di avvio benchmark; il resto resta autonomo. Stato e prossimo comando
  dell'agente in `research/63_c2077_wpr_attribution/STATUS.md`. Nessuna modifica al gioco.

- **2026-09-26 (25) — Presa in carico da Claude e handoff portabile.**
  Creato `HANDOFF.md` nella root con obiettivo, cronologia, risultati, limiti, fonti e prossime azioni.
  Claude non disponibile per istruzione dell'utente; nessun nuovo avvio del relativo harness.
  Trovata la cattura WPR reale delle 22:28 dell'8 settembre, successiva al vecchio STATUS:
  ETL 21.098.397.696 byte, PresentMon exit 0, sampling 1 ms. Recupero offline completato:
  5304 frame nativi allineati strettamente alle righe 7745–13048, 64,2440852 s / 82,56013 FPS;
  Hardware Independent Flip su tutta la finestra. Tracestats e check_loss PASS, perdite 0/0.
  Salvate copie normalizzate e native_analysis_v2 senza alterare i raw; hash verificati.
  Tre selfcheck PASS; verificati i 21 link relativi dell'handoff. STATUS aggiornato.
  Resta attribuzione CPU/driver/GPU e valutazione della perturbazione, non un nuovo benchmark
  preventivo. Nessuna nuova cattura o modifica a gioco, driver, cache, Registry o sicurezza.

- **2026-10-16 (26) — Analisi offline WPR esistente, nei limiti delle evidenze validate.**
  Nessun nuovo benchmark. Reader OpenTrace/TDH raw-QPC e parser specifici ai layout verificati;
  439.214.592 eventi letti, proprietà decodificate senza errori. Clock ETL validato contro
  1276 SampleProf, 51340 CSwitch, 26314 ReadyThread e 10 eventi DXGI indipendenti, zero discrepanze.
  Tutti i 5304 frame abbinati a una sequenza contigua di Present stop: finestra ETL
  [49,9097700, 114,1538552) s. Timestamp online/WPR non bit-identici (residui 0,2–12,9 µs),
  nessun fitting dell'offset. CPU gioco: 444920 campioni; 48,80% eseguibile, 28,40% ntoskrnl,
  8,44% ntdll, 7,87% amdxc64, 1,23% D3D12Core. Running di 34 thread concorde con xperf entro
  0,5 µs; percorsi effettivi WaitForSingleObjectEx/ReleaseSemaphore, senza dichiararli eliminabili.
  Mappati device/context/proprietario/node; replay FIFO DMA target 75,7717% della finestra,
  93450 start e 2714 segmenti preempted, zero timeout. Non è occupancy hardware o costo shader.
  Layout distinti validati: 178 DMA, 244 scalar WAIT=4, 245 array SIGNAL=5; 52876 Unwait associati.
  Conservati ma respinti i tentativi con enum invertito/puntatore riusato e il filtro stack
  Profile ambiguo. Caller sampled CPU ancora non validati, anche dopo diagnostica sullo smoke
  storico senza filtro PID; critical path completo non dimostrato. Nella finestra campionati
  13,964 CPU-s in simboli Etw*/Etwp* e 27,277 CPU-s in due helper StackWalks: tracing rilevante,
  ma quota causale del calo rispetto alle passive non isolata. Nessun tuning driver giustificato,
  nessuna provenienza shader/PSO e nessuno speedup dimostrato. Test nuovi/esistenti, confronti
  nativi e hash input PASS; ETL SHA-256 e2e4ae42ccb8bb1e41d8717513abe1bb469d6e4969ef1b8e363f229a5b21e739.
  Report `research/63_c2077_wpr_attribution/OFFLINE_ATTRIBUTION_20261016.md`; artefatti/comandi
  in `fs1440_r1/offline_20261016/`. Aggiornati HANDOFF e STATUS. Prossima decisione: colmare
  caller sampled/perturbazione o provenienza shader con un percorso motivato; nessuna nuova
  cattura automatica e nessuna modifica a gioco, driver, cache, Registry, boot o sicurezza.

- **2026-10-16 (27) — Avviato percorso concreto di esperimenti shader Cyberpunk.**
  Lorenzo chiede di passare a modifiche motivate/reversibili, non altra analisi generale.
  Hash prima della copia dei contenitori shader installati: identici all'inventario di settembre;
  analisi esclusivamente su copie in `research/64_c2077_shader_access_20261016/copies/`.
  Probe con selfcheck individua 19950 contenitori DXBC/DXIL strutturalmente leggibili: 19037 nel
  contenitore principale, 913 nello statico. Occorrenze per stage: 5238 pixel, 13983 vertex,
  661 compute, 68 library; non tutti unici o dimostrati attivi nel benchmark. Estratto un payload
  per stage con hash/offset; un pixel e un compute disassemblati dal DXC installato, exit 0,
  stderr vuoto. IR reale ora disponibile, ma nessuna variante ancora applicata o ottimizzata.
  Prossimo esperimento: round-trip/validazione offline e percorso applicativo di reinserimento
  realmente supportato e reversibile, quindi canary identificabile e oracle; niente patch del
  driver firmato o sostituzione speculativa delle cache. Misure runtime solo alla riapertura
  della fase test. Stato: `research/64_c2077_shader_access_20261016/STATUS.md`; aggiornato HANDOFF.
  Nessun nuovo benchmark, nessuna modifica a file installati del gioco, driver o cache AMD.

- **2026-10-16 (28) — Round-trip reale e prima canary DXIL, PASS_OFFLINE.**
  Utility SDK `tools/dxil_roundtrip.cpp`: assembler e validatore esterno Microsoft, hash/firme
  delle DLL SDK verificati, niente -Vd. Pixel/compute/glass ricostruiti: IR intero identico
  (solo normalizzazione newline) e parti SFI0/ISG1/OSG1/PSV0 identiche; payload non bit-identici.
  Rimossa la reflection STAT aggiunta dall'assembler con ContainerBuilder, poi validazione
  esterna e seconda validazione dei file risultanti. Selezione glass con GUID 15973390170752892218
  collegata alla stringa di compilazione renderstage_transparent/MeshStatic/PassIndex 0.
  Preregistrazione C2077-DXIL-CANARY-001: solo quattro output RGBA del target 0 sostituiti con
  (1,0,1,1); discard/target 1 e resto del modulo invariati. Canary compilata e validata,
  SHA-256 9da6f87440e40e8d42a4f6bc2afba073a6675d0ddffec91805426142a4e085db.
  Tre negativi PASS: sintassi errata, opcode 999 respinto dal validatore esterno (0x80aa0009),
  overwrite negato/hash invariato. 21 subprocess registrati. Parser RDHS v10 verificato su
  19037 shader e 19647 compilation records; etichette stage upstream corrette con slot A/B
  neutrali dopo riscontro con i token DXIL. Repacking no-op byte-identico, controllo/canary
  ripacchettati soltanto in research con 19036 altri payload e metadata invariati.
  Cache installate ancora originali; copie non dichiarate accettate dal gioco o pronte da installare.
  Nessuna via REDmod documentata per questo DXIL arbitrario trovata; possibile loader DX12
  ReShade/RenoDX da revisionare e autorizzare specificamente prima di installare/hookare solo
  Cyberpunk. Non sostituire cache installate o driver e non usare nei giochi anti-cheat.
  Stato `research/65_c2077_dxil_roundtrip_20261016/STATUS.md`; preregistrazione e r1/result.json.
  Aggiornati HANDOFF e fase 64. Nessun gioco/benchmark avviato, nessuno speedup affermato.

- **2026-10-16 (29) — Loader Cyberpunk autorizzato, installato CONTROL; runtime pending.**
  Autorizzazione specifica utente per loader/hooking solo Cyberpunk e download necessari.
  ReShade ufficiale 6.8.0 Full Add-on x64: setup scaricato non eseguito, estratta sola DLL x64;
  SDK API 20/commit 18deaa52de0c425a78b329e9cb3c497281cd00ec. OptiScaler non necessario.
  Add-on locale con guard percorso e SHA EXE, confronto bytecode pixel per tutti i byte:
  osserva init_pipeline anche per library, crea clone PSO con stesso layout e redirige bind
  senza mutare PSO originali, cache o DLL preesistenti. Payload fase 65 incorporati invariati.
  Disabilitati effetti, addon depth/sync e shortcut overlay. Nessun cambio HDR/FG/risoluzione.
  PASS selftest C++ descrittori/selezione/negativi/host errato e Python install/mode/rollback/
  collisioni/file cambiato/file utente sconosciuto. Ripristino r0 sul target reale PASS:
  84 file originali, 527653806 byte, stesso insieme nomi/hash; directory propria rimossa.
  Reinstallato pacchetto identico in control: cinque soli file nuovi, manifest/archivio presenti.
  EXE/cache engine agli hash originali. ReShade host NotSigned, setup catena localmente non
  attendibile: limite esplicito, nessuna importazione certificati o modifica protezioni.
  Driver letto attualmente 32.0.21045.11001, diverso dal 32.0.21045.5002 storico; niente pooling.
  Nessun avvio gioco/benchmark/cattura: attesa partita manuale, poi verificare PSO clone/bind
  e immagine normale prima di canary. Bind non prova shader eseguito/frammenti visibili;
  nessun costo o speedup dimostrato. Stato/preregistrazione/manifest in
  `research/66_c2077_shader_loader_20261016/`; aggiornato HANDOFF.

- **2026-10-16 (30) — Control runtime: PSO accettate e bind target osservati.**
  Avvio manuale utente, PID 5396; add-on guard EXE passato. Snapshot live preservati in
  fase 66 `runtime_control_r1/`: 5316 init DX12, 5 match esatti, 5 cloni PSO control,
  zero errori di clonazione e 406 bind target. Prima lettura ancora a 4 cloni/0 bind;
  aggiornamento successivo positivo, non classificato come bug. Un ciclo D3D11 transiente
  termina prima del reload D3D12 attivo; log separati. Un WARN IDXGIFactory2 reference count
  (4) nel log host conservato, nessun ERROR nel campione. Confermati caricamento/creazione/
  bind, non draw/completamento GPU/frammenti visibili/correttezza immagine o costo.
  Richiesta conferma immagine normale e chiusura utente prima di canary a nuovo avvio manuale.
  Nessun benchmark/cattura automatica, nessuna modifica al pacchetto o mode control.

- **2026-10-16 (31) — Control qualitativo accettato, canary armata.**
  Utente conferma «chiuso, immagine normale»; processo Cyberpunk verificato assente.
  Copie finali log/config propri in `runtime_control_r1/closed/`: ultimo heartbeat 5360 init,
  5 match/cloni, zero errori di clonazione, 1044 bind. Mancante unloaded finale del ciclo
  D3D12; host termina Finished exiting ma segnala reference count swapchain e add-on ancora
  caricati in uscita. WARN conservati, causa/lifecycle completo/exit code non dimostrati.
  Controllo visivo operatore qualitativo, non confronto pixel quantitativo o prova GPU.
  Verificati hash immutabili e EXE, impostato solo mode.txt=canary tramite CLI a gioco chiuso;
  nessun nuovo build o sostituzione di DLL/cache. Manifest deployment aggiornato; pacchetto
  congelato invariato. Evidenza `canary_r1/preparation.json`; attesa avvio manuale stessa scena,
  nuovo PID/log canary e marker magenta. Nessun gioco/benchmark avviato automaticamente,
  nessuno speedup. Aggiornati STATUS/HANDOFF.

- **2026-10-16 (32) — Canary runtime accettata e bind target confermati, marker pending.**
  Nuovo avvio manuale utente, PID 14612; log mode=canary distinti dal control 5396.
  Snapshot live `canary_r1/live_snapshot_1/`: 5239 init DX12, 5 match/cloni PSO, zero errori
  di clonazione, 544 bind target, guard EXE e first_target_bind presenti. DLL immutabili
  agli hash congelati. Nessun ERROR nel campione host, un WARN IDXGIFactory2 reference count
  allo startup conservato. Non prova draw, frammenti visibili, completamento GPU o speedup.
  Richiesto all'operatore se vede superfici rosa-fucsia; nessuna risposta visiva ancora.
  Pacchetto/mode invariati a processo attivo, nessun benchmark/cattura automatica.
  Aggiornati STATUS/HANDOFF, evidenza in `canary_r1/RESULT.md`.

- **2026-10-16 (33) — Canary visivamente negativa; osservatore mirato installato.**
  Utente: nessuna superficie rosa, immagine invariata. Gate visivo non superato; PID 14612
  poi chiuso, ultimo heartbeat 5 PSO/2033 bind/zero errori di clonazione. Raw negativi e log
  finali preservati. Distinti HASH shader/digest/DXIL; quattro output magenta corretti;
  tutti i payload interi nel binario installato. SDK factory/bind sorgenti revisionati:
  fatti statici non equivalgono a esecuzione GPU/marker, causa ancora ignota.
  Preregistrata fase 67 C2077-SHADER-PROBE-001: un add-on separato solo osservativo per
  RT count/formats/write masks/blend/depth e contatori CPU draw/indirect/bundle/submission.
  Nessuna API GPU di modifica/creazione/query, draw callback sempre false. PASS selftest C++
  stato/reset/rebind/device key/bundle/submission/empty/masks/zero RT/host errato; PASS Python
  rollback log probe, preservazione sconosciuti e ordinamento cronologico dei log (non PID).
  Nuovo observer aggiunto atomicamente a processo assente e al manifest di proprietà;
  host/ShaderLab/bytecode/mode canary invariati. Rimozione estesa ai soli log probe riconosciuti.
  Driver attuale WMI ancora 32.0.21045.11001. Nessun avvio/benchmark automatico, nessun fix o
  speedup dichiarato; mancante loop GPU/immagine unattended. Attesa partita manuale stessa
  scena per nuovi log probe. Stato `research/67_c2077_canary_probe_20261016/STATUS.md`.

- **2026-10-16 (34) — Probe r1 attiva, quattro PSO note ma target non bindato nei comandi osservati.**
  Avvio manuale PID 11348. Sonda riceve eventi draw/queue globali, ma target binds/draw/
  submission ancora zero; quattro PSO create hanno RT0 presente, RGB mask 0xF, src RGB one,
  op add, dst source1_color. Quest'ultimo è dual-source blending: SV_Target1 non equivale
  necessariamente a un secondo RT indipendente. Non ricostruita la quinta PSO bindata nelle
  sessioni precedenti e non esclusi discard/occlusione/compositing. Snapshot/enum verificati
  in fase 67 `r1/`. Richiesto solo breve giro visuale non in pausa nella stessa sessione,
  nessun riavvio o benchmark, per osservare un bind target. Causa originaria ancora ignota;
  nessuna modifica live e nessuna inferenza di assenza GPU basata sui soli counter CPU.

- **2026-10-17 (35) — Giro concluso senza uso target osservato; catalogo backbuffer installato.**
  Utente «fatto», ancora zero bind/draw target nei comandi della sessione 11348, poi chiusa.
  Log finali preservati; non chiedere altri giri per lo stesso vetro. Causa del vecchio marker
  assente non stabilita, precedenti bind non ritirati. ShaderLab passato a observe a processo
  assente; nessuna sostituzione shader attiva. Nuovo C2077-BACKBUFFER-PROBE-001 readonly:
  identità risorse swapchain/RTV0, shader SHA256, draw diretti/indexed/indirect e submission.
  Vecchio observer verificato, archiviato/rimosso; nuovo file nel manifest, host/ShaderLab
  invariati. Nessuna API GPU mutante o timing, compute/UAV/copie/bundle restano limiti.
  PASS selftest C++ risorsa/device/resize/reset/rebind/empty/submission/SHA/host e Python
  log propri/sconosciuti/rollback. Indice offline 8340 SHA unici/19950 occorrenze preparato.
  Attesa normale avvio manuale stessa scena, poi scegliere candidato realmente osservato;
  nessun nuovo shader/canary, benchmark o avvio automatico. Stato fase 68, HANDOFF aggiornato.
