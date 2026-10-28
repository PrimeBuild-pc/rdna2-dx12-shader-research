# Cyberpunk fullscreen scaling — verdetto v2

## Verdetto

**1440p prevalentemente GPU-bound (evidenza forte); 720p limitato soprattutto da
alimentazione/pacing non-GPU, compatibile con CPU/submission (probabile).
Questi CSV NON separano CPU del gioco da driver, né dimostrano un difetto del driver.**

La GPU occupa circa il 98.6% del frametime a 1440p
contro il 77.5% a 720p; GPUWait cresce di
5.65 volte rispetto al 1080p. Sono rapporti di timing PresentMon,
NON utilizzo device misurato: GPUWait non è tutto l'idle globale, CPUBusy non è campionamento
CPU e può includere pacing/back-pressure. Il cambio di regime è supportato anche dallo
scaling a present path invariato, non dalla sola disuguaglianza CPUBusy > GPUBusy.

## Dati completi, senza trim

| Run | FPS | Frame ms | GPUBusy ms | CPUBusy ms | GPUWait ms | CPUWait ms |
|---|---:|---:|---:|---:|---:|---:|
| fs1440_r1 | 112.368 | 8.8994 | 8.7747 | 8.7430 | 0.0988 | 0.1564 |
| fs1080_r1 | 163.965 | 6.0989 | 5.8543 | 5.9392 | 0.1960 | 0.1597 |
| fs720_r1 | 185.826 | 5.3814 | 4.1720 | 5.2297 | 1.1069 | 0.1517 |
| fs1440_r2 | 111.905 | 8.9361 | 8.8007 | 8.7801 | 0.1076 | 0.1560 |

| Run | p95 ms | p99 ms | 1% low FPS | 0,1% low FPS | Spike | Severi |
|---|---:|---:|---:|---:|---:|---:|
| fs1440_r1 | 10.717 | 11.776 | 75.13 | 60.68 | 1 | 0 |
| fs1080_r1 | 8.069 | 9.032 | 99.09 | 84.56 | 0 | 0 |
| fs720_r1 | 8.138 | 9.393 | 95.61 | 82.42 | 2 | 0 |
| fs1440_r2 | 11.045 | 12.211 | 74.85 | 65.54 | 0 | 0 |

Low = reciproco del tempo medio dei frame peggiori che coprono l'1% / 0,1% del tempo
totale (definizione pmparse). Spike: frame > 2x mediana locale centrata di 21 frame E
almeno 2 ms oltre la mediana; severo: > 3x mediana E almeno 8 ms assoluti.
Le finestre storiche tagliate restano separate e mantengono la definizione legacy N/(tultimo-tprimo).
Le analisi v2 complete usano N/somma degli N intervalli.

## Gate e provenienza

Tutte e quattro: 100% Hardware: Independent Flip, tearing=1, SyncInterval=0,
windowMode=2, stesso PID e swapchain, 360 Hz prima/dopo nei metadata. I campi dei summary
nativi coincidono salvo risoluzione e risultati; non sono una verifica di impostazioni
che i summary non registrano. PresentMon exit 0, conteggi CSV verificati.
Deriva FPS 1440p r2/r1 **-0.411%**, entro il gate preesistente di 0,5%.
Due ancore non provano deriva monotona né misurano separatamente rumore e deriva;
n=1 a 1080/720p, niente intervalli di confidenza run-to-run né MDE preso dalla serie borderless.
Nessun fit include la vecchia baseline borderless. Telemetria clock/termica assente.

33 hash di raw, risultati nativi, analisi storiche e pmparse verificati invariati.
Backup dello script originale e proposta precedente in `v2_provenance/`.
Ogni `native_analysis_v2/analysis.json` contiene hash input/codice e controlli di allineamento.

## Diagnosi dell'errore e correzioni effettive

Il benchmark nativo del 720p è `benchmark_2026-09-08_21-08-37` (11942 frame).
Riprodotto il difetto originale: picco globale **6415**, primo blocco **6414**,
blocchi centrale/finale a offset globale 6415. Allungare i blocchi a un terzo NON basta:
il primo resta un frame indietro. Non è un picco rivale lontano; la diagnosi precedente
"finestra troppo corta, traccia certamente completa" era troppo forte.

