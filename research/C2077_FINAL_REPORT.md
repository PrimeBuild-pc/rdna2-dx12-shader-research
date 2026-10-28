# Cyberpunk 2077 — report consolidato della sessione 2026-09-07

> **Aggiornamento 2026-09-08:** la nuova serie fullscreen è chiusa nel
> [verdetto v2](62_c2077_fullscreen_scaling/VERDICT_V2.md): GPU dominante a 1440p,
> probabile limite CPU/submission a 720p; CPU vs driver non attribuiti. Le quattro
> analisi v2 preservano i dati precedenti e dichiarano l'incertezza di un frame a 720p.
> Il testo seguente resta il report storico della sessione borderless, non lo stato corrente.

**Stato: analisi passiva completata sui dati disponibili; milestone non ancora chiusa.** Cinque catture contengono un benchmark completo verificato, ma solo quattro appartengono al protocollo manuale omogeneo. Manca una quinta run manuale omogenea. Steel Nomad post-sessione è stato acquisito e verificato nel successivo aggiornamento. Nessun guadagno da ottimizzazione dimostrato; nessuna mod applicata.

## Configurazione e autorità

GOG single-player, Cyberpunk 2.31, DX12, RX 6950 XT / Ryzen 7 5800X3D / 32 GB, Windows 11 Pro 10.0.26200, Radeon 26.8.1. 2560×1440 borderless, Custom, texture High e qualità avanzate mostrate High; crowd High, FOV 100, anisotropia 16. VSync/cap/upscaling/dynamic resolution/frame generation/RT/PT disattivati. Film grain, aberrazione cromatica, DOF, lens flare, motion blur e vignette off; contact shadows e improved facial lighting on. Configurazione verificata da screenshot, risultati nativi e hash UserSettings.

LAST PROMPT.md e istruzioni successive dell’utente governano la sessione: parsing dopo ogni run autorizzato; Computer Use dismesso su richiesta. Phase 2U resta autorevole. PoC congelato: Render Color −41,43%, GPU frame −24,47% misurato, −21,78% stima clock-corrected; hit rate circa 1/9. Nessuna riapertura del tuning driver o delle fasi concluse.

## Controlli macchina

| Superposition 4K Optimized / DirectX | Score | Min FPS | Avg FPS | Max FPS |
|---|---:|---:|---:|---:|
| 1 | 17166 | 102.41 | 128.40 | 157.69 |
| 2 | 17139 | 108.54 | 128.20 | 157.43 |
| 3 | 17124 | 108.03 | 128.09 | 157.40 |
| 4 | 17130 | 105.21 | 128.12 | 157.39 |
| 5 | 17133 | 106.60 | 128.15 | 157.85 |

Score medio Superposition 17138.4; CV campionario 0.0954%. Screenshot e SHA-256 in experiment_metadata.json. Temperatura GPU non disponibile negli screenshot.

Steel Nomad pre: **4184 punti / 41,849308 FPS**. Post: **4189 punti / 41,897465 FPS**. Δ score **+0.1195%**, Δ FPS **+0.1151%**; risultati nativi SUCCESS, medesimo test DX12 v1.0 e configurazione, differisce solo il percorso del risultato. Copie e hash in steel_nomad_post/native_evidence; dati in steel_nomad_post/analysis.json. Il pre differisce di oltre 0,5% dai riferimenti storici 4139/4137: gate di comparabilità storica FAIL, soglia invariata. I due controlli pre/post sono coerenti entro il riferimento 0,5%; non dimostrano l’assenza di variazioni durante ogni minuto della sessione. Nessuna modifica ai controlli. Non trovato un eseguibile di comando dedicato nell’installazione locale; GUI non utilizzata dopo l’istruzione dell’utente.

## Catture, provenance e finestre

PresentMon console 2.5.1, --v2_metrics, filtro Cyberpunk2077.exe, 150 secondi per le run valide. Il tempo di registrazione comprende menu/caricamento/risultati. Il gioco misura circa 64,25 secondi di frame del benchmark; non è il tempo totale percepito dall’avvio.

