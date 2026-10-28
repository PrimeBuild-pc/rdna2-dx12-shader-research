# Phase 1.5-A — Risultati: attribuzione CPU su Fortnite (4 run ETW)

Catture 2026-09-04. Driver 32.0.21045.5002, Win 11 26200, HAGS=2.
Run 1–3: 8 kHz, 75 s, ~13.5 GB/ETL. Run 4: 4 kHz, 60 s, 11.9 GB, **con PresentMon valido**.
Dati derivati: `run1/`…`run4/`, `summary_3runs.csv`, `raw/*-presentmon.csv`.
**Gli ETL sono stati cancellati dopo l'analisi** (~50 GB); tutti i CSV derivati sono conservati.

---

## Risposta alla domanda della fase

> Di quei ~1,53 ms CPU per frame di Fortnite, quanto è speso nel driver AMD?

```
UMD AMD DX12 (amdxc64.dll)  =  2.1% del percorso critico del frame
                            ≈  0.03 ms/frame in condizioni normali
```

**Sotto la soglia del 3% pre-registrata ⇒ il ramo "ottimizzare l'UMD AMD per Fortnite
Performance Mode" si chiude.**

## Come è stato identificato il thread del percorso critico

Nelle run 1–3 mancava PresentMon, quindi la conversione in ms/frame era bloccata fra due
candidati (2.1% o 26.9%). La run 4 ha PresentMon **nella stessa cattura**, e questo permette
un test quantitativo diretto:

```
MsCPUBusy 2.7636 ms  x  329.2 fps  =  0.9098 core-equivalenti   <- percorso critico misurato
```

Confronto con i thread della stessa cattura (4 kHz, 74.78 s):

| TID | core | scarto dal percorso critico | `amdxc64.dll` sul thread |
|---|---:|---:|---:|
| **18844** | **0.9152** | **+0.6%** | **2.1%** |
| 14936 | 0.6215 | −32% | 0% |
| 2392 | 0.4373 | −52% | 26.4% |
| 13940 | 0.3915 | −57% | 0.9% |

Un solo thread corrisponde, con scarto dello 0.6%. Il TID 2392 — quello con il 26.4% di
`amdxc64` — vale 0.4373 core: se fosse lui a presentare, `MsCPUBusy` sarebbe 1.33 ms invece dei
2.76 ms misurati. **Escluso quantitativamente.**

**Conferma incrociata su sessione indipendente.** Nelle run 1–3 (altra sessione di gioco, TID
diversi, 8 kHz, frame rate diverso) il thread corrispondente era il **TID 7080: 0.919 core, e
`amdxc64.dll` di nuovo al 2.1%**. Due sessioni indipendenti, stesso identico valore.

> Limite: PresentMon non espone il TID, quindi questa resta un'**inferenza quantitativa**, non
> una lettura diretta. Ma con scarto 0.6% su una cattura e riproduzione esatta su un'altra
> sessione, la classifico **strong**.

## Composizione del thread critico (TID 18844, 0.9152 core)

| modulo | % del thread |
|---|---:|
| `ntoskrnl.exe` | **84.0%** |
| `"Unknown"` (codice Fortnite) | 5.8% |
| `dxgkrnl.sys` | 2.1% |
| **`amdxc64.dll`** | **2.1%** |
| `dxgmms2.sys` | 1.7% |
| `EasyAntiCheat_EOS.sys` | 1.3% |

Percorso grafico completo sul percorso critico (UMD + dxgkrnl + dxgmms2): **5.9%** ≈ 0.09 ms/frame.

Anche azzerando *tutto* il costo grafico lato CPU si guadagnerebbe ~5.5% di frametime — e
azzerarlo è impossibile. Un miglioramento realistico del 25% del solo UMD vale **0.5% del
frametime**, contro una MDD di Fortnite del **2.2%**: **non sarebbe nemmeno misurabile**.

## Dove va davvero il percorso critico: 84% in `ntoskrnl.exe`

Passata mirata sul TID 18844 (`tools/etw_kernel_probe.py`, output in
`run4/tid18844_ntoskrnl_pages.csv`):

| pagina | campioni | % del tempo kernel |
|---|---:|---:|
| `ntoskrnl+0x233000` | 69 698 | **30.3%** |
| `ntoskrnl+0x234000` | 30 455 | 13.2% |
| `ntoskrnl+0x34d000` | 30 363 | 13.2% |
| `ntoskrnl+0x235000` | 20 973 | 9.1% |
| `ntoskrnl+0x236000` | 5 285 | 2.3% |

