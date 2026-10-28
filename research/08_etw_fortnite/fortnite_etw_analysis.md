# Phase 1.5-A — ETW/WPR attribution su Fortnite

**Stato: pipeline costruita e validata end-to-end. Le tre catture Fortnite NON sono state
eseguite** — richiedono che tu giochi il percorso Creative. Non lancio né guido il gioco.

Procedura: [`PROCEDURE.md`](PROCEDURE.md) · Script: [`tools/capture_etw.ps1`](../../tools/capture_etw.ps1),
[`tools/etw_analyze.py`](../../tools/etw_analyze.py) · Validazione: [`dryrun_validation/`](dryrun_validation/)

Nessuna injection, nessun hooking, nessuna modifica al gioco. WPR e PresentMon sono entrambi
consumatori ETW passivi.

---

## 1. Cosa misura e cosa no

PresentMon definisce `MsCPUBusy` come il tempo in cui la CPU produce il frame, ma non lo
attribuisce ai moduli. ETW con **CPU Sampled Profile + stack** lo attribuisce: ogni campione
porta processo, thread, program counter e **modulo** che possiede quell'indirizzo. Da lì:

```
% campioni del processo che cadono in amdxc64.dll  ×  1.529 ms  =  ms/frame di UMD AMD
```

Il prodotto è una stima, non una misura diretta: assume che i campioni siano distribuiti
uniformemente nel tempo CPU del processo (vero per il sampling a intervallo fisso) e che il
tempo CPU del processo nella finestra sia dominato dalla produzione dei frame (da verificare
per thread, ecco perché `hot_threads.csv`).

## 2. Configurazione di cattura

| | |
|---|---|
| Profili WPR | `CPU` (sampled profile + stack walk) + `GPU` (DxgKrnl) |
| Modalità | `-filemode` (obbligatoria: in memoria il buffer non regge 75 s) |
| **Intervallo di sampling** | **`xperf -setprofint 1221`** = 0.1221 ms ≈ **8 kHz** |
| Ripristino | `xperf -setprofint 10000` (1 kHz, default) a fine cattura |
| In parallelo | PresentMon 2.5.1 sullo stesso processo, stessa finestra |
| Contorno | snapshot dei processi in background salvato per ogni run |

**Perché 8 kHz.** A 620 FPS il default di 1 kHz dà ~1.6 campioni per frame: troppo pochi per
distinguere i moduli dentro un frametime da 1.6 ms. Misurato sul dry-run:

| profint | durata | campioni totali | campioni/s |
|---|---:|---:|---:|
| 10000 (default, 1 kHz) | 13.15 s | 22 055 | 1 677 |
| **1221 (8 kHz)** | ~9 s | **146 848** | **~16 300** |

≈ 8.7× in più, esattamente come atteso. Su 75 s di Fortnite ci si aspettano ~1.2 M campioni
totali, di cui una frazione ampia sul render/RHI thread: abbondanti per attribuire i moduli e
anche per fare istogrammi di offset dentro `amdxc64.dll`.

Costo: il dry-run da 13 s ha prodotto un ETL da **240 MB**. Una cattura da 75 s a 8 kHz starà
verosimilmente fra 1 e 2 GB. Tenere spazio libero.

## 3. Pipeline di analisi (validata)

`tools/etw_analyze.py` fa **streaming** di `xperf -a dumper` e aggrega in memoria: non scrive
mai il dump testuale (che nel dry-run sarebbe stato di 1.45 GB per 13 s di traccia).

Eventi consumati e verificati presenti nel dry-run:

| evento | colonne usate | a cosa serve |
|---|---|---|
| `SampledProfile` | TimeStamp, Process(PID), TID, PrgrmCtr, CPU, ThreadStartImage!Function, **Image!Function** | attribuzione per modulo e per thread |
| `I-DCStart` / `I-DCEnd` | Process(PID), BaseAddr, EndAddr, FileName | base dei moduli → **RVA** = PC − base; e path reale del modulo caricato |
| `CSwitch` | New/Old Process(PID), TID, **Wait Reason**, OldState | context switch e attese per thread |

Output prodotti:

```
cpu_module_attribution.csv   processo × modulo: campioni, % del processo, % traccia,
                             bucket (amd_driver / d3d_runtime / os_kernel / os_usermode / app_or_other),
                             ms stimati per secondo di un core
hot_threads.csv              per thread: campioni, % del processo, thread start image,
                             context switch in ingresso, top 6 moduli
amdxc64_hot_offsets.csv      per i moduli AMD: base, PC assoluto, RVA, campioni, % del modulo,
                             path del modulo effettivamente caricato
thread_waits.csv             wait reason per thread
module_timeline_1s.csv       campioni per (secondo, processo, modulo)
resolved_functions.csv       SOLO i nomi che xperf ha risolto da solo (mai inventati)
```

### Validazione end-to-end (dry-run, nessun gioco coinvolto)

