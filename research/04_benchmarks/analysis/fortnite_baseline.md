# Baseline — Fortnite DX12 Performance Mode, 7 run

Dati: `research/fortnite_DX12_PerformanceMode/` — 7 CSV raw intatti (~15 MB ciascuno).
Metodo e definizioni: [`METHOD.md`](METHOD.md). Tabella completa: [`fortnite_runs.csv`](fortnite_runs.csv).

## 0. Finestra di test — cosa si può e cosa non si può dire

La richiesta era di isolare la finestra corrispondente al percorso Creative ed escludere
launcher/menu/loading. Evidenza raccolta:

**Cosa è certo (confirmed):**

- Le catture **non contengono launcher, menu o loading**. Il frame 0 di ogni run è già a
  1.7 ms (≈590 FPS) e il primo bin da 2 s gira a 473–498 FPS. Un menu Fortnite o una schermata
  di caricamento non produce quel profilo.
- Un solo `SwapChainAddress`, un solo ProcessID, `FrameType = Application` al 100%, nessun
  cambio di `PresentMode` — nessuna transizione di stato dentro la cattura.
- Ogni run contiene **uno spike di 363–448 ms a t = 0.43–0.55 s**. È presente in 7 run su 7,
  sempre nello stesso punto, ed è un artefatto di aggancio della cattura, non del gioco.
  → escluso dal warm-up trim di 2 s.

**Cosa NON è determinabile con questi dati (documentato, non indovinato):**

- **Non posso identificare i confini del percorso Creative dentro la cattura.** Il CSV non
  contiene marker di gioco, posizione, mappa o stato; PresentMon vede solo present. Non esiste
  nessun segnale nel dataset che dica "qui inizia il percorso".
- Non posso quindi escludere che parte della cattura copra secondi di posizionamento iniziale o
  di attesa a fine percorso. La finestra analizzata è convenzionale: **[2.0 s, ultimo secondo
  intero]**, uguale per tutti i run, non "il percorso".

**Allineamento tra run (probable):** i 7 run condividono una forma comune — ~610 FPS per i primi
~22 s, poi un gradino a ~635 FPS, poi ~620 FPS finali. Il salto è **a gradino, non una rampa**,
quindi è probabilmente un cambio di scena/zona del percorso e **non** un warm-up residuo. La
correlazione a coppie delle tracce FPS/s è però solo 0.55 in media (min −0.11): i run seguono lo
stesso percorso ma **non sono allineati frame-per-frame**, a differenza di Steel Nomad.

Conseguenza pratica: **Fortnite non è uno strumento di misura, è un carico realistico.**
Per A/B statisticamente puliti va usato Steel Nomad (o Wukong); Fortnite serve a verificare che
un guadagno trovato lì sopravviva in un gioco vero.

## 1. Per-run

| run | dur valida | frame | avg FPS | median FPS | 1% low (time) | 0.1% low (time) | ft avg | ft p95 | ft p99 | ft max | spike | severe | dropped |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| r1 | 54.99 s | 33 997 | 618.25 | 626.84 | 329.0 | 143.4 | 1.618 | 2.149 | 2.488 | 12.49 | 12 | 2 | 0 |
| r2 | 55.99 s | 34 801 | 621.56 | 630.00 | 330.7 | 133.6 | 1.609 | 2.125 | 2.448 | 12.90 | 10 | 2 | 0 |
| r3 | 55.99 s | 34 802 | 621.58 | 628.73 | 345.6 | 175.9 | 1.609 | 2.127 | 2.449 | 13.09 | 8 | 1 | 0 |
| **r4** | 55.99 s | 33 559 | **599.38** | 616.30 | **279.2** | 190.9 | 1.669 | 2.327 | 2.887 | 12.84 | **28** | 1 | 0 |
| r5 | 55.99 s | 34 582 | 617.65 | 626.47 | 327.8 | 120.4 | 1.619 | 2.142 | 2.492 | **20.27** | 12 | 2 | 0 |
| r6 | 54.99 s | 33 665 | 612.22 | 622.20 | 330.4 | 190.7 | 1.634 | 2.203 | 2.557 | 12.17 | 7 | 1 | 0 |
| r7 | 56.99 s | 35 475 | 622.48 | 629.88 | 354.1 | 225.6 | 1.607 | 2.126 | 2.458 | 12.99 | 4 | 1 | 0 |

