# Phase 2F — Microbenchmark D3D12: varianza e Wave32 vs Wave64

RX 6950 XT (vendor 0x1002, 16337 MB), driver 32.0.21045.5002.
D3D12 nativo, timestamp query, nessun rendering, nessun VSync, nessun gioco.
Codice: [`bench.cpp`](bench.cpp) (MSVC 14.51, `/O2`), shader compilati con DXC (SDK 10.0.26100).

---

## 1. Come misura il banco

- Adapter selezionato con `EnumAdapterByGpuPreference(HIGH_PERFORMANCE)`, verificato AMD.
- Coda DIRECT, `ID3D12QueryHeap` di tipo `TIMESTAMP`, `GetTimestampFrequency()` = **100 MHz**
  (risoluzione 10 ns).
- Ogni **misura** = `EndQuery(start)` → N `Dispatch` → `EndQuery(end)` → `ResolveQueryData` →
  execute → fence wait → lettura. Il tempo riportato è **ns per singolo dispatch**
  (totale del batch / N).
- **Warm-up: 10 misure scartate** prima di iniziare, così il clock GPU è salito e stabile.
- 25 misure per variante, 8 dispatch per misura, 4096 gruppi per dispatch.
- Statistiche: mediana, media, p95, deviazione standard, CV, min, max.

### Un difetto di correttezza trovato e corretto

Alla prima esecuzione `s3_mem` aveva **CV 68.7%** e `s4_pressure` 9.6%. Causa: il buffer SRV
era **non inizializzato**, quindi gli shader leggevano bit indeterminati — inclusi denormali e
NaN, che sulla GPU hanno costi diversi. Dopo aver inizializzato il buffer con dati noti
(`t ∈ [0.25, 1.25]`, nessun denormale, nessun NaN):

| shader | CV prima | CV dopo |
|---|---:|---:|
| `s3_mem` | **68.71%** | **0.09%** |
| `s4_pressure` | 9.57% | 5.78% |
| `s2_alu` | 0.04% | 2.06% |
| `s5_divergent` | 0.10% | 0.11% |

Senza questa correzione qualunque confronto sarebbe stato rumore.

## 2. Varianza del banco (misurata prima di cambiare qualsiasi cosa)

Tre esecuzioni indipendenti del processo, stesse baseline, nessuna modifica:

| shader | run 1 | run 2 | run 3 | mediana | **spread run-to-run** | CV intra-run |
|---|---:|---:|---:|---:|---:|---:|
| `s2_alu` | 56 960 | 56 960 | 56 970 | 56 960 ns | **0.02%** | 1.5–2.1% |
| `s3_mem` | 121 285 | 120 950 | 121 055 | 121 055 ns | **0.28%** | 0.09–0.12% |
| `s4_pressure` | 79 400 | 79 420 | 77 575 | 79 400 ns | **2.32%** | 5.8–6.7% |
| `s5_divergent` | 6 825 | 6 840 | 6 835 | 6 835 ns | **0.22%** | 0.10–0.23% |

**La mediana è molto più stabile del CV intra-run.** Su `s4_pressure` il CV interno è ~6% ma la
mediana varia del 2.3%: il rumore è fatto di outlier alti (probabile oscillazione del boost
clock), non di dispersione simmetrica. Per questo la metrica di confronto è la **mediana di
mediane su 3 run**, non la media.

### Soglia decisionale

```
s2_alu        : rumore ±0.02%  ->  reale un cambiamento >= 0.5%
s3_mem        : rumore ±0.28%  ->  reale un cambiamento >= 1%
s5_divergent  : rumore ±0.22%  ->  reale un cambiamento >= 1%
s4_pressure   : rumore ±2.32%  ->  reale un cambiamento >= 5%   (shader piu' rumoroso)
```

Un outlier osservato e gestito: al run 1, `s5_divergent_w32/w64` hanno prodotto 35 430 e
40 830 ns contro ~6 840 e ~7 830 dei run successivi (5-6×). È il costo della prima creazione
PSO/compilazione, non tempo di esecuzione. La mediana su 3 run lo elimina; una media l'avrebbe
propagato.

## 3. Wave32 vs Wave64 — il risultato

`[WaveSize(N)]` in HLSL (SM 6.6) è l'equivalente legittimo di
`SCOption_GFX10_FORCE_WAVE32/64_SCHEDULING`, e **non richiede di toccare il driver**.

