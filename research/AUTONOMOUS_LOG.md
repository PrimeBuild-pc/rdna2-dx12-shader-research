# Autonomous log — audit handoff 2026-09-05

Session ID: `HANDOFF-20260905`. Fonte autorevole: [CODEX_HANDOFF_AUDIT.md](CODEX_HANDOFF_AUDIT.md).

## Entry AUDIT-00 — gate iniziale, non ciclo GPU

- **Obiettivo:** ricostruire storia e stato reale prima di qualunque modifica operativa; verificare se sussistono le condizioni per proseguire automaticamente in 2O.
- **Attività:** letture di report/dati/sorgenti, inventario filesystem, versioni live, SHA-256, diff Git locale, decodifica tlog esistenti, confronto offline header ↔ inventario storico. Nessun build/benchmark o modifica a sorgenti/strumenti.
- **Metadata:** RX 6950 XT, Ryzen 5800X3D, Windows 11 26200, driver installato 32.0.21045.5002; package locale 32.0.21045.9003 distinto. DXS HEAD `213dd4fd4918ea009dd8f35adee1aff1f2ecaba4`, FFX HEAD `60f4ea81909200d8542eca14dccb2628b763a9a3`. Configurazione attesa MiniEngine Profile/x64/v145, Sponza 1920×1080 secondo dati storici; non avviata per riconfermarla.
- **Verifiche positive:** 40/40 associazioni scope/stage/hash del CSV storico corrispondono agli header attuali; ModelViewerPS 12.612 byte, custom hash `52CE6C5E64AB2E82`. Shader PS/Lighting attuali uguali a upstream. DXS con 10 file tracked modificati; FidelityFX pulito.
- **Discrepanze bloccanti:** buildv non fail-closed (exit code/header assente), caller legacy non integrati, catena di propagazione runtime non provata; GPA multipass senza identità di workload garantita.
- **Invalidazioni interpretative:** 2× export MRT non è 2× overdraw; TexUnitBusy non esclude ALU/cache/latency né prova throughput di filtraggio saturo. Classificazione 2N sospesa, non falsificata sperimentalmente.
- **Altra discrepanza:** scoring best/oracle 2K include varianti scartate per correttezza, quindi 2.5× richiede ricalcolo. Nessun dataset storico sovrascritto.
- **Controllo del log GPA:** warning command list nel log conservato precedono BeginSession; non sono usati come prova di invalidità dei sample Render Color. Il suffisso one_rt del file non prova una variante runtime.
- **Delta GPU / counter nuovi / qualità immagine:** N/A. Non prodotti; nessun risultato di performance inventato.
- **Verdetto:** **STOP_CRITICAL_HANDOFF_DISCREPANCY / BUILD_PIPELINE_UNVALIDATED**. Si applica la condizione di arresto del brief prima dei cicli autonomi. Non si procede a riparazioni o ablation run in questa sessione.
- **Budget:** 0/6 cicli sperimentali; 0 workload GPU; nessun consumo sperimentale >10 GB. Solo piccoli output documentali/manifest.
- **Preservazione:** nessun delete/Clean, driver/cache/Registry/security invariati, nessun gioco aperto, nessuna applicazione personale chiusa. Nessun tool/dipendenza installato. `PLAN.md` aggiornato con errata corrente senza cancellare la storia.
- **Artefatti:** `research/handoff_audit_20260905/`, `research/CODEX_HANDOFF_AUDIT.md`, `research/AUTONOMOUS_SESSION_REPORT.md`.
- **Piano sospeso:** 8 passi / massimo 6 cicli in §7 dell'audit: gate → O1 build-canary → O2 null/replay → O3 materiali → O4 ombre → O5 filtro → O6 replica → chiusura. 2P non iniziata.

Nessuna entry O1–O6: non sono state eseguite. Riprendere con nuovi ID e appendere risultati/fallimenti senza sovrascrivere questa entry.

---

# Autonomous log — ripresa 2026-09-06

Session ID: `RESUME-20260906`. Continua da `HANDOFF-20260905` senza sovrascriverla.
Fonte autorevole invariata: [CODEX_HANDOFF_AUDIT.md](CODEX_HANDOFF_AUDIT.md), §7.

## Entry GATE-01 — passo 1 (gate fail-closed), non ciclo GPU

- **Obiettivo:** eseguire il passo 1 di §7 — verificare che esista una sola pipeline
  condivisa fail-closed e che rifiuti i quattro modi di fallimento nominati dall'audit,
  con un test piccolo **senza GPU**, prima di autorizzare qualunque ciclo O1–O6.
- **Stato di partenza:** `tools/buildv.py`, `tools/o1_probe.h`, `tools/run_o1.py` scritti il
  2026-09-05 alle 17:37–17:42 e **mai eseguiti**; `research/24_phase2o_build_gate/` inesistente.

### Test del gate — `tools/test_buildv.py` (nuovo)

Rifiuti verificati, ognuno con il messaggio atteso:

| Modo di fallimento | Richiesto da | Esito |
|---|---|---|
| processo con exit code diverso da 0 | A01 (`returncode` ignorato) | rifiutato |
| riuso di un log già esistente | §7.1 output univoci | rifiutato |
| header assente / ambiguo (0 o 2 header) | §7.1 | rifiutato |
| hash inatteso (`expected` diverso) | §7.1 | rifiutato |
| hash invariato quando è attesa una canary (`different`) | §7.1 / §7.2 | rifiutato |
| header senza array, array duplicato, token non-hex, container non-DXBC, container troncato | A01 (`MANCANTE` non fatale) | rifiutati (5/5) |
| inventario runtime: scope errato, hash errato, size errata, `indices=0`, `native_matches=0`, CSV vuoto | §7.2 | rifiutati (6/6) |

Controllo positivo: header valido + CSV runtime coerente **passa**. Il test non costruisce
né misura nulla; usa solo DXC come compilatore.

### Riproduzione indipendente dell'artefatto storico

Ricompilando `MiniEngine/Model/Shaders/ModelViewerPS.hlsl` con i flag del gate
(`-E main -T ps_6_2 -D _GAMING_DESKTOP=1 -HV 2021`): **12 612 byte**, custom hash
**`52CE6C5E64AB2E82`**. Coincide con il valore dell'inventario storico ricalcolato offline
dall'audit. Confidenza: **confirmed** per l'identità dell'artefatto sorgente→bytecode.
**Non** dimostra ancora la propagazione fino al PSO eseguito: quella è O1.

### Difetto trovato ed eliminato — `prepare` attempt 1, FALLITO

`tools/run_o1.py:127` — `replace_once()` decodifica i byte grezzi
(`read_bytes().decode("utf-8-sig")`, nessuna traduzione di line ending) mentre
`Core/GameCore.cpp` è CRLF. L'unico anchor che attraversa un a capo conteneva `\n` e non
poteva **mai** corrispondere a `\r\n`: conteggio 0, non 2 (il messaggio "patch not unique"
copre entrambi i casi). Gli altri 15 anchor sono su riga singola e avevano già matchato,
lasciando il workspace patchato a metà.

**Falso OK del mio stesso pre-flight:** il dry-run leggeva con `Path.read_text()`, che
applica la traduzione universal-newline e trasforma CRLF in LF; riportava 16/16 anchor OK.
Un pre-flight deve usare **lo stesso percorso di decodifica** del codice che verifica.

Correzione: `replace_once()` converte anchor e sostituzione al line ending del file quando
il file è CRLF. Evita anche di inserire LF nudi in file CRLF. Fallimento conservato in
`research/24_phase2o_build_gate_FAILED_prepare_01/` con `FAILURE.md`; nulla cancellato.

### `prepare` attempt 2 — riuscito

- Experiment ID `O1_20260906_004007`, workspace `%TEMP%\claude\O1_20260906_004007`.
- 2,121 GB copiati da `%TEMP%\claude\src\dxs` (`MiniEngine` senza `Build/`, `Packages`,
  `vcpkg`, `vcpkg_installed`), **SHA-256 verificato prima e dopo ogni copia**;
  `input_hashes.csv` 1,3 MB. Copie reali, non hardlink/junction: né la build né il runtime
  possono scrivere sui file storici.
- 16 patch applicate, nessun line ending misto nei sorgenti C++ toccati.
- Redirezione output verificata a mano: i 4 punti di `PropertySheets/Build.props`
  (`OutDir`, `IntDir`, `IncludePath`, `HeaderFileOutput`) puntano a `$(O1BuildRoot)`, e
  Build.props è importato da tutti e 4 i progetti (`Core`, `Model`, `ModelConverter`,
  `ModelViewer`). L'esclusione di `MiniEngine/Build` dalla copia è una seconda barriera
  contro artefatti stale.
- Input di build presenti nel workspace: `vcpkg.json`, `vcpkg/DirectX.vcpkg.targets`,
  i due target NuGet (`zlib-msvc-x64`, `WinPixEventRuntime`), `NuGet.Config`,
  asset `Sponza/sponza.h3d`, DLL `GPUPerfAPIDX12-x64.dll`. `Libraries/` non è referenziato
  da MiniEngine, quindi la sua assenza dalla copia è corretta.