Telemetria e configurazione (medie sulla finestra valida):

| | valore |
|---|---|
| Present Mode | `Hardware: Independent Flip` 100% dei frame, tutti i run |
| Present Runtime | DXGI · SyncInterval 0 (uncapped) · AllowsTearing 1 |
| Frame Type | `Application` 100% — **nessun frame generato** (no AFMF/FSR-FG attivo) |
| Dropped frames | **0** su tutti i run |
| GPU Utilization | 72.9–74.1% |
| GPU clock medio | 2 555–2 575 MHz |
| GPU power medio | 234.5–240.4 W (max 254–261 W) |
| GPU temp max | 65–67 °C |
| CPU utilization | 43.8–46.9% · **CPU clock 4 427–4 447 MHz** |
| VRAM usata (max) | 1 872–1 906 MB |

## 2. Dove sta il collo di bottiglia — il risultato più importante

```
frametime medio    1.623 ms
MsCPUBusy medio    1.529 ms      94% del frame
MsCPUWait medio    0.095 ms
MsGPUBusy medio    1.373 ms      -> headroom GPU 15.3%
MsGPUWait medio    0.204 ms
GPU utilization   73.9%          (contro 98.98% di Steel Nomad)
```

**Fortnite Performance Mode su questo sistema è CPU-bound, non GPU-bound.** `MsCPUBusy` >
`MsGPUBusy` in tutti e 7 i run, la GPU ha il 15% di margine, gira al 74% di utilizzo e la CPU sta
a 4.45 GHz contro i 2.8 GHz del carico GPU-bound. Il frametime è quasi interamente
`MsCPUBusy + MsCPUWait`.

Implicazioni dirette per il progetto, entrambe importanti:

- **Ridurre il costo ISA/occupancy degli shader qui non produrrebbe quasi nulla.** Anche
  azzerando il 15% di GPU busy che avanza, il frame resta limitato dai 1.53 ms di CPU.
- **Ma il costo CPU del driver AMD è esattamente in quel 1.53 ms.** Validazione dei command
  list, traduzione D3D12 → PM4, lookup della pipeline cache, gestione dei descriptor: è tutto
  lavoro user-mode driver dentro `MsCPUBusy`. Un carico CPU-bound è il posto **giusto**, non
  sbagliato, per misurare l'overhead CPU dell'UMD.

PresentMon non separa "CPU del gioco" da "CPU del driver" dentro `MsCPUBusy`: quella
scomposizione richiede ETW/WPA (Fase 1G) ed è il prossimo passo naturale.

## 3. Varianza run-to-run

Su tutti e 7 i run:

| metrica | media | SD | **CV%** | range% | MDD (n=7) | run flaggati (MAD z>3.5) |
|---|---:|---:|---:|---:|---:|---|
| avg FPS | 616.16 | 8.19 | **1.329%** | 3.75% | **2.17%** | r4 |
| median FPS | 625.77 | 4.96 | 0.793% | 2.19% | 1.29% | — |
| 1% low (time) | 328.11 | 23.76 | 7.243% | 22.8% | 11.8% | r3, r4, r7 |
| 0.1% low (time) | 168.64 | 37.57 | **22.28%** | 62.4% | 36.3% | — |
| ft avg | 1.6234 ms | 0.0219 | 1.352% | 3.81% | 2.20% | r4 |
| ft p99 | 2.5399 ms | 0.1578 | 6.213% | 17.3% | 10.1% | r4 |
| ft max | 13.82 ms | 2.86 | 20.70% | 58.6% | — | r5 |
| spike count | 11.6 | 7.79 | **67.3%** | 207% | — | r4 |
| GPU power medio | 238.63 W | 2.00 | 0.840% | 2.48% | — | r4 |
| GPU util medio | 73.87% | 0.461 | 0.624% | 1.71% | — | r3, r4 |

