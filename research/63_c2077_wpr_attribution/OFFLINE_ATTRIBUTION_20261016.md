# Cyberpunk / WPR — attribuzione offline della cattura esistente

**Data:** 2026-10-16 · **Analysis ID:** `C2077-WPR-OFFLINE-20261016`  
**Cattura:** `c2077_fs1440_attribution-run1-20260908-222856-633` · nessun nuovo benchmark.

## Verdetto

1. **Confirmed:** orologi e finestra ricostruiti; tutti i **5304 frame** corrispondono a una sequenza contigua di Present DXGI nell'ETL. Non sono stati selezionati nuovi tagli favorevoli.
2. **Confirmed:** costi CPU esclusivi, tempi schedulati e percorsi reali di attesa/risveglio sono ora disponibili. Il processo esegue molta sincronizzazione tramite semafori; questo **non dimostra che sia lavoro eliminabile**.
3. **Confirmed:** device → proprietario → context → node e segmenti DMA ricostruiti. Nella run profilata esistono intervalli senza lavoro DMA del gioco, attese e preemption; **non è una GPU costantemente alimentata come suggerivano le passive 1440p**.
4. **Strong:** la cattura ha una perturbazione di tracing rilevante. I campioni colpiscono direttamente routine ETW e stack-walk. **La quota del calo di FPS causata da WPR non è identificata**, mancando un controllo abbinato con/senza profiling.
5. **Nessun candidato di ottimizzazione accettato.** Non sono dimostrati un collo di bottiglia del driver nelle passive, uno shader costoso modificabile, né uno speedup sul gioco. Non modificare driver, cache o shader sulla base di questa traccia.

L'analisi offline è completata **nei limiti delle evidenze validate**. Restano aperti il critical path completo e i caller dei campioni CPU: non vanno segnati come risolti dal solo successo dei parser.

## Dati e integrità

Directory corrente degli artefatti: [offline_20261016](fs1440_r1/offline_20261016/README.md).

- ETL originale: **21.098.397.696 byte**, SHA-256 `e2e4ae42ccb8bb1e41d8717513abe1bb469d6e4969ef1b8e363f229a5b21e739`, calcolato due volte concordemente. Nessuna modifica all'ETL.
- PresentMon, metadata e copie native `frames.csv` / `summary.json`: hash ancora uguali a quelli registrati a settembre.
- [Manifest](fs1440_r1/offline_20261016/artifact_manifest.json): input, reader compilato, sorgenti dei parser, decoder di riferimento e risultati JSON.
- Perdita ETW: **0 buffer / 0 eventi**, come da [validazione originale](fs1440_r1/trace_validation.txt). Non usati `-tle` / `-tti`.
- Metadata **storici della cattura**, non del sistema attuale: RX 6950 XT, 5800X3D, 32 GB, Windows 26200, driver `32.0.21045.5002` / Radeon 26.8.1; Cyberpunk 2.31; 2560×1440 fullscreen, RT/upscaling/FG off. Cache non alterata dall'agente; non ricostruito uno stato cache completo.

## 1. Orologi: risolto senza duration-only matching

Il reader nativo usa `OpenTraceW` / `ProcessTrace` in modalità **raw timestamp**, leggendo dall'ETL frequenza QPC **10.000.000 Hz** e origine **324166830818 tick**. Conversione verificata contro gli stessi eventi esportati da xperf:

```text
ETL microseconds = (raw QPC - 324166830818) / 10
finestra nativa  = [49.9097700, 114.1538552) secondi ETL
QPC             = [324665928518, 325308369370) tick
```

Controllo indipendente dei primi 200 ms, non usati come benchmark:

| Eventi | Reader raw | xperf | Discrepanze |
|---|---:|---:|---:|
| SampleProf | 1276 | 1276 | 0 |
| CSwitch | 51340 | 51340 | 0 |
| ReadyThread | 26314 | 26314 | 0 |

Anche **10 eventi DXGI** coincidono per tempo relativo, thread e opcode.

L'online PresentMon e WPR **non hanno timestamp bit-identici**: i Present stop ETL precedono i corrispondenti CPUStart online di **0,2–12,9 µs**, mediana **0,3 µs**. La causa precisa dello scarto di emissione fra sessioni non è isolata. Nessun offset adattato è stato sottratto ai dati. Tutti i 5304 abbinamenti sono contigui e univoci; la seconda alternativa più vicina dista almeno **8819,9 µs**. Errore massimo sugli intervalli **12,6 µs**.

