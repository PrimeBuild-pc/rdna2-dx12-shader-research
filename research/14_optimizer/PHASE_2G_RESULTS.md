# Phase 2G — Automated Shader Optimizer

RX 6950 XT, driver 32.0.21045.5002. Target: `s4_pressure` (144 VGPR, il caso a maggiore
pressione registri). Nessun driver/Registry/cache/gioco toccato.
Codice: [`tools/opt_loop.py`](../../tools/opt_loop.py). Dati: [`optimizer_results.csv`](optimizer_results.csv).

---

## Esito

**Trovate 3 varianti corrette, riproducibili e sopra il rumore. La migliore è −30.03%.**

Il ciclo automatico funziona end-to-end:

```
genera variante HLSL -> DXC (cs_6_6) -> compilatore AMD (RGA: ISA, VGPR, SGPR, inst)
   -> microbenchmark D3D12 (3 run indipendenti) -> verifica numerica dell'output
   -> conserva / scarta
```

16 varianti generate one-variable-at-a-time, deduplicate per SHA-256 del sorgente,
ognuna compilata in processo separato con timeout.

## 1. Verifica di correttezza — ha fatto la differenza

Il banco ora copia i primi 65 536 `float4` dell'output su file dopo un dispatch pulito.
Confronto con la baseline: errore relativo massimo, tolleranza **1e-4**.
Validato prima dell'uso: due esecuzioni dello stesso shader danno output **identico bit-a-bit**.

**Tre varianti sono state scartate perché sbagliate — ed erano le più veloci:**

| variante | ns | Δ% | **errore relativo** | esito |
|---|---:|---:|---:|---|
| `L2_unroll8` | 30 720 | **−61.06%** | **1.56** | **SCARTATA** |
| `L2_unroll4` | 33 690 | **−57.30%** | **1.50** | **SCARTATA** |
| `L2_unroll12` | 93 005 | +17.88% | 2.00 | SCARTATA |

Errore relativo di **1.5–2.0**, cioè 150–200%: non è riassociazione in virgola mobile, è un
**risultato semanticamente diverso**. Il loop L2 ha dipendenze loop-carried
(`v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24])` legge elementi già riscritti in iterazioni
precedenti) e l'unroll parziale ne cambia l'ordine di lettura/scrittura.

Senza la verifica avremmo dichiarato un **−61% inesistente**. È il risultato più importante di
questa fase.

> Nota di onestà: non ho stabilito *se* la colpa sia di come genero la variante o del
> comportamento di DXC con `[unroll(N)]` su un loop con dipendenze. Il fatto accertato è che
> l'output differisce, quindi la variante non è valida — la causa resta da indagare.

## 2. Criterio di accettazione (corretto in corsa)

Il primo criterio usava solo il rumore globale dello shader (±2.32%) e accettava 5 varianti.
Sbagliato: `tg32` e `L1_loop` migliorano del ~2.9% ma hanno uno **spread run-to-run di
3.07–4.42%**, cioè maggiore del loro stesso miglioramento.

Criterio corretto: `miglioramento > max(rumore_shader, spread_variante, spread_baseline)`.

| variante | Δ% | soglia | esito |
|---|---:|---:|---|
| `L3_loop` | −30.03 | 2.32 | **ACCETTATA** |
| `all_loop` | −29.87 | 2.32 | **ACCETTATA** |
| `L2_loop` | −14.54 | 2.32 | **ACCETTATA** |
| `tg32` | −2.96 | **4.42** | scartata: dentro il proprio rumore |
| `L1_loop` | −2.82 | **3.07** | scartata: dentro il proprio rumore |
| `acc4`, `acc2`, `L2_temps`, `wave32` | −0.05 … +1.70 | 2.32–2.81 | scartate |
| `wave64` | +7.05 | 2.32 | peggiore |
| `tg128`, `tg256` | +23.73, +48.92 | | molto peggiori |