Escludendo `r4` (n=6):

| metrica | media | SD | CV% | MDD (n=6) |
|---|---:|---:|---:|---:|
| avg FPS | 618.96 | 3.84 | **0.620%** | 1.11% |
| median FPS | 627.35 | 2.93 | 0.467% | 0.84% |
| 1% low (time) | 336.27 | 10.91 | 3.245% | 5.82% |
| ft avg | 1.616 ms | 0.010 | 0.623% | 1.12% |
| ft p99 | 2.482 ms | 0.041 | 1.669% | 2.99% |
| 0.1% low (time) | 164.93 | 39.73 | 24.09% | 43.2% |

### `baseline noise ≈ ±1.3%` con tutti i run · `≈ ±0.6%` escludendo r4

Sull'avg FPS. Sulle code il rumore è di un altro ordine: **±7% sull'1% low, ±22% sullo 0.1% low,
±67% sul conteggio spike.**

**Soglie operative per Fortnite:**

| metrica | differenza minima dichiarabile reale (7v7) | soglia prudente |
|---|---:|---|
| avg FPS / ft avg | 2.2% (1.1% senza run anomali) | **≥ 3%** |
| 1% low | 11.8% | **≥ 15%** |
| 0.1% low | 36% | **inutilizzabile come metrica A/B** |
| spike count | — | serve un ordine di grandezza |

Lo 0.1% low e il conteggio spike **non vanno usati per decidere** su 7 run: il rumore è più
grande di qualsiasi guadagno plausibile da ottimizzazione driver.

### Run anomalo: r4

`fortnite_r4` è l'unico run realmente fuori distribuzione, flaggato su 8 metriche indipendenti.
Profilo: prima metà normale (616 FPS, in linea con gli altri), **seconda metà a 582 FPS (−5.5%)**
mentre in 6 run su 7 la seconda metà è *più veloce* della prima (+1.9…+5.0%). L'andamento FPS/2s
mostra il crollo netto da ~610 a ~545 FPS a partire da t≈44 s, che poi non si riprende. In quella
coda si concentrano 15 dei suoi 28 spike, tutti piccoli (3.6–4.5 ms, ratio ~2.2) — un
peggioramento **di regime**, non un hitch isolato.

Non è throttling: GPU power *più bassa* (234.5 W contro 239–240 W), temp identica (66 °C),
GPU util *più bassa* (72.9%). Il frame costa di più sulla CPU (`MsCPUBusy` 1.573 contro 1.514 ms)
con lavoro GPU invariato (`MsGPUBusy` 1.381 contro 1.370 ms). È coerente con **un consumatore di
CPU esterno o un cambio di percorso**, non con un limite hardware. Causa: **sconosciuta** — non
ci sono note sui processi in background per questi run.

**Raccomandazione:** tenere r4 nel dataset (i CSV non si toccano) ma escluderlo dalle baseline di
confronto, documentando l'esclusione. E registrare da qui in avanti i processi in background
nel metadata di ogni run.

## 4. Spike / stutter

81 spike totali sui 7 run (tabella completa: [`frametime_outliers.csv`](frametime_outliers.csv)),
media 11.6 per run ≈ 12.6/minuto, di cui 10 "severe" (≥8 ms). Tempo perso in hitch: 22–73 ms per
run, cioè **lo 0.04–0.13% del tempo totale** — trascurabile sull'FPS medio, ma sono gli eventi
che si sentono.

Firma degli spike, identica in tutti e 81:

