# Handoff — ricerca AMD RDNA2 / Cyberpunk 2077

**Aggiornato: 2026-10-16, da Codex. Punto di ingresso per qualsiasi agente/harness.**
Questo documento riassume lo stato ricostruito dai file, non richiede accesso alla chat o a Claude.
Le misure sono del 3–8 settembre; recupero WPR il 26 settembre, analisi offline il 16 ottobre. Nessuna nuova cattura del gioco.

## Stato immediato e presa in carico

- Lorenzo ha comunicato che l'abbonamento Claude non è più attivo. **Il lavoro passa a Codex o al prossimo agente disponibile**: non avviare Claude, non aspettare sue risposte e non dipendere dalle vecchie pane Herdr.
- Il PoC sui sample è concluso e congelato. Le cinque run manuali Cyberpunk e Steel Nomad sono già stati eseguiti. Anche lo scaling fullscreen 1440p/1080p/720p/1440p è concluso.
- **La cattura WPR di Cyberpunk esiste già.** Il precedente `STATUS.md` diceva di aspettare il click, ma era stato scritto prima della cattura delle 22:28 dell'8 settembre. Il 26 settembre sono stati verificati ETL, metadata e risultato nativo e completato l'allineamento del benchmark.
- **Analisi offline WPR svolta il 16 ottobre, senza nuovi benchmark.** Orologi/finestra, CPU exclusive, scheduler e code GPU ora validati; report corrente: [OFFLINE_ATTRIBUTION_20261016.md](research/63_c2077_wpr_attribution/OFFLINE_ATTRIBUTION_20261016.md). Perturbazione di tracing rilevante osservata; caller sampled CPU e critical path completo non risolti. Non trasferire il regime della run profilata alle passive, né attribuire tutto il calo a WPR.
- **Direzione richiesta da Lorenzo: esperimenti concreti e reversibili sugli shader.** Accesso reale nella [fase 64](research/64_c2077_shader_access_20261016/STATUS.md), round-trip e canary `glass` validati nella [fase 65](research/65_c2077_dxil_roundtrip_20261016/STATUS.md). La canary cambia quattro soli operandi di output; repacking delle cache solo su copie di ricerca, non installato.
- **Autorizzazione loader/hooking ricevuta per il solo Cyberpunk; [fase 66](research/66_c2077_shader_loader_20261016/STATUS.md) installata, ora in OBSERVE (nessun override shader).** ReShade ufficiale 6.8.0 Full Add-on x64, SDK API 20; add-on locale con guard percorso/SHA EXE e bytecode pixel esatto. Crea PSO separate e redirige bind in memoria, senza sostituire cache o file originali. Cinque file iniziali aggiunti al bin/x64, più l'osservatore corrente; quello della fase 67 è archiviato/rimosso. Ripristino sul target reale verificato: 84 file originali, nomi e hash identici; poi reinstallato il medesimo pacchetto. **Control avviato manualmente, immagine normale confermata dall'utente e gioco chiuso.** Ultimo heartbeat PID 5396: 5 PSO create, 1044 bind, zero errori di clonazione; [control r1](research/66_c2077_shader_loader_20261016/runtime_control_r1/RESULT.md). **Canary r1 conclusa negativa:** utente riferisce nessuna superficie rosa, immagine invariata. Ultimo heartbeat PID 14612 poi chiuso: 5 PSO/2033 bind, zero errori clonazione; [risultato negativo](research/66_c2077_shader_loader_20261016/canary_r1/RESULT.md). Gate visivo non superato, causa non stabilita. Fase 67 conclusa: PID 11348 chiuso, anche dopo giro visuale zero bind/draw target osservati. Non insistere col vetro. Installato [catalogo readonly fase 68](research/68_c2077_backbuffer_catalog_20261016/STATUS.md), ShaderLab observe, vecchia sonda archiviata/rimossa. Attesa avvio manuale per identificare SHA di shader nei draw verso backbuffer reali, senza modificare shader. Bind non prova draw/frammenti visibili. WARN host di reference count/add-on caricati in uscita conservati, causa e exit code non validati. Nessun benchmark o speedup.
- Host ReShade `NotSigned`, setup con catena non attendibile localmente: limite registrato, nessun certificato/protezione modificati. Driver attuale letto **32.0.21045.11001**, diverso dal 32.0.21045.5002 di settembre: non riusare quelle baseline come confronto prestazionale attuale.

