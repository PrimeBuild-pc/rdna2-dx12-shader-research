# Baseline — 3DMark Steel Nomad (DX12), 7 run

Dati: `research/3DMark_SteelNomad_DX12/{1..7}/` — CSV raw intatti.
Metodo e definizioni: [`METHOD.md`](METHOD.md). Tabella completa: [`steelnomad_runs.csv`](steelnomad_runs.csv).

## 0. Rettifica sul workload

La richiesta parlava di **Time Spy** e di segmentare **Graphics Test 1 / 2**. Le catture sono di
**Steel Nomad v1.0 (DX12)**, che ha **un solo graphics test continuo**: lo confermano sia i dati
(nessun gap, nessuna caduta di FPS, curva continua da t=0 a t≈59 s in tutti e 7 i run) sia le
schermate 3DMark, dove il grafico Monitoring mostra un unico segmento etichettato
"Graphics test" da 00:00 a 01:00.

**Non c'è quindi niente da segmentare.** Le catture non contengono launcher, menu, CPU test o
loop demo: PresentMon è stato agganciato al processo già dentro il test. Nessun dato è stato
eliminato; l'unico trim è la finestra valida standard (primi 2 s + ultimo secondo incompleto).

Cross-check indipendente con la GUI 3DMark (le uniche due schermate lette):

| Run | 3DMark score | 3DMark "Graphics test" | `median_fps` parser | Δ |
|---|---:|---:|---:|---:|
| r1 | 4 139 | 41.40 FPS | 41.283 | −0.28% |
| r3 | 4 137 | 41.38 FPS | 41.385 | +0.01% |

Le altre 5 schermate non sono state lette; i punteggi non sono riportati per non inventarli.

## 1. Per-run

| run | dur valida | frame | avg FPS | median FPS | 1% low (time) | 0.1% low (time)¹ | ft avg | ft p95 | ft p99 | ft max | spike |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| r1² | 50.97 s | 2110 | 41.399 | 41.283 | 37.75 | 37.47 | 24.167 | 25.830 | 26.328 | 26.69 | 0 |
| r2 | 55.97 s | 2323 | 41.506 | 41.520 | 37.39 | 36.91 | 24.104 | 25.874 | 26.513 | 27.45 | 0 |
| r3 | 56.98 s | 2358 | 41.384 | 41.385 | 37.45 | 37.16 | 24.176 | 25.864 | 26.517 | 26.94 | 0 |
| r4 | 56.99 s | 2359 | 41.397 | 41.436 | 37.28 | 36.73 | 24.168 | 25.832 | 26.516 | 27.45 | 0 |
| r5 | 54.97 s | 2277 | 41.421 | 41.447 | 37.46 | 37.12 | 24.152 | 25.896 | 26.522 | 27.00 | 0 |
| r6 | 56.96 s | 2357 | 41.377 | 41.422 | 37.91 | 37.50 | 24.180 | 25.763 | 26.207 | 26.75 | 0 |
| r7 | 55.97 s | 2318 | 41.414 | 41.394 | 37.68 | 37.38 | 24.158 | 25.820 | 26.377 | 26.87 | 0 |

¹ **Lo 0.1% low di Steel Nomad poggia su 2 frame** (`frames_in_01pct` = 2). Non usarlo come
metrica di confronto: non è statisticamente significativo.
² r1 ha 5 s in meno perché la **cattura** è partita in ritardo, non perché il run sia diverso: la
curva FPS/s di r1 è la stessa degli altri traslata di ~5 s (il picco a 45 FPS cade all'indice 7
invece che 12), e 3DMark ha comunque registrato il test intero (4139 punti).

Telemetria (medie sulla finestra valida, identiche entro rumore su tutti i run):

| | valore |
|---|---|
| Present Mode | `Hardware: Independent Flip` 100% dei frame (tutti i run) |
| Present Runtime | DXGI · SyncInterval 0 · AllowsTearing 1 |
| Frame Type | `Application` 100% — nessun frame generato |
| Dropped frames | **0** su tutti i run |
| GPU Utilization | 98.98% |
| GPU clock medio | 2 328–2 334 MHz (min 2 258–2 272) |
| GPU power medio | 288.4–288.6 W (max 290–291 W) |
| GPU temp max | 68–69 °C |
| CPU busy / wait | 24.09 ms / 0.073 ms |
| CPU utilization | 13.2–13.4% · CPU clock 2 774–2 857 MHz |
| VRAM usata (max) | **6 463 → 6 996 MB, crescente run dopo run** (vedi §4) |

## 2. Dove sta il collo di bottiglia

```
frametime medio   24.158 ms
MsGPUBusy medio   24.132 ms   -> 99.9% del frame è lavoro GPU
MsGPUWait medio    0.013 ms
MsCPUWait medio    0.073 ms
GPU utilization   98.98%
```

**GPU-bound al 99.9%, senza ambiguità.** Il headroom GPU è 0.1%. La CPU è ferma al 13% con i
clock in idle-boost (2.8 GHz contro i 4.45 GHz di Fortnite). `MsGPUWait` a 13 µs significa che la
GPU non aspetta mai la CPU.

Conseguenza per il progetto: **Steel Nomad misura esclusivamente il tempo di esecuzione GPU**.
Qualsiasi ottimizzazione che riduca il costo ISA/occupancy degli shader si vedrebbe qui quasi
1:1. Qualsiasi ottimizzazione del costo CPU del driver (submission, PSO, cache lookup) qui è
**invisibile**. È lo strumento giusto per la metà "shader/ISA" della ricerca e quello sbagliato
per la metà "driver overhead".

## 3. Varianza run-to-run

