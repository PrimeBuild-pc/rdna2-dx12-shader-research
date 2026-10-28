# Phase 2I — AI-guided search: progetto (NON implementato)

Progettata in 2H su richiesta. **Nessuna riga di questa fase è stata scritta.**
Va letta insieme ai limiti stabiliti in [`PHASE_2H_RESULTS.md`](PHASE_2H_RESULTS.md), che
cambiano il senso della fase.

---

## 1. Cosa 2H obbliga a cambiare rispetto all'idea iniziale

L'architettura proposta era:

```
Claude/Codex -> variante HLSL -> DXC + compilatore AMD -> ISA/stats
             -> microbenchmark 6950 XT -> correctness -> ns -> accetta/rifiuta
```

Il principio («l'IA esplora, la 6950 XT decide») resta giusto. Ma 2H ha mostrato tre cose che
il ciclo di 2G non aveva:

1. **Il riferimento va scelto, non assunto.** Il −30% di 2G era misurato contro una baseline
   che avevo pessimizzato io. Ogni ricerca deve partire dal **default del compilatore**, e ogni
   guadagno va riportato relativo a quello.
2. **Il banco può mentire.** Due difetti (warm-up a iterazioni, duty cycle) davano errori fino
   a 5×. Il banco va autoverificato a ogni sessione, non dato per buono.
3. **La correttezza da sola non basta come filtro, e il criterio va scelto con lo shader.**
   Su `pressure24` qualunque riassociazione esce da 1e-4 su 7 input su 20, incluso il default
   di DXC. Un filtro rigido avrebbe scartato il compilatore stesso.

## 2. Struttura proposta

```
                      ┌─────────────────────────────────────┐
                      │  corpus + shader target             │
                      └───────────────┬─────────────────────┘
                                      v
   ┌──────────────┐   proposta   ┌─────────────────┐
   │  proponente  │─────────────>│ generatore HLSL │
   │  (LLM)       │<─────────────│ + dedup per SHA │
   └──────────────┘   feedback   └────────┬────────┘
          ^                               v
          │                        ┌──────────────┐
          │                        │ DXC + RGA    │  ISA, VGPR, wait, clause,
          │                        └──────┬───────┘  distanza load->wait
          │                               v
          │                        ┌──────────────┐
          │                        │ gate statico │  scarta subito: scratch nuovo,
          │                        └──────┬───────┘  VGPR oltre soglia, compile fail
          │                               v
          │                        ┌──────────────┐
          │                        │ correttezza  │  N dataset, max abs/rel, RMS,
          │                        └──────┬───────┘  NaN/Inf, vs DEFAULT del compilatore
          │                               v
          │                        ┌──────────────┐
          │                        │ misura GPU   │  >=3 processi freschi, burst continuo
          │                        └──────┬───────┘
          │                               v
          │                        ┌──────────────┐
          └────────────────────────│ accetta/no   │
             ISA + ns + errore     └──────────────┘
```

L'LLM **non** decide se una variante è migliore. Riceve ISA, tempi ed errori misurati e propone
la trasformazione successiva. La decisione è aritmetica.

## 3. Punti da definire prima di scrivere codice

**Riferimento.** Sempre il default del compilatore (nessun attributo). Riportare due numeri:
`d% vs default` e `d% vs miglior variante nota`. Mai solo il secondo.

**Autoverifica del banco.** All'avvio di ogni sessione, prima di qualunque esperimento:
- lo shader di sola scrittura deve dare il pavimento atteso (~3.15 µs a 262 144 thread);
- due esecuzioni dello stesso CSO devono dare output bit-identico;
- tre processi freschi devono concordare entro l'1%;
- una variante nota lenta (`wave64`) e una nota veloce devono ordinarsi correttamente.
Se un check fallisce, la sessione si ferma. Nessun risultato viene registrato.

**Criterio di correttezza a due livelli**, deciso *prima* del sweep e registrato nei metadati:
- *stretto* (bit-identico o max rel ≤ 1e-6): la variante è un sostituto sicuro;
- *riassociazione* (RMS rel ≤ 1e-5 e nessun NaN/Inf divergente): la variante è equivalente a
  meno di riordino FP — la stessa classe in cui cade il default di DXC.
Una variante fuori da entrambi è scartata. La classe va riportata, non nascosta.

**Spazio delle trasformazioni.** Solo trasformazioni sorgente, nessuna che riduca
volontariamente la precisione:
`[loop]` / `[unroll]` / `[unroll(N)]` per ciclo, `[numthreads(N)]`, `[WaveSize(N)]`,
numero di accumulatori, temporanei espliciti, scambio di cicli, fissione e fusione di cicli,
scelta fra `StructuredBuffer` e `ByteAddressBuffer`, precaricamento esplicito in un array
locale, uso di LDS come staging. Escluse per ora: riscritture dell'access pattern (cambiano i
dati letti, servirebbe un criterio d'invarianza matematica invece dell'uguaglianza numerica).

**Bilancio esplorazione/sfruttamento.** Top-K come parent (K=5), più una quota fissa di
proposte casuali dallo spazio, per non restare in un minimo locale. Dedup per SHA-256 del
sorgente **e** per SHA dell'ISA: due sorgenti diversi che compilano allo stesso ISA vanno
misurati una volta sola.

**Budget.** Ogni sessione dichiara un tetto di compilazioni e di tempo GPU. Nessuna ricerca
aperta senza limite.

**Registro anti-illusione.** Ogni variante accettata viene rimisurata a fine sessione in
processi freschi. Le regressioni fra la misura di ricerca e la rimisura finale vanno
registrate: è il segnale che il banco sta derivando.

## 4. Cosa 2I può ragionevolmente scoprire

Dopo 2H, l'aspettativa va calibrata verso il basso. Sui 20 shader del corpus il default di DXC
non è mai stato battuto da `[loop]`, e `[unroll]` lo batte solo dove il compilatore aveva già
scelto di non srotolare (9 casi su 20, mediana −3%).

Quindi la domanda realistica di 2I **non** è «battiamo il compilatore», ma:

- esiste una combinazione di più trasformazioni (unroll parziale + accumulatori + wave size +
  threadgroup) che il compilatore non esplora, e che vince in modo riproducibile?
- si può costruire un **predittore** della classe di shader dove `[unroll]` fa male, usando le
  metriche ISA già raccolte (gruppi di load, distanza load→wait, array vivo fra iterazioni)?
  Questo avrebbe valore anche se nessuna variante nuova vincesse.

Un esito negativo pulito («il compilatore AMD è già vicino all'ottimo su questa classe di
shader») è un risultato accettabile e va riportato come tale.

## 5. Prerequisiti prima di far girare 2I

- [ ] Autoverifica del banco implementata e verde.
- [ ] Corpus esteso con shader più vicini a un carico reale (texture sampling, più risorse,
      thread group non banali).
- [ ] Criterio di correttezza a due livelli implementato e testato sui falsi positivi noti
      di 2G (`L2_unroll4/8/12` devono essere ancora respinti).
- [ ] Metadati per esperimento: driver, versione DXC, versione RGA, SHA del banco, dataset,
      workload, dpm, numero di processi.