## Obiettivo finale e direzione

Trovare un'ottimizzazione reale, riproducibile e corretta del lavoro shader/pipeline DX12 su RX 6950 XT, capendo dove il software spreca tempo. Il nome della cartella `driver mod` non significa che vada patchato il driver: la ricerca si è spostata dalle leve del compilatore a trasformazioni degli shader applicativi, poi alla verifica su un gioco reale.

Un risultato positivo richiede un percorso costoso identificato, provenienza sorgente → bytecode → PSO eseguito, correttezza dell'immagine e confronto A/B rispetto al rumore misurato. Un risultato negativo documentato è valido; non forzare un miglioramento cambiando qualità, soglie o finestre a posteriori.

La direzione corrente, su richiesta di Lorenzo dopo il report WPR, è passare a esperimenti concreti sugli shader applicativi: accesso al DXIL reale, round-trip, sostituzione reversibile verificabile, poi una singola trasformazione con oracle/A-B. WPR resta una fonte CPU/queue già analizzata, non il prerequisito da riaprire all'infinito; da solo non identifica shader ottimizzabili o il limite ALU/texture/banda.

## Regole operative e preferenze di Lorenzo

- Continuare autonomamente con lettura, parsing, analisi, verifiche e lavoro locale autorizzato; fermarsi quando serve davvero un'azione manuale. Non limitarsi al report se esiste lavoro utile eseguibile.
- Computer Use è stato dismesso perché inaffidabile. Lorenzo avvia manualmente gioco e benchmark; l'agente gestisce strumenti, acquisizione e analisi. Il parsing dopo ogni run è autorizzato e supera la vecchia istruzione di attendere cinque run.
- Il benchmark dura circa **71 s percepiti dall'operatore**; la sequenza nativa misurata è circa **64,24 s**. Le catture includono margine per menu/caricamento: non tagliare i dati a 71 s arbitrariamente.
- Non modificare driver installati/package firmati, Registry, boot/sicurezza, impostazioni Adrenalin o cache. Nessuna interazione invasiva con Fortnite/Warzone/anti-cheat. Conservare raw, esclusioni, backup e risultati negativi.
- Eventuali interventi reversibili sul single-player richiedono prima candidato motivato, provenienza, backup/hash/manifest, ripristino verificabile e oracle/A-B. L'autonomia non equivale a un invito a fare injection o patch speculative. Eccezione autorizzata attuale: loader DX12 e add-on della fase 66 nel solo Cyberpunk, solo file nuovi, mai anti-cheat. Mode/rimozione a gioco chiuso, niente hot-unload.
- Prima delle prossime misure verificare ambiente e processi attuali: PID, impostazioni e stato admin del settembre 8 sono **storici**, non attestazioni della sessione attuale. Non fermare sessioni WPR/PresentMon altrui.
- Usare direttamente le CLI richieste (`codex`, `herdr`, ecc.); non cercarle nuovamente salvo errore, non creare Agent-Launcher. Claude ora escluso per richiesta dell'utente. Herdr e subagent sono strumenti opzionali, non prerequisiti per riprendere.

## Riassunto del percorso già svolto

