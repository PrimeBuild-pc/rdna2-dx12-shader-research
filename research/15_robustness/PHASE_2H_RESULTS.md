# Phase 2H — Robustezza e causa del guadagno

RX 6950 XT, driver 32.0.21045.5002. Nessun driver / Registry / cache / gioco toccato.
Criteri di 2G **congelati**: tolleranza relativa 1e-4 decisa a priori, soglia di accettazione
`|d%| > max(2.32%, spread_variante, spread_baseline)`.

Dati: [`robust_correct.csv`](robust_correct.csv), [`robust_datasets.csv`](robust_datasets.csv),
[`robust_scaling.csv`](robust_scaling.csv), [`../16_corpus/corpus_results.csv`](../16_corpus/corpus_results.csv),
[`../17_rgp/latency_sweep.csv`](../17_rgp/latency_sweep.csv).
Codice: [`tools/robust.py`](../../tools/robust.py), [`tools/corpus.py`](../../tools/corpus.py),
[`tools/cpu_ref.py`](../../tools/cpu_ref.py), [`tools/isa_mem.py`](../../tools/isa_mem.py).

---

## 0. Il risultato che cambia l'interpretazione di 2G

**La baseline di 2G non era il default di DXC: era uno shader con `[unroll]` scritto a mano
da me.** Il default di DXC su `s4_pressure` produce già il codice veloce.

```
pressure24 con [unroll] esplicito (= "baseline" di 2G)   66 175 ns
pressure24 senza attributi        (= default di DXC)     55 100 ns
pressure24 con [loop]             (= "L3_loop" di 2G)    55 385 ns
```

`dxc_default` e `L3_loop` coincidono entro lo 0.5% su tutti e 20 i dataset e su tutte e 15 le
combinazioni di scala. Quindi l'optimizer di 2G **non ha battuto il compilatore**: ha annullato
una pessimizzazione che avevo introdotto io nella baseline.

In 2G avevo scritto *«su questo shader il default di DXC (unroll completo) è una scelta
sbagliata»*. **È falso.** Il default di DXC non era unroll completo. La frase va cancellata.

Il ciclo automatico resta valido come meccanismo — ha trovato una trasformazione reale,
riproducibile e misurata. Ma il punto di riferimento era sbagliato, e con un riferimento
sbagliato il guadagno non significa quello che sembrava.

## 1. Rimisura con il banco corretto

Durante 2H ho trovato **due difetti di misura nel banco**, entrambi corretti prima di
qualunque conclusione:

1. **Warm-up a iterazioni invece che a tempo.** 10 iterazioni di uno shader da 3 µs sono 30 µs:
   il clock GPU non sale e lo shader si misura a clock basso. Misurato su `poly_horner`:
   26 565 ns come prima variante della lista, 5 135 ns dopo secondi di carico — **5.2×**.
2. **Duty cycle basso.** Con una submission + fence per ogni misura, per gli shader corti la
   GPU è ferma la maggior parte del tempo e il governor tiene i clock giù. Ora tutte le `reps`
   misure stanno in **una sola command list** e la GPU lavora senza pause.

Dopo la correzione la ripetibilità fra processi indipendenti è 0.3–0.6% (prima fino a 419%).

Il set di 2G rimisurato, 5 processi freschi:

| variante | 2G (banco difettoso) | 2H (banco corretto) | spread | esito col criterio congelato |
|---|---:|---:|---:|---|
| `all_loop` | −29.87% | **−16.65%** | 0.60% | accettata |
| `L3_loop` | −30.03% | **−16.31%** | 0.37% | accettata |
| `L2_loop` | −14.54% | **−1.63%** | 0.42% | **respinta** (dentro il rumore) |
| `baseline` | 0 | 0 | **12.70%** | riferimento |
| `wave64` | +7.05% | +19.77% | 1.69% | peggiore |

**Il terzo vincitore di 2G (`L2_loop`) non sopravvive.** Restano due, e sono la stessa cosa.

La baseline `[unroll]` ha uno spread run-to-run del **12.7%** contro lo 0.3–0.6% di tutte le
altre, ed è **bimodale**: su 75 misure, 35 cadono a 66–68 µs e 13 a 74–76 µs. Le altre varianti
sono unimodali.

## 2. Correttezza numerica — il risultato più severo

20 dataset deterministici (zeri, uni, 1e-6, 1e6, negativi, alternati, magnitudini miste
1e-8..1e8, casuali su 4 scale, multipli di π e π/2, 1e-30, 1e30, potenze di 2 esatte, interi
grandi, rampa, zeri sparsi), 3 workload, output **completo** confrontato (1 048 576 float),
metriche: max abs, max rel, RMS, RMS relativo, NaN/Inf divergenti.