## 3. Classifica finale — 3 varianti valide

| # | variante | trasformazione | **ns (mediana 3 run)** | **Δ%** | spread | err. rel. | VGPR | inst | ISA |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | **`L3_loop`** | `[loop]` sul loop di riduzione | **55 205** | **−30.03%** | 0.145% | 4.4e−6 | **136** | **719** | cambiata |
| 2 | `all_loop` | `[loop]` su tutti e tre i loop | 55 335 | −29.87% | 0.262% | 4.4e−6 | 136 | 705 | cambiata |
| 3 | `L2_loop` | `[loop]` sul loop centrale | 67 430 | −14.54% | 0.193% | 1.1e−5 | **152** | 716 | cambiata |

baseline: 78 900 ns, 144 VGPR, 691 istruzioni.

Tutte e tre hanno **spread run-to-run < 0.3%** su 3 esecuzioni indipendenti: il miglioramento è
100× più grande del rumore. Errore numerico ≤ 1.1e−5, ben dentro la tolleranza — coerente con
la sola riassociazione FP dovuta a un diverso ordine di valutazione.

## 4. Le metriche statiche continuano a non predire nulla

Questa fase produce due contro-esempi ancora più netti di quelli di 2F:

```
L2_loop    VGPR 144 -> 152  (PIU' registri)      -> -14.54%  (PIU' veloce)
L3_loop    inst  691 -> 719  (PIU' istruzioni)   -> -30.03%  (PIU' veloce)
wave64     VGPR 144 -> 116  (MENO registri)      -> + 7.05%  (PIU' lento)
```

Né il conteggio VGPR né quello delle istruzioni ordinano correttamente le varianti per
velocità. **Solo la misura diretta lo fa.** Se avessimo selezionato per "meno VGPR" avremmo
scelto `wave64` (la peggiore fra le corrette) e scartato `L2_loop`.

Interpretazione di *perché* `[loop]` vince qui: non l'ho stabilita. L'ipotesi ovvia è che
srotolare completamente tre loop da 24 iterazioni su un array `float4 v[24]` produca un blocco
enorme con tutti i valori vivi contemporaneamente, e che il loop non srotolato riduca le live
range. Ma `L2_loop` ha *più* VGPR ed è più veloce, quindi la spiegazione "meno pressione
registri" non basta. **Serve l'analisi dell'ISA e delle stall per dirlo — non l'ho fatta.**

## 5. Limiti di questo risultato

- Vale per **un solo shader sintetico** (`s4_pressure`), scelto apposta come caso estremo di
  pressione registri. Non è un risultato generalizzabile a shader reali.
- `[loop]` è una direttiva già disponibile a chiunque scriva HLSL: l'optimizer non ha scoperto
  nulla di nascosto nel driver, ha trovato che **su questo shader il default di DXC (unroll
  completo) è una scelta sbagliata**. È comunque esattamente ciò che il ciclo doveva fare.
- Non ho eseguito l'esplorazione con i migliori come *parent* per nuove trasformazioni: il
  brief chiedeva di fermarsi al primo miglioramento reale >1%, e ne ho tre.
- Le trasformazioni di **access pattern** sono state escluse a monte: cambiare gli indici di
  lettura cambia i dati letti e quindi l'output, che la verifica giustamente rifiuterebbe.
  Per testarle servirebbe un criterio di correttezza diverso (invarianza matematica, non
  uguaglianza numerica).
- Tolleranza 1e-4 scelta a priori, non derivata dall'analisi dell'errore atteso.

## 6. Cosa è pronto per il passo successivo

Il ciclo `genera → compila → misura → verifica → tieni/scarta` è **operativo e onesto**: rifiuta
i falsi positivi (tre −57%/−61% inesistenti) e i miglioramenti dentro il rumore. È la base su cui
l'esplorazione automatica può girare, con la top-3 come parent per nuove trasformazioni.
