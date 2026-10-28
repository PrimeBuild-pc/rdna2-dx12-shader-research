# Phase 2I — AI-guided shader search: risultati

RX 6950 XT, driver 32.0.21045.5002. Nessun driver / Registry / cache / gioco toccato.
**Il riferimento è sempre il default reale di DXC/AMD**: nessun attributo, nessun hint.

Dati: [`search_history.csv`](search_history.csv) · [`accepted_variants.csv`](accepted_variants.csv) ·
[`confirm_detail.csv`](confirm_detail.csv) · [`rejected_correctness.csv`](rejected_correctness.csv) ·
[`accepted_correctness.csv`](accepted_correctness.csv) · [`isa_dedup.csv`](isa_dedup.csv) ·
[`causal_bdiv.csv`](causal_bdiv.csv).
Codice: [`tools/ai_search.py`](../../tools/ai_search.py), [`tools/bench_selfcheck.py`](../../tools/bench_selfcheck.py).

---

## Esito

**Sì: si può battere il compilatore.** 9 varianti su 23 superano il default reale in modo
robusto. La migliore di **−69.5%**, e non su una baseline artificiale.

L'obiettivo dichiarato era *una* variante corretta, >1%, ripetibile, su ≥3 combinazioni
indipendenti. Ce ne sono nove.

## 1. Lo strumento, prima di tutto

Il self-check è stato eseguito e ha **fallito al primo tentativo** (riproducibilità 2.72%
contro una soglia di 1%), il che ha portato a ridisegnare la statistica invece di allentare
la soglia.

Con confronti fra mediane indipendenti la riproducibilità fra processi freschi è 1.1–1.3%:
**non basta per risolvere un +1%**. La misura di 2I è quindi un **confronto appaiato**:

- in ogni processo il default è misurato **due volte**, in prima e ultima posizione, e il
  riferimento è la media delle due — cancella la deriva di clock lungo il processo, che è
  reale e misurata: **+0.35%** sistematici sulla seconda posizione di `pressure24`;
- le varianti sono **mescolate** a ogni run;
- si riporta media, SE e `media + 2·SE` delle differenze appaiate.

Rumore del nullo appaiato (stesso CSO misurato due volte in un processo, 8 processi):
**media −0.058%, SE 0.049%**. Un effetto dell'1% è 20 SE. Lo strumento è qualificato.

Soglie fissate **prima** di guardare i risultati: candidato se media < −0.5%; accettato se
media < **−1.0%** su **tutte e 3** le combinazioni (workload, dataset) **e** `media + 2·SE < 0`
in tutte, con 10 processi ciascuna.

## 2. Deduplica — due risultati negativi gratuiti

Deduplica a tre livelli: HLSL normalizzato → DXIL → ISA. Ha eliminato 2 varianti su 32
**prima di misurarle**, e ognuna è un'informazione:

| variante | livello | significato |
|---|---|---|
| `p24__load_then_scale` | **ISA identica** al default | separare load e scala non cambia nulla: il compilatore lo fa già |
| `bdiv__select` | **DXIL identico** al default | DXC canonicalizza già `if/else` in una select |

Il secondo è importante per la sezione 5: la select non sopravvive al backend AMD.

## 3. Correttezza

5 dataset deterministici (originale, negativi, casuali ±1, potenze di 2 esatte, 1e30),
output completo, due livelli definiti in 2H:

- **strict**: max rel ≤ 1e−6 → sostituto sicuro
- **riassociazione**: RMS rel ≤ 1e−5 e nessun NaN/Inf divergente
- fuori da entrambi → eliminata, e non può diventare parent

**Eliminata 1 su 24**: `trig__unroll4` (max rel 4.45e−04, RMS rel 2.43e−04 su **tutti** i
dataset). È lo stesso fenomeno di `L2_unroll` in 2G: l'unroll parziale di una catena seriale
`sin`/`cos` cambia davvero il risultato.

Le 9 accettate stanno quasi tutte al livello **strict**:

| variante | ds0 | ds8 (casuale) |
|---|---|---|
| `trig__unroll` | strict, **0.000e+00** | strict, **0.000e+00** |
| `dot__unroll` | strict, 0.000e+00 | strict, 1.19e−07 |
| `dot__acc4_unroll` | strict, 0.000e+00 | strict, 1.19e−07 |
| `dot__acc4` | strict, 2.63e−07 | strict, 3.62e−07 |
| `bdiv__hoist_parity` | strict, 2.01e−07 | strict, 4.06e−07 |
| `bdiv__hoist_parity_batch` | strict, 1.62e−07 | strict, 4.06e−07 |
| `ldsred__tree` | strict, 0.000e+00 | riassociazione, RMS 1.63e−07 |
| `ldsred__wave` | strict, 0.000e+00 | riassociazione, RMS 1.63e−07 |
| `mix__unroll` | strict, 7.56e−07 | riassociazione, RMS 1.47e−07 |

Il vincitore `bdiv__hoist_parity` è **strict su entrambi**: non è una vittoria comprata con
la precisione.

## 4. Le 9 varianti accettate

10 processi per combinazione, 3 combinazioni: (262 144 thread, ds0), (65 536, ds8),
(1 048 576, ds12).

| variante | correttezza | peggiore | migliore | max(media+2SE) | combo<0 |
|---|---|---:|---:|---:|---:|
| **`bdiv__hoist_parity`** | strict | **−69.54%** | −70.51% | −69.15% | 3/3 |
| `bdiv__hoist_parity_batch` | strict | −49.72% | −50.88% | −49.06% | 3/3 |
| `trig__unroll` | **bit-exact** | −25.45% | −25.79% | −25.36% | 3/3 |
| `ldsred__wave` | riassoc. | −14.54% | −15.60% | −14.49% | 3/3 |
| `ldsred__tree` | riassoc. | −14.41% | −15.63% | −14.33% | 3/3 |
| `mix__unroll` | riassoc. | −6.22% | −8.18% | −4.92% | 3/3 |
| `dot__unroll` | strict | −5.82% | −6.36% | −5.79% | 3/3 |
| `dot__acc4` | strict | −5.82% | −6.25% | −5.77% | 3/3 |
| `dot__acc4_unroll` | strict | −1.23% | −3.90% | −0.95% | 3/3 |