**Le tre varianti superano la tolleranza di 1e-4 su 7 dataset su 20.**

| ds | input | max rel err (L3_loop) | verdetto |
|---:|---|---:|---|
| 4 | large_1e6 | 2.96e−04 | **NO** |
| 7 | mixed_mag_1e-8_1e8 | 1.70e−03 | **NO** |
| 8 | rand_pm1 | 1.20e−03 | **NO** |
| 9 | rand_pm100 | 2.26e−03 | **NO** |
| 13 | big_int | 5.89e−04 | **NO** |
| 18 | rand_sparse_zero | 6.47e−04 | **NO** |
| 19 | rand_pm10000 | 2.98e−04 | **NO** |
| | altri 13 | ≤ 1.14e−06 | SI |

Nessun NaN/Inf divergente in nessun caso. Il RMS relativo è **1e−7 ovunque**, anche dove il
max rel supera la soglia: gli errori sono punti isolati di cancellazione nella somma finale,
non un errore sistematico. È la firma della riassociazione in virgola mobile, non di un
risultato semanticamente diverso (per confronto, le varianti `L2_unroll*` scartate in 2G
avevano max rel **1.5–2.0**).

Il punto decisivo: **`dxc_default` fallisce sugli stessi identici 7 dataset con gli stessi
identici errori.** Non è la trasformazione a essere numericamente instabile — è lo shader:
qualunque riordino della somma di 24 prodotti su input mal condizionati esce da 1e-4. La
tolleranza scelta a priori è troppo stretta per questo shader, ma **non la cambio a posteriori**.

`wave64` è l'unica variante **bit-identica** alla baseline su tutti i 20 dataset. Ed è la più lenta.

### Reference CPU

Implementata in float32 sugli **stessi bit** letti dalla GPU (l'input viene dumpato dal banco,
non rigenerato). Baseline GPU vs reference CPU:

| dataset | max rel err | RMS rel | NaN/Inf div |
|---|---:|---:|---:|
| orig_0.25_1.25 | 3.09e−04 | 1.05e−05 | 0 |
| rand_pm1 | 4.60e−01 | 3.35e−06 | 0 |
| pow2_exact | 1.02e+00 | 6.94e−03 | 0 |

La GPU calcola la matematica giusta (RMS rel 1e−5 su ds0). Le divergenze grandi sono
attribuibili a `v_sin_f32`/`v_cos_f32`, che su argomenti grandi (pow2_exact arriva a ~2^12·48)
hanno una riduzione di range molto meno precisa di `numpy`. **Nota importante di scala:** lo
scarto GPU↔CPU (4.6e−01 su rand_pm1) è tre ordini di grandezza più grande dello scarto fra le
varianti GPU (1.2e−03). Il rumore numerico dello shader domina quello della trasformazione.

## 3. Il vantaggio non dipende da cache o warm-up

- **PSO**: 0.07–0.17 ms per tutte le varianti, nessuna differenza sistematica.
- **Processi freschi**: ogni run è un processo nuovo; la ripetibilità è 0.3–0.6%.
- **Warm-up separato**: `ns_cold`, `ns_warm_median` e `warm_iters` sono in tutti i CSV. La
  baseline `[unroll]` parte da ~410 µs a freddo contro ~55 µs di `L3_loop`, e serve un ordine
  di grandezza più warm-up per stabilizzarsi.
- Nessuna cache di shader è stata cancellata o manipolata.

## 4. Dipendenza da input e da scala

**20 dataset, 5 run, 262 144 thread:**

`L3_loop` e `all_loop` sono più veloci della baseline **su tutti e 20 gli input**, con
guadagno fra **−12.75% e −25.23%**. La direzione è robusta; la magnitudine varia di 2×.
`L2_loop` va da −11.04% a **+1.54%**: non è un vincitore. `wave64` è peggio ovunque
(+7.81% … +19.86%).

**3 dataset × 3 workload × 5 dpm × 5 run = 75 configurazioni:**

Il guadagno regge in tutte e 45 le combinazioni di scala, fra −12.2% e −32.0%. È **più
grande sui workload piccoli** (65 536 thread: −19% … −32%) che su quelli grandi
(1 048 576 thread: −12% … −25%).

**Verdetto col criterio congelato applicato ai 20 dataset:**

| variante | accettata | sopra il rumore | output entro 1e-4 |
|---|---:|---:|---:|
| `dxc_default` | 13/20 | 20/20 | 13/20 |
| `L3_loop` | 13/20 | 20/20 | 13/20 |
| `all_loop` | 13/20 | 20/20 | 13/20 |
| `L2_loop` | **0/20** | 0/20 | 13/20 |
| `wave64` | 0/20 | 0/20 | 20/20 |