La doppia esportazione offline PresentMon non ha funzionato: versione installata ora 2.6.0 e 2.5.1 ufficiale recuperata per compatibilità non hanno prodotto CSV utilizzabili; 2.5.1 è terminata con exit 0. Non è stato interpretato come successo. Il fallback raw ETW è quello validato.

Fonte: [clock_and_layout_validation.json](fs1440_r1/offline_20261016/analysis/clock_and_layout_validation.json). La finestra conserva **64,2440852 s / 82,56013 FPS**, contro 82,56697 nativi. PresentMode resta Hardware Independent Flip.

## 2. CPU: costo esclusivo e residenza, non percentuali inclusive sommate

Nella finestra: **444920 campioni del gioco**. Attribuzione tramite IP e intervalli di immagini effettivamente caricati, con ownership dei thread ricostruita dagli eventi, non dal PID indeterminato dell'header kernel.

| Modulo | Campioni | % campioni del processo |
|---|---:|---:|
| Cyberpunk2077.exe | 217122 | 48,800% |
| ntoskrnl.exe | 126368 | 28,402% |
| ntdll.dll | 37546 | 8,439% |
| amdxc64.dll | 35030 | 7,873% |
| PhysX3_x64.dll | 6207 | 1,395% |
| D3D12Core.dll | 5463 | 1,228% |
| amdkmdag.sys | 959 | 0,216% |
| dxgkrnl.sys | 895 | 0,201% |
| dxgmms2.sys | 788 | 0,177% |

57 campioni del gioco non hanno un modulo mappato (**0,0128%**). Altri 100 campioni dell'intero sistema hanno ownership sconosciuta, separata dal gioco. Nomi privati di funzioni AMD/gioco **non inventati**.

Il report nativo xperf, con pesi temporali anziché conteggi semplici, stima **446,934 CPU-s aggregati** nel contesto del gioco: distribuzione concorde (gioco 48,80%, AMD UMD 7,90%). Non sono secondi di frame né tempo di un singolo core fisico. La residenza da CSwitch è **458,400 CPU-s**: misure diverse, non forzate a coincidere.

**Kernel/DPC:** i campioni kernel nel contesto di un thread del gioco possono includere interrupt e lavoro di tracing. Non sono automaticamente costo richiesto dal gioco, né UMD AMD. xperf misura separatamente circa **10,525 s DPC in dxgkrnl su CPU 0** nella finestra; questo non identifica da solo un problema AMD. I thread System del GPU scheduler restano distinti dal processo del gioco.

Fonti: [cpu_modules.csv](fs1440_r1/offline_20261016/analysis/cpu_modules.csv), [xperf_weighted_cpu_modules.csv](fs1440_r1/offline_20261016/analysis/xperf_weighted_cpu_modules.csv), [funzioni risolte](fs1440_r1/offline_20261016/analysis/xperf_target_functions.csv), [DPC/ISR](fs1440_r1/offline_20261016/dpc_isr.txt).

### Thread e wait/signal

**34 thread** del gioco con campioni e riscontro nel report preciso nativo: tempi running concordi entro **0,5 µs**.

| TID storico | Running s | Ready s | Waiting s | Altro off-CPU s |
|---|---:|---:|---:|---:|
| 2700 | 61,5183 | 2,4505 | 0,2021 | 0,0732 |
| 18604 | 26,7027 | 3,7239 | 33,8117 | 0,0058 |
| 13144 | 26,2613 | 3,2554 | 34,7243 | 0,0031 |

Il TID 2700 è schedulato per circa il **95,76%** della finestra; il **53,38% dei suoi campioni** cade in ntdll. A livello del processo, `RtlQueryPerformanceCounter` pesa circa **33,331 CPU-s**. Questi fatti non autorizzano a chiamarlo un busy-wait eliminabile o il critical thread delle passive.

Stack precisi effettivi:

