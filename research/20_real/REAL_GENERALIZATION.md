# Phase 2K — Generalizzazione su shader reali + memoria delle misure

RX 6950 XT, driver 32.0.21045.5002. Pipeline di valutazione invariata rispetto a 2I/2J.
Nessun driver / Registry / cache / gioco toccato. Nessun gioco multiplayer usato.

Corpus: **DirectX-Graphics-Samples** (Microsoft) e **FidelityFX-SDK** (AMD), clonati in
shallow+sparse. Dati: [`measurement_memory.csv`](measurement_memory.csv) ·
[`shader_features.csv`](shader_features.csv) · [`transform_proposals.csv`](transform_proposals.csv) ·
[`validation_results.csv`](validation_results.csv) · [`corpus.csv`](corpus.csv) · [`probe.csv`](probe.csv).
Codice: [`tools/harvest2k.py`](../../tools/harvest2k.py) · [`tools/hlsl_tf.py`](../../tools/hlsl_tf.py) ·
[`tools/real2k.py`](../../tools/real2k.py) · [`tools/measure2k.py`](../../tools/measure2k.py) ·
[`bench2.cpp`](bench2.cpp).

---

## Risposta alla domanda

> **Su shader realistici mai visti, la memoria delle misure trova ottimizzazioni con meno
> benchmark rispetto al random?**

**Sì, circa 2.5×.** Su 24 shader reali di REAL_VALIDATION, mai usati per costruire il ranking:

| budget | memoria | hit rate | random | hit rate | P(random: 0 successi) | oracolo |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | **−6.57%** | 33% | **+1.59%** | 19% | 0.81 | −9.11% |
| 2 | **−7.02%** | 50% | −4.76% | 38% | 0.64 | |
| 3 | −7.02% | 58% | −6.59% | 48% | 0.58 | |
| 5 | −9.11% | 71% | −8.75% | 66% | 0.51 | |
| 8 | −9.11% | 71% | −9.11% | 71% | 0.50 | |

**La memoria con 2 benchmark (−7.02%) equivale a random con 5.**
Il divario più netto è a budget 1: la memoria trova −6.57%, mentre la singola scelta casuale
è in media una **regressione** (+1.59%).

Ma il vantaggio è **più piccolo di quello sul corpus sintetico** (2J: 4×), e il motivo è
strutturale, non statistico — vedi sezione 3.

## 1. Il corpus è davvero reale

| passo | quantità |
|---|---:|
| file HLSL nei due repo | 476 |
| entry point compute che compilano standalone | 66 |
| unici per DXIL | 64 |
| eseguibili con risorse fittizie | **64 / 64** |
| misurabili (baseline ≥ 5 µs) | 58 |
| **dev / REAL_VALIDATION** | **34 / 24** |

Lo split è per hash del nome, deterministico, fissato **prima** di costruire qualunque ranking.

Per eseguirli è servito un banco nuovo ([`bench2.cpp`](bench2.cpp)): questi shader vogliono
`Texture2D`, `RWTexture2D`, `Texture2DArray`, constant buffer, sampler, buffer strutturati,
raw e con contatore — non l'unico SRV `float4` del banco sintetico. La root signature viene
**sintetizzata dalla tabella dei binding letta nel disassembly DXIL**, e le risorse fittizie
sono create con il tipo giusto per ogni slot dichiarato. Il constant buffer è riempito con
valori benigni e non con zeri, che farebbero degenerare i cicli guidati da costanti.

## 2. La memoria delle misure

Un solo database persistente, [`measurement_memory.csv`](measurement_memory.csv), 216 righe.
Per ogni esperimento: shader, split, trasformazione, parametri, livello di correttezza,
max rel / RMS rel / NaN-Inf divergenti, Δ%, incertezza (SE), Δ+2SE, numero di run, tempo
base, workload, dataset, hash DXIL, VGPR, SGPR, LDS, branch, waitcnt, waitcnt per operazione
di memoria, distanza load→uso, clause, VMEM, numero di cicli, dimensione del threadgroup,
validità e verdetto.

Il predittore è **solo evidenza**: kNN (k=5) sulle feature ISA/sorgente normalizzate, media
pesata per distanza dei Δ osservati sugli shader dev più simili; fallback alla media globale
della trasformazione quando non ci sono esempi. **Nessuna regola scritta a mano.**