- Toolset: `v145` è l'unico platform toolset x64 installato (VS 18 Community,
  MSVC 14.51.36231), coerente con la configurazione storica.

- **Delta GPU / counter nuovi / qualità immagine:** N/A. Nessuna build, nessun workload GPU,
  nessuna misura di tempo. **0/6 cicli sperimentali consumati.** Un `prepare` fallito per
  difetto di script non è un ciclo sperimentale.
- **Preservazione:** nessun delete, nessun Clean; driver, cache, Registry e sicurezza
  invariati; nessun gioco aperto; nessuna applicazione personale chiusa.
- **Verdetto:** passo 1 di §7 **superato per la parte dimostrabile senza GPU**. La
  propagazione fino al PSO eseguito resta da dimostrare: è il ciclo O1.

## Entry O1 — propagazione build, ciclo 1 di 6. **PASS**

- **Ipotesi (§7.2):** una canary semanticamente osservabile e compilabile nel PS live arriva
  fino al PSO eseguito e all'immagine, e il ripristino riporta all'hash di baseline.
- **Experiment ID:** `O1_20260906_010146`. Risultati completi:
  [`24_phase2o_build_gate/PHASE_2O_O1_RESULTS.md`](24_phase2o_build_gate/PHASE_2O_O1_RESULTS.md).
- **Metadata:** RX 6950 XT, driver 32.0.21045.5002, Windows 11 26200, MiniEngine Profile/x64/v145,
  Sponza 1920×1080, cattura al frame 140, GPUPerfAPI **disabilitato**, nessun export di timing.

### Esito

| Stage | Bytecode | SHA-256 preregistrato | Esito |
|---|---|---|---|
| A baseline | 12 612 B · `52CE6C5E64AB2E82` | `3fbca1dd…74c6` corrisponde | PASS |
| B canary | 12 616 B · `863C3DDA7C0BCD9A` | `f226996f…30c7` corrisponde | PASS |
| A2 ripristino | 12 612 B · `52CE6C5E64AB2E82` | `3fbca1dd…74c6` corrisponde | PASS |

Entrambi gli hash attesi calcolati **offline prima di qualunque build** e scritti nel manifest.

- **Propagazione:** bytecode presente **esattamente una volta** in `Model.lib` e in
  `ModelViewer.exe`; **34 draw** di `Render Color` con `ps_hash` atteso, `ps_bytes` 12 612,
  `native_matches=1`, su **2 PSO nativi** (`m_ModelPSO`, `m_CutoutModelPSO`), 836 757 indici.
  Corrobora la correzione dell'audit: i 28,90 draw/frame di 2M erano **una** delle due
  componenti dello scope.
- **Canary rilevata come valore, non come semplice differenza:** 2 073 557 pixel = **100,00%**
  del frame, frazione cambiata R/G/B = **1.0 / 0.0 / 0.0**, tutti positivi, delta decodificato
  mediano **+0,124268** — cioè +0,125 quantizzato in R11. Verde e blu invariati al bit.
- **Reversibilità:** A2 riproduce l'immagine **bit-identica** ad A (0 pixel diversi) con un
  eseguibile di SHA-256 **diverso**: la build è avvenuta davvero. È il controllo diretto del
  difetto di 2N in cui MSBuild saltava la ricompilazione e si misurava due volte lo stesso binario.
- **Determinatezza:** spread di baseline **misurato 0 su 3 processi**. Registrato come
  *spread misurato*, **non** come determinismo: `FillLightGridCS.hlsli:163-173` alloca gli slot
  luce con `InterlockedAdd` e `Lighting.hlsli` somma `colorSum` in quell'ordine. Il meccanismo
  c'è; non si è manifestato qui. 2L trovò il secondo hash in 1 run su 6 e catturava dopo le
  particelle, questa cattura le precede.
- **Correttezza:** l'oracolo immagine è tipizzato (formato DXGI, dimensioni, row pitch e target
  registrati; padding di riga scartato) e verifica finitezza per canale. Output della canary
  intenzionalmente diverso → **diagnostic_only**, mai variante accettata.
- **Delta GPU / counter:** N/A per progetto. Nessuna misura di tempo, nessun counter, nessun
  verdetto di prestazione prodotto in questo ciclo.

### Difetti eliminati prima che il ciclo potesse essere valido — 14

Quelli che avrebbero prodotto un verdetto **falso o spurio**:

1. **`CL.read.1.tlog` come prova di propagazione.** Misurato sul tlog storico reale: 3134 voci
   di header, **0** sotto l'albero di output. Il FileTracker di MSBuild **esclude output e
   Packages**. Sostituito dal controllo bytecode-nel-binario. **Diagnostica anche la domanda
   aperta dell'audit su `dxc.write.1.tlog`: non è la granularità dei timestamp ipotizzata in 2N.**
2. **B costruita con `expected=None`** → avrebbe accettato qualunque bytecode diverso da A.
3. **`-MD` mette DXC in modalità solo-dipendenze**: scrive il depfile, non emette `-Fh`/`-Fo`,
   esce 0. L'invocazione combinata non produceva **nessun header**.
4. **Regex troncante** `(?:hlsl|hlsli)` → `Common.hlsli` diventava `Common.hlsl` →
   `resolve(strict=True)` sollevava `FileNotFoundError`.
5. **Cattura al frame 7**: `RenderLightShadows` copia **una** slice su 128 per frame.
6. **Baseline gated a 1 ULP** contro un meccanismo di nondeterminismo noto.
7. **`inline constexpr` in build C++14** → errore C7525. Trovato dal compilatore alla stage A
   tentativo 1, e **il gate ha rifiutato la build**: è il comportamento che A01 dichiarava assente.
8. **`replace_once` confrontava `\n` con un file CRLF** → workspace patchato a metà.

Più: hash dell'eseguibile non riverificato fra build e run; inventario dei sorgenti scritto ma
mai controllato; path del workspace preso da JSON senza validazione; budget contato su metà
albero; oracolo canary senza magnitudine decodificata; un solo repeat di baseline; directory di
stage non riutilizzabili dopo un fallimento.

Provenienza: **10** da review avversariale indipendente (agent Codex `gatecheck`), **2** dalla
prova a secco offline della metà DXC di `build()`, **1** dal compilatore, **1** da `prepare`.

- **Budget:** ciclo **1/6** consumato da O1. I fallimenti non hanno prodotto misure e non
  consumano cicli; sono conservati con la loro causa in
  `24_phase2o_build_gate_{FAILED_prepare_01, SUPERSEDED_prepare_02, SUPERSEDED_prepare_03,
  FAILED_A_01}`. Nuovi output ≈ 6 GB, sotto il tetto di 8 GB.
- **Preservazione verificata:** **3266 file del clone originale ricontrollati contro gli SHA-256
  pre-esperimento, 0 modificati.** Nessun delete, nessun Clean. Driver, cache, Registry e
  sicurezza invariati; nessun gioco aperto; nessuna applicazione personale chiusa.

## Entry GPA-01 — validità dei counter di 2N (indagine parallela, read-only)

- Report: [`25_gpa_validity/GPA_VALIDITY.md`](25_gpa_validity/GPA_VALIDITY.md). Nessuna build,
  nessun workload GPU. Non consuma cicli.
- **A03 confermato con il numero:** il set di 31 counter richiede **13 passate**, ottenuto
  *offline* da `GpaCounterLibGetPassCount` sulla counter library locale con identità
  `1002:73A5:C0`. La doc locale (`gpa/4_4/help/_sources/usage.rst.txt:441`) richiede
  *"an identical GPU workload once for each pass"*; `PHASE_2N_RESULTS.md:46` equipara timestep
  fisso a ripetizione dello stesso frame — è errato.
- **Risultato più forte di A03:** la domanda causale di 2N **non è rispondibile con i counter
  disponibili**. `TexUnitBusy` è documentato come comprensivo di *"all extra fetches and any
  cache or memory effects"*; nei 145 counter enumerati **non esiste alcun contatore
  VALU/SALU/occupancy per lo stage pixel** (esistono per VS/GS/tessellation/CS); i soli counter
  di filtraggio descrivono la *composizione* del filtraggio, e 2N non ne aveva abilitato nessuno
  tranne `TexAveAnisotropy`. Quindi *"texture-unit throughput bound, ALU esclusa"* non è
  "da rivalidare": con quella strumentazione **non era ottenibile**.
- **Vincoli pratici:** il massimo sottoinsieme single-pass contenente `TexUnitBusy` è di
  **7 counter**; `PSTime` richiede 3 passate da solo, `TexAveAnisotropy` **5**.