Traccia sintetica di 13 s: 4 thread Python che bruciano CPU, sistema per il resto normale.
12 288 497 righe di dumper processate in 25 s. Risultati in `dryrun_validation/`:

| processo | modulo | campioni | % processo |
|---|---|---:|---:|
| python.exe | python311.dll | 10 122 | 82.1% |
| python.exe | ucrtbase.dll | 1 714 | 13.9% |
| Discord.exe | Discord.exe | 2 065 | 61.0% |
| dwm.exe | **amdxx64.dll** | 50 | 9.4% |

L'attribuzione funziona **senza simboli**. E il caso `dwm.exe → amdxx64.dll` prova che la
risoluzione dei moduli AMD funziona e che il calcolo dell'RVA è corretto:

```
process  module        module_base      abs_pc               rva        path
dwm.exe  amdxx64.dll   0x7ffaacf90000   0x00007ffaadf1ba88   0xf8ba88   ...ȃ303.inf_amd64_...\B026363\amdxx64.dll
```

Il path conferma anche, **con evidenza runtime**, che i moduli grafici caricati vengono dal
DriverStore `B026363` — cioè la revisione installata, non il package del progetto.

## 4. Cosa questa analisi potrà e non potrà concludere

**Potrà**, con affidabilità alta:

- la ripartizione per modulo del tempo CPU di `FortniteClient-Win64-Shipping.exe`;
- quali thread la consumano e con quale mix di moduli (render/RHI vs game vs worker);
- gli offset più caldi dentro `amdxc64.dll`, in RVA, pronti per un'analisi Ghidra **mirata**;
- wait reason e context switch dei thread principali.

**Non potrà**, e va detto prima:

- **nomi di funzione AMD**: non esistono simboli pubblici per `amdxc64.dll`. Si arriverà a
  `amdxc64.dll+0x1234ab`, che è comunque sufficiente per puntare Ghidra. Nessun nome inventato.
- **correlazione affidabile con i singoli spike di frametime**: WPR e PresentMon hanno origini
  temporali diverse e la cattura non allinea i QPC. `module_timeline_1s.csv` permette una
  correlazione **grossolana al secondo**, non frame-per-frame. Con 4–12 spike per run da 1.6 ms
  su 55 s, la risoluzione al secondo non basta a concludere. Lo dichiaro come limite, non lo
  aggiro con una stima.
- **separare "CPU del gioco" da "CPU del driver" dentro la stessa funzione inlined**: il
  sampling attribuisce al modulo che possiede il PC, che è la granularità giusta per la domanda,
  ma non vede il lavoro che l'UMD fa eseguire ad altri (es. code kernel via `amdkmdag.sys`,
  che comparirà separato come `os_kernel`).

## 5. Soglia decisionale, fissata prima di guardare i dati

Con `MsCPUBusy` medio = **1.529 ms** su Fortnite (baseline 7 run):

| quota campioni in `amdxc64.dll` | ms/frame | lettura |
|---|---:|---|
| ≥ 15% | ≥ 0.23 ms | ramo UMD **molto interessante**: anche un −25% del costo driver darebbe ~4% di frametime, sopra la MDD di Fortnite (2.2%) |
| 8–15% | 0.12–0.23 ms | **interessante ma marginale**: servirebbe un taglio grosso per superare il rumore |
| 3–8% | 0.05–0.12 ms | poco promettente per Fortnite; il ramo resta valido solo per carichi diversi |
| < 3% | < 0.05 ms | **chiude il ramo** per Fortnite Performance Mode: niente reverse engineering dell'UMD per questo target |

Fissata adesso, prima di avere i dati, per non razionalizzare a posteriori.

## 6. Cosa serve da te per completare la parte A

Tre esecuzioni dello **stesso** percorso Creative della baseline, con Fortnite già avviato e in
partita, da una PowerShell **elevata**, nella cartella del progetto:

```powershell
.\tools\capture_etw.ps1 -Run 1
.\tools\capture_etw.ps1 -Run 2
.\tools\capture_etw.ps1 -Run 3
```

Lo script arma WPR + PresentMon, fa un conto alla rovescia di 10 s per farti tornare nel gioco,
cattura 75 s, si ferma da solo, ripristina l'intervallo di sampling e scrive `-meta.json` con
versione driver, build OS e stato HAGS. Poi:

```bash
python tools/etw_analyze.py research/08_etw_fortnite/raw/<file>.etl research/08_etw_fortnite/run1 --process FortniteClient-Win64-Shipping.exe
```

Nota sul rumore: nel dry-run **Discord era attivo** e consumava CPU in modo non trascurabile
(2 065 campioni, 61% del proprio processo). È un candidato plausibile per l'anomalia di
`fortnite_r4`. Lo script salva l'elenco dei processi in background di ogni run proprio per
questo: se possibile, chiudi Discord e l'overlay prima delle catture.