## 3. Il risultato strutturale: lo spazio delle trasformazioni collassa

Questo è il fatto più importante della fase.

Sull'IR sintetico di 2J avevo **17 trasformazioni** e ~11 applicabili per shader. Su HLSL
arbitrario ne restano mechanicamente sicure molte meno: **3.6 per shader in media**.

| trasformazioni applicabili | shader |
|---:|---:|
| 2 | 9 |
| 4 | 11 |
| 5 | 2 |
| 6 | 1 |
| 8 | 1 |

Il motivo è dichiarato e non aggirabile senza un vero AST: su sorgente arbitrario si può
applicare solo ciò che è **verificabile meccanicamente**.

- **Attributi di ciclo** (`[unroll]`, `[loop]`, `[unroll(4)]`, per ciclo o su tutti): sicuri
  per costruzione, sono hint di codegen.
- **`[WaveSize(N)]`**: applicabile sempre; se cambia il risultato lo dice il gate di
  correttezza, non un'euristica.
- **`numthreads`**: valida solo con guard (vedi sezione 4).

Le trasformazioni **strutturali** che avevano prodotto i risultati grossi in 2I/2J —
sollevamento di condizioni, split di accumulatori, tree reduction, batching delle load —
**non sono state implementate su HLSL reale**. Farlo richiede un AST HLSL vero; senza,
sarebbe "fidarsi del modello sulla correttezza", che il brief vieta esplicitamente.

Questo spiega perché il vantaggio della memoria si riduce da 4× a 2.5×: con 3.6 opzioni,
anche scegliere a caso arriva presto in fondo. A budget 8 tutte le politiche coincidono
perché hanno provato tutto.

## 4. Un errore di metodo trovato durante la fase

Le prime misure davano `tg32x1` / `tg128x1` / `tg256x1` a **esattamente −50%** su alcuni
shader. Era un artefatto, e la correttezza **non poteva** catturarlo.

`ParticleDispatchIndirectArgsCS` è `[numthreads(1,1,1)]` e scrive un solo scalare: **ogni
thread scrive lo stesso valore allo stesso indirizzo**. Il mio harness lo dispatcha su
65 535 gruppi per renderlo misurabile. Passando a `numthreads(32,1,1)` il dispatch diventa
32 768 × 32 = 16× più thread, ma misura −50% perché i gruppi da un thread solo sprecano il
wave. Il risultato è **identico** (le scritture sono idempotenti), quindi il gate numerico
passa. Il numero misura la mia scelta di dispatch, non lo shader.

Correzione, meccanica e dichiarata: una trasformazione è valida solo se **conserva il numero
totale di thread del dispatch**. 9 misure invalidate; restano nel database con
`valid=no_workload_mismatch` e sono escluse da ranking e valutazione.

La lezione generalizza: **il gate di correttezza non protegge da trasformazioni che cambiano
la quantità di lavoro senza cambiare il risultato.** Serve un invariante separato sul carico.

## 5. Il corpus sintetico aveva insegnato una cosa falsa

In 2F e 2H, su shader sintetici, `[WaveSize(64)]` era **sempre peggiore**: da +7.0% a +19.8%,
senza eccezioni. La conclusione registrata era «wave64 è sempre più lento su questa GPU».

Su shader reali (58, threadgroup ≥ 32):

| | n | mediana | migliore | accettate |
|---|---:|---:|---:|---:|
| `wave32` | 51 | +0.07% | −2.42% | **0** |
| `wave64` | 51 | −0.83% | **−49.86%** | **23** |

`wave64` è la trasformazione **più spesso accettata** dell'intera fase. `wave32` è un no-op,
coerente con 2F: il driver sceglie già wave32.

Il corpus sintetico non conteneva shader con il profilo che rende wave64 conveniente — ordinamenti
bitonici con gruppi da 1024 thread, LDS pesante, molte wave op. È esattamente il tipo di errore
che questa fase doveva scoprire.

## 6. I guadagni trovati su codice Microsoft/AMD non modificato

Tutti i seguenti sono su REAL_VALIDATION, tutti con correttezza **strict** (max rel ≤ 1e−6):