- **Difetti di integrazione, con `file:line`:** `ComputeContext::Begin` non chiama mai
  `OnContextBegin` (spiega `HDR Tone Mapping` assente); `Flush` resetta la command list senza
  hook; **10 return code GPA ignorati**, incluso `GpaGetPassCount`; `GpaEnableCounterByName`
  fallito riduce il set in silenzio; `Shutdown()` mai chiamata.
- **Marcato come inferenza, non verificato:** che riaprire con
  `kGpaOpenContextEnableHardwareCountersBit` esponga counter raw `SQ`/`TA` utili. Il flag esiste
  ed espone counter hardware (verificato); che quelli utili siano lì no.
- **Conseguenza sul piano:** **il ciclo O5 come preregistrato non è eseguibile.**

## Entry GPA-02 — opzione (a): counter raw. **Counter utili trovati; (c) non necessaria**

- **Istruzione:** procedere con (a) — rienumerare con `kGpaOpenContextEnableHardwareCountersBit`
  — e passare direttamente a (c) solo se non emergono counter utili. **Sono emersi.**
- Report: [`26_gpa_hwcounters/GPA_HW_COUNTERS.md`](26_gpa_hwcounters/GPA_HW_COUNTERS.md).
  Nessuna build dell'app, nessun rendering, nessun benchmark, **nessuna misura di workload**:
  solo enumerazione dei counter e query di pass count. Non consuma cicli sperimentali.

### Risultato

- **145 → 4001 counter** (3855 raw aggiunti). Confermato **due volte in modo indipendente**:
  offline sul contesto virtuale della counter library (device `1002:73A5:C0`, nessun device DX12)
  e **live** su un contesto DX12 reale che GPA identifica come *"AMD Radeon RX 6950 XT"*.
  I due insiemi di nomi sono **identici**: 4001 = 4001, zero solo-offline, zero solo-live.
  L'inferenza che `GPA_VALIDITY.md` aveva marcato **non verificata** è ora **verificata**.
- **L'ALU dello stage pixel è misurabile.** 96 counter `SQ` mascherati `PS` (24 eventi distinti
  × 4 shader engine): `INSTS_VALU`, `INST_CYCLES_VALU`, `ITEM_CYCLES_VALU`, `INSTS_SALU`,
  `INSTS_TEX_LOAD`/`_TEX_STORE`, `WAVES`/`WAVES_32`/`LEVEL_WAVES`, più cache SQC.
  È esattamente ciò che mancava quando 2N escluse l'ALU **per argomentazione**.
- **Il costo di filtraggio è nel blocco `TA`, non `TD`.** 14 eventi × 80 instance (una per CU):
  `TA_BUSY` e la distribuzione `ANISO_{1..16}_CYCLE_QUADS`, `MIP_{1,2}`, `VOL_{1,2}` —
  cioè i **cicli** spesi a filtrare, confrontabili con `TA_BUSY`. `TD` su questa ASIC espone
  solo eventi ray-tracing BVH.
- **Pass count misurati** (non ipotizzati): tutti e 36 i counter `SQ_PS*` = **1 passata**;
  `TA_BUSY` su tutte le 80 CU = **1 passata**; `TA_BUSY` + un bucket aniso su 80 CU = 1 passata;
  distribuzione `TA` completa = 7; `SQ`+`TA_BUSY` = 2; con `GPUTime` derivato = 3; tutti i 4001 = 38.
  Due fatti strutturali: il costo dipende dagli **eventi per blocco, non dalle instance**
  (1, 4 o 80 instance costano uguale → copertura per-CU gratuita), e **`TA` regge 2 eventi
  per passata**.

### Conseguenze sul piano

- **O5 torna eseguibile**, con i counter raw. Non con il set derivato e non con la
  strumentazione usata in 2N. `GPA_VALIDITY.md` resta valido: era circoscritto ai 145 derivati.
- **(c) non serve.** Registrato secondo l'istruzione ricevuta.
- **A03 diventa verificabile invece che assunto.** Ogni metà del discriminante è single-pass,
  quindi la coppia si cattura come due sessioni indipendenti a una passata. E la configurazione
  strumentata di O1 (camera congelata, TAA/motion blur/adaptation disattivati, timestep fisso,
  128 shadow slice risolte prima della cattura) **è** il workload congelato che l'SDK richiede
  per il multipass: O1 ha mostrato che produce immagini **bit-identiche su 3 processi**.
  Verificare se il frame *N* e *N+1* presentano lo stesso workload di `Render Color` diventa un
  esperimento economico e decisivo → va in **O2**, e determina se un set multipass sia ammissibile.

### Limiti dichiarati

- Solo enumerazione e scheduling. **Nessun counter è stato letto da alcun workload.** Nulla qui
  dice ancora alcunché su `Render Color`.
- La semantica dei counter raw (unità, quad vs cicli vs istruzioni, aggregazione per-SIMD o
  per-CU) va fissata sulla documentazione AMD prima di interpretare qualunque numero.
  Indovinarla ripeterebbe l'errore che questa fase esiste per correggere.
- Restano da correggere i 10 return code GPA ignorati, l'ordine `Begin`/`OnContextBegin`,
  `ComputeContext::Begin` che non registra mai, e `Shutdown()` mai chiamata
  (`GPA_VALIDITY.md` §6). Enumerare un counter non equivale a campionarlo correttamente.

## Entry O2 — semantica dei counter, identità del workload, baseline. Ciclo 2 di 6

- **Ipotesi:** (a) l'aggregazione dei counter raw è verificabile contro i derivati che l'SDK
  dichiara costruiti su di essi; (b) nella configurazione congelata il workload è identico fra
  frame e fra passate; (c) è possibile una baseline pulita di `Render Color`.
- **Experiment ID:** `O2_20260906_014011`. Report:
  [`27_o2_counters/PHASE_2O_O2_RESULTS.md`](27_o2_counters/PHASE_2O_O2_RESULTS.md).
- **Nessuna ablazione.** Pixel shader byte-identico alla baseline O1 (12 612 byte,
  `52CE6C5E64AB2E82`, stesso SHA-256), verificato dallo stesso gate fail-closed.
  Nessun verdetto di prestazione.
- 4 sessioni: `sq_ps` (32 counter, 1 passata), `ta_busy` (80, 1), `crosspass` (85, 2),
  `aniso` (721, 5); 8 sample su frame consecutivi dal 140.

### Aggregazione — 3 formule validate, 2 contro l'ipotesi naturale sbagliata

| Affermazione | Esito |
|---|---|
| `CPF_PERF_SEL_CPF_STAT_BUSY` = `GPUBusyCycles` | **esatto** |
| `TexAveAnisotropy` = `Σ(N·quads_N)/Σ(quads_N)` | **esatto**, 1,2181 |
| `TexUnitBusyCycles` = **somma** dei 80 `TA_BUSY` | **FALSO** (88 646 506 vs 1 124 256) |
| `TexUnitBusyCycles` = **massimo** fra le CU | **esatto** |
| `TexUnitBusy%` = `max(TA_BUSY)/GPUBusyCycles·100` | **esatto**, 94,627017 |

**`TexUnitBusy` è un MASSIMO su 80 CU, non una media.** Il 94,6% di 2N significa che *la singola
CU più carica* aveva la texture unit occupata al 94,6% dei cicli GPU-busy — non che le texture
unit fossero occupate al 94,6%. Qui l'imbalance misurata è 1,013 (mean 1 112 895, max 1 127 503),
quindi numericamente cambia poco, ma il significato del counter è ora **stabilito, non assunto**.
Corroborazione di provenienza: `TexUnitBusy` misurato **94,63%** contro **94,609951%** di 2N.

### Identità del workload — criterio preregistrato FALLITO, decomposizione più fine

Criterio preregistrato: *"nessun counter deve variare oltre lo 0,1% fra i frame campionati"*.
**FALLITO su tutti i set** (peggiori: `sq_ps` 0,63%, `ta_busy` 3,87%, `GPUTime` 19,92%,
`aniso` 64,52% su un counter per-CU quasi nullo). Era un criterio troppo grossolano: mescolava
tre grandezze diverse. Quanto segue **va oltre il preregistrato** ed è etichettato come tale.

| Tipo | Esempio | Su 8 frame consecutivi |
|---|---|---|
| Lavoro **aggregato** su tutte le instance | istogramma quad aniso, `ITEM_CYCLES_VALU` | **bit-identico, 0,0000%** |
| Lavoro **per-instance** | `TA18_..._QUADS`, `SQ_PS0_INSTS_VALU` | varia: il lavoro si redistribuisce fra CU/SE |
| **Timing** | `GPUTime` 19,9%, `TA_BUSY` 1,7%, `GPUBusyCycles` 0,81% | varia sempre |

Misura decisiva: **i totali dei bucket aniso sulle 80 CU sono bit-identici su tutti e 8 i sample
di una sessione a 5 PASSATE**, cioè su 40 frame diversi con i 721 counter schedulati in passate
distinte. `ITEM_CYCLES_VALU` vale esattamente 4 943 027 896 su ogni sample e ogni shader engine.
La GPU esegue davvero lo stesso lavoro ogni frame; ciò che non è riproducibile è **quale CU** ne
fa quale parte e **quanto tempo** ci mette.