- CSwitch del gioco: **6.873.198 stack**; `KernelBase!WaitForSingleObjectEx` compare in **6.553.792** (95,35%). Caller del gioco conservati come RVA, non etichettati con nomi privati.
- ReadyThread con stack eseguiti nel processo del gioco: **6.719.067**; `KernelBase!ReleaseSemaphore` compare in **6.518.411** (97,01%). Sono stack del **readying context**, non automaticamente lo stesso insieme dei thread risvegliati del gioco.
- Ricostruzione dei wake diretti ai thread del gioco: **6.826.668**; 6.564.705 hanno come contesto CPU un thread dello stesso processo, 221.466 sono marcati InDPC. Un contesto interrotto non è il proprietario del dispositivo che segnala.

**Confirmed:** esiste un percorso frequente di sincronizzazione intra-processo tramite semafori. **Non dimostrato:** che ridurne il numero preservi correttezza e migliori il frame.

Running include residenza durante DPC/ISR. Ready/waiting sono ricostruzioni da eventi, non wait-object critical-path completo: il decoder incontra anche uno stato raw 9 che xperf stesso stampa `<out of range>`, tenuto in “altro off-CPU”. Nel subset con padding sono registrati 77872 ready-while-current, 8161 duplicate-ready e 4 switch-in senza ready. Non sono occultati; la verifica nativa valida il running, non ogni decomposizione ready/wait.

Fonti: [threads.csv](fs1440_r1/offline_20261016/analysis/threads.csv), [wake_edges.csv](fs1440_r1/offline_20261016/analysis/wake_edges.csv), [stack wait](fs1440_r1/offline_20261016/analysis/switch_TblSI.csv), [stack signal](fs1440_r1/offline_20261016/analysis/ready_TblSI.csv).

### Limite dei caller sampled CPU

`SampledProfile` e `SampleProf` nel report stack xperf non restituiscono tabelle utilizzabili. Verificato anche sullo **smoke storico riletto offline senza filtro PID**, includendo `PerfInfo`: tabelle ancora vuote, quindi non basta togliere il filtro del processo ([diagnostica](fs1440_r1/offline_20261016/stack_diagnostic_smoke/command.json)). Il filtro più ampio `Profile` restituisce una popolazione molto maggiore dei campioni CPU, con distribuzione esclusiva differente: **non validato come CPU sampling**, escluso da percentuali e caller CPU. Il vecchio problema WPA `[Root]` non è dichiarato risolto.

Gli stack CSwitch/ReadyThread sopra sono invece reali e risolti con PDB Microsoft corrispondenti ai GUID/age della traccia. Simboli scaricati solo dal server Microsoft e cache solo nel progetto; [provenienza](fs1440_r1/offline_20261016/symbol_provenance.json).

## 3. GPU: ownership, segmenti, attese e preemption

Adapter target: `0xffff9a8c8a21a000`. Device ownership dal **payload hProcessId**, poi Context.hDevice/NodeOrdinal. Non usato il PID del DPC come proprietario.

Il replay usa le code DMA FIFO per node: **DmaPacket Start è enqueue sul node, non un timestamp hardware di inizio shader**; l'inizio stimato del pacchetto successivo è la completion del precedente. Completion da DmaPacket Info, più stretta dello Stop notificato dopo. Sono quindi **bounds/proxy dello scheduler**, non occupancy ALU/texture o timestamp di un draw.

| Node | Evidenza tipo | DMA gioco / finestra | DMA altri processi |
|---|---|---:|---:|
| 0 | EngineType 3D | 74,751% | 2,068% |
| 2 | FriendlyName Compute 0 | 12,862% | 0% |
| 1 | EngineType Copy | 0,876% | 0% |
| 4 | EngineType Copy | 0% | 3,329% |

Queste percentuali **non si sommano**: gli engine possono sovrapporsi. Unione del lavoro del gioco sui node: **48.678,8322 ms / 75,7717%** della finestra. La somma GPUBusy online attribuita ai 5304 frame è **48.679,9528 ms**, differenza **1,1206 ms**: forte riscontro del decoder, con confini CPU-window/frame-GPU diversi, non misura hardware indipendente.

Node 0, quando la coda DMA è vuota:

- **15,475%** della finestra senza DMA target in attesa né wait-packet attivo;
- **3,629%** con DMA target pendente senza wait-packet attivo;
- **3,510%** con DMA target pendente e wait-packet attivo;
- **0,566%** senza DMA target pendente ma con wait-packet attivo.

