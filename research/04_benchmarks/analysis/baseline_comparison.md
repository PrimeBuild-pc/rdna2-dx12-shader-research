# Baseline comparison — Fortnite vs Steel Nomad

Metodo: [`METHOD.md`](METHOD.md) · Dettaglio: [`fortnite_baseline.md`](fortnite_baseline.md),
[`steelnomad_baseline.md`](steelnomad_baseline.md). Tutti i CSV raw sono intatti.

## 1. I due carichi misurano cose diverse

| | Fortnite DX12 Perf Mode | 3DMark Steel Nomad |
|---|---:|---:|
| run | 7 | 7 |
| durata valida | 55.0–57.0 s | 51.0–57.0 s |
| frame per run | 33 559 – 35 475 | 2 110 – 2 359 |
| **avg FPS** | **616.16** | **41.41** |
| frametime medio | 1.623 ms | 24.158 ms |
| **MsCPUBusy medio** | **1.529 ms (94% del frame)** | 24.09 ms |
| **MsGPUBusy medio** | **1.373 ms** | **24.13 ms (99.9%)** |
| MsGPUWait medio | 0.204 ms | 0.013 ms |
| **GPU utilization** | **73.9%** | **99.0%** |
| headroom GPU | **15.3%** | 0.1% |
| GPU power | 238.6 W | 288.5 W |
| GPU clock | 2 570 MHz | 2 330 MHz |
| CPU clock | 4 440 MHz | 2 815 MHz |
| CPU utilization | 44.6% | 13.3% |
| VRAM max | 1.88 GB | 6.46 → 7.00 GB |
| spike totali | 81 | **0** |
| dropped frames | 0 | 0 |
| **collo di bottiglia** | **CPU / submission** | **GPU execution** |

Entrambi: `Hardware: Independent Flip`, DXGI, SyncInterval 0, AllowsTearing 1,
`FrameType = Application` al 100%, zero dropped frame. Nessun frame generato in nessuna cattura.

## 2. Rumore di base e soglia di rilevabilità — la conclusione richiesta

CV = deviazione standard / media, su 7 run. MDD = differenza minima dichiarabile reale in un A/B
7-contro-7 (t a due campioni, α=0.05, potenza 0.80) = 1.631 × CV.

| metrica | Steel Nomad CV | Steel Nomad MDD | Fortnite CV | Fortnite MDD | Fortnite CV senza r4 |
|---|---:|---:|---:|---:|---:|
| avg FPS | **0.105%** | **0.17%** | **1.329%** | **2.17%** | 0.620% |
| median FPS | 0.174% | 0.28% | 0.793% | 1.29% | 0.467% |
| ft medio | 0.107% | 0.17% | 1.352% | 2.20% | 0.623% |
| ft p99 | 0.472% | 0.77% | 6.213% | 10.13% | 1.669% |
| 1% low (time) | 0.598% | 0.97% | 7.243% | 11.81% | 3.245% |
| 0.1% low (time) | 0.779%¹ | 1.27%¹ | 22.276% | 36.33% | 24.086% |
| spike count | — (0 spike) | — | 67.3% | — | — |

¹ basato su 2 frame per run: **non usare**.

### Conclusione

```
Steel Nomad :  baseline noise ≈ ±0.11%   ->  è reale un guadagno ≥ 0.2%  (prudente: ≥ 0.5%)
Fortnite    :  baseline noise ≈ ±1.3%    ->  è reale un guadagno ≥ 2.2%  (prudente: ≥ 3%)
              (±0.6% e ≥1.1% escludendo il run anomalo r4)
```

Sulle metriche di coda il rumore è di un altro ordine e va detto esplicitamente:

```
Fortnite 1% low   : ±7%    -> serve ≥ 12% per dichiararlo
Fortnite 0.1% low : ±22%   -> inutilizzabile come metrica decisionale con 7 run
Fortnite spike    : ±67%   -> serve un ordine di grandezza, non una percentuale
```

**Steel Nomad è ~12× più preciso di Fortnite** come strumento di misura. Questo determina la
divisione del lavoro per tutte le fasi successive:

- **Steel Nomad (o Wukong) = strumento.** Ci si decide se una modifica funziona.
- **Fortnite = verifica di realtà.** Ci si controlla che il guadagno sopravviva in un gioco vero,
  sapendo che sotto il 3% non si distingue dal rumore.

Per stringere la soglia di Fortnite servono più run, non run più lunghi: la MDD scala come
1/√n. Da 7 a 20 run la MDD passa da ~2.2% a ~1.2% (a parità di CV, e assumendo di eliminare la
causa di r4).

## 3. Correlazioni: cosa è correlazione e cosa è causa probabile