Respinte al confirm: `p24__tg32` (−0.65%, sotto la soglia dell'1%) e `bdiv__unroll`
(+1.49%, peggiore).

**Su `p24` — lo shader su cui erano concentrate 2F/2G/2H — nessuna variante batte il
default.** Sette trasformazioni provate, zero accettate. Il compilatore lì è già a posto.

## 5. Causa del vincitore — l'ipotesi ovvia è sbagliata

`bdiv` è il ciclo con ramo divergente:

```hlsl
for (i = 0; i < 32; ++i) { a = In[(t*32+i) & 65535];
  if ((t + i) & 1) s += a*a; else s += sin(a)*cos(a); }
```

La trasformazione: la parità dipende solo da `t`, quindi il ramo si **solleva fuori dal
ciclo** in due corpi rettilinei. L'ordine delle somme è identico.

La mia prima ipotesi era il **parallelismo di memoria**. Cinque controlli la falsificano:

| variante | d% | `s_cbranch` | exec ops | `v_sin`/`v_cos` | clause |
|---|---:|---:|---:|---:|---:|
| default | 0 | **32** | **95** | 128/128 | 0 |
| `pair_branch` (2 load/iter, ramo per elemento) | −27.64% | **32** | **95** | 128/128 | 15 |
| `hoist_seq` (ramo sollevato, 1 load/iter) | **−67.00%** | **2** | **2** | 128/128 | 6 |
| `hoist_parity4` (4 load/iter) | −67.52% | 2 | 2 | 128/128 | 6 |
| `hoist_parity` (2 load/iter) | **−70.86%** | 6 | 2 | 48/48 | 6 |
| *controllo:* `loadonly_seq` (sole load) | −47.79% | 0 | 0 | — | 2 |
| *controllo:* `loadonly_pair` (sole load, a coppie) | −45.25% | 0 | 0 | — | 3 |

Il controllo decisivo: **raddoppiare le load in assenza di ramo non dà nulla**
(`loadonly_pair` è del 4.3% *peggio* di `loadonly_seq`). Quindi il parallelismo di memoria
non è la causa.

`hoist_seq` ha **la stessa identica aritmetica** del default (128 `v_sin`, 128 `v_cos`) e
differisce solo per 32→2 branch divergenti e 95→2 operazioni sulla exec mask: **−67.0%**.

> **Catena causale.** DXC riduce sia `if/else` sia la select allo stesso DXIL. Il backend AMD
> ne ricava **32 rami divergenti** con 95 manipolazioni di exec mask — una scelta sensata in
> generale (saltare il ramo costoso quando l'intero wave prende un lato), ma qui la condizione
> è la parità di `t`, che **divide sempre il wave**: il salto non paga mai e i due lati vengono
> eseguiti comunque. Sollevare il ramo lascia lo stesso lavoro aritmetico con 2 regioni
> divergenti invece di 32.

Confidenza **strong**. Contributo secondario: appaiare le load abilita le clause di memoria
(0→15) e vale da solo −27.6%; i due effetti non si sommano (−70.9%, non −94%) perché una volta
tolti i rami la latenza è già coperta dall'ALU.

Il residuo fra `hoist_seq` (−67.0%) e `hoist_parity` (−70.9%) è dimensione del codice:
289 VALU statiche contro 709, perché il ciclo resta arrotolato.

## 6. Causa degli altri vincitori

| variante | d% | cosa cambia nell'ISA |
|---|---:|---|
| `ldsred__wave` | −14.5% | `WaveActiveSum` al posto di 64 letture LDS per lane: **`s_waitcnt` 26→3**, inst 171→142, LDS 1024→512 B |
| `ldsred__tree` | −14.4% | riduzione ad albero in LDS: `s_waitcnt` 26→22, branch 2→6, log₂64 passi invece di 64 letture |
| `trig__unroll` | −25.4% | catena seriale di trascendenti: inst 251→502, VGPR 13→7, sparisce il costo per iterazione del ciclo |
| `dot__acc4` | −5.8% | 4 catene indipendenti: VMEM statiche 12→33, clause 2→4 — più load in volo |
| `dot__unroll` | −5.8% | stessa famiglia |
| `mix__unroll` | −6.2% | VMEM 11→25, clause 2→3, distanza load→uso mediana 7→30 |

`ldsred__wave` è il caso più netto dopo `bdiv`: una riduzione sequenziale in LDS sostituita da
una wave op abbatte i `s_waitcnt` di quasi un ordine di grandezza.

## 7. Cosa non ha funzionato, e perché conta

| variante | d% | lettura |
|---|---:|---|
| `p24__lds_stage` | **+109.8%** | 24 KB di LDS per gruppo distruggono l'occupancy |
| `dot__lds_stage` | +99.9% | 32 KB di LDS: idem, peggio |
| `mix__lds_stage` | +93.0% | idem |
| `ldsred__acc4` | +43.8% | `s_waitcnt` 26→35: più accumulatori su LDS peggiorano |
| `dot__load_first` | +28.3% | array di 32 `float4` → VGPR 34→57 |
| `mix__load_first` | +24.9% | idem, e correttezza **strict**: pura perdita |
| `p24__tg128` | +5.1% | |
| `p24__raw_buffer`, `dot__raw_buffer` | +0.4%, +0.1% | `ByteAddressBuffer` non cambia nulla |

Lo **staging LDS coalescente** — la trasformazione classica da manuale — è il peggior
risultato dell'intera fase, tre volte su tre. Il costo in occupancy supera di gran lunga il
guadagno in coalescenza. È un buon promemoria del perché la funzione obiettivo deve essere
il tempo misurato.

## 8. Limiti dichiarati

- Corpus **sintetico**, 6 shader. Nessuna conclusione trasferita a shader di gioco reali.
- Le trasformazioni sono proposte a mano, non generate da una ricerca automatica: 2I dimostra
  che il ciclo *decide* correttamente, non che *esplora* da solo.
- `bdiv` è costruito attorno a un ramo divergente su parità: un caso volutamente sfavorevole
  al compilatore. Il −69.5% misura quanto costa quella scelta di codegen, non un guadagno
  generico.
- Contatori di stall ancora non misurati (RGP leggibile solo da GUI). Le cause restano
  *strong*, non *confirmed*.
- I risultati di `dot__acc4_unroll` (−1.23% nel caso peggiore) sono vicini alla soglia:
  accettati, ma con margine sottile.

## 9. Prossimo passo naturale

Il predittore. Su 23 varianti misurate, le metriche ISA che separano vincitori e perdenti
sono ora tre e concrete: **numero di regioni divergenti**, **`s_waitcnt` per operazione di
memoria/LDS**, e **byte di LDS per gruppo** (che governa l'occupancy). Un modello su queste
tre, validato contro i tempi già raccolti, permetterebbe di proporre trasformazioni mirate
invece che a tappeto — senza mai usarle per decretare il vincitore, che resta la misura.
