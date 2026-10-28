# Phase 2L — Workload-driven targeting: progetto (NON implementato)

Scritta in 2K su richiesta. **Nessuna riga di questa fase è stata eseguita.**

L'idea: smettere di ottimizzare shader scelti da noi e far scegliere al profilo di un
workload DX12 reale *quali* shader meritino di essere ottimizzati.

```
workload DX12 reale (non multiplayer, non protetto)
        │
        ▼  RGP: cattura di un frame
shader ordinati per costo GPU reale nel frame
        │
        ▼  filtro economico: costo × probabilità di guadagno
i pochi shader che valgono davvero
        │
        ▼  memoria delle misure (2K): 2-5 trasformazioni proposte
varianti HLSL
        │
        ▼  banco su RX 6950 XT (pipeline 2I congelata)
migliore variante, con guadagno misurato e correttezza verificata
        │
        ▼  ri-cattura RGP
guadagno **nel frame reale**, non solo nel microbenchmark
```

---

## 1. Perché questa fase cambia il senso del progetto

Fino a 2K la domanda era «sappiamo ottimizzare uno shader?». La risposta è sì, ma è una
risposta priva di valore economico finché non si sa *quale* shader. Un −20% su uno shader
che occupa lo 0.1% del frame vale 0.02% del frame; un −5% su uno che ne occupa il 30% vale
1.5%, cioè settantacinque volte tanto.

2L introduce quindi una **funzione obiettivo diversa**: non `Δ tempo dello shader` ma
`Δ tempo del frame = quota_frame × Δ shader`.

## 2. Scelta del workload

Vincolo permanente del progetto: niente Fortnite/Warzone, niente processi con anti-cheat.
Candidati in ordine di preferenza:

1. **Black Myth: Wukong Benchmark** — già previsto in 1F, tuttora non installato. È il
   workload controllato ideale: pesante, ripetibile, senza anti-cheat.
2. **3DMark Steel Nomad** — già caratterizzato (CV 0.11%, GPU-bound al 99.9%), ma è chiuso
   e gira a cache calda: RGP può catturarlo, però non possiamo sostituirne gli shader.
3. **Un sample DX12 open source pesante** (es. MiniEngine di DirectX-Graphics-Samples, già
   clonato in 2K) — l'unico caso dove il ciclo si **chiude davvero**: possiamo modificare
   il sorgente dello shader, ricompilare l'applicazione e rimisurare il frame.

**Raccomandazione: partire da (3).** È l'unico che permette di verificare il guadagno end-to-end
invece di stimarlo. (1) e (2) restano utili come controprova su un carico più realistico, ma lì
si può solo misurare, non intervenire.

## 3. Estrazione del profilo

RGP è già validato in 2H: cattura per dispatch con instruction tracing
(`RadeonDeveloperPanelCLI --rgp-auto-capture`). **Limite noto e bloccante: il file `.rgp` si
legge solo dalla GUI.** Prima di 2L serve risolvere questo, in ordine di preferenza:

- verificare se le versioni recenti di RGP espongono un export CLI o un formato documentato;
- in alternativa usare **contatori GPU per-dispatch** già ottenibili senza RGP: timestamp
  query attorno a ciascun dispatch/draw dentro l'applicazione open source, che è modificabile.
  Meno ricco di RGP ma sufficiente per il ranking di costo, che è tutto ciò che serve qui.

La seconda strada è quella da preferire per il workload (3): non dipende da uno strumento che
non sappiamo leggere.

## 4. Filtro economico

Per ogni shader del frame:

```
quota_frame        = tempo_shader / tempo_frame
guadagno_atteso    = stima dalla memoria delle misure (2K), per feature simili
valore_atteso      = quota_frame × guadagno_atteso
costo              = numero di benchmark previsti (budget)
```

Si ottimizzano solo gli shader con `valore_atteso` sopra una soglia **fissata prima** di
guardare i dati (proposta: 0.2% di frame time, cioè un guadagno percepibile ma non assurdo).
Questo è il punto in cui la memoria delle misure di 2K serve davvero: non per scegliere la
trasformazione, ma per **decidere se vale la pena provare**.

## 5. Cosa va verificato, e che è facile sbagliare

- **Il guadagno nel microbenchmark non è il guadagno nel frame.** Nel frame lo shader gira
  con occupancy diversa, in concorrenza con altro lavoro, su dati reali e con cache calde.
  Il numero che conta è la ri-cattura, non la stima.
- **I dati sintetici di 2K sono un limite noto** (vedi `REAL_GENERALIZATION.md`): il ranking
  delle trasformazioni è condizionato a input finti. Nel frame reale l'ordine può cambiare.
- **Barriere e dipendenze**: accorciare uno shader che non è sul percorso critico del frame
  non riduce il frame time. Serve il grafo delle dipendenze, non solo la somma dei tempi.
- **Regressione altrove**: cambiare `numthreads` o wave size può spostare il collo di
  bottiglia. Va rimisurato il frame intero, non il singolo dispatch.

## 6. Criteri di accettazione, da fissare prima

Una trasformazione entra nel risultato finale solo se:

1. correttezza verificata con la policy a due livelli di 2H/2I (strict o riassociazione);
2. guadagno sullo shader sopra il rumore, col protocollo appaiato di 2J;
3. **guadagno sul frame** misurato su ≥5 catture indipendenti, sopra la varianza del frame
   già misurata in 1E (Steel Nomad ±0.11%, Fortnite ±1.3%; da rimisurare per il workload scelto);
4. nessuna regressione sopra il rumore su altri shader dello stesso frame.

Il punto 3 è quello che finora non è mai stato verificato in questo progetto, ed è l'unico
che giustifica tutta la catena.

## 7. Prerequisiti

- [ ] Workload scelto e caratterizzato (varianza frame-to-frame misurata prima di tutto).
- [ ] Profilo per-dispatch ottenibile in modo programmatico (RGP con export, oppure timestamp
      query nel sample open source).
- [ ] Ciclo chiuso: possibilità di ricompilare lo shader dentro l'applicazione.
- [ ] Memoria delle misure di 2K estesa con gli shader del workload scelto.

## 8. Esito atteso, dichiarato in anticipo

Realisticamente il risultato più probabile è **un guadagno di frame piccolo** — sotto l'1% —
perché le trasformazioni meccanicamente applicabili a HLSL arbitrario sono poche (2K mostra
che si riducono in pratica ad attributi di ciclo, wave size e threadgroup) e perché i shader
di un sample maturo sono già ragionevolmente scritti.

Un esito negativo pulito («sul workload X nessuno shader supera la soglia di valore atteso»)
è un risultato accettabile e va riportato come tale: significherebbe che il valore del sistema
sta nell'evitare lavoro inutile, non nel trovare oro.