Ogni cattura valida ha un solo PID/swapchain. I frames.csv nativi individuano la sequenza completa nel raw ETW mediante correlazione del pattern temporale; tre blocchi indipendenti (inizio/centro/fine) devono concordare sullo stesso offset. Si conservano tutti i frame interni, anche lenti. Il numero di frame coincide con il risultato nativo e gli FPS differiscono meno dello 0,018%. Questo supporta l’allineamento, non costituisce una prova universale dell’assenza di eventi ETW persi.

Due finestre distinte: **full_benchmark**, intero benchmark allineato; **standard_trimmed_window**, medesima traccia con regola pmparse storica di esclusione dei primi 2 s e dell’ultimo secondo incompleto. Nessuna modifica a formule FPS/low/stutter. Le tabelle seguenti usano full_benchmark; i valori del trim storico restano separati nel JSON.

| Cattura | Frame | FPS PM | FPS gioco | FT medio / mediano ms | p95 / p99 ms | 1% / 0,1% low FPS | Spike |
|---|---:|---:|---:|---:|---:|---:|---:|
| bench_r2 | 6167 | 96.008 | 95.992 | 10.417 / 10.374 | 12.522 / 13.638 | 67.897 / 57.912 | 0 |
| manual_r1 | 7261 | 113.026 | 113.009 | 8.849 / 8.818 | 10.752 / 11.787 | 78.601 / 68.686 | 0 |
| manual_r2 | 7259 | 112.979 | 112.965 | 8.852 / 8.829 | 10.814 / 12.049 | 76.642 / 67.614 | 0 |
| manual_r3 | 7253 | 112.903 | 112.888 | 8.858 / 8.824 | 10.907 / 11.983 | 78.030 / 71.887 | 0 |
| manual_r4 | 7255 | 112.931 | 112.917 | 8.856 / 8.812 | 10.856 / 12.129 | 75.434 / 65.374 | 0 |

I low principali sono time-integrated, secondo METHOD.md. Anche i low percentili sono salvati. Spike: frametime >2× mediana locale centrata di 21 frame e almeno +2 ms; severe: >3× mediana e ≥8 ms. Zero eventi secondo questa definizione non significa assenza assoluta di ogni irregolarità percepibile.

**bench_r2 è una cattura valida, ma appartiene al workflow Computer Use e misura ~96 FPS.** Le impostazioni registrate sono uguali; causa della differenza non identificata. Overhead di automazione/cattura UI, condizioni di presentazione, carico e clock restano ipotesi non isolate. La differenza verso ~113 FPS non è un miglioramento ottenuto da una modifica. Non si elimina il dato e non si uniscono silenziosamente le distribuzioni.

Unione diagnostica delle cinque catture: 109.570 FPS, CV 6.919%. Questo numero descrive condizioni miste, non la baseline omogenea accettata.

Esclusi: bench_r1 (preflight menu/pending RT, nessun benchmark), schema_probe (verifica formato), bench_r3 (menu), bench_r4 (600 s senza nuovo risultato nativo). Dati storici 60_c2077/bench_r1 e screenshot 14:22 preservati e non aggregati.

## Rumore delle quattro run manuali

| Metrica | Media | SD campionaria | CV % |
|---|---:|---:|---:|
| avg_fps | 112.9601 | 0.0542 | 0.0479 |
| ft_avg_ms | 8.8540 | 0.0042 | 0.0478 |
| ft_median_ms | 8.8205 | 0.0073 | 0.0822 |
| ft_p95_ms | 10.8322 | 0.0660 | 0.6091 |
| ft_p99_ms | 11.9871 | 0.1459 | 1.2174 |
| fps_1pct_low_time | 77.1766 | 1.4239 | 1.8450 |
| fps_01pct_low_time | 68.3901 | 2.7090 | 3.9611 |