**Cross-pass (preregistrato): PASS.** `Σ TA_BUSY` 1 passata 89 032 254 contro 2 passate
88 646 506 → **0,43%**, contro uno spread frame-a-frame di **1,72%** della stessa grandezza.

Regola operativa che ne deriva: il multipass è **valido per i counter di lavoro aggregati**;
per i counter di timing non è la fonte d'errore dominante, ma va sempre riportato lo spread
frame-a-frame invece di un valore singolo; i valori **per-instance non vanno trattati come
riproducibili**. La cattura a 13 passate di 2N mescolava i tre tipi e riportava valori singoli:
resta invalida, ma ora la ragione è misurata e non è "ogni passata girava su un frame diverso
quindi è tutto sbagliato" — il lavoro era identico, il timing e la distribuzione per-CU no.

**Cautela dichiarata:** `INSTS_VALU`, `INSTS_SALU`, `INSTS_TEX_LOAD`, `WAVES` variano dello
0,35–0,40% anche come totali, mentre `ITEM_CYCLES_VALU` e i quad TA sono esatti. AMD marca i
primi `{emulated}` e alcuni `{global}`. Se quello 0,4% sia variazione reale o artefatto di
emulazione **non è stabilito qui**: vanno trattati come ±0,4%, non esatti.

### Baseline `Render Color` (mediana di 8 sample, shader non modificato)

PS waves 39 214 · **`WAVES_32` = 0 → il pixel shader gira in wave64** · VALU inst 71 015 448 ·
VALU inst-cycles 183 167 994 · VALU item-cycles 4 943 027 896 · SALU 6 296 226 ·
`INSTS_TEX_LOAD` 6 115 386 · tex store 0 · `Σ TA_BUSY` 89 032 254 (per-CU 1 084 292…1 127 503) ·
`GPUBusyCycles` 1 188 712 · `GPUTime` 801 920 ns (705 480–881 000).
Aniso: 11 224 454 quad totali, 88,5% con 1 solo sample, media 1,2181; bucket 10–16 tutti a zero.
Rapporti riportati **come misure, non come tesi**: 14,56 cicli `TA_BUSY` per istruzione texture
di stage pixel; 2,58 cicli-istruzione VALU per istruzione VALU.

### Quello che questo ciclo NON stabilisce

Nessuna tesi sul collo di bottiglia. `TA_BUSY` **non è attribuito a uno stage**: divide un
counter di timing dell'intero blocco per un counter di lavoro del solo stage pixel; che
`ModelViewerVS` non campioni texture è atteso ma **non misurato** (esistono
`SQ_VS*_PERF_SEL_INSTS_TEX_LOAD`, una sessione single-pass basta). Il legame fra
`INSTS_TEX_LOAD`, quad filtrati e `TA_BUSY` non si riduce a un'identità pulita e non ne viene
proposta una. `GPUTime` varia del 19,9% fra frame: un tempo GPU di singolo frame non è una misura.

### Difetti eliminati prima che il ciclo producesse un numero — 4 build rifiutate dal gate

1. **`CommandContext::Flush` invalida la registrazione GPA** (`ExecuteCommandList` + `Reset`);
   il flush prima di `Render Color` (`SponzaRenderer.cpp:371`) è dentro `if (SSAO::AsyncCompute)`,
   che la configurazione congelata disattiva. `O2Gpa::Scope` ora **esige** che la command list
   viva coincida con quella registrata, invece di dipendere da quella fortuna.
2. Un frame di misura che non produce sample avrebbe lasciato la passata incompleta per sempre.
3. Il path di include GPA era solo in `Core.vcxproj`; spostato nel property sheet condiviso.
4. `ModelViewer.cpp` chiamava `O2Gpa::` senza includerne l'header.

`tools/o2_gpa.h` è un modulo nuovo, non un patch di `GpaProfiler.cpp`: ogni return code GPA è
controllato, un counter che non si abilita **aborta** invece di ridurre il set in silenzio, il
pass count deve coincidere con quello preregistrato offline, sessione e contesto vengono chiusi.

- **Budget:** ciclo **2/6**. Le 4 build fallite non hanno prodotto misure e non consumano cicli.
- **Preservazione:** nessun delete, nessun Clean; driver, cache, Registry e sicurezza invariati.
  Fallimenti conservati in `27_o2_counters_{SUPERSEDED_prepare_01, FAILED_build_01}`.

## Entry O3 — ablazione del campionamento materiali. Ciclo 3 di 6. **PASS**

Report completo: [`28_o3_material_ablation/PHASE_2O_O3_RESULTS.md`](28_o3_material_ablation/PHASE_2O_O3_RESULTS.md).

4 build (`mat0..mat3`), ognuna gated su uno SHA-256 di bytecode preregistrato **offline prima**
che girasse qualunque build; sostituzioni type-preserving al sito di sample.

**Dose misurata, non assunta:** 1,06 / 2,07 / 3,34 istruzioni texture rimosse per wave PS, su
**155,9** per wave. I tre sample dei materiali sono il **2,1%** delle istruzioni texture del
pixel shader; gli altri ~153 sono i fetch di luci e shadow map di `ShadeLights`.

**Confondente quantificato:** `mat3` toglie 2,1% di texture e **11,3% di VALU** — muore anche la
matematica TBN. `mat1` è il punto pulito: texture −0,68%, ALU **+0,55%**, tempo −1,53%.

**Risposta** (mediana di 3 processi, ordine interlacciato; soglia A/A max(2%, 3×1,03%) = 3,09%):
Δ`TA_BUSY` −2,33 / −5,71 / **−13,91%**, monotona, con `GPUTime` e `GPUBusyCycles` d'accordo
indipendentemente. **I 3 sample costano il 13,9% dei cicli busy della texture unit pur essendo
il 2,1% delle sue istruzioni** — le conte di istruzioni sono un pessimo proxy del costo TA, qui
di un fattore ~7.

**Difetto di strumentazione trovato:** i counter SQ per-shader-engine tornano a volte corrotti su
SE0 e SE2 — valori di un evento sotto il nome di un altro, bit-identici a una sessione diversa.
Non dipende dal numero di passate né di sample. Aggiunto `tools/sq_validity.py`, che rifiuta una
sessione se gli shader engine divergono >25% su un evento non nullo; le dosi O3 usano SE1+SE3.
Nessuna conclusione precedente ne è toccata. Un crash a shutdown (`0xC0000005`) su un run `mat3`
è stato **rifiutato dal gate** e ripetuto; i suoi dati non sono stati usati.

**Non stabilisce** che il pass sia texture-filter-throughput bound: stabilisce che una riduzione
verificata di lavoro della texture unit dà una riduzione di tempo proporzionale ma smorzata
(0,59–0,82).

## Entry O4 — ablazione del solo sampler, a bytecode invariato. Ciclo 4 di 6. **PASS**

Report completo: [`29_o4_sampler/PHASE_2O_O4_RESULTS.md`](29_o4_sampler/PHASE_2O_O4_RESULTS.md).

Il confondente di O3 eliminato **per costruzione**: nello shader non cambia niente. Cambia solo
il sampler statico dei materiali in C++, e il gate esige che tutte e 5 le build producano lo
stesso bytecode del pixel shader (`52CE6C5E64AB2E82`, 12 612 byte). Scope verificato nel
sorgente: dentro `Render Color` girano solo i draw Sponza opachi+cutout, che campionano
esclusivamente via `defaultSampler` (`s10`).

**ALU tenuta ferma e verificata, non solo argomentata** (sessione `sq_ps`, 4 shader engine sani
sotto il gate di O3): `INSTS_VALU`, `INST_CYCLES_VALU`, `ITEM_CYCLES_VALU`, `INSTS_TEX_LOAD`,
`WAVES` invariati entro **0,07%**; `ITEM_CYCLES_VALU`, che O2 ha mostrato essere esatto, entro
0,01%. `WAVES_32 = 0`: ancora wave64.

**Dose:** istogramma aniso collassato — ogni quad nel bucket a 1 ciclo — media 1,2181 → 1,0000,
**−17,9%** di cicli aniso, con il numero di quad costante allo 0,06%.

**Risposta** (32 sample × 3 processi, ordine interlacciato/invertito):

| variante | Δ`TA_BUSY` | Δ`GPUBusyCycles` | Δ`GPUTime` |
|---|---:|---:|---:|
| `s_aniso1` | −2,73% | −2,20% | −2,31% |
| `s_aniso16` | +0,10% | +0,25% | −0,18% |
| `s_point` | −3,50% | −2,63% | −2,86% |
| `s_bilinear` | −3,54% | −2,78% | −2,52% |