| segnale | al frame di spike | mediana locale |
|---|---|---|
| `MsCPUBusy` | 3.5 – 20.2 ms | 1.5 – 2.0 ms |
| `MsGPUBusy` | **1.5 – 2.4 ms** | **1.3 – 1.5 ms** |
| `MsGPUWait` | 1.2 – 18.3 ms | 0.1 – 0.5 ms |

**Il lavoro GPU durante uno spike non cambia.** Lo spike è interamente CPU-side, e `MsGPUWait`
sale perché la GPU resta senza lavoro mentre la CPU è bloccata: è una **conseguenza**, non la
causa. Nessuno degli 81 spike mostra un aumento di `MsGPUBusy`.

I 10 spike severe (12.2–20.3 ms) mostrano anche un calo di GPU clock (a 1 142–2 100 MHz) e di
GPU util (23–52%). Anche questo è coerente con l'effetto: la GPU si de-clocka perché è idle.
**Attenzione**: clock e utilizzo sono campionati a ~10 Hz, cioè un valore ogni ~6 frame a
620 FPS — la risoluzione temporale non basta a stabilire chi viene prima. Correlazione
osservata, direzione causale **non dimostrabile con questi dati**.

Distribuzione temporale: sparsi su tutta la durata, nessun addensamento nei primi secondi.
**Non c'è evidenza di stutter da compilazione shader** in queste catture — atteso, dato che la
cache era calda (7 run consecutivi sullo stesso percorso). Il caso cold-cache non è ancora stato
misurato ed è il vero test.

## 5. Correlazioni (ρ di Spearman, media sui 7 run)

| segnale | ρ | delta mediano sui frame di spike | lettura |
|---|---:|---:|---|
| MsCPUBusy | 0.999 | +3.37 ms | **definitorio** (ft ≈ CPUBusy + CPUWait), non causale |
| MsGPUTime | 0.859 | +3.21 ms | include l'attesa: segue il frametime |
| MsGPUWait | 0.829 | +2.97 ms | **effetto** dello stallo CPU, non causa |
| MsGPUBusy | 0.714 | **+0.26 ms** | ρ alto ma delta minimo: il lavoro GPU è quasi costante |
| MsRenderPresentLatency | −0.451 | −0.02 (p=0.31) | non significativo sugli spike |
| GPUUtilization | −0.116 | −1.79 pp (p=0.21) | non significativo |
| GPUPower | −0.109 | −5.86 W (p=0.14) | non significativo |
| GPUFrequency | −0.078 | −27.8 MHz (p=0.12) | non significativo |
| GPUMemorySizeUsed | +0.049 | (p=0.21) | nessuna relazione |
| CPUFrequency | +0.005 | −6.8 MHz (p=0.34) | nessuna relazione |
| MsCPUWait / MsInPresentAPI | 0.019 | +0.015 ms (p=0.0009) | significativo ma **irrilevante**: 15 µs |

Sintesi onesta:

- **Correlazione forte e causa probabile**: il frametime di Fortnite è determinato dal tempo CPU.
- **Correlazione forte ma causa invertita**: `MsGPUWait` (la GPU aspetta perché la CPU è in ritardo).
- **Nessuna correlazione utile**: clock GPU, power, temperatura, VRAM, clock CPU. Nessun segnale
  di power limit — e comunque le colonne `*Limited` sono **tutte NA**, quindi il power limit
  **non è verificabile** da questo dataset, in nessuna direzione.

## 6. Grafici

`charts/fortnite_{frametime_over_time, frametime_distribution, percentile_curve, fps_per_run,
fps_timeline, gpubusy_vs_frametime, cpubusy_vs_frametime, gpuclock_vs_frametime,
gpupower_vs_frametime}.png`

Da guardare per primi: `fortnite_cpubusy_vs_frametime.png` (retta perfetta) contro
`fortnite_gpubusy_vs_frametime.png` (nuvola piatta) — è tutta la storia in due immagini.