Trim storico, media FPS 113.0976, CV 0.0415%. Varianze e range sono in consolidated_analysis.json. Quattro run omogenee non soddisfano ancora il minimo di cinque per la baseline; la bassa dispersione degli FPS medi non rende altrettanto precise le code 1%/0,1%. Nessuna soglia di acceptance è stata cambiata o ricavata retroattivamente da questi numeri.

## Profiling, bottleneck e ceiling

Nelle run manuali GPUBusy medio è 8,7196–8,7246 ms, a fronte di frametime medio 8,8489–8,8585 ms: rapporto 98,47–98,59%. GPUWait medio 0,0996–0,1085 ms. **Classificazione: forte indizio di prevalenza del lavoro GPU nel benchmark; limite shader/ALU/banda/texture/ROP non risolto.** CPUBusy è quasi uguale al frametime per pacing; confrontarlo direttamente con GPUBusy non prova che il carico sia CPU-bound.

Mancano clock, temperatura, potenza, occupancy, stall counters, timing per pass e provenienza degli shader runtime. PresentMon non determina quale componente del lavoro GPU sia riducibile mantenendo l’immagine identica. La prima cattura mostra GPUWait maggiore, ma non è un intervento A/B capace di attribuirne la causa.

**Ceiling shader-side: non quantificabile con questi dati.** Il rapporto GPU busy/frame non misura il margine di ottimizzazione. In particolare, il residuo ~1,5% NON è un tetto al guadagno shader e GPU busy ~98,5% NON è il guadagno ottenibile. Per un modello condizionale T′ = max(C, G·(1−f·r)) servono frazione critica modificabile f, riduzione corretta r e vincolo CPU C: qui non sono misurati. Nessuna percentuale di speedup sostenuta dai dati.