| Fase | Risultato che conta oggi |
|---|---|
| Inventario e analisi driver | Mappati package, componenti e UMD DX12 `amdxc64.dll`. Il package 26.9.1 nella root **non coincide** col driver installato nelle misure. Documentate cache e superfici di configurazione senza patchare file firmati. |
| ETW e compilatore iniziali | Analisi Fortnite storica e prove controllate RGA. Il parser `AMD_SC_OPTIONS` è attivo, ma le 272 `SCOption_*` non sono impostabili attraverso i canali trovati: disponibili opzioni di dump, non una leva di tuning dimostrata. Non riaprire questo ramo senza nuove evidenze. |
| Laboratorio shader, fino a 2N | Costruiti strumenti di compilazione, ISA, microbench e misure runtime. Diverse conclusioni iniziali sono state corrette: proxy/microbench non provano un guadagno sul workload; vecchie A/B senza provenienza runtime non valgono come prova causale. |
| Audit e 2O | Riparata e verificata la catena build/bytecode/runtime/immagine. Corretta semantica dei counter: `TexUnitBusy` è massimo per CU, non media; due MRT non dimostrano overdraw 2×; multipass ammesso per lavoro aggregato, non singoli timing. Falsificata la tesi del solo throughput di filtraggio; ALU e texture risultano entrambe critiche nel sample studiato. |
| 2P/2Q, PoC MiniEngine/Sponza | `stack3_scalar`, 68 righe di diff HLSL: **Render Color −41,43%; frame GPU −24,47% misurato; −21,78% stima corretta per clock**, da non confondere. Correttezza float32 entro 7 ULP sul caso verificato, una componente bit-identica. Canary iniziale rotta dalla review e ricostruita con controllo positivo. Audit: 64 build, 422 run, 22 cicli senza discrepanze. |
| 2R e congelamento | Trasferimento a nBody riuscito come metodo, nessuna trasformazione accettata. Fasi 2P/2Q/2R congelate: non ritoccare per aumentare il numero. Il PoC è dipendente da scena/GPU/driver e non dimostra guadagni sui giochi. |
| 2T | 0 hit su 4 workload. Candidati corretti sotto soglia o candidati veloci non corretti; corretto pairing temporale che altrimenti avrebbe fabbricato un'accettazione. |
| 2U | 0 hit su 4; totale programma circa **1 hit su 9 workload distinti**. Ceiling gate e decomposizione evitano lavoro inutile. `shadow_tmax`, byte-identico e circa −1,8/−2,2%, resta respinto dalle soglie preregistrate. Il −41% del PoC è un outlier, non un rendimento atteso. |
| Cyberpunk baseline | Cinque run manuali, controlli macchina, parsing/allineamento nativo e inventario superficie mod. Nessuna mod applicata. |
| Cyberpunk scaling | Serie iniziale borderless inadeguata al confronto di risoluzione perché cambiava il present path. Rifatta in fullscreen; verdetto v2 concluso. |
| WPR CPU+GPU | Analisi offline 16 ottobre: clock/5304 frame validati; 444920 campioni CPU gioco; running di 34 thread concorde con xperf entro 0,5 µs; wait/signal reali; DMA FIFO/ownership/preemption ricostruiti. Tracing materialmente presente, nessun candidato di ottimizzazione; caller sampled/critical path e causa del calo rispetto alle passive restano aperti. |

I budget storici (ad esempio i 12 cicli di 2U, consumati) appartengono alle rispettive fasi: non considerarli un nuovo budget disponibile. Le vecchie checkbox di `PLAN.md` non sono tutte un backlog da eseguire oggi.

## Cyberpunk: risultati acquisiti e limiti

### Baseline borderless e controlli, 7 settembre

Directory: [research/60_c2077_20260907_codex](research/60_c2077_20260907_codex).

- `manual_r1`…`manual_r5`: 113,0262 / 112,9794 / 112,9032 / 112,9315 / 113,0928 FPS. Media **112,9866**, SD campionaria **0,07564**, CV **0,06695%**. Fonte aggiornata: [manual_five_statistics.json](research/60_c2077_20260907_codex/manual_five_statistics.json).
- La quinta run segue un riavvio del gioco; non assumere identica distribuzione delle code. Gli FPS medi sono molto stabili, lo 0,1% low è più variabile. MDD descrittiva/di pianificazione non equivale a soglia di accettazione di una futura variante.
- `bench_r2` circa 96 FPS è una cattura completa separata; causa della differenza non isolata. **96 → 113 non è un'ottimizzazione**. Preflight/menu-only e schema probe restano esclusi e conservati.
- Superposition: cinque score, media 17138,4, CV 0,0954%; controllo macchina, non workload shader DX12 primario.
- Steel Nomad pre/post: **4184 → 4189**, FPS **41,849308 → 41,897465**. Score +0,1195%; gate verso riferimenti più vecchi fallito, quindi nessun pooling storico. Questi endpoint non garantiscono stabilità a ogni minuto né coprono la successiva run 5.
- Le vecchie metriche full della baseline usavano N/(ultimo−primo timestamp). Lo scaling v2 usa N intervalli completi: non mescolare silenziosamente le formule.