Soglie per-metrica dal controllo A/A misurato qui: `GPUBusyCycles` 2,00% (passano tutte e tre le
varianti verso il basso), `GPUTime` 3,88% (non passa nessuna, N95 1,29%). **Verdetto co-primario
conservativo: riduzione di `TA_BUSY` e `GPUBusyCycles` stabilita, riduzione del tempo suggestiva
ma non confermata.** Scegliere a posteriori la metrica più quieta sarebbe cherry-picking.

**Risultato del ciclo:** spegnere del tutto l'anisotropico, o scendere al filtro più economico
dell'hardware, muove `Render Color` **al massimo del ~3%**. L'ipotesi ereditata da 2N —
«texture-filter-throughput bound» — prevedeva un effetto grande da esattamente questo intervento.
**Non è supportata.** La texture unit è occupata al 94%, ma non a *filtrare*.

**Fallimenti dichiarati:** il braccio verso l'alto (`s_aniso16`) produce solo **+0,71%** di dose,
perché il contenuto non chiede quasi mai più di 8×: la bidirezionalità preregistrata è
formalmente presente ma sperimentalmente inefficace, e il suo nullo non falsifica nulla. Il
rapporto 3,50/13,91 = 25% **non** è una partizione «filtraggio / resto»: sono due interventi
diversi e l'additività non è mai stata misurata.

**Difetti trovati:** (1) `CubeMapSamplerDesc` è copy-init da `DefaultSamplerDesc`, quindi
cambiava anche `s12` — fuori scope, nessun numero toccato, ma l'invariante scritta nel manifest
era falsa; (2) `defaultSampler` è usato anche da `DepthViewerPS` e `SkyboxPS` fuori scope e può
lasciare le cache in stato diverso; (3) **DXIL identico non garantisce ISA nativa identica** — il
driver compila il PSO con la root signature e i suoi static sampler in mano — a cui risponde la
misura ALU sopra; (4) `tools/o4_analyse.py` calcolava N95 con un denominatore dipendente
dall'ordine e fissava `GPUTime` come metrica di soglia, scelta assente dalla preregistrazione.
Tutti corretti o riportati.

**Audit indipendente (Codex, via herdr):** dose e risposta ricalcolate da zero dai CSV grezzi con
uno script proprio e riprodotte. I difetti 1–3, la bocciatura della bidirezionalità e il rifiuto
della partizione 25/75 vengono da lì e sono stati adottati, sostituendo affermazioni più forti
nella prima stesura del report. Conservati `29_o4_sampler/audit/codex_recalc_o4.py` e
`audit/codex_audit_transcript.txt`.

- **Budget:** cicli **3/6** e **4/6** consumati. Nessuna build rifiutata dal gate in O4.
- **Preservazione:** nessun delete, nessun Clean; driver, cache, Registry, sicurezza e giochi
  invariati.

## Entry O5 — attribuzione di stage e classificazione cache/memoria. Ciclo 5 di 6. **PASS**

Report completo: [`30_o5_memory/PHASE_2O_O5_RESULTS.md`](30_o5_memory/PHASE_2O_O5_RESULTS.md).

**Nessuna build.** Riusati i 5 eseguibili di O4, SHA-256 riverificato a prepare e a ogni run;
cambiano solo i set di counter. Questo trasforma le varianti sampler di O4 in una **leva di
traffico di memoria a bytecode byte-identico**. Passate misurate offline **prima** di correre:
`tcp_ta` 320 counter in **1 passata**, `l1l2` 96 in **1**, `dram` 144 in **1**.

**L'attribuzione di stage ha richiesto un controllo per essere chiusa.** `SQ_VS*` legge zero waves
e zero istruzioni texture, e da solo questo non distingue «il vertex stage non campiona» da «il
vertex stage non gira sotto quella maschera». Sweep di tutte e 8 le maschere: il lavoro vertex sta
sotto `GS` (NGG primitive shader), 9 596 waves, e **emette** 28 852 istruzioni texture — **0,47%**
del totale, 3,007 per wave, cioè un attribute fetch a 3 stream (`INSTS_TEX_LOAD` conta anche i
buffer load). Predizione preregistrata <1%: **PASS**, ma non per la ragione che la lettura del
sorgente suggeriva. Senza il controllo avrei riportato «VS = 0%» come conferma pulita di una tesi
che i dati non sostenevano.

**Tre cause eliminate per misura:**

| candidato | misura | esito |
|---|---|---|
| la cache L0 stalla l'addresser | `Σ TCP_TA_REQ_STALL / Σ TA_BUSY` = **0,24%** (banda ≤10%) | falsificato |
| traffico di miss L0 | hit **97,66%**, 0,21 miss per istruzione texture | falsificato |
| banda DRAM | **31,88 MB = 39,6 GB/s** contro 555–621 GB/s su altri pass dello stesso frame | falsificato |

Il counter dello stallo non è morto: l'intervento sampler lo muove come il suo significato impone
(TCP req −12%, miss L0 −30%, stallo −24%) mentre `TA_BUSY` non se ne accorge. E la lettura della
gerarchia si valida da sola: **L2 miss × 64 B = 31,90 MB contro 31,88 MB** calcolati
indipendentemente da `EA_RDREQ_{32,64,96,128}B`, **0,06% di scarto**.

Numeri: **156,0 istruzioni texture per wave PS**, **14,51 cicli `TA_BUSY` per istruzione**,
9,07 richieste L0 per istruzione, duty cycle TA **93,25%** (coerente col 94,63% di O2, che è il
massimo sulle 80 CU).

**Correzione aggiunta dopo O6:** la sezione «cosa resta in piedi» elencava solo candidati del
percorso texture e si leggeva come se il percorso texture fosse *il* limite. L'ALU del pixel
shader era un quinto candidato, mai testato in O5.

## Entry O6 — replica del coefficiente a bytecode fisso. Ciclo 6 di 6. **REPLICATO**, con una correzione che indebolisce la tesi

Report completo: [`31_o6_lightcount/PHASE_2O_O6_RESULTS.md`](31_o6_lightcount/PHASE_2O_O6_RESULTS.md).

O5 finiva con un coefficiente, e un coefficiente si falsifica muovendolo. La leva è il **numero di
luci che sopravvivono al culling**: dato C++ in `CreateRandomLights` (`radiusSq = 0` per stride di
indice, così il mix sfera/cono/cono-ombreggiato resta proporzionale e le luci superstiti sono
bit-identiche). 4 build, 4 eseguibili distinti, **un solo bytecode**, imposto dal gate.

**Dose misurata, mai dedotta dallo stride:** istruzioni texture per wave 155,99 → 100,86 → 49,92 →
33,40 (−35,4 / −68,1 / −78,6%), waves costanti allo 0,19%. Il 155,99 riproduce il 156,0 di O5 da
build e sessione diverse.

**Verdetto sulle bande preregistrate:** Δ`TA_BUSY`/Δtex = **0,94 / 0,90 / 0,90** (banda
[0,75–1,25]) e **13,6 / 13,1 / 13,1 cicli** per istruzione rimossa (banda [10–19]; O5 prediceva
14,5). `GPUBusyCycles` scende del **32,5 / 60,2 / 69,4%**. Fit lineare: **l'88,2% dei cicli del
pass scala col conteggio di istruzioni texture**, il 90,4% per `TA_BUSY`.

**Errore mio, trovato e corretto nella stessa stesura.** Avevo diviso `INST_CYCLES_VALU` per 320
SIMD — il layout GCN — invece che per **160**: RDNA2 ha 2 SIMD32 per CU. Il duty VALU non è 48,3%
ma **96,64%**. Il controllo che lo smaschera è aritmetico: ÷80 darebbe un impossibile 193%.
Conseguenza: alla baseline il pass è **co-saturo** — VALU 96,64%, texture addresser 93,61%, con
l'ALU *marginalmente più alta*. **O6 non può classificare texture sopra ALU**, perché ogni suo
braccio le muove insieme. La prima stesura sosteneva il contrario ed era sbagliata.

Cosa regge, alla forza che l'evidenza consente: il coefficiente replica (13,1–13,6 contro 14,5
predetti da una misura diversa); il lavoro texture è sul percorso critico, ma questo viene da
**O4**, l'unico braccio della fase che ha mosso una sola delle due unità (a ALU fissa verificata
allo 0,07%, `TA_BUSY` −3,5% → pass −2,6%); e via via che il loop si accorcia le due divergono
(VALU 96,6→71,8%, TA 93,6→88,5%), coerente con un *mix* di costi e non con un limite unico.

`GPUTime` qui è inaffidabile (N95 **13,99%**): il primo processo di ogni batch gira a clock più
basso (1,476 contro 1,688 cicli/ns) mentre `GPUBusyCycles` si muove sotto lo 0,7%. Conclusioni su
`GPUBusyCycles` e `TA_BUSY`.