## 5. Causa — catena supportata, con tre controlli

Non ho potuto estrarre contatori di stall: RGP cattura correttamente (due tracce in
[`../17_rgp/`](../17_rgp/), catturate con `RadeonDeveloperPanelCLI --rgp-auto-capture=dispatch`
e instruction tracing) ma si legge solo dalla GUI, che non posso interrogare a riga di comando.
Le tracce restano disponibili.

La causa è stata determinata per altra via, con controlli.

### Cosa cambia nell'ISA

Occupancy identica: **entrambe le versioni allocano 144 VGPR dall'hardware**, LDS 0, scratch 0.
Nessuna delle due contiene branch — `[loop]` **non** impedisce lo srotolamento nell'ISA finale.
La versione `[unroll]` ha perfino *meno* istruzioni. Quindi non è né occupancy, né pressione
registri, né dimensione del codice.

Ciò che cambia è **come sono schedulate le 24 load**:

| | `[unroll]` (lenta) | default / `[loop]` (veloce) |
|---|---:|---:|
| load VMEM | 24 | 24 |
| `s_waitcnt` | **23** | **14** |
| `s_clause` | **1** | **3** |
| distanza load→wait, mediana | **3** | **8** |
| distanza load→wait, media | 8.5 | 12.4 |
| load con distanza ≤ 2 istruzioni | **12 su 24** | **1 su 24** |
| load emesse per gruppo, media | **1.5** | **6.0** |

La versione `[unroll]` emette le load quasi una per volta e si ferma entro 3 istruzioni; quella
a ciclo le raggruppa a 6 e ha ~9 istruzioni di lavoro utile prima del wait.

### I tre controlli

1. **Controllo nullo — tolgo la memoria.** `pressure24_nomem` ha la stessa aritmetica, lo stesso
   array `float4 v[24]`, la stessa pressione registri, ma i valori sono calcolati invece che
   letti (0 load nell'ISA). La penalità di `[unroll]` **sparisce**: +34.54% con le load,
   −4.44% senza.
2. **Controllo negativo — rendo le load dipendenti.** `mem_gather` calcola l'indirizzo con una
   catena LCG seriale. `[unroll]` cambia l'ISA esattamente come in `mem_seq` (11→32 load,
   gruppi 5.5→8.0) ma il guadagno è **+0.01%**: le load in più non possono partire in anticipo.
   L'ISA da sola non predice; serve la struttura delle dipendenze.
3. **Controllo positivo — vario la latenza.** Stesso shader, working set diverso:

   | working set | default | `[unroll]` | penalità |
   |---|---:|---:|---:|
   | 4 KB | 32 170 | 32 070 | **−0.31%** |
   | 64 KB | 33 255 | 35 105 | +5.56% |
   | 1 MB | 55 010 | 69 185 | **+25.77%** |
   | 16 MB | 72 845 | 72 940 | **+0.13%** |
   | 64 MB | 73 840 | 74 480 | +0.87% |

   La penalità **non cresce monotonamente con la latenza**: ha un massimo. A 4 KB tutto è in
   cache vicina e lo scheduling non conta; a 16–64 MB entrambe le versioni sono già limitate
   dalla memoria (il default sale da 55 a 73 µs) e di nuovo non conta. La penalità esiste solo
   nel regime intermedio, dove la latenza è significativa ma non ancora il vincolo dominante —
   cioè esattamente dove nasconderla ha valore.

### Enunciato

> `[unroll]` su un ciclo che tiene vivo un array grande costringe lo scheduler a intercalare
> ogni load con l'ALU che la consuma. I gruppi di load collassano da 6 a 1.5 e la distanza
> load→wait dimezza, quindi il wave si ferma sulla latenza di memoria ~24 volte invece di ~14.
> Il costo si manifesta solo quando la latenza è significativa e non è già il vincolo dominante.

Confidenza: **strong**, non *confirmed*. Ho l'evidenza strutturale nell'ISA più tre controlli
indipendenti, ma **non ho misurato direttamente i cicli di stall**.

## 6. Generalizzazione — 20 shader, 65 varianti

Corpus: ALU dipendente, ALU con ILP, trigonometria, trascendenti, Horner, pressione registri a
3 taglie (8/24/48) più la versione senza memoria, memoria sequenziale / con stride / gather,
mix memoria+ALU, riduzioni (dot, min/max), branch uniforme, branch divergente, dipendenza
loop-carried stretta, riduzione LDS, shuffle LDS. Trasformazioni: default, `[loop]` ovunque,
`[unroll]` ovunque, `[loop]` solo sull'ultimo ciclo. 5 run indipendenti.