RGP può aggiungere dettaglio hardware e richiede un profilo apposito tramite Radeon Developer Panel/Service; non è stato acquisito su Cyberpunk in questa sessione. Non viene affermato che richieda necessariamente una modifica del Registry: la compatibilità con i vincoli della sessione resta da verificare prima di un’eventuale cattura. Nessun driver experiment o clock override eseguito. [Documentazione AMD](https://gpuopen.com/manuals/rdp_manual/).

## Superficie modificabile e decisione

Inventario locale: tools/redmod/bin/redMod.exe, script e tweaks REDmod; engine/shader_final.cache e staticshader_final.cache; file rendering.ini con parametro DecalsHideDistance. Directory mods con sola .stub. La ricerca dei nomi non trova file .hlsl/.glsl/.dxil/.cso autonomi: non prova che i contenitori siano privi di shader. Hash e dimensioni finali in surface_inventory.json; nessun contenitore decodificato o sostituito.

REDmod offre ufficialmente modding di script, suoni, animazioni e contenuti; la sua presenza non dimostra una catena source→bytecode→PSO per gli shader costosi di questa scena. [CD PROJEKT RED](https://www.cyberpunk.net/en/modding-support). Ridurre distanza decals/qualità o sostituire asset può cambiare l’output: non è un’ottimizzazione esatta automaticamente accettabile.

**Decisione: nessun intervento invasivo giustificato.** Non è stata identificata una trasformazione concreta con headroom misurato, provenienza runtime e oracle di correttezza. Nessuna injection o mod forzata per ottenere un risultato positivo. Non si conclude che qualsiasi ottimizzazione di Cyberpunk sia impossibile.

## Correctness, A/B e ripristino

Correctness della misura: raw intatti, numero di frame nativi verificato, allineamento indipendente a blocchi, riscontro FPS/durata, impostazioni e hash invariati. Correctness di una trasformazione: non applicabile, nessuna variante prodotta. Nessun oracle pixel-wise deterministico è stato costruito. A/B di ottimizzazione: non eseguito; le ripetizioni sono baseline/A-A descrittive.

UserSettings SHA-256 prima e dopo: `f26e59eaf9dedd486c5417e2bdcb1c0de8840a3dbb0dbe69d454617b4aa36f01`. Copia originale in UserSettings.before.json. Nessuna scrittura dell’agente a file del gioco, Registry, driver, sicurezza o cache; le scritture native del gioco non vengono chiamate modifiche dell’agente. Nessun ripristino di mod necessario e nessun hash pre-modifica inventato: surface_inventory.json è solo inventario finale osservato.

Modifiche al tooling del progetto: capture_game.py usa console v2 e stampa il segnale per l’avvio manuale; pmparse.py aggiunge alias esatti del formato console v1 senza equiparare msGPUActive a GPUBusy; c2077_native.py allinea le tracce native e riusa le metriche esistenti. Backup iniziali in questa sessione. Selfcheck parser e allineamento PASS; regressione delle 14 catture storiche con frame identici documentata in parser_regression.json. Raw, prove e report storici preservati.

## Falsi positivi fermati e limiti

- Header console v1 incompatibile con le colonne GPU attese: corretto prima delle misure utilizzabili.
- Selettore basato solo sulla durata avrebbe selezionato il menu: sostituito nel percorso operativo dall’allineamento alla traccia nativa.
- Pending RT accidentale nel preflight: mai applicato; nessuna run baseline eseguita con quel pending, ripristino osservato e hash invariato.
- Auto-review ha respinto input GUI non ritenuti verificati: nessun aggiramento; passaggio manuale richiesto dall’utente.
- Miglioramento apparente 96→113 FPS: non attribuito a ottimizzazione.
- Cinque catture complete non equivalgono a cinque repliche omogenee; controllo post ora verificato, quinta replica manuale ancora mancante.
- Nessun percorso gameplay secondario: rappresentatività oltre il benchmark non testata. Fortnite/Warzone non aperti né modificati.

## Cosa è dimostrato e NEXT RECOMMENDED ACTION

Dimostrato: quattro benchmark manuali ripetibili a ~112,96 FPS, catture complete verificabili e pipeline di parsing riutilizzabile; configurazione invariata; forte componente temporale GPU. Non dimostrato: baseline omogenea ≥5, bottleneck microarchitetturale, ceiling shader, guadagno/correctness di una mod, causa del run iniziale lento.

1. Alla prossima apertura manuale di Cyberpunk: una run aggiuntiva manual_r5 con le stesse impostazioni. Poiché il gioco viene chiuso, registrare il riavvio come nuovo sottogruppo e verificare comparabilità, senza presumere che una sola misura attraverso il riavvio basti.
2. Steel Nomad post **completato**: 4189 contro 4184, +0,1195%; condizioni del test uguali. Il risultato non isola la causa del precedente Cyberpunk da 96 FPS.
3. Solo dopo la chiusura dei controlli, valutare una cattura hardware separata per attribuire il costo ai pass, se ottenibile entro i vincoli. Nessuna mod prima di headroom e oracle adeguati.

Il lavoro offline disponibile è consolidato. Lo stato resta esplicitamente aperto per le acquisizioni manuali mancanti; non è un report di ottimizzazione riuscita.


## Aggiornamento — Steel Nomad post-sessione verificato

Risultato nativo terminato alle 18:26:39 del 2026-09-07. Non serve uno screenshot aggiuntivo: gli archivi .3dmark-result pre/post sono stati copiati e verificati. La cattura ETW contiene 2684 righe e circa 12,8 s di inizializzazione; la media sull’intero CSV confonderebbe caricamento e workload. La sezione a regime è diagnostica e non coincide esattamente con tutti i 2513 campioni FPS nativi: il confronto di controllo usa gli score/FPS nativi, non un taglio scelto per ottenere un punteggio desiderato.

Nessuno shader Cyberpunk è stato modificato o migliorato. Non esiste ancora una variante da sottoporre ad A/B. Il prossimo passo di ottimizzazione richiede attribuzione del costo a pass/shader e un oracle di correttezza; altre ripetizioni identiche da sole non forniscono questa informazione. La quinta run manuale riguarda soltanto il completamento della baseline prevista.
