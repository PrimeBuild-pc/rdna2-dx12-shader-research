# Phase 2J — Feature-Guided Transformation Predictor

RX 6950 XT, driver 32.0.21045.5002. Pipeline di valutazione **invariata** rispetto a 2I.
Nessun driver / Registry / cache / gioco toccato.

Dati: [`shader_features.csv`](shader_features.csv) · [`transform_proposals.csv`](transform_proposals.csv) ·
[`search_history.csv`](search_history.csv) · [`validation_results.csv`](validation_results.csv) ·
[`budget_sweep.csv`](budget_sweep.csv) · [`correctness.csv`](correctness.csv) · [`dedup.csv`](dedup.csv).
Codice: [`tools/ir2j.py`](../../tools/ir2j.py) · [`tools/corpus2j.py`](../../tools/corpus2j.py) ·
[`tools/pred2j.py`](../../tools/pred2j.py) · [`tools/run2j.py`](../../tools/run2j.py) ·
[`tools/eval2j.py`](../../tools/eval2j.py).

---

## Risposta alla domanda

> **L'IA riesce a trovare trasformazioni utili con meno tentativi rispetto a cercare a caso?**

**Sì, di circa 4×.**

| budget | guidato: miglior guadagno | random: miglior guadagno | guidato: hit rate | random: hit rate |
|---:|---:|---:|---:|---:|
| 1 | **−22.19%** | −2.27% | 62.5% | 36.5% |
| 2 | **−37.18%** | −13.31% | 62.5% | 36.3% |
| 3 | −37.34% | −21.45% | 58.3% | 36.5% |
| 5 | −37.34% | −29.91% | 43.1% | 36.5% |
| 8 | −38.53% | −35.03% | 37.0% | 36.5% |

**Il guidato con 2 benchmark (−37.18%) batte random con 8 (−35.03%).**
Con budget 5 il guidato trova **l'ottimo esatto su 7 shader di validazione su 8**, e su quei
sette random non lo batte mai (P = 0.000 su 4000 estrazioni).

| shader (mai visto) | oracolo | guidato@5 | random@5 | P(random batte guidato) |
|---|---:|---:|---:|---:|
| `v_cond_mod4` | −80.53% | **−80.53%** | −43.83% | 0.000 |
| `v_cond_cheap` | −55.96% | **−55.96%** | −35.98% | 0.000 |
| `v_lds128` | −54.84% | **−54.84%** | −54.76% | 0.000 |
| `v_cond_uniform` | −46.26% | **−46.26%** | −39.00% | 0.000 |
| `v_dot_light` | −29.47% | **−29.47%** | −28.59% | 0.000 |
| `v_chain_exp` | −24.09% | **−24.09%** | −24.09% | 0.000 |
| `v_pipe8` | −0.90% | **−0.90%** | −0.56% | 0.000 |
| `v_pipe16` | −16.16% | −6.64% | −12.44% | **0.627** |

## Ma il merito non è delle mie regole

Questo è il risultato più importante della fase, e va contro l'ipotesi da cui sono partito.

| politica | frazione dell'oracolo catturata | hit rate |
|---|---:|---:|
| **A** — solo regole scritte a mano + prior statici | **80.1%** | 47.5% |
| **B** — A + evidenza misurata dai soli shader dev | **96.9%** | 42.5% |
| **C** — B + apprendimento online sulla validation | **96.9%** | 42.5% |
| **R** — random | **77.7%** | 35.9% |

Le regole da sole valgono **80.1% contro il 77.7% di random**: praticamente nulla. Tutto il
vantaggio arriva quando il punteggio usa la **storia misurata** dei dev shader al posto delle
regole (96.9%). Il predittore funziona perché ricorda misure, non perché ragiona bene.

E l'apprendimento online durante la validazione ha aggiunto **esattamente zero** (C = B):
con 8 shader e budget 5 non c'è abbastanza trasferimento fra shader diversi perché serva.
Risultato negativo pulito.