| relazione | evidenza | classificazione |
|---|---|---|
| ft ↔ `MsCPUBusy` (ρ 0.999–1.000 su entrambi) | vale in ogni run di ogni carico | **definitorio**: in PresentMon 2.x ft ≈ CPUBusy + CPUWait. Non è una scoperta. |
| Steel Nomad: ft ← `MsGPUBusy` | GPUBusy = 99.9% del frame, GPUWait 13 µs, util 99% | **causa confermata** |
| Fortnite: ft ← tempo CPU | CPUBusy 1.53 > GPUBusy 1.37 in 7/7 run, util GPU 74% | **causa confermata** (ma il CSV non separa CPU-gioco da CPU-driver) |
| Fortnite: spike → `MsGPUWait` alto | 81/81 spike: GPUWait sale a ~= l'entità dello spike | **effetto confermato**, direzione causale invertita rispetto all'intuizione |
| Fortnite: spike ↔ `MsGPUBusy` | delta mediano **+0.26 ms** su spike di 3.5–20 ms | **il lavoro GPU non è la causa degli spike** |
| Fortnite: spike severi ↔ calo di GPU clock/util | clock 1 142–2 100 MHz, util 23–52% durante i 10 spike severi | **correlazione osservata, causa non determinabile**: telemetria a 10 Hz = 1 campione ogni ~6 frame |
| power limit come causa | colonne `GPUPowerLimited`/`*Limited` **tutte NA** in 14/14 file | **non verificabile**. Indizi indiretti (power 288.5 W ±0.05, temp ≤69 °C) sono coerenti con nessun limite attivo su Steel Nomad. |
| VRAM ↔ frametime | ρ ≤ 0.05 su entrambi, campionamento 0.05 Hz | **nessuna relazione rilevabile** |
| CPU clock/util ↔ frametime | ρ ≤ 0.05 (Fortnite); −0.45 su Steel Nomad ma campionato a 1 Hz | **artefatto di campionamento**, non relazione |
| Steel Nomad: VRAM +8.2% su 7 run consecutivi | 6 463→6 996 MB, monotòna, ~80 MB/run | **correlazione confermata, causa speculativa** (accumulo lato driver o app). Nessun impatto su FPS. |

Avvertenza generale sul campionamento: GPU clock/power/util ~10 Hz, CPU clock/util ~1 Hz,
VRAM ~0.05 Hz. A 620 FPS un campione di telemetria copre ~60 frame. **Ogni ρ calcolato contro
questi segnali è sovra-campionato e va trattato come indicativo, mai come prova.**

## 4. Cosa questo significa per l'obiettivo del progetto

L'ipotesi di partenza era che ottimizzare shader/ISA/pipeline sul percorso DX12 AMD potesse dare
performance. Questa baseline la divide in due, e le due metà hanno bersagli diversi:

1. **Costo di esecuzione GPU degli shader (ISA, occupancy, VGPR/SGPR).**
   Rilevante dove il carico è GPU-bound → Steel Nomad, Wukong, Fortnite a impostazioni alte.
   **Irrilevante su Fortnite Performance Mode**, che ha il 15% di GPU inutilizzata.
   Misurabile con precisione 0.2% su Steel Nomad.

2. **Costo CPU del driver user-mode (submission, PSO, cache lookup, descriptor).**
   Vive dentro `MsCPUBusy`, cioè nel 94% del frametime di Fortnite. **È qui che la baseline dice
   di guardare per i giochi target ad alto frame rate.** Ma PresentMon non lo isola dal codice del
   gioco: serve ETW/WPA (Fase 1G) per attribuire quel millisecondo e mezzo tra Fortnite e l'UMD AMD.

3. **Compilazione shader / cache.** Non osservabile in questo dataset: tutte le catture sono a
   cache calda. Gli 81 spike sono sparsi, non concentrati all'avvio, e non c'è aumento di
   `MsGPUBusy` — nessuna evidenza di compilazione in corso. Il caso cold-cache va misurato.

## 5. File prodotti

```
research/04_benchmarks/analysis/
├── METHOD.md                     definizioni (1% low, 0.1% low, spike, MDD) e validazione
├── fortnite_runs.csv             7 run x ~120 metriche
├── steelnomad_runs.csv           7 run x ~120 metriche
├── frametime_outliers.csv        81 spike, con i segnali CPU/GPU al frame e la mediana locale
├── correlations.csv              rho/r per run per segnale + Mann-Whitney spike-vs-normale
├── run_to_run_variance.csv       media, SD, CV, range, IC95, MDD, run flaggati
├── parser_validation.csv         parser vs -stats.csv di PresentMon, 14/14 file
└── charts/                       18 grafici PNG
```