| metrica | media | SD | **CV%** | range% | MDD (n=7, α .05, pot .80) |
|---|---:|---:|---:|---:|---:|
| avg FPS | 41.414 | 0.0434 | **0.105%** | 0.31% | **0.17%** |
| median FPS | 41.413 | 0.0720 | 0.174% | 0.57% | 0.28% |
| 1% low (time) | 37.558 | 0.2245 | 0.598% | 1.67% | 0.97% |
| ft avg | 24.158 ms | 0.0258 | 0.107% | 0.32% | 0.17% |
| ft p99 | 26.426 ms | 0.1247 | 0.472% | 1.19% | 0.77% |
| ft max | 27.021 ms | 0.3103 | 1.149% | 2.80% | 1.87% |
| GPU power medio | 288.50 W | 0.051 | 0.018% | 0.05% | — |
| GPU util medio | 98.98% | 0.0056 | 0.006% | 0.02% | — |

### `baseline noise ≈ ±0.11%` (CV di avg FPS)

Nessun run anomalo di rilievo: il flag MAD segnala `r2` su avg FPS, ma è un +0.22% sulla media —
dentro il rumore, non un'anomalia reale. `r1|r6|r7` sono flaggati su `ft_p99` per lo stesso motivo
(spread totale 1.2%). Con 7 run **non c'è nessun run da scartare**.

**Soglia operativa: un A/B con 7+7 run può dichiarare reale una differenza ≥ 0.17% su avg FPS.**
In pratica, per prudenza contro drift termico/ambientale: **≥ 0.5% = interessante, ≥ 1% = solido.**

## 4. Anomalia: VRAM crescente run dopo run

`GPUMemorySizeUsed` massimo, nell'ordine cronologico di esecuzione:

| r1 | r2 | r3 | r4 | r5 | r6 | r7 |
|---:|---:|---:|---:|---:|---:|---:|
| 6 463 MB | 6 547 MB | 6 622 MB | 6 700 MB | 6 775 MB | 6 851 MB | 6 996 MB |

Monotòna crescente, +533 MB (+8.2%) su 7 esecuzioni consecutive dello stesso identico test,
**~80 MB per run**, senza alcun effetto misurabile sulle performance (avg FPS piatto entro 0.31%).
Il gap di ~4 minuti prima di r7 non ha resettato la crescita.

Correlazione **confermata** (monotonicità perfetta su 7 punti). Causa **speculativa**: accumulo
lato driver/runtime (heap di risorse, cache di pipeline residenti, allocazioni non rilasciate tra
run) oppure semplice mancata deallocazione di 3DMark. Con 16 GB di VRAM non satura, ma è
**esattamente il tipo di comportamento driver-side che questo progetto vuole capire** — ed è
misurabile senza toccare niente. Vale un esperimento dedicato in Fase 2.

Nota: `GPUMemorySizeUsed` è campionato a ~0.05 Hz (3–4 valori per run), quindi il valore è
grossolano; la *tendenza* su 7 run resta però inequivocabile.

## 5. Spike / stutter

**Zero spike su tutti e 7 i run**, con la definizione di METHOD.md (0 anche abbassando a
`ratio > 1.5`, dato che `ft_max` è 27 ms contro una mediana di 24.2 ms: il frame peggiore è solo
il +12% del tipico). La distribuzione di frametime è quasi degenere.

È il comportamento di un benchmark deterministico GPU-bound e conferma che la strumentazione
non introduce artefatti: gli spike che si vedono in Fortnite non sono di PresentMon.

## 6. Correlazioni (ρ di Spearman, media sui 7 run)

| segnale | ρ | lettura |
|---|---:|---|
| MsCPUBusy | 1.000 | **definitorio**, non causale: ft ≈ CPUBusy + CPUWait |
| MsGPULatency | 0.970 | conseguenza della pipeline GPU-bound |
| MsGPUBusy / MsGPUTime | 0.941 | **il frametime è il tempo GPU** — causa probabile diretta |
| MsRenderPresentLatency | 0.939 | conseguenza |
| CPUUtilization | −0.452 | artefatto di campionamento (1 Hz su frame da 24 ms) |
| GPUTemperature | 0.244 | debole; drift termico lungo il run, non causa per-frame |
| GPUPower / GPUFrequency | 0.080 / 0.064 | **nessuna correlazione utile** |
| GPUMemorySizeUsed | −0.033 | nessuna |

Non essendoci spike, il test Mann-Whitney spike-vs-normale non è calcolabile (NaN in
`correlations.csv`) — corretto, non è un errore.

Nessuna evidenza di power/thermal throttling: GPU power inchiodato a 288.5 W ±0.05 W, temp max
69 °C, clock stabile a ~2 330 MHz. Le colonne `GPUPowerLimited`/`GPUTemperatureLimited` sono
**NA** in tutto il dataset, quindi il throttling **non è verificabile direttamente**; le prove
indirette (varianza di power e clock quasi nulla) sono però coerenti con "nessun limite attivo".

## 7. Grafici

`charts/steelnomad_{frametime_over_time, frametime_distribution, percentile_curve, fps_per_run,
fps_timeline, gpubusy_vs_frametime, cpubusy_vs_frametime, gpuclock_vs_frametime,
gpupower_vs_frametime}.png`

## 8. Verdetto

Steel Nomad è un **eccellente strumento di misura** per questo progetto: CV 0.105%, zero spike,
zero dropped frame, 99.9% GPU-bound, sette run indistinguibili. È il workload di controllo da
usare per tutto ciò che tocca il costo di esecuzione degli shader.

Limite: essendo un benchmark chiuso di UL, non è un carico *rappresentativo* dei giochi target e
non espone il percorso di compilazione shader (la cache è già calda dopo il primo run).
Resta valido il piano di aggiungere **Black Myth: Wukong** come workload controllato aperto.
