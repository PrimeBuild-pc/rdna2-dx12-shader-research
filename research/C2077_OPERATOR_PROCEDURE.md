# Cyberpunk 2077 — procedura operativa (non invasiva)

Scope e limiti sono fissati in [`PHASE_2U_PREREGISTRATION.md`](PHASE_2U_PREREGISTRATION.md),
sezione «Milestone C2077». Questo documento è solo il come.

**Il gioco lo avvii tu, a mano, da GOG. Nessuno script lo lancia**, e lo strumento di cattura si
rifiuta di partire se il processo non è già in esecuzione — non è una convenzione, è un controllo
nel codice (`tools/capture_game.py`).

## Cosa è già pronto e verificato

| pezzo | stato |
|---|---|
| `tools/capture_game.py` | **validato oggi** su un processo D3D12 vivo: 11 030 frame in 20,1 s, exit 0 |
| `tools/pmparse.py` | esteso ai tre schemi CSV di PresentMon; **le 14 baseline esistenti danno numeri identici** dopo la modifica |
| PresentMon 2.5.1 | consumer ETW, nessuna injection. Serve shell elevata |
| Metriche | p95/p99 frametime, 1% e 0.1% low time-integrated, conteggio stutter — definizioni in `research/04_benchmarks/analysis/METHOD.md`, invariate |
| 3DMark Steel Nomad | installato in `E:\3DMark`, CV run-to-run 0,11% — il controllo più stabile del progetto |
| Unigine Superposition | in download in questa sessione |

## Cosa serve da te

1. **Installa Cyberpunk 2077 da GOG** su `E:` (226 GB liberi). Nessuna patch, nessuna mod,
   nessun launcher di terze parti.
2. **Configura la grafica una volta sola** dal menu del gioco e **non toccarla più**: DX12,
   risoluzione nativa 2560×1440, preset a piacere ma **fisso**, **V-Sync OFF**, frame cap OFF,
   ray tracing a scelta ma dichiarato. Niente FSR/DLSS dinamico: se usi un upscaler, tienilo su
   un fattore fisso.
3. **Fammi sapere il preset scelto**: entra nei metadati dell'esperimento.

## Il protocollo di misura

Ogni sessione, in quest'ordine. Serve una shell elevata.

### 1. Controllo prestazionale *prima* (manuale, tuo)

Steel Nomad da `E:\3DMark`. È GUI, quindi lo lanci tu. Mi dai il punteggio; io lo confronto con
la baseline già in `research/3DMark_SteelNomad_DX12/`. **Se si discosta più dello 0,5%, la
sessione non è comparabile con le precedenti** e si ferma lì: è tutto il senso del controllo.

### 2. Il benchmark integrato del gioco, ≥5 run

Il benchmark interno di Cyberpunk è il workload preferito: percorso fisso, quindi ripetibile.

```
# avvii il gioco a mano, arrivi al menu benchmark, poi per ogni run:
python -B tools/capture_game.py --process Cyberpunk2077.exe --seconds 90 \
       --label bench_r1 --session 60_c2077
# lanci il benchmark entro pochi secondi; ripeti per r2..r5
```

`--delay N` se vuoi far partire la cattura N secondi dopo il comando.

**Cinque run minimo prima di qualunque affermazione.** La varianza run-to-run si misura *prima*,
come per ogni altro workload di questo progetto — la regola non cambia perché il workload è un
gioco commerciale.

### 3. Una sessione di gameplay ripetibile (secondaria)

Un percorso fisso in una zona fissa, stessa ora del giorno in-game, 120 s. Serve a vedere se il
benchmark integrato è rappresentativo. Non è la misura primaria: non è ripetibile frame per
frame, e questo va detto invece che nascosto dietro una media.

### 4. Controllo prestazionale *dopo* (manuale, tuo)

Steel Nomad di nuovo. Se prima e dopo differiscono, la sessione è sospetta: probabile drift
termico o di clock, e i run vanno riletti alla luce di questo.

## Cosa non viene fatto, e resta così

- Nessuna modifica a file del gioco, config, Registry, driver o cache.
- Nessuna injection, nessun hook, nessuna variabile d'ambiente iniettata nel processo del gioco.
  La superficie `AMD_SC_OPTIONS` trovata in fase 1.5B **non viene usata qui**; se mai lo sarà,
  avrà una preregistrazione propria con la sua dichiarazione di rischio.
- Nessuno script lancia il gioco.
- 3DMark e Superposition sono **controlli**, mai bersagli: niente viene modificato, patchato o
  scriptato dentro di loro.

## Cosa questa milestone può e non può concludere

La pipeline congelata **ricompila uno shader dal sorgente**. Cyberpunk non distribuisce sorgenti
e i suoi file non si toccano: **la pipeline di trasformazione non può girare qui, e nessuna parte
di questa milestone sosterrà il contrario.** Quello che può girare è la metà che precede
l'ipotesi — profilare, attribuire, classificare il limite — e rispondere onestamente a una
domanda: *esiste qui un tetto shader-side che un metodo source-level potrebbe toccare, e come
faremmo a saperlo senza il sorgente?*

## Fortnite / Warzone

Non aperti da questa milestone. Eventualmente dopo, come milestone separata, e limitati in
anticipo a profiling passivo e a impostazioni cambiate dai menu dei giochi stessi. Nessuna
injection, nessun hooking, nessuna interferenza con l'anti-cheat, nessuna modifica a file
protetti — un limite che non si muove qualunque cosa esca da Cyberpunk.