### Scaling fullscreen, 8 settembre — verdetto corrente

Fonte: [VERDICT_V2.md](research/62_c2077_fullscreen_scaling/VERDICT_V2.md), con [scaling_analysis_v2.json](research/62_c2077_fullscreen_scaling/scaling_analysis_v2.json).

| Run | FPS | Frame medio ms | GPU busy ms | GPU wait ms |
|---|---:|---:|---:|---:|
| fs1440_r1 | 112,368 | 8,8994 | 8,7747 | 0,0988 |
| fs1080_r1 | 163,965 | 6,0989 | 5,8543 | 0,1960 |
| fs720_r1 | 185,826 | 5,3814 | 4,1720 | 1,1069 |
| fs1440_r2 | 111,905 | 8,9361 | 8,8007 | 0,1076 |

- PresentMode identico: Hardware Independent Flip, fullscreen `windowMode=2`; deriva ancore 1440p **−0,411%**, entro il gate storico 0,5%. Una sola run per risoluzione bassa: niente CI o MDD trasferita dalla baseline borderless.
- **1440p prevalentemente GPU-bound: strong. 720p limitato prevalentemente da alimentazione/pacing non-GPU, compatibile con CPU/submission: probable.** CPUBusy include pacing; non distingue CPU gioco da driver. Rapporti busy/frame non sono utilizzo hardware misurato.
- A 720p i tre blocchi differiscono di un frame: finestra 6415–18356, tolleranza ±1 dichiarata e sensibilità verificata. Non spacciarla per identità esatta frame-per-frame. Gli altri casi usano concordanza stretta.
- Correzioni v2: durata su N intervalli; QPC usato per continuità, non per trovare la finestra con la sola durata; il localizzatore duration-only è stato smentito. 33 hash storici preservati.
- **Ritirate** le interpretazioni del termine costante 4,81–5,38 ms come costo CPU e di 186 FPS come tetto rigido. Il guadagno abbassando la risoluzione non è né speedup shader ottenuto né suo upper bound.

## WPR: ciò che è già pronto e ciò che ho ripreso

Percorso: [research/63_c2077_wpr_attribution](research/63_c2077_wpr_attribution).

### Cattura reale recuperata, non da ripetere preventivamente

- ETL: `fs1440_r1/c2077_fs1440_attribution-run1-20260908-222856-633.etl`, **21.098.397.696 byte**; log [capture_r1.log](research/63_c2077_wpr_attribution/capture_r1.log).
- Metadata originali: suffisso `-meta.json`; PID storico **16316**; PresentMon exit 0; **18.405 righe dati** (18.406 inclusa intestazione); sampling preservato a **1 ms**. WPR ha salvato correttamente la traccia. Non usare quel PID per azioni sulla sessione attuale.
- Risultato nativo originale: `C:\Users\Lorenzo\Documents\CD Projekt Red\Cyberpunk 2077\benchmarkResults\benchmark_2026-09-08_22-29-31`.
- Il 26 settembre ho creato copie normalizzate `metadata.json` e `presentmon.csv` per riusare il parser esistente senza cambiarlo. Originali intatti. Copie di `frames.csv` e `summary.json` nativi e hash delle sorgenti sono ora conservati in [native_analysis_v2](research/63_c2077_wpr_attribution/fs1440_r1/native_analysis_v2).
- **Allineamento stretto PASS:** 5304 frame, righe dati zero-based **7745–13048**, tre blocchi concordi, continuità QPC verificata. **64,2440852 s / 82,56013 FPS**, contro 82,56697 FPS nativi; differenza −0,00829%. Native 2560×1440, windowMode 2, RT/upscaling/FG off.
- PresentMode verificato nella finestra: **Hardware: Independent Flip su tutti i 5304 frame**. Verificati anche uguaglianza byte delle copie normalizzate e hash sorgenti registrati dal parser.
- QPC della finestra: **32466592,8518 → 32530836,9370 ms**, fine esclusiva dopo l'ultimo intervallo. Conversione ETL validata il 16 ottobre: **[49,9097700, 114,1538552) s**; origine raw QPC 324166830818, frequenza 10 MHz. Tutti i 5304 stop DXGI abbinati in sequenza contigua; timestamp online/ETL non bit-identici, residui 0,2–12,9 µs, senza fitting dell'offset.
- `xperf -a tracestats`: exit 0, **zero Lost Buffers / Lost Events**, controllo `etw_analyze.check_loss` PASS. Evidenza [trace_validation.txt](research/63_c2077_wpr_attribution/fs1440_r1/trace_validation.txt). Intervallo ETL 177,2226409 s.
- La run profilata è molto più lenta delle passive (~82,56 vs ~112 FPS). **Perturbazione/condizioni da quantificare: non attribuire automaticamente tutta la differenza a WPR, non usare questa run come braccio A/B e non trasferirne il regime alle passive senza verifica.**