**Due `prepare` rifiutati prima di quello valido**, conservati come
`31_o6_lightcount_SUPERSEDED_prepare_{01,02}`: il primo perché `save_json` apre in modalità
esclusiva e non riscrive un artefatto (il gate che funziona), il secondo perché l'`experiment_id`
non coincideva col nome del workspace e **ogni build sarebbe stata rifiutata** — trovato leggendo
il gate, non facendo fallire una build. Nessuno dei due ha costruito o misurato nulla.

### Conclusione di Fase 2O

`Render Color` è **dominato** dal loop per-luce di `ShadeLights`: l'**88% dei cicli GPU del pass
sta su una retta nel lavoro di quel loop** (R²=0,9996 su 4 bracci), e alla baseline quel loop
lascia **sia** la VALU (96,6%) **sia** il texture addresser (93,6%) vicini alla saturazione.
Quattro spiegazioni eliminate per misura, ciascuna nell'ambito dichiarato: filtraggio texture
(O4, ≤3%), back-pressure `TCP→TA` (0,24%), traffico di miss L0 (hit 97,66%), **saturazione** di
banda DRAM (39,6 GB/s su 555–621). Non è esclusa la latenza di memoria in generale: nessun counter
la misura. **Non stabilito** quale delle due unità sature sia vincolante alla baseline: distano
3 punti, ogni braccio di O6 le muove insieme, e tutto O6 resta compatibile con un pass ALU-bound
in cui ogni iterazione rimossa porta con sé 13,1 cicli di addresser. Servirebbe lo specchio di O4,
un braccio che muova solo l'ALU.
Il costo localizzabile è il **numero di operazioni texture e ALU per pixel dell'algoritmo di
shading** — proprietà dell'applicazione, non del driver, del compilatore, del sampler o della
cache.

**Audit indipendente (Codex, via herdr).** Dose, elasticità e costo marginale ricalcolati da zero
dai CSV e riprodotti fino alla sesta cifra; ha trovato **da solo lo stesso errore del divisore
SIMD**, citando l'ISA RDNA2. Quattro sue correzioni adottate: i 13,1 cicli sono cicli-unità su
80 TA, non durata del pass (quella è 0,171 `GPUBusyCycles`/istruzione); R²=0,9996 non è causalità,
la dose è collineare con VALU e lunghezza del loop; un'ipotesi ALU-bound sopravvive a tutto O6;
`TCP→TA` esclude quella back-pressure, non la latenza di memoria. Ha inoltre verificato in positivo
che il counter TCP è vivo (80/80 istanze non nulle, è il numeratore di `MemUnitStalledCycles` di
GPA) e che `Render Shadow Map` non legge `radiusSq`. Conservato in
`31_o6_lightcount/codex_audit_o5_o6.txt`.

- **Budget:** cicli **5/6** e **6/6**. Fase 2O chiusa.
- **Preservazione:** nessun delete, nessun Clean; driver, cache, Registry, sicurezza e giochi
  invariati. Tutte le build hanno passato il gate fail-closed sul bytecode.

## Entry 2P — ottimizzatore del loop per-luce di `ShadeLights`. 8 cicli. **RISULTATO POSITIVO**

Report finale: [`PHASE_2P_FINAL_REPORT.md`](PHASE_2P_FINAL_REPORT.md) ·
worklog per ciclo: [`PHASE_2P_WORKLOG.md`](PHASE_2P_WORKLOG.md) ·
memoria delle misure: [`PHASE_2P_MEASUREMENT_MEMORY.csv`](PHASE_2P_MEASUREMENT_MEMORY.csv).

**Replica clean-room di 2O prima di tutto** (ciclo R), su macchina verificata inattiva: counter di
lavoro a **+0,00%** e **+0,01%**, bracci O4 e O6 dentro tolleranza. Il carico di background non
guidava nessuna conclusione di 2O, e l'escursione di clock su `GPUTime` si ripresenta anche a
macchina ferma: è del hardware, non contesa.

**Le ipotesi vengono dall'ISA vera**, non dal sorgente: `(gloss+2)/8` il compilatore la solleva
già; `pow(x,5)` di `FSchlick` no — esce come `v_log`+`v_mul`+`v_exp`, due transcendentali a
quarto di rate per luce.

**Quattro trasformazioni accettate, immagine bit-identica**: `fresnel5` −3,17%, `shadowskip`
−5,48%, `falloffskip` **−27,59%**, `scalar` −3,84%. La migliore combinazione, **`stack3_scalar`**,
vale **−41,60%** di `Render Color` in cicli GPA e **−40,34%** misurata dal timer del motore — due
strumenti indipendenti — con **frame GPU −24,39%** (≈−21,7% al netto di un effetto di clock che
ho quantificato usando i pass che la modifica non può toccare). Sono **68 righe di diff su un solo
file HLSL**; quattro delle cinque modifiche sono la stessa idea a quattro profondità (non calcolare
ciò che viene moltiplicato per zero esatto) e la quinta abilita un percorso che il motore
spediva disattivato.

**Il braccio che mancava a 2O è stato fornito.** `fresnel5` muove l'ALU a conteggio texture fisso
(−0,08%) e il pass segue del −3,17%; O4 muoveva la texture a ALU fissa e il pass seguiva del
−2,6%. **Entrambe le unità sature sono sul percorso critico e nessuna domina.**

**Cosa è andato storto, e come.** Un criterio di correttezza preregistrato si è rivelato
irrealizzabile alla prima applicazione (1 ULP di R11G11B10 vale ~1,6% relativo, quindi la soglia
1e-3 poteva passare solo un'immagine byte-identica): `ndotlskip` resta **rifiutata** con quel
criterio, che è stato sostituito **in avanti** in P3 senza toccare il verdetto emesso. Un'etichetta
era sbagliata e l'ha corretta la misura (`falloffskip` non è alu-only: il compilatore affonda un
buffer load dietro il ramo). Due controlli sull'occupancy sono **falliti**: `LEVEL_WAVES` restituisce
lo stesso valore impossibile su ogni build, e il padding pensato per tenere alti i registri viene
rimaterializzato dal compilatore. Tre `prepare` rifiutati dal gate e due crash intermittenti
rifiutati dal runner: nessuno ha prodotto un numero.

**Review avversariale (Codex via herdr): tre richieste, due completate, nessuna ha confermato
qualcosa.** Hanno indebolito l'equivalenza da "esatta" a "esatta sotto il contratto dei dati di
questo workload", mostrato che un'immagine quantizzata bit-identica non prova identità in float32,
stabilito che l'occupancy è una co-causa non separata, e ricalcolato ogni numero in modo
indipendente. La terza review — quella del candidato finale — si è interrotta perché il reviewer
ha esaurito il proprio limite d'uso: **il candidato finale non ha una review indipendente
completata**, ed è detto nel report invece che nascosto.