“Pendente” comprende pacchetti preempted in attesa di resume. “Wait attivo” è lo stato del pacchetto nello scheduler, non prova che ogni microsecondo sia bloccato su una particolare fence. I vuoti senza submission sono compatibili con mancata alimentazione; quelli con lavoro pendente ammettono dipendenze e scheduling. **Non è legittimo assegnarli tutti a CPU gioco, driver o a uno shader.**

Altri riscontri della finestra:

- **93450** DmaPacket Start del gioco; **2714** segmenti preempted; **0** QueuePacket timeout. Preemption di segmento non equivale a timeout o stutter.
- **0 completamenti fuori ordine**. Due completion senza Start sono nel padding iniziale, **prima** della finestra nativa; nessuna dentro.
- Tutti i **436393 QueuePacket Start mappati al gioco** hanno anche event PID 16316: ownership confermata indipendentemente dal PID di completion.
- 18 eventi non mappati = sei triplette Start/Info/Stop di **PacketType 6, DEVICE_COMMAND_BUFFER**; esplicitamente esclusi, nessun DmaPacket sconosciuto in queste 18 righe.
- Tre layout QueuePacket distinti per ID/versione/proprietà: **178 DMA**, **244 scalar WAIT=4**, **245 array SIGNAL=5**. Il filename/nome evento comune non basta a decodificarli.
- **52932** wait-packet completati; **52876** join validati a Unwait, 56 non associati. Start→Unwait: mediana **0,92035 ms**, p95 **5,95895 ms**, p99 **7,750375 ms**. Include lavoro davanti al wait: **non è tempo netto di fence bloccata**.
- **52721** wait hanno un'osservazione della stessa coppia oggetto/valore di fence; 52666 sono soltanto signal **enqueued** e 55 signal completed osservati prima dell'endpoint. Non trasformati in 52721 catene causali di soddisfacimento della fence.
- Submission CPU→enqueue DMA: mediana **0,79175 ms**, p95 **5,660865 ms**; Stop arriva in media **48,77 µs** dopo l'interrupt. Non usare il solo Start→Stop come durata shader.

Fonti: [summary.json](fs1440_r1/offline_20261016/analysis/gpu/summary.json), [node totals](fs1440_r1/offline_20261016/analysis/gpu/node_timeline_totals.csv), [context map](fs1440_r1/offline_20261016/analysis/gpu/contexts.csv), [segmenti](fs1440_r1/offline_20261016/analysis/gpu/dma_fifo_spans.csv), [wait/fence](fs1440_r1/offline_20261016/analysis/gpu/wait_packets.json).

## 4. Perturbazione: cosa è dimostrato e cosa no

L'intero ETL contiene **439.214.592 eventi in 177,223 s**, inclusi circa **117,964 milioni di syscall enter** e **117,677 milioni di exit**. Questi conteggi sono della traccia intera, non della sola finestra benchmark.

Nella finestra, dai **campioni CPU esclusivi pesati** del gioco:

- **13,964 CPU-s / 3,12%** nei soli simboli `ntoskrnl!Etw*` / `Etwp*`;
- altri **27,277 CPU-s / 6,10%** in `RtlpLookupFunctionEntryForStackWalks` e `RtlpWalkFrameChain`;
- anche routine di unwind generiche sono calde, ma non sono assegnate tutte a ETW senza caller sampled validati.

Sono costi osservati in routine di tracing/stack collection, non una sottrazione di FPS costruita a posteriori. La run contiene inoltre attività del launcher e di altri processi: non è isolato l'effetto del solo WPR.

| Dato descrittivo | Passive fullscreen 1440p | Run WPR |
|---|---:|---:|
| FPS | 112,368 / 111,905 | 82,560 |
| GPUBusy medio ms | 8,7747 / 8,8007 | 9,1780 |
| GPUWait medio ms | 0,0988 / 0,1076 | 2,7267 |

**Non è A/B**, non c'è varianza run-to-run della configurazione profilata e non è stimato il contributo causale di ciascuna differenza. I rapporti busy/frame non sono utilizzo hardware. Il verdetto precedente “1440p passive prevalentemente GPU-bound: strong” resta valido; non è sostituito con “Cyberpunk è CPU-bound” sulla base di questa run.

## 5. Correzioni e controlli

Prima del verdetto sono stati intercettati e conservati come tentativi non utilizzabili:

