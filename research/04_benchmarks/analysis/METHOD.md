# Metodo di analisi — Phase 1E

Tutti i CSV raw in `research/` sono **intatti**: nessuno script apre i file in scrittura.
Codice: [`tools/pmparse.py`](../../../tools/pmparse.py) (parser + self-check),
[`tools/validate.py`](../../../tools/validate.py), [`tools/analyze.py`](../../../tools/analyze.py).

## 1. Sorgente dati

PresentMon 2.5.1, loadout completo (66 colonne). Header **identico** in tutti e 14 i file
(md5 `6f207fcf…`), quindi un solo parser.

Colonne realmente popolate (frazione media non-NA su 14 file):

| Popolate 100% | Popolate 50% | Sempre vuote (NA) |
|---|---|---|
| Application, ProcessID, SwapChainAddress, PresentRuntime, SyncInterval, PresentFlags, AllowsTearing, PresentMode, FrameType, TimeInSeconds, MsBetweenPresents, MsBetweenDisplayChange, MsInPresentAPI, MsRenderPresentLatency, MsUntilDisplayed, CPUStartTime, MsBetweenAppStart, MsCPUBusy, MsCPUWait, MsGPULatency, MsGPUTime, MsGPUBusy, MsGPUWait, MsAnimationError, MsFlipDelay, AnimationTime, GPUPower, GPUVoltage, GPUFrequency, GPUTemperature, GPUUtilization, GPUMemoryFrequency, GPUMemorySize, GPUMemorySizeUsed, GPUMemoryMaxBandwidth, GPUFanSpeed[0], CPUUtilization, CPUFrequency | MsBetweenSimulationStart, MsPCLatency | MsAllInputToPhotonLatency, MsClickToPhotonLatency, InstrumentedLatency, 3D/ComputeUtilization, MediaUtilization, GPUMemoryPower, GPUMemoryVoltage, GPUMemoryEffectiveFrequency, GPUMemoryTemperature, GPUMemoryRead/WriteBandwidth, GPUFanSpeed[1..3], **tutti i `*Limited`**, CPUPower, CPUTemperature |

Conseguenze operative:

- **Non esiste una colonna `Dropped`** in questo loadout. Un frame mai arrivato al display
  lascerebbe `MsBetweenDisplayChange` NaN o 0: **0 occorrenze su 14 file** → 0 dropped frame.
- **Tutte le colonne `GPUPowerLimited` / `GPUTemperatureLimited` / … sono NA.** Il driver AMD
  non espone i limit-reason a PresentMon su questa GPU. Quindi *"power limit"* come causa degli
  spike **non è verificabile con questi dati**, solo inferibile indirettamente da clock+power.
- CPUPower e CPUTemperature non sono disponibili.

### Frequenza di campionamento della telemetria (misurata)

| Segnale | Aggiornamenti/s |
|---|---:|
| GPUFrequency, GPUPower, GPUUtilization, GPUVoltage | ~9–10 Hz |
| GPUTemperature | ~3.7 Hz |
| CPUUtilization, CPUFrequency | ~1 Hz |
| GPUMemorySizeUsed | ~0.05 Hz (3–4 valori per run) |

**Questo è il vincolo più importante dell'intera analisi.** A 620 FPS un campione di clock GPU
copre ~60 frame; a 41 FPS ne copre ~4. Qualsiasi correlazione per-frame tra frametime e
clock/power/VRAM è quindi **sovra-campionata**: il valore di telemetria è costante su decine di
righe. I ρ di Spearman su questi segnali sono riportati ma **non vanno letti come causalità**, e
per Fortnite la risoluzione è insufficiente a distinguere causa da effetto su un singolo spike.

## 2. Finestra valida

`duration_valid` esclude:

- **head**: `TimeInSeconds < 2.0 s`. Tutte le catture Fortnite contengono uno spike di
  365–448 ms a t≈0.44–0.55 s (artefatto di avvio cattura / warm-up engine) e il primo bin da 2 s
  gira a 473–498 FPS contro 600+ a regime. Steel Nomad ha uno spike di 41–53 ms a t≈0.2 s.
- **coda**: l'ultimo secondo incompleto (`TimeInSeconds >= floor(max)`), altrimenti l'ultimo bin
  sembra un crollo di FPS quando è solo troncato.

I file raw non vengono toccati: il trim è in memoria.

## 3. Frametime