> **Nota su un controllo non valido.** Ho misurato anche una politica "ordine di catalogo"
> (prime 5 applicabili nell'ordine in cui ho scritto il catalogo): 97.4%, la migliore di tutte.
> **Non è un controllo neutro**: quell'ordine l'ho scritto io e riflette gli stessi prior del
> predittore. La riporto per completezza ma non prova niente. Il baseline valido è random.

## Le due sconfitte, e sono la stessa

Le regole che ho **dedotto ragionando** invece che misurando sono quelle che hanno fatto danni:

**R2 — "condizione uniforme sul wave ⇒ sollevarla è inutile".** Falsa. Su `v_cond_uniform`
(condizione `(gid.x + i) & 1`, uniforme sul wave) `hoist_cond2` vale **−46.26%**. La regola,
scritta senza una sola misura a supporto, penalizzava di −2.5 e buttava fuori dai primi 5
la variante migliore. La politica A perde qui il 92% del guadagno disponibile.

**R5 — "array vivo fra le iterazioni ⇒ niente unroll".** Vera a n=24 e n=48 (dove era stata
misurata: +34.5% e +31.0%), **falsa a n=16**, dove `unroll_all` vale −16.16%. Questa resta
sbagliata anche in B e C: l'interpolazione sulla dimensione dell'array tira verso l'evidenza
a n=24, e nessuna delle due politiche recupera `v_pipe16`. È l'unico shader dove random è
meglio del guidato.

Entrambe sono lo stesso errore: **una regola enunciata in assoluto invece che condizionata
all'intervallo di feature in cui è stata misurata.**

## Come funziona il sistema

Il salto rispetto a 2I: in 2I le varianti le scrivevo a mano. Qui uno shader è una struttura
dati e ogni trasformazione è una funzione IR → IR; il predittore sceglie *quali* applicare e
l'HLSL lo genera il programma. Il controllo è verificabile: l'emettitore riproduce
`bdiv__hoist_parity` di 2I **meccanicamente** dall'IR.

```
IR dello shader  ──►  feature (sorgente | DXIL | ISA della sola baseline)
                          │
                          ▼
                  regole interpretabili + evidenza misurata
                          │   (dove esiste evidenza, la regola tace)
                          ▼
                  top-N trasformazioni proposte
                          │
    ┌─────────────────────┴──────────────────────┐
    │  pipeline 2I, invariata:                   │
    │  emit HLSL → DXC → RGA → dedup H/DXIL/ISA  │
    │  → correttezza 5 dataset → benchmark       │
    │    appaiato → accept/reject                │
    └────────────────────────────────────────────┘
```

**17 trasformazioni** meccaniche: `unroll_all`, `loop_all`, `unroll_loads`, `widen2/4`,
`hoist_cond2/4`, `acc2/4`, `load_first`, `lds_stage`, `tree_reduce`, `wave_reduce`,
`tg32/128`, `raw_buffer`, `split_reduce`.
**10 regole** interpretabili, ognuna con l'evidenza dev che la giustifica scritta accanto.

Feature tenute separate come richiesto: 21 di sorgente (dall'IR, non dal testo), 9 da DXIL
(disassembly `dxc -Fc`), 15 da ISA AMD (RGA), più occupancy stimata da VGPR e da LDS.
**Il predittore vede solo le feature della baseline**: vedere l'ISA delle varianti
equivarrebbe a vederne il risultato.

## La correttezza ha trovato bug miei, non del compilatore

Al primo giro il gate ha respinto **10 varianti su 112**. Tutte per bug nelle **mie
trasformazioni meccaniche**, nessuna per comportamento del compilatore:

| variante | causa |
|---|---|
| tutti i `lds_stage` (6) | indice di staging sbagliato: `shm[gtid*n + e − t*n]` invece di `shm[gtid*n + e]` |
| `v_cond_uniform__tg32`, `__tg128` | **la trasformazione non è valida su quello shader**: la condizione legge `gid.x`, quindi cambiare `numthreads` cambia il risultato, non solo le prestazioni |
| `v_cond_mod4__hoist_cond4` | sollevamento con modulo 4 emesso con 2 rami invece di 4: i residui 2 e 3 finivano nel ramo sbagliato |

Il secondo è il più istruttivo: `tg32/tg128` ora è dichiarata non applicabile quando una
condizione dipende da `gid`/`gtid`. Dopo le correzioni: **112 su 112 corrette**, 43 accettate.

Deduplica a tre livelli: 14 varianti su 140 eliminate prima di misurarle
(HLSL normalizzato → DXIL → ISA).

## Limiti dichiarati

- **Corpus sintetico**, 6 dev + 8 validation, tutti dalla stessa famiglia di IR. Nulla è stato
  trasferito a shader di gioco reali.
- Gli shader di validazione li ho scritti io. Ho provato a metterci tre trappole deliberate
  per le mie stesse regole (`v_cond_uniform`, `v_cond_cheap`, `v_pipe8`) e due hanno funzionato
  come trappole, ma **non è un campione indipendente**: resta il rischio che l'IR stesso
  favorisca le trasformazioni che ho messo nel catalogo.
- Il budget-sweep confronta politiche su una tabella di verità **già misurata per intero**.
  È esatto e non favorisce nessuno, ma presuppone che il costo di un benchmark sia costante:
  in realtà `lds_stage` costa una compilazione in più e alcuni shader sono più lenti da misurare.
- `v_pipe16` resta irrisolto da tutte le politiche guidate. Non ho aggiustato le regole per
  farlo passare: sarebbe stato fitting sulla validation.
- L'apprendimento online (C) non ha aggiunto nulla su 8 shader. Serve un corpus più grande
  per dire se è inutile o solo prematuro.

## Cosa dice questa fase per il passo successivo

Il ricercatore funziona, ma il motore è la **memoria delle misure**, non le euristiche. La
conseguenza pratica per la fase su shader reali: conviene investire nel far crescere il
database di misure per feature, non nello scrivere altre regole. Le regole servono solo dove
non c'è ancora evidenza, e proprio lì sono meno affidabili — è esattamente quello che è
successo su `v_cond_uniform` e `v_pipe16`.