### Harness e verifiche già disponibili

- [capture_etw.ps1](tools/capture_etw.ps1): metriche v2, QPC ms, quoting dei percorsi, timeout/exit verificati, sessioni/output unici, niente stop di sessioni altrui; sampling preservato per default, eventuale valore esplicito ripristinato; ETL incompleto salvato in caso di errore.
- [c2077_native.py](tools/c2077_native.py): allineamento e validazione a tre blocchi, riscontro nativo FPS/durata, controllo QPC, incertezza ±1 solo se esplicitamente autorizzata e giustificata dai dati.
- [etw_analyze.py](tools/etw_analyze.py): controllo perdite e aggregazione streaming CPU per modulo. **Non completa da solo l'attribuzione richiesta**: mancano il filtro della finestra nativa e la ricostruzione causale stack/queue.
- Nuova analisi: [etl_extract.cpp](tools/etl_extract.cpp), [c2077_etw_offline.py](tools/c2077_etw_offline.py), [c2077_gpu_queue.py](tools/c2077_gpu_queue.py), [c2077_etw_check.py](tools/c2077_etw_check.py). Input/output e comandi in [offline_20261016/README.md](research/63_c2077_wpr_attribution/fs1440_r1/offline_20261016/README.md); usare solo i risultati canonici, non i tentativi superseded.
- Rieseguiti il 16 ottobre, tutti PASS: `pwsh -NoProfile -File tools/test_capture_etw.ps1`, `python -B tools/c2077_native.py`, `python -B tools/etw_analyze.py --selfcheck`; PASS anche selfcheck dei nuovi reader/parser e confronti reali raw/xperf/PresentMon.
- Lo smoke storico ha verificato stack CPU e DxgKrnl. Le sue statistiche non sono quelle del benchmark. WPA esporta stack precise/CSwitch, ma sampled export fermo spesso a `[Root]`; i GUID GPU senza preset non producono un export GPU valido. Non dichiarare già risolti questi limiti.

### Risultati aggiunti il 16 ottobre

- CPU exclusive del gioco: 48,80% eseguibile, 28,40% ntoskrnl, 8,44% ntdll, 7,87% amdxc64, 1,23% D3D12Core. Percentuali di campioni del processo, non frazioni del frame critico. Kernel/DPC non equiparati al driver UMD.
- Stack precisi: WaitForSingleObjectEx e ReleaseSemaphore osservati in milioni di eventi; nessuna prova che la sincronizzazione sia eliminabile. Il TID storico 2700 è running per 61,518 s su 64,244 s; non identificato come critical thread delle passive.
- GPU: unione DMA FIFO del gioco **75,7717%** della finestra profilata; 93450 start DMA, 2714 segmenti preempted, nessun timeout. Non è occupancy hardware. Tutti i 436393 QueuePacket Start target mappati concordano sul proprietario 16316; 18 eventi DEVICE_COMMAND_BUFFER separati non mappati.
- Layout corretti: **244 scalar WAIT=4**, **245 array SIGNAL=5**; 52876 Unwait validati. Conservati ma scartati i replay iniziali con enum invertito/join di puntatori riusati.
- ETL intero: 439 milioni di eventi. Nella finestra campionati 13,964 CPU-s in simboli Etw*/Etwp*, più 27,277 CPU-s in due helper StackWalks espliciti. Non è quantificato il contributo causale al calo di FPS.
- **Caller sampled CPU non validati:** filtri SampledProfile/SampleProf vuoti; anche lo smoke storico senza filtro PID non risolve. Il filtro ampio Profile è ambiguo e respinto come sorgente di costi/caller CPU. Stack CSwitch/ReadyThread invece utilizzabili.
- Hash di PM/metadata/native invariati; ETL SHA-256 `e2e4ae42ccb8bb1e41d8717513abe1bb469d6e4969ef1b8e363f229a5b21e739`. Nessuna modifica al sistema o ai giochi.