Segnale primario: **`MsBetweenPresents`** (pacing dei present dell'applicazione).
`MsBetweenDisplayChange` è riportato a parte (`ft_disp_*`) come pacing effettivo a schermo.

## 4. FPS e low

- `avg_fps` = frame validi / durata finestra valida.
- `median_fps` = 1000 / mediana(frametime).
- **`fps_1pct_low_time` / `fps_01pct_low_time` (metrica primaria, "time-integrated")**:
  si ordinano i frametime dal più lento, si accumulano finché il tempo cumulato raggiunge
  l'1% (0.1%) del **tempo totale** della finestra; il risultato è `n_selezionati / tempo_selezionato`.
  È la definizione che pesa gli hitch per la loro durata: un singolo frame da 1000 ms la muove,
  un percentile no.
- **`fps_1pct_low_p99` / `fps_01pct_low_p999` (secondaria, "percentile")**: `1000 / p99(frametime)`.
  È la definizione usata dal riassunto GUI di PresentMon (`1st Percentile FPS`).

Le due divergono per costruzione. Self-check in `pmparse._selfcheck`: su
999 frame da 10 ms + 1 frame da 1000 ms il metodo percentile restituisce 100 FPS,
quello time-integrated 1 FPS. Entrambi sono in tabella; **i confronti A/B futuri usano il primo**.

Nota statistica: con 2110–2359 frame validi, lo 0.1% low di Steel Nomad poggia su ~2 frame
(colonna `frames_in_01pct`). Per Fortnite sono ~34. Lo 0.1% low di Steel Nomad **non è
statisticamente significativo** e non va usato come metrica di confronto.

## 5. Definizione di spike / stutter

Un frame *i* è **spike** se:

```
ft[i] > 2.0 × median(ft in finestra centrata di 21 frame)
        AND
ft[i] - median_locale >= 2.0 ms
```

**severe spike** se `ft[i] > 3.0 × median_locale AND ft[i] >= 8.0 ms`.

Ragione della doppia condizione: a 620 FPS il median locale è 1.6 ms, quindi il solo criterio
"2× la mediana" segnalerebbe qualsiasi frame da 3.3 ms, che non è percepibile. Il pavimento
assoluto di 2 ms filtra il rumore ad alto frame rate. La mediana **mobile** (non globale) fa sì
che un cambio di regime sostenuto (es. la caduta a 545 FPS di `fortnite_r4`) **non** venga
contato come una raffica di spike: viene contato solo ciò che è isolato rispetto al vicinato.
Entrambi i comportamenti sono coperti dal self-check.

Metriche derivate: `spikes`, `spikes_per_min`, `severe_spikes`,
`spike_time_lost_ms` (somma dell'eccesso sopra la mediana locale = tempo perso in hitch).

## 6. Varianza run-to-run e soglia di rilevabilità

Per metrica: media, SD (ddof=1), **CV%** = 100·SD/media, range%, semiampiezza IC95%.
Run anomali: **z-score modificato su MAD**, |z| > 3.5.

**Minimum Detectable Difference (MDD)** — la differenza più piccola che un A/B con n run per
gruppo può dichiarare reale (t a due campioni, α=0.05, potenza 0.80):

```
MDD% = CV% × (t(0.975, 2n-2) + t(0.80, 2n-2)) × sqrt(2/n)
```

Con n=7 il fattore è **1.631 × CV%**.

## 7. Correlazioni

Spearman ρ e Pearson r per-run tra frametime e ogni segnale popolato, più, per i soli frame
marcati spike, un Mann-Whitney U contro i frame normali e il delta di mediana.

**Avvertenza obbligatoria**: `MsCPUBusy` correla ρ≈0.999–1.000 con il frametime **per
definizione**, non per causa: in PresentMon 2.x `frametime ≈ MsCPUBusy + MsCPUWait`. Vale lo
stesso per `MsGPUBusy` in un carico GPU-bound. Correlazione e causa probabile sono riportate
separatamente in `baseline_comparison.md`.

## 8. Validazione del parser

`tools/validate.py` confronta il parser con i `-stats.csv` prodotti da PresentMon stesso, sulla
finestra **non tagliata**, su tutti e 14 i file. Risultato:

| Metrica | Deviazione massima |
|---|---:|
| Total Frames | **0.0000%** (identico su 14/14) |
| Duration | 0.0102% |
| Average FPS | 0.0534% |
| Minimum FPS | 0.0018% |
| 1st Percentile FPS | 0.0001% |
| 5th Percentile FPS | 0.0001% |
| Maximum FPS | 0.0005% |

Output: `parser_validation.csv`. Il match esatto sui percentili conferma che
`MsBetweenPresents` è il segnale che PresentMon usa per FPS/percentili.