**`[loop]` è quasi sempre un no-op: 0 meglio, 0 peggio, 20 uguale** (mediana +0.00%, estremi
−2.66% / +0.53%). Stesso esito per `[loop]` solo sull'ultimo ciclo. Il default di DXC si comporta
già come `[loop]`.

**La variabile che conta è `[unroll]`, e va in entrambe le direzioni:**

| | n | mediana | migliore | peggiore |
|---|---:|---:|---:|---:|
| `all_unroll` | 20 | −3.08% | **−65.89%** | **+40.69%** |

- **9 migliorano**, **3 peggiorano**, **8 invariati**
- peggior regressione: `lds_reduce` **+40.69%**

| dove `[unroll]` aiuta | d% | perché (dai dati ISA) |
|---|---:|---|
| `alu_ilp4` | −65.89 | il compilatore **collassa algebricamente** il ciclo: 110→21 istruzioni |
| `poly_horner` | −47.87 | più ILP nella catena di Horner (67→142 istruzioni, comunque 2× più veloce) |
| `trig_heavy` | −25.60 | catena di trascendenti, nessuna memoria |
| `transcend` | −23.82 | idem |
| `mem_alu_mix` | −8.99 | più load in volo (11→25) |
| `lds_shuffle` | −8.71 | più letture LDS indipendenti |
| `reduce_dot` / `reduce_minmax` / `mem_seq` | −6 | load in volo 12→33 |

| dove `[unroll]` danneggia | d% | perché |
|---|---:|---|
| `lds_reduce` | +40.69 | wait LDS 26→56, VGPR 40→68 |
| `pressure24` | +34.54 | gruppi di load 6.0→1.5, wait 14→23 |
| `pressure48` | +31.01 | idem, e spilla 176 byte di scratch in **tutte** le varianti |

**Caratteristica che discrimina**: conta se il corpo del ciclo tiene vivo un array grande fra
le iterazioni. Se sì, l'unroll costringe lo scheduler a serializzare load e consumo → costo.
Se no (corpo piccolo, valori indipendenti), l'unroll espone più operazioni in volo → guadagno.
Il conteggio di istruzioni e di VGPR non discrimina.

## 7. Limiti dichiarati

- **Pavimento del banco: ~3.15 µs**, misurato con uno shader di sola scrittura (4 MB di store).
  `alu_ilp4__all_unroll` (3 130 ns) e `alu_chain_dep` (3 105–3 190 ns) sono **al pavimento**: i
  loro delta sono limitati dalla banda di scrittura, non dal calcolo. Il −65.89% di `alu_ilp4`
  va letto come «il compilatore ha ridotto lo shader a nulla», non come una vittoria dello scheduling.
- Contatori di stall **non misurati**. La causa è supportata da struttura ISA + tre controlli.
- Corpus **sintetico**. Nessuna conclusione trasferita a shader reali di gioco.
- Il criterio 1e-4 è troppo stretto per shader con somme mal condizionate; l'ho tenuto perché
  era congelato, e ho riportato in parallelo il RMS relativo.
- `L2_unroll4/8/12` (i falsi positivi da −57%/−61% di 2G) non sono stati rianalizzati: restano
  scartati per output errato.

## 8. Risposta alla domanda della fase

> **Il −30% è un risultato robusto e qual è la classe di shader per cui questa trasformazione
> è utile?**

**No, il −30% non regge**, per due motivi distinti:

1. Col banco corretto è **−16.5%**, non −30%. La differenza era clock GPU non stabilizzato.
2. Soprattutto: era misurato contro una baseline `[unroll]` scritta da me. **Contro il default
   di DXC il guadagno è zero.** `[loop]` non batte il compilatore su nessuno dei 20 shader del
   corpus.

Quello che **è** robusto è il fatto complementare: **`[unroll]` esplicito è una pessimizzazione
in una classe identificabile di shader**, e lì il guadagno del rimuoverlo (−12.75%…−32%) è
riproducibile su tutti i 20 input, tutte le scale, con spread <1%.

**La classe**: cicli il cui corpo mantiene vivo fra le iterazioni un array indicizzato
alimentato dalla memoria, con working set nel regime dove la latenza è significativa ma non
dominante. Fuori da questa classe `[unroll]` è neutro o utile.

Corollario per il progetto: la leva non è `[loop]`. È **evitare `[unroll]` dove fa male**, e
l'unico modo per saperlo è misurare — il criterio statico giusto non esiste.