- decoder Image che trattava `KernelBase` come Image Load, corretto filtrando gli opcode reali;
- inversione iniziale scalar/array WAIT/SIGNAL, corretta contro l'enum primario e bloccata con test;
- join Unwait basato su un vecchio puntatore riusato, che generava un falso estremo di 39 s; scartato. Ora lifetime, tipo e ordine Start≤Unwait≤Stop sono verificati;
- richiesta errata di timestamp online/ETL bit-identici: sostituita con sequenza contigua e residui espliciti, senza fitting dell'offset;
- filtro stack `Profile` ambiguo, respinto come sorgente CPU sampled.

**PASS eseguiti:** reader x64 ABI; parser/immagini/clipping scheduler; tre layout QueuePacket, FIFO e riordino; confronto reale xperf/raw; controllo running di 34 thread; ownership/node totals/ordine delle fence; hash delle fonti; selfcheck esistenti `etw_analyze.py`, `c2077_native.py`, `test_capture_etw.ps1`.

## Riproduzione offline

Da root, reader compilato con toolchain Windows già installata:

```text
research\63_c2077_wpr_attribution\fs1440_r1\offline_20261016\build_reader.cmd
```

Comando di estrazione esatto e ambiente dei report nativi: `extract_v2.command.json` e `xperf_cpu.command.json` nella directory offline. Il reader rifiuta output già esistenti; preservare i precedenti o scegliere un nuovo prefisso.

```bash
python -B tools/c2077_etw_offline.py research/63_c2077_wpr_attribution/fs1440_r1/offline_20261016/events_v2 <NUOVA_DIRECTORY> --lo 324665928518 --hi 325308369370 --origin 324166830818
python -B tools/c2077_gpu_queue.py <DIRECTORY_ANALISI>
python -B tools/c2077_etw_check.py research/63_c2077_wpr_attribution/fs1440_r1/offline_20261016
```

L'ultimo check valida la directory canonica già prodotta e rigenera solo i riassunti, non catture. Il parser è deliberatamente specifico ai layout verificati: SampleProf v2/16 byte, CSwitch v5/28, ReadyThread v2/8. Per altre tracce verificare anche il riuso dei TID del processo target.

## Fonti primarie e prossima decisione

- SDK Windows locale: `evntrace.h`, `evntcons.h`, `tdh.h`; API [OpenTraceW](https://learn.microsoft.com/en-us/windows/win32/api/evntrace/nf-evntrace-opentracew), [ProcessTrace](https://learn.microsoft.com/en-us/windows/win32/api/evntrace/nf-evntrace-processtrace), [TdhGetEventInformation](https://learn.microsoft.com/en-us/windows/win32/api/tdh/nf-tdh-tdhgeteventinformation).
- Decoder Intel PresentMon, commit **e13fce6acdb55a808fd8318175a56863e532d95f**: [QueuePacket enum](https://github.com/GameTechDev/PresentMon/blob/e13fce6acdb55a808fd8318175a56863e532d95f/PresentData/ETW/Microsoft_Windows_DxgKrnl.h), [DMA enqueue/completion semantics](https://github.com/GameTechDev/PresentMon/blob/e13fce6acdb55a808fd8318175a56863e532d95f/PresentData/PresentMonTraceConsumer.cpp), [FIFO model](https://github.com/GameTechDev/PresentMon/blob/e13fce6acdb55a808fd8318175a56863e532d95f/PresentData/GpuTrace.cpp). Copie locali in `sources/`; usati come riferimento, non eseguiti.
- Help delle CLI installate e artefatti grezzi del progetto. Ricerca mirata di skill ETW: nessuna specialistica pertinente agli strumenti disponibili; nessuna installazione di skill/plugin.

**Gate attuale:** non c'è un percorso modificabile giustificato. ETW non dà provenienza shader/PSO né distingue ALU/texture/banda. Non riaprire il PoC congelato e non patchare il gioco per inseguire questi vuoti.

Se in futuro si vuole attribuire il regime delle passive, la lacuna concreta è una misura **meno perturbante**, con caller sampled validati e controllo della perturbazione, oppure un'acquisizione GPU mirata per shader/PSO. Non ripetere automaticamente l'attuale profilo verbose. **Nessuna nuova cattura richiesta o avviata oggi**; nessuna modifica a gioco, driver, Registry, impostazioni, boot, sicurezza o cache AMD.