## Prossima decisione e lacune concrete

1. **Priorità attuale: catalogo da uso reale della [fase 68](research/68_c2077_backbuffer_catalog_20261016/STATUS.md).** Il giro visuale fase 67 non ha fatto comparire bind/draw target; processo 11348 chiuso. ShaderLab ora observe, zero shader override. Catalogo readonly installato, vecchia sonda rimossa/archiviata. Attendere normale avvio manuale e leggere nuovi log/PID `backbuffer` con `python -B tools/c2077_shader_loader.py status`. Selezionare da identità RTV0/backbuffer e draw/submission, poi SHA esatto nell'indice offline (8340 unici/19950 occorrenze), non dai nomi. GPU completion/visibilità/costo non provati dai counter; compute/copie/bundle sono limiti. Nessun benchmark/cache clearing/nuove canary prima di selezione e oracle. Uninstall a processo chiuso comprende nuovo add-on/log propri.
2. Il report WPR corrente resta acquisito: non rifare allineamento, scaling o benchmark già completati. Un eventuale approfondimento CPU è secondario alla nuova direzione; i **caller sampled CPU** restano non validati, non usare `Profile` ambiguo né `[Root]`. Critical path completo e soddisfacimento causale delle fence non sono dimostrati dagli aggregati.
3. La traccia profilata non identifica il regime delle passive né shader/PSO ottimizzabili. Un'eventuale misura futura deve essere meno perturbante e controllarne l'effetto; non ripetere automaticamente lo stesso profilo verbose. Solo dopo approvazione per la nuova acquisizione.
4. **Nessun tuning prestazionale validato.** La canary è diagnostica e altera intenzionalmente l'immagine: non misurarla come ottimizzazione. Una futura trasformazione richiede shader/PSO realmente usato, oracle, preregistrazione, backup/ripristino e A/B. Non riaprire il PoC congelato né fabbricare uno speedup.

RGP è una possibile strada successiva per dettaglio GPU, non una cattura Cyberpunk già disponibile. I suoi vincoli di clock/profiling e sincronizzazione vanno valutati separatamente; non eseguire script che cambiano Registry/gruppi come espediente automatico.

## Mappa delle fonti e documenti superati

Ordine di lettura consigliato:

1. Questo file, [fase 68 — catalogo corrente](research/68_c2077_backbuffer_catalog_20261016/STATUS.md) e preregistrazione, [fase 67 — diagnosi conclusa](research/67_c2077_canary_probe_20261016/STATUS.md) e preregistrazione, poi [fase 66 — loader](research/66_c2077_shader_loader_20261016/STATUS.md) e relativa README/preregistrazione, [fase 65 — canary offline](research/65_c2077_dxil_roundtrip_20261016/STATUS.md), [accesso shader 64](research/64_c2077_shader_access_20261016/STATUS.md), poi [report WPR](research/63_c2077_wpr_attribution/OFFLINE_ATTRIBUTION_20261016.md) e [STATUS WPR](research/63_c2077_wpr_attribution/STATUS.md).
2. [Verdetto fullscreen v2](research/62_c2077_fullscreen_scaling/VERDICT_V2.md).
3. [PoC congelato](research/POC_FROZEN.md), [risultati 2T](research/PHASE_2T_RESULTS.md), [risultati 2U](research/PHASE_2U_RESULTS.md), [memoria delle misure](research/MEASUREMENT_MEMORY.csv).
4. [PLAN.md](PLAN.md), [C2077_WORKLOG.md](research/C2077_WORKLOG.md), [AUTONOMOUS_LOG.md](research/AUTONOMOUS_LOG.md) per la cronologia; [metodo metriche](research/04_benchmarks/analysis/METHOD.md).

