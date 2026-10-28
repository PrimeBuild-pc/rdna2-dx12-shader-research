# Ramo statico — dove vivono i 272 flag `u32SCOptions` e quali sono attivi su Navi 21

Solo analisi statica e lettura di dump già prodotti. **Nessun valore patchato, nessuna bitmask
modificata, nessun binario alterato.**
Dati: [`scoptions_observed.csv`](scoptions_observed.csv) (272 righe).

---

## 1. Non è servito reverse engineering: il driver li stampa

Il dump prodotto in fase 2C (`dump-all=1`) contiene, per **ogni shader compilato**, l'elenco
esplicito dei flag attivi:

```
//!option SCOption_C2 = 1
//!option SCOption_R1000_DISABLE_INDEXED_RESOURCE_TYPE_CHECK = 1
//!option SCOption_SCHEDULE_EXPORTS = 1
//!option SCOption_REASSOCIATE_AGGRESSIVELY = 1
...
```

Questa è la risposta diretta e verificata alla domanda "quali sono attivi su Navi 21", senza
disassemblare l'inizializzatore. Il formato di stampa `u32SCOptions[0] = 0x%08X` trovato in 2E
conferma che sotto è una **bitmask di uint32**, e la tabella indicizzata a RVA `0x2722060`
(indice = ID opzione) serve a decodificarla.

## 2. Quanti sono attivi

24 shader nel dump (PS, VS, GS, CS), 4 shader ID distinti.

| stato | n° | quota |
|---|---:|---:|
| **sempre attive** (in tutti gli shader) | **22** | 8.1% |
| **dipendono dallo shader** | **12** | 4.4% |
| **mai viste attive** | **238** | 87.5% |
| totale | 272 | |

**Su Navi 21 solo 34 delle 272 opzioni vengono mai accese**, e l'87.5% resta a zero in tutti i
casi osservati.

`compileFlag` osservati: `0x00000080` per VS/GS/CS, `0x00000084` per PS — il bit aggiuntivo è
verosimilmente legato allo stage pixel, **ma non l'ho verificato**.

## 3. Le 12 che dipendono dallo shader

Sono la parte interessante per l'ipotesi "indurre l'euristica dall'input":

```
SCOption_GFX10_DEGGIGXX0_8374_WORKAROUND
SCOption_GFX10_DEGGIGXX0_8448_NSA_AND_CLAUSE_CAN_HANG
SCOption_GFX10_DEGGIGXX0_8602_NSA_CANNOT_FOLLOW_WRITELANE
SCOption_GFX10_DEGGIGXX0_8666_PREFETCH_0_BRANCH_HANG
SCOption_GFX10_DEGGIGXX0_8877_WORKAROUND
SCOption_GFX10_DEGGIGXX0_8925_LDS_VMEM_NOT_WAITING_VM_VSRC
SCOption_GFX10_DEGGIGXX0_9088_PREFETCH_FWD64_BRANCH
SCOption_GFX10_DEGGIGXX0_9122_DEGGIGXX2_3298_FP_ATOMIC_DENORM_HAZARD
SCOption_GFX10_DEGGIGXX2_1116_CHECK_IMAGE_SRD_TYPE
SCOption_GFX92_ENABLE_DL_OPS
SCOption_GFX9_TRANSFORM_FOR_POPS
SCOption_UNPATCHABLE_EXPORTS
```

**Undici su dodici sono workaround hardware**, attivati in base a *cosa contiene lo shader*:
istruzioni NSA, prefetch attraverso branch, LDS+VMEM in sequenza, atomiche FP con denormali,
image sample. Cioè: l'input **induce** il flag, esattamente il meccanismo ipotizzato — ma per
**correttezza**, non per prestazioni. Disattivarli non è "ottimizzare": è rimuovere un
workaround a un bug hardware noto. Fuori discussione.

L'unica non-workaround che varia è `SCOption_GFX92_ENABLE_DL_OPS` (dot-product ops), che
plausibilmente si accende quando lo shader contiene pattern mappabili su istruzioni DL — questa
sì sarebbe inducibile dall'input per motivi di prestazioni, **ma non l'ho verificata**.

## 4. Le 22 sempre attive

Sono il "profilo fisso" del compilatore per questa GPU: fra le altre
`SCOption_SCHEDULE_EXPORTS`, `SCOption_REASSOCIATE_AGGRESSIVELY`,
`SCOption_USE_F16FMA_FOR_F16MAD`, `SCOption_EMBED_IMMEDIATE_CONST_ARRAYS`,
`SCOption_DISABLE_PEEPHOLE_ON_SMALL_SHADERS`, `SCOption_AVOID_LDS_BANK_CONFLICT_ONCHIP_*`.
Non variano con lo shader: non sono inducibili.

## 5. Le opzioni "interessanti" sono tutte spente

Quelle che 2D aveva segnalato come candidate per l'ottimizzazione risultano **mai viste attive**:

| opzione | indice | stato |
|---|---:|---|
| `SCOption_MINIMIZE_VGPRS` | 20 | mai attiva |
| `SCOption_PBQP_REGISTER_ALLOCATION` | — | mai attiva |
| `SCOption_LIVENESS_BASED_INSTRUCTION_SCHEDULING` | — | mai attiva |
| `SCOption_GFX10_FORCE_WAVE32/64_SCHEDULING*` | 184–187 | mai attiva |
| `SCOption_GFX10_ENABLE_SUBVECTOR*` | 179–180 | mai attiva |
| `SCOption_GFX10_ENABLE_ML_MODEL_FOR_PS_WAVESIZE_CHOICE` | 192 | mai attiva |

Il compilatore le lascia disattivate di default su questa GPU e per questi shader, e — come
stabilito in 2E — non esiste alcun canale di configurazione per accenderle.

## 6. Conclusione per il progetto

- **Dove sono inizializzati**: non l'ho isolato nel codice, ma non serve più: il driver dichiara
  lo stato risultante nel dump, per shader, che è l'informazione che volevamo.
- **Quali sono attivi su RDNA2**: 34 su 272 (22 fisse + 12 shader-dipendenti).
- **Quali dipendono dallo shader**: 12, di cui 11 workaround hardware.
- **L'ipotesi "induco l'euristica dall'input"** è **vera come meccanismo** ma **inutile come
  leva di ottimizzazione**: ciò che l'input induce sono workaround di correttezza, non
  ottimizzazioni. Le opzioni di ottimizzazione restano spente e non raggiungibili.

Questo chiude il ramo `u32SCOptions` come via per migliorare le prestazioni. La leva che
funziona resta quella dimostrata in 2G: **cambiare l'HLSL e misurare**.