La localizzazione dalla sola durata QPC proposta è non univoca: sceglie 2815 anziché
2859 a 1440p r1, 7237 anziché 7360 a 1440p r2, e 6414 a 720p. **Non adottata come gate.**
QPC viene invece verificato alla posizione trovata: `diff(QPC) = FrameTime[:-1]`
(v2 misura intervalli in avanti), continuità entro 1 us su tutta la cattura e durata
QPC della finestra inclusiva dell'ultimo intervallo. Non modifica `pmparse.py` né i raw.
Questa verifica esclude buchi CSV di intervalli non nulli, NON perdita ETW a monte.

Implementati: durata N-intervalli, cross-check nativo 0,05% FPS / 0,5 s,
`--out-name`, margini del picco fuori +/-50 frame (minimo diagnostico 0,05), tre terzi
completi della traccia. Accordo esatto resta il default. Solo 720p usa esplicitamente
`--max-block-lag 1`, con QPC obbligatorio e sensibilità dei risultati alle finestre
6414/6415/6416. Non vengono eliminati, interpolati o ricuciti frame.
**Questa è una policy post-diagnosi per statistiche aggregate con incertezza di un frame,
non il superamento del vecchio gate esatto e non un matching causale frame-per-frame.**

Finestra centrale 720p **6415–18356, indici zero-based senza header**;
la predizione esatta 6416–18357 è smentita, benché rientri nella sensibilità +/-1.
Il mapping nativo è giusto; l'identità esatta dei singoli frame resta non dimostrata.
Durata 64.2643997 s, FPS 185.826057.
Le tre finestre danno FPS fra 185.823502
e 185.834675;
la conclusione aggregata non dipende dalla scelta di uno di questi bordi.

## Predizioni 720p: verifica, senza trasformare approssimazioni in soglie

- GPUBusy previsto **3,76 ms**, misurato **4.1720 ms**:
  errore **+10.96%**. Il numero NON è accurato;
  resta però molto sotto 5,38 ms, non vicino all'alternativa GPU satura ~5,2 ms.
- CPUBusy previsto **5,22 ms**, misurato **5.2297 ms**:
  errore **+0.19%**, coerente. Essendo circa
  FrameTime-CPUWait, non è una prova indipendente di lavoro CPU effettivo.
- GPUWait previsto **>0,196 ms**, misurato **1.1069 ms**: direzione confermata.
- Mapping esatto/QPC locator: smentiti come sopra. FPS ~185,82: confermato a livello aggregato.

## Modelli e cosa non si può concludere

Per frametime, il 1080p è -0.7483 ms
(-10.93%) rispetto alla retta 1440–720:
modello lineare unico non adeguato. Per GPUBusy il residuo corrispondente è
-0.2355 ms
(-3.87%). Fit e residui completi nel JSON;
nessuna intercetta viene identificata con il costo CPU/driver.

**Ritirata la precedente interpretazione C=4,81–5,38 ms come prima misura del costo CPU
e ~186 FPS come tetto rigido.** Anche 1080→720 migliora ancora di
13.33%; qui c'è un limite non-GPU crescente, non un plateau
isolato sperimentalmente. Il +65.37% rispetto al 1440p è
il guadagno MISURATO cambiando risoluzione, non un guadagno shader dimostrato né un suo limite superiore.

La ricerca GPU/shader a 1440p ha senso come prossimo bersaglio, ma nessun pass/shader
specifico o guadagno è provato. Per attribuire il limite basso a gioco vs UMD/driver vs
sincronizzazione serve WPR CPU+GPU con stack e code, in cattura di attribuzione separata.
Non necessaria per il verdetto di regime qui sopra; non avviata automaticamente.
Nessuna modifica a gioco, driver, cache, registro o impostazioni. Nessun click richiesto.

## Riproduzione

`python -B tools/c2077_scaling_check.py`

Rigenera le directory v2 mancanti, verifica hash e risultati se già presenti, non le
sovrascrive; aggiorna questo report e `scaling_analysis_v2.json`. Selfcheck sintetici
in `tools/c2077_native.py`: traccia esatta/rumorosa, ambiguità, lag ammesso/non ammesso,
frame mancanti nel CSV, QPC e durata N-intervalli. Il check reale riproduce il difetto
originale e verifica tutti i frame/campi copiati nelle quattro nuove finestre.