**Il 50% del tempo kernel sta in 3 pagine, l'80% in 11.** Le pagine `0x233000–0x236000` sono
**contigue** e da sole fanno il **55%**: 16 KB di codice kernel che consumano metà del percorso
critico del frame.

Non ho i simboli di `ntoskrnl.exe` (nessun download di simboli è stato fatto: nessuna richiesta
di rete) e **non invento nomi di funzione**. Quello che si può affermare: non è codice del
driver AMD, e non è codice del display driver in generale (`dxgkrnl` e `dxgmms2` sono moduli
distinti e valgono insieme il 3.8%).

Con i simboli pubblici Microsoft quei 4 offset si risolverebbero in pochi minuti — è l'unico
modo per sapere *cosa* sia, e richiederebbe una ricattura visto che gli ETL non ci sono più.

## Tabella riassuntiva delle 4 run

| | run1 | run2 | run3 | run4 |
|---|---:|---:|---:|---:|
| sampling | 8 kHz | 8 kHz | 8 kHz | 4 kHz |
| campioni Fortnite | 2 760 599 | 2 790 143 | 2 860 833 | 1 188 781 |
| `amdxc64.dll` / processo | 3.75% | 3.75% | 3.63% | 3.61% |
| CPU processo | 4.006 core | 4.049 core | 4.151 core | 3.974 core |
| thread critico | 0.920 | 0.921 | 0.918 | 0.915 |
| `amdxc64` sul thread critico | 2.1% | 2.1% | 2.1% | 2.1% |
| PresentMon | ✗ | ✗ | ✗ | **24 695 frame** |

## Un limite importante: WPR altera il carico

Con la cattura attiva Fortnite gira a **329 FPS invece di ~620**, e `MsCPUBusy` sale da 1.529 a
2.764 ms. L'overhead dello stack walking è pesante. Le **quote percentuali** sono però stabili
fra 8 kHz e 4 kHz e fra sessioni diverse (il 2.1% si ripete identico su tutte e quattro le run),
quindi le uso; i valori **assoluti per frame** in condizioni di cattura non sono trasferibili
tali e quali al gioco senza strumentazione.

## Il risultato che resta utile: dove sta il costo dell'UMD

Anche se il ramo Fortnite si chiude, la mappa del codice caldo dell'UMD resta valida e vale per
qualunque carico DX12:

- **204 pagine distinte** su ~6 200 di `.text` ricevono campioni;
- le prime 10 (**40 KB**) coprono il **29.4%** del tempo CPU dell'UMD;
- la più calda, `amdxc64+0x17cc000`, da sola il 6.2%.

Elenco completo in `run*/amdxc64_hot_offsets.csv`.

## Conclusioni

**Stabilito (4 run, CV ≤ 2%)**

1. L'UMD AMD DX12 vale il **2.1% del percorso critico** di Fortnite Performance Mode
   (≈ 0.03 ms/frame). Il ramo è **chiuso** per questo target: sotto la soglia pre-registrata,
   e un miglioramento realistico sarebbe sotto il rumore di misura.
2. Il percorso critico è dominato all'**84% da `ntoskrnl.exe`**, concentrato in 3 pagine.
   Non è driver AMD.
3. L'UMD nel complesso consuma ~0.15 core-equivalenti, ma l'81% di quel costo sta su un thread
   di submission che **non è** sul percorso critico del frame — cioè lavoro che avviene in
   parallelo e non allunga il frametime.
4. Il codice caldo dell'UMD è concentrato in 40 KB.

**Non stabilito**

- Cosa sia `ntoskrnl+0x233000–0x236000` (servono simboli pubblici + ricattura).
- Se la ripartizione a 620 FPS senza WPR sia la stessa: le percentuali sono stabili su quattro
  run in due condizioni di sampling, ma nessuna misura è stata fatta senza overhead.
- Correlazione con i singoli spike di frametime: ora sarebbe possibile (PresentMon e CPU sample
  nella stessa cattura, `TimeInQPC` disponibile), ma non è stata fatta e gli ETL non ci sono più.

**Cosa NON chiude questo risultato**

Il ramo **compilatore/codegen su carichi GPU-bound** resta aperto e non è toccato da questa
analisi: su Steel Nomad il costo è al 99.9% esecuzione GPU, dove il costo CPU dell'UMD è
irrilevante e conta invece la qualità dell'ISA generato.