**Non dimostrato:** equivalenza a piena precisione (l'oracolo è un target quantizzato); generalità
oltre questa scena (a un quarto delle luci il guadagno scende a −20,19% ma resta); quanto del
guadagno venga dall'occupancy invece che dal lavoro rimosso.

- **Budget:** 8 cicli su 10. Stop su conclusione robusta e replicata, non per budget.
- **Preservazione:** nessun delete, nessun Clean; driver, cache, Registry, sicurezza e giochi
  invariati; nessuna applicazione personale chiusa. Tutte le build attraverso il gate fail-closed.

## Entry overnight (2026-09-06 → 07) — Fasi 2Q e 2R. 5 cicli su 12. **2Q positiva, 2R negativa e informativa**

Report: [`OVERNIGHT_FINAL_REPORT.md`](OVERNIGHT_FINAL_REPORT.md) ·
log per ciclo: [`OVERNIGHT_SESSION_LOG.md`](OVERNIGHT_SESSION_LOG.md) ·
memoria misure 2R: [`PHASE_2R_MEASUREMENT_MEMORY.csv`](PHASE_2R_MEASUREMENT_MEMORY.csv).

**2Q — equivalenza a piena precisione.** Il dubbio lasciato aperto da 2P (un'immagine
R11G11B10 bit-identica non prova equivalenza float32) è chiuso. Catturando in un target
`R32G32B32A32_FLOAT`: `SCALAR_BRANCH` è **bit-identico anche in float32**; il resto differisce al
massimo di **7 ULP** e **4,4e-7** relativo, **senza NaN, Inf o zero negativo**. `fresnel5` è stato
verificato **esaustivamente su tutti i 1 065 353 217 valori float32** del suo dominio e non è solo
equivalente: è **più accurato** di `pow(x,5)` — mai oltre **3 ULP** dal valore vero contro gli
**8 388 608 ULP** di `pow`, con riferimento calcolato in doppia precisione. Il data contract su cui
poggiano gli early-out è stato **misurato** con una canary (qualunque NaN/Inf/negativo avrebbe
portato il pixel a 1e30): non è mai scattata, il massimo resta 56,3287467956543 come nel baseline.
Replica prestazionale finale con 7 processi controbilanciati: `Render Color` **−41,43%**, frame GPU
**−24,47% MISURATO** e **−21,78% come stima corretta per il clock**, tenuti separati.

**2R — secondo workload.** Criteri di scelta scritti **prima**; scelto `D3D12nBodyGravity`
(simulazione n-body O(N²), compute, LDS, nessuna texture: l'opposto strutturale di ModelViewer).
Compilato, strumentato e gated; baseline con **A/A N95 0,05%** e oracolo esatto (lo stato delle
particelle è byte-identico su 5 processi). Tre trasformazioni guidate dall'ISA: una era **già fatta
dal compilatore** (bytecode identico), una bit-identica ma **più lenta dell'1,28%**, una **più
veloce del 3,58% e rifiutata dalla correttezza**. Quest'ultima è la più istruttiva: `mass_hoist` è
esatta in algebra, ma la somma di 10 000 forze che si cancellano ha numero di condizionamento ~1e5,
e dopo **un solo passo** la differenza è già di 164 301 ULP. Riassociare è lecito in matematica e
non in quella somma. **Nessuna trasformazione accettata sul secondo workload**, con la soglia mai
toccata dopo aver visto il numero.

**Il gate ha fermato cinque cose** prima che diventassero numeri: un header di probe che non
compilava, **due preregistrazioni fatte col compilatore sbagliato** (DXC del Windows SDK invece di
quello del pacchetto NuGet del progetto), una copia dell'eseguibile senza la sottocartella
dell'Agility SDK, e due varianti che compilavano allo stesso bytecode.

**Limite dichiarato:** il reviewer avversariale (Codex) aveva esaurito il proprio limite d'uso
prima dell'inizio della sessione, quindi **né 2Q né 2R hanno una review indipendente**. È il buco
più grande di questa sessione ed è la prossima azione raccomandata.

- **Budget:** 5 cicli su 12; ~1,1 GB di nuovi dati su 10 GB; 97 GB liberi. 2S non avviata.
- **Preservazione:** nessun delete di dati storici; driver, cache, Registry, sicurezza e giochi
  invariati; nessuna interazione con Fortnite/Warzone o anti-cheat.

## Entry review + freeze (2026-09-07) — 2 cicli. **La review ha rotto un punto; ricostruito; PoC congelato**

Documento di congelamento: [`POC_FROZEN.md`](POC_FROZEN.md) ·
review integrale: [`OVERNIGHT_REVIEW_2Q_2R.txt`](OVERNIGHT_REVIEW_2Q_2R.txt) ·
audit di provenienza: [`PROVENANCE_AUDIT.json`](PROVENANCE_AUDIT.json).

**La review avversariale (Codex via herdr, quota tornata) su quattro bersagli dichiarati.**
Verdetti: ULP/sweep **REGGE CON RISERVA**; canary del data contract **ROTTO**; conditioning in 2R
**ROTTO nella formulazione**; occupancy **REGGE CON RISERVA**.

**Il colpo vero: la canary.** Scriveva il sentinella 1e30 *dentro* il valore che viene poi
moltiplicato per zero, quindi su `distanceFalloff == 0` e `lit == 0` diventava `0 * 1e30 = 0`.
**Era cieca esattamente dove doveva vedere**, e `ndotlskip` non era coperto (controllava
`nDotL*RHS`, non `RHS`). Ricostruita (ciclo Q4) con una maschera di violazione propagata nelle
quattro funzioni, impostata **prima di ogni moltiplicazione**, mai moltiplicata, applicata a
`colorSum` una sola volta alla fine, un bit per contratto. **0 pixel su 2 073 600.** E il
controllo positivo che alla v1 mancava (Q5): la stessa maschera forzata a scattare su ogni valore
finito accende **2 073 600 pixel su 2 073 600** a 1e30. Il silenzio della v2 e' quindi evidenza.

**Conditioning:** la mia stessa errata (amplificazione ~20 epsilon mediana, 425 al massimo) era
gia' stata scritta prima che la review riportasse; il reviewer converge e aggiunge un dettaglio
che avevo mancato — la somma accumula **112 contributi fantasma dall'origine** piu' un termine
correttivo pesato −112, che fabbrica cancellazione extra. Nessun errore algebrico in `mass_hoist`.

**Buco di provenienza chiuso:** i primi `sweep_*.json` erano stati prodotti da un host precedente.
Sweep rieseguito con host tracciato (`provenance.json`: hash di host, sorgente, HLSL, DXIL,
disassemblato, versione DXC): **ogni campo riprodotto identico**.

**Audit di provenienza dell'intero progetto:** 64 record di build e 422 run su 22 directory di
ciclo, **zero discrepanze** fra manifest, build ed eseguibili.

**Congelamento.** 2P/2Q/2R sono congelate come proof of concept validato, con i limiti scritti
esplicitamente: magnitudine dipendente dalla scena, contratto misurato e non universale,
riferimento fp64 non e' un oracolo formale, occupancy non separata, un solo frame/scena/GPU,
nessun counter hardware sul secondo workload. **Nessuna ulteriore ottimizzazione**: il numero non
va spremuto.

**Prossima fase proposta, una sola: 2T — misurare l'hit rate del metodo** su 3–5 workload D3D12
open source dichiarati prima di guardarli, con la pipeline congelata e senza modificarla,
riportando quante volte produce una trasformazione accettata, negativi compresi.

- Nessuna modifica a driver, cache, Registry, sicurezza o giochi.

## Entry 2026-09-07 — Fase 2T. 7 cicli su 10. **Hit rate misurato: 0 su 4**

Report: [`PHASE_2T_RESULTS.md`](PHASE_2T_RESULTS.md) ·
preregistrazione: [`PHASE_2T_PREREGISTRATION.md`](PHASE_2T_PREREGISTRATION.md) ·
verdetti: [`49_2t_w1`](49_2t_w1/verdict.json) · [`50_2t_w2`](50_2t_w2/verdict.json) ·
[`51_2t_w3`](51_2t_w3/verdict.json) · [`52_2t_w4`](52_2t_w4/verdict.json).

La sessione riprende da dove la precedente si era fermata: W4 aveva baseline costruita e tre run,
nessuna analisi. Nessun workload è stato sostituito con uno più facile, come preregistrato.

**Il risultato.** Zero trasformazioni accettate su cinque costruite e misurate, su quattro
workload. Due chiusi prima di ogni ipotesi perché il pass non è migliorabile — e le misure che li
chiudono sono giuste, non pigre: 5,76 µs di dispatch e 480 ns di draw. W2 ha prodotto tre ipotesi
dall'ISA che hanno rimosso l'aritmetica bersagliata senza spostare il pass.

**W4 è il miss che vale.** Ha l'oracolo più solido del progetto (back buffer byte-identico su 14
processi in due sessioni), A/A N95 0,44%, e una sonda di Amdahl che dà **−16,59% di frame** —
quindi, a differenza di `Render Color` in 2M, qui **il tetto esiste**. La pipeline non ne ha preso
niente, e i due candidati dividono le ragioni in modo pulito: `gather_pcf` era abbastanza veloce
per contare ma non esatta (43 pixel su un texel diverso, delta fino a 41), `zeroskip_shadow` era
byte-identica ma non contava (+0,13%). Il dato collaterale più utile: **dimezzare le istruzioni
texture del pixel shader caldo vale lo 0,5% del pass**, quindi quel 16,6% non è throughput di
texture.

**Provenienza dichiarata.** Il pattern di `zeroskip_shadow` viene da 2P, non dall'ISA di W4. La
preregistrazione vieta di proporre a memoria; l'ho riportato a parte invece di nasconderlo, così
che un eventuale hit non fosse accreditato alla pipeline ISA-only. Non ha fatto hit.

**Due difetti fermati dal gate prima che diventassero numeri.** Gli header in `aux` non venivano
salvati né ripristinati, quindi il workspace restava sporco dopo una build che tocca
`Common.hlsli` — preso dall'hash preregistrato di `Glass_PSMain`. E l'analizzatore accoppiava per
numero di rep: con la base scivolata dell'1,2% fra le due sessioni avrebbe scorato `gather_pcf` a
~−1,5% contro una baseline vecchia e **fabbricato un'accettazione**. Corretti alla radice
(`source_rels()`, pairing per prossimità temporale, A/A che non mescola sessioni) e W1–W3
rianalizzati: verdetti invariati.

**Lettura onesta del progetto.** Contando anche i due workload riportati a parte, il metodo sta a
**1 hit su 6**, e l'unico hit vale −41% mentre nient'altro ha superato l'1,3%. Il −41% di 2P
somiglia più a un outlier — un loop per-luce insolitamente grande e insolitamente rimuovibile —
che a un tasso di successo.

- **Budget:** 7 cicli su 10. Fase chiusa perché W1–W4 sono tutti chiusi, non per budget. W5 non
  usato: era riservato a un workload non tentabile, e tutti e quattro sono stati tentati.
- **Preservazione:** nessun delete; driver, cache, Registry, sicurezza e giochi invariati; nessuna
  interazione con Fortnite/Warzone o anti-cheat.

## Entry 2026-09-07 — Fase 2U. 12 cicli su 12. **Hit rate 0 su 4; il collo di bottiglia e' identificato**

Report: [`PHASE_2U_RESULTS.md`](PHASE_2U_RESULTS.md) ·
preregistrazione: [`PHASE_2U_PREREGISTRATION.md`](PHASE_2U_PREREGISTRATION.md) ·
W4: [`PHASE_2U_W4_CEILING.md`](PHASE_2U_W4_CEILING.md) ·
memoria: [`MEASUREMENT_MEMORY.csv`](MEASUREMENT_MEMORY.csv) ·
Cyberpunk: [`C2077_OPERATOR_PROCEDURE.md`](C2077_OPERATOR_PROCEDURE.md).

**L'obiettivo era alzare l'hit rate. Non e' salito, e adesso si sa perche'.** Le tre modifiche
preregistrate hanno funzionato tutte, e nessuna ha prodotto un hit:

- **Ceiling gate.** Due workload su quattro chiusi prima di scrivere un'ipotesi, con un numero
  invece che con un giudizio: −0,38% (U-A) e +0,22% (U-C). Un ciclo ciascuno, zero tentativi,
  e restano nel denominatore. E' il modo onesto di far salire il tasso *condizionale*: separa
  «qui non c'era niente» da «il metodo ha fallito». Entrambi i tassi sono riportati.
- **Decomposizione del ceiling.** Su U-B, i raggi ombra sono il 55% del tetto, i riflessi il 34%,
  e la matematica del Phong l'1%. Cioe': ogni candidato che tocca solo ALU era gia' morto prima
  di essere costruito. Su W4 la stessa cosa spiega a posteriori un risultato di 2T.
- **Correttezza a due livelli.** Non e' servita: due candidati su tre sono tornati byte-identici.

**Il risultato che conta.** `shadow_tmax` — limitare il raggio ombra alla distanza della luce
invece che a 10000 — da' **immagine byte-identica** e **−2,18%**, replicato a protocollo piu' fine
a **−1,81% con separazione completa fra i due gruppi di processi**. La soglia preregistrata lo
**rifiuta**, perche' chiede tre volte la peggior coppia A/A e su questa macchina fa ~3-4%. Quindi:
**non e' l'ipotesi a mancare, sono l'esattezza e la soglia.** Su W4 il 72% del tetto sta dietro un
confronto duro (`depth >= depth`) e non esiste una strada bit-esatta per arrivarci.

Ho dichiarato che la replica e' stata fatta *perche'* il risultato era un quasi-successo. Non l'ha
salvato. La soglia non e' stata toccata dopo aver visto il numero, ed e' riportato anche che la
regola ha un difetto suo — «N95» e' implementato come massimo, quindi la soglia **cresce col
numero di run di baseline**: misurare con cura viene punito. Con un vero 95° percentile la soglia
sarebbe 2,58% invece di 4,02% e `shadow_tmax` fallirebbe comunque, quindi nessun verdetto dipende
da questo.

**Due credenze standard misurate false.** Sollevare il lavoro uniforme al vertex stage costa
+4,31% su W4 — previsione sbagliata nel segno, e il pass depth-only a +7,24% con il postprocess
fermo a +0,14% dice esattamente perche'. Il PERFORMANCE TIP di Microsoft sul non portare valori
attraverso `TraceRay` vale −0,09%: il compromesso di cui parla non e' misurabile qui.

**Sei difetti fermati dal gate** prima che producessero numeri. Il piu' grave: l'analizzatore
accoppiava per numero di rep e, con la baseline scivolata dell'1,2% fra due sessioni, avrebbe
**fabbricato un'accettazione**.

**Milestone Cyberpunk preparata, non avviata** (il gioco non e' installato). L'harness di cattura
e' scritto e **validato su un processo DX12 vivo**; si rifiuta per codice di lanciare il bersaglio.
Il parser e' stato esteso ai tre schemi CSV di PresentMon con **regressione verificata: le 14
baseline esistenti danno numeri identici**. Superposition scaricato, firma verificata, installato
in silent con uninstaller — con il limite dichiarato che e' DX11/Vulkan e non DX12.

- **Budget:** 12 cicli su 12.
- **Preservazione:** nessun delete; driver, cache, Registry, sicurezza e giochi invariati; nessuna
  interazione con Fortnite/Warzone o anti-cheat; il gioco non e' stato lanciato da nessuno script.


## C2077 2026-09-07 — Codex resume
Started passive baseline preparation; see C2077_WORKLOG.md and 60_c2077_20260907_codex/experiment_metadata.json. Historical data preserved. No game/system changes.

### 2026-09-07 — Cyberpunk continuation, GUI navigation pending
Confirmed first completed contemporary benchmark artifacts in 60_c2077_20260907_codex/bench_r2. UserSettings SHA-256 unchanged. No performance aggregation before the five-run minimum. Computer Use Settings clicks and activation did not leave the results screen; requested the single manual Settings click. Automatic review rejected a navigation key because focus was not verified; no workaround used. Next: observe benchmark menu, capture bench_r3, complete four more runs, validate segmentation, then analyze and perform post control.

### 2026-09-07 — remaining Cyberpunk runs blocked on automatic UI review
User opened Settings and reauthorized four autonomous runs. Automatic approval review twice rejected B Run Benchmark, including after a fresh screenshot. bench_r3 was a 150 s menu-only capture (exit 0, 27943 rows), excluded. No performance analysis or settings modification. Manual Start requested; completed benchmark count remains one, not two.


## manual_r1 validated and analyzed
PresentMon exit 0, 23404 raw rows; native 17:46:23 result 7261 frames / 64.251335 s / 113.009323 FPS. All native frame intervals aligned with one PresentMon stream, rows 4688–11948; head/middle/tail block offsets agree. Full PresentMon FPS 113.026176 (+0.014912% vs game). Full and historical-standard trimmed metrics separately recorded in manual_r1/native_analysis/analysis.json and manual_r1/analysis.md. Zero stutter events under existing definition. Settings hash unchanged. Added minimal native-trace alignment tool with fail-closed structural checks and passing selfcheck; old duration-only selector not used. One manual run cannot establish run variance or gains; prior GUI-controlled run not pooled. Next manual_r2.


## manual_r2 validated and analyzed
PresentMon exit 0, 22731 raw rows. All 7259 native frames matched to rows 3892–11150 with agreeing head/middle/tail offsets. Full benchmark 112.979426 FPS, p99 12.049448 ms, time-integrated lows 76.641555 / 67.613618 FPS, zero defined spikes. Native FPS agreement +0.012807%. Settings SHA-256 unchanged and native configuration equal manual_r1. FPS delta vs r1 -0.0414%; n=2 CV provisional, no significance/gain claim. Full and standard trimmed metrics stored separately in manual_r2/native_analysis/analysis.json. Next manual_r3.


## manual_r3 validated and analyzed
PresentMon exit 0, 22623 raw rows; all 7253 native frames matched to rows 3136–10388 with agreeing three-block offsets. FPS 112.903162; p99 11.983140 ms; time-integrated lows 78.030307 / 71.886798 FPS; zero defined spikes. Native FPS cross-check +0.013140%. Settings hash and native configuration unchanged. n=3 manual FPS CV 0.054965% (interim only). Full and standard-trimmed metrics separate in manual_r3/native_analysis/analysis.json; comparison_after_r3.json records descriptive variance. Next manual_r4; earlier Computer Use run not pooled.


## Consolidation after manual_r4
manual_r4 validated: 7255 frames, 112.931485 FPS, zero defined spikes; settings hash unchanged. bench_r2 also native-aligned successfully (6167 frames, 96.008442 FPS). Five complete captures exist, but only four are homogeneous manual repeats; manual mean 112.960062 FPS, CV 0.047947%. Initial slow GUI-controlled run retained separately, causal difference unresolved. Passive profiling suggests substantial GPU work but no demonstrated shader-side ceiling or justified modification. Local REDmod/cache/config surface inventoried read-only; no mod/injection/driver changes. C2077_FINAL_REPORT.md and consolidated_analysis.json written with explicit incomplete milestone status: fifth homogeneous manual run and Steel Nomad post remain missing. User authorized closing Cyberpunk; offline analysis complete, no silent relaunch.


## Steel Nomad post verified
Native .3dmark-result archives located and copied with SHA-256. Pre 4184 / 41.849308 FPS, post 4189 / 41.897465 FPS: score delta 0.119503%, FPS delta 0.115072%. SUCCESS, same DX12 test/version/settings except result filename. Pre/post endpoints consistent; historical >0.5% comparability failure unchanged. Raw PM 2684 rows includes initialization; 2509-row approximate steady section not treated as exact native 2513-frame equivalence. No full-raw FPS/stutter claim. Prior report/status preserved before update. No modified shader exists; no variant A/B required now. Remaining protocol acquisition: fifth homogeneous manual Cyberpunk run, with restart comparability caveat.