| shader | trasformazione | Δ | SE |
|---|---|---:|---:|
| `BitonicPreSortCS` | `[unroll(4)]` su tutti i cicli | **−77.43%** | 0.012 |
| `ParticleSpawnCS` | `[WaveSize(64)]` | **−49.86%** | 0.128 |
| `BitonicPreSortCS` | `[unroll(4)]` sul 2º ciclo | −39.12% | 0.014 |
| `BitonicPreSortCS` | `[WaveSize(64)]` | −32.12% | 0.142 |
| `ParticlePreSortCS` | `[WaveSize(64)]` | −23.62% | 5.663 |
| `DoFPass2CS` | `[unroll(4)]` su tutti i cicli | −17.85% | 0.407 |
| `DoFPass2CS` | `[unroll(4)]` sul 1º ciclo | −15.59% | 0.373 |
| `DebugDrawHistogramCS` | `[WaveSize(64)]` | −15.27% | 0.064 |
| `ParticleDepthBoundsCS` | `[WaveSize(64)]` | −7.67% | 0.312 |
| altre 8 fra −2.7% e −1.2% | | | |

**12 shader su 24** hanno almeno una variante accettata. Tasso di scarto per correttezza su
REAL_VALIDATION: **4.7%** (contro 0% sul corpus sintetico dopo le correzioni di 2J) — tutti
`fuori_tolleranza`, nessun NaN/Inf divergente.

> `ParticlePreSortCS` ha SE 5.66: il guadagno di −23.62% supera il rumore ma quello shader è
> instabile. Accettato dal criterio (Δ+2SE < 0), ma con margine sottile.

## 7. Un baseline che dichiaro non valido

Ho misurato anche una politica "solo regole" con un ordine di priorità fisso delle
trasformazioni: batte la memoria a budget 2 e 3 (−8.47% contro −7.02%).

**Non lo considero un risultato**: quell'ordine l'ho scritto io *dopo* aver visto 2J, quindi
contiene informazione che una politica non informata non avrebbe. È lo stesso errore che
avevo già dichiarato in 2J con l'ordine di catalogo. Il solo baseline pulito è random, ed è
quello su cui si legge il 2.5×.

## 8. Limiti dichiarati

- **Il codice è reale, i dati no.** Le risorse sono fittizie: texture riempite dal driver,
  constant buffer con valori plausibili ma inventati. Il ranking delle trasformazioni è
  condizionato a input sintetici. Su dati reali l'ordine può cambiare, e per gli shader
  data-dependent (culling, sorting) probabilmente cambia.
- **Il dispatch lo scelgo io** (~1M thread, o 1024×1024 per gli shader 2D), non
  l'applicazione. Vedi sezione 4 per quanto questo possa ingannare.
- **Nessuna trasformazione strutturale** su HLSL reale. È il tetto principale del risultato.
- **Deduplica a 2 livelli** (HLSL normalizzato + DXIL), non 3: l'ISA per ogni variante
  costava troppo tempo RGA. La deduplica DXIL ha comunque eliminato 30 varianti su 242.
- **Un solo dataset** per la correttezza, contro i 5 del corpus sintetico: con risorse
  fittizie non ha senso variarle, ma significa che il gate è più debole qui.
- 24 shader di validazione sono pochi per una statistica robusta sul confronto fra politiche;
  il 2.5× va letto come ordine di grandezza, non come misura precisa.

## 9. Cosa serve davvero adesso

Il collo di bottiglia non è più il predittore: è **il numero di trasformazioni applicabili
in modo verificabile a sorgente arbitrario**. Con 3.6 opzioni per shader, qualunque politica
di ricerca conta poco.

Le due strade, in ordine di valore:

1. **Un AST HLSL vero** (o l'uso del DXIL come IR intermedia), che riaprirebbe le
   trasformazioni strutturali che in 2I/2J valevano −30%/−70%.
2. **Phase 2L**: smettere di ottimizzare shader scelti da noi e far scegliere al profilo di
   un workload DX12 reale. Progetto in [`PHASE_2L_DESIGN.md`](PHASE_2L_DESIGN.md), non eseguito.

La (2) è quella che il brief indica come prossimo passo, ed è quella che dà valore economico
ai guadagni: un −77% su `BitonicPreSortCS` vale qualcosa solo se quello shader pesa qualcosa
nel frame — e questa fase non lo sa ancora.