Attenzione alle fonti storiche:

- `LAST PROMPT.md` **attualmente** contiene la richiesta di rifare lo scaling in fullscreen: completata. Non contiene più tutti i precedenti prompt operativi.
- `CLAUDE.md` contiene contesto e vincoli iniziali, ma alcune indicazioni di fase/installazione/dependency sono vecchie. Il nome del file non obbliga a usare Claude.
- `research/CODEX_HANDOFF_AUDIT.md` è l'audit del 5 settembre, non questo handoff: le sue correzioni sono importanti, ma diversi blocchi sono stati poi risolti da 2O e fasi successive.
- Il corpo di `research/C2077_FINAL_REPORT.md` e parti dei worklog dicono ancora che manca la run 5. **È superato** da `manual_five_statistics.json` e dai dati `manual_r5`. La baseline borderless non va mescolata con fullscreen.
- L'indicazione WPR «in attesa del click» era superata dagli artefatti delle 22:28. Nessuna seconda cattura va richiesta solo perché quella frase è rimasta nel vecchio stato.

## Portabilità e ripresa su altro harness

Root attuale: `C:\Users\Lorenzo\Downloads\driver mod`. I link di questo file sono relativi. Trasferire **almeno `HANDOFF.md`, `PLAN.md`, `CLAUDE.md`, `LAST PROMPT.md`, `tools/` e `research/`**, preservando raw, JSON, hash, backup ed ETL/PDB necessari. Il solo Markdown dà contesto, non sostituisce gli artefatti per riprodurre le misure.

Dipendenze locali storiche da ricontrollare se si cambia macchina:

- PresentMon installato verificato il 16 ottobre: `C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication\PresentMon-2.6.0-x64.exe`; le misure storiche usavano 2.5.1. Copia 2.5.1 ufficiale firmata Intel recuperata solo per replay offline nella directory `offline_20261016`.
- WPR/WPT: `C:\Windows\System32\wpr.exe`, `C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\` (`xperf`, WPA, WPAExporter).
- Python con numpy/pandas/scipy; PowerShell `pwsh`; tool AMD nella cartella RadeonDeveloperToolSuite della root.
- Cyberpunk GOG: `E:\GOG\Cyberpunk 2077`; risultati nativi in Documents/CD Projekt Red; impostazioni in `%LOCALAPPDATA%\CD Projekt Red\Cyberpunk 2077\UserSettings.json`.
- Alcuni sample/build storici erano in `%TEMP%\claude\src\...`: non considerarli versionati o trasferiti solo perché `research/` esiste. Verificare dipendenze e provenienza prima di riprodurre build congelate.
- Hardware delle misure: RX 6950 XT, Ryzen 7 5800X3D, 32 GB, Windows 11 build 26200; driver 32.0.21045.5002 / Radeon 26.8.1. Non dedurre il driver attuale dall'installer 26.9.1 nella root.

Prompt minimo per riprendere:

> Leggi HANDOFF.md e research/68_c2077_backbuffer_catalog_20261016/STATUS.md. Control normale, canary senza marker; fase 67 senza bind/draw target anche dopo giro visuale, PID 11348 chiuso. Non insistere con quel vetro. Ora ShaderLab observe e nuovo catalogo readonly installato (vecchia sonda archiviata/rimossa). Attendi avvio manuale normale e nuovi log backbuffer/PID, identifica shader dai draw verso risorse swapchain e SHA esatto offline; non scegliere prima dai nomi. Nessuna shader mod attiva, nessun benchmark/WPR/cache clearing/driver patch/anti-cheat. Counter CPU non provano GPU completion/visibilità/FPS. Uninstall manifest-owned include nuovo add-on/log. Non avviare Claude; conserva raw e aggiorna HANDOFF/PLAN.

## Regola di manutenzione

Aggiornare questo stesso file a ogni traguardo o cambio di direzione: data, artefatti prodotti, controlli effettivamente eseguiti, conclusioni/limiti, cosa resta e prossima azione. Conservare i dettagli nei report di fase e linkarli; evitare nuovi handoff concorrenti. Non segnare completata un'analisi solo perché la cattura o lo smoke sono riusciti.