| shader | variante | ISA | VGPR | ΔVGPR | inst | wave | **ns (mediana 3 run)** | **Δ%** |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `s2_alu` | base | — | 24 | 0 | 1994 | 32 | 56 960 | — |
| | w32 | **identica** | 24 | 0 | 1994 | 32 | 56 975 | +0.03% |
| | **w64** | **cambiata** | **16** | **−8** | 1995 | 64 | 66 250 | **+16.31%** |
| `s3_mem` | base | — | 40 | 0 | 215 | 32 | 121 055 | — |
| | w32 | **identica** | 40 | 0 | 215 | 32 | 121 030 | −0.02% |
| | **w64** | **cambiata** | **32** | **−8** | 215 | 64 | 143 325 | **+18.40%** |
| `s4_pressure` | base | — | 144 | 0 | 691 | 32 | 79 400 | — |
| | w32 | **identica** | 144 | 0 | 691 | 32 | 78 620 | −0.98% |
| | **w64** | **cambiata** | **116** | **−28** | 678 | 64 | 85 410 | **+7.57%** |
| `s5_divergent` | base | — | 24 | 0 | 1037 | 32 | 6 835 | — |
| | w32 | **identica** | 24 | 0 | 1037 | 32 | 6 840 | +0.07% |
| | **w64** | **cambiata** | **20** | **−4** | 1037 | 64 | 7 830 | **+14.56%** |

### Tre conclusioni

**a) Il driver sceglie già wave32 di default.** `[WaveSize(32)]` produce un ISA **byte-identico**
alla baseline (stesso SHA-256 del disassemblato) su tutti e 4 gli shader, e differenze di tempo
fra −0.98% e +0.07%, tutte dentro il rumore. Non c'è niente da guadagnare.

**b) Wave64 riduce i VGPR in tutti i casi ed è più lento in tutti i casi.** Questo è il punto:

```
s4_pressure    VGPR 144 -> 116  (-19%)   inst 691 -> 678   ISA cambiata
               tempo 79 400 -> 85 410 ns  (+7.6%, sopra la soglia del 5%)
```

Meno VGPR **e** meno istruzioni, eppure **più lento**. La correlazione "meno registri = più
veloce" qui è falsificata da una misura diretta.

**c) Perché — e attenzione a come si leggono i VGPR.** Un VGPR in wave64 contiene 64 lane invece
di 32: in termini di file registri fisico, **116 VGPR wave64 ≈ 232 VGPR wave32-equivalenti**
contro i 144 della baseline. L'occupancy **peggiora**, non migliora. **Il confronto diretto del
numero di VGPR fra wave32 e wave64 è fuorviante** e non va messo nella stessa colonna senza
questa avvertenza. RDNA2 è progettata attorno a wave32 e i risultati lo confermano su tutti e
quattro i profili di shader (ALU-bound, memory-bound, register-pressure, divergente).

## 4. Classifica delle varianti più veloci

**Nessuna variante è più veloce della baseline.** Non ne invento cinque.

| # | variante | Δ vs baseline | soglia rumore | verdetto |
|---|---|---:|---:|---|
| 1 | `s4_pressure_w32` | −0.98% | ±2.32% | **dentro il rumore** — non è un miglioramento |
| 2 | `s3_mem_w32` | −0.02% | ±0.28% | dentro il rumore |
| 3 | `s2_alu_w32` | +0.03% | ±0.02% | identico (ISA byte-identico) |
| 4 | `s5_divergent_w32` | +0.07% | ±0.22% | dentro il rumore |
| 5 | *(tutte le w64)* | +7.6% … +18.4% | — | **peggiori, in modo riproducibile** |

Il `−0.98%` di `s4_pressure_w32` è la sola cifra negativa fuori dallo zero, ma l'ISA è
**byte-identico** alla baseline: è impossibile che sia un effetto reale, ed è ampiamente sotto
il rumore di quello shader (±2.32%). Contarlo come miglioramento sarebbe un errore.

## 5. Cosa è stabilito

La catena richiesta è chiusa e funzionante:

```
HLSL -> DXC -> DXIL -> compilatore AMD (driver installato) -> ISA RDNA2 + VGPR/SGPR/inst
     -> esecuzione reale sulla RX 6950 XT -> tempo GPU in ns (timestamp query)
```

Il banco è riutilizzabile: dato un `.cso`, produce una misura con rumore noto. È la base su cui
un ciclo automatico "genera variante → compila → misura → tieni/scarta" può girare.

## 6. Limiti

- Solo compute shader; nessuna pipeline grafica (niente PS/VS reali, niente render target).
- Un solo dimensionamento (4096 gruppi, 8 dispatch/misura): non ho verificato se il ranking
  regge a occupancy diverse.
- Le misure includono il costo di `Dispatch` back-to-back senza barriere fra loro: dispatch
  consecutivi dello stesso PSO possono sovrapporsi, quindi il numero è *throughput*, non latenza
  di un singolo dispatch isolato.
- `s4_pressure` resta il caso peggiore per rumore (±2.3%): serve più campionamento se lo si
  vuole usare per differenze fini.
- Nessuna verifica di correttezza numerica dell'output fra varianti: il brief la richiede
  ("non produce output diversi") e **non è implementata** — le varianti wave differiscono solo
  per l'attributo, ma un controllo del contenuto dell'UAV andrebbe aggiunto prima di accettare
  varianti che riscrivono il sorgente.
