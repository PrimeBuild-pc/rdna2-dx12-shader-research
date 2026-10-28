# Procedura di cattura ETW — ripetibile

Read-only rispetto a gioco e driver. WPR e PresentMon sono consumatori ETW passivi:
nessuna injection, nessun hook, nessuna modifica al processo del gioco.

## Prerequisiti

- **PowerShell elevata** (WPR richiede admin). Lo script si rifiuta di partire senza.
- ~5 GB liberi sul disco di destinazione (3 ETL da 1–2 GB).
- Fortnite già avviato, in partita, sullo stesso percorso Creative della baseline.
- Consigliato: chiudere Discord e gli overlay. Nel dry-run Discord risultava fra i maggiori
  consumatori di CPU di background ed è un candidato per l'anomalia di `fortnite_r4`.

## Esecuzione

Dalla cartella del progetto, una run alla volta:

```powershell
.\tools\capture_etw.ps1 -Run 1
```

Sequenza dello script:

1. salva l'elenco dei processi di background in `*-background.csv`;
2. `xperf -setprofint 1221` → sampling a ~8 kHz (il default a 1 kHz è troppo grezzo a 620 FPS);
3. `wpr -start CPU -start GPU -filemode`;
4. avvia PresentMon sullo stesso processo, stessa finestra;
5. conto alla rovescia di 10 s → **torna nel gioco e inizia il percorso**;
6. cattura 75 s, poi `wpr -stop` da solo;
7. ripristina `xperf -setprofint 10000` e scrive `*-meta.json` (driver, build OS, HAGS, timing).

Ripeti con `-Run 2` e `-Run 3`, lasciando ~30 s di idle fra una e l'altra.

Parametri utili: `-Seconds`, `-PreRoll`, `-OutDir`, `-Process`, `-Tag`, `-SkipPresentMon`.
Per un workload diverso (es. Steel Nomad):

```powershell
.\tools\capture_etw.ps1 -Run 1 -Tag steelnomad -Process 3DMarkSteelNomad.exe
```

## Analisi

```bash
python tools/etw_analyze.py research/08_etw_fortnite/raw/<nome>.etl research/08_etw_fortnite/run1 --process FortniteClient-Win64-Shipping.exe
```

Senza `--process` aggrega tutto il sistema (utile per vedere il contorno).
Tempi indicativi: ~25 s di analisi ogni 13 s di traccia a 1 kHz; con 75 s a 8 kHz aspettati
diversi minuti. La memoria resta bassa: l'aggregazione è in streaming.

## Se qualcosa va storto

| sintomo | causa / rimedio |
|---|---|
| `wpr -start` fallisce | una sessione è già attiva → `wpr -cancel` |
| ETL enorme o disco pieno | abbassa `-Seconds`, o usa `-ProfInt 2441` (4 kHz) |
| pochi campioni sul processo | verifica che `-setprofint` sia stato applicato prima di `wpr -start`: il conteggio di `SampledProfile` deve essere ~8× quello a default |
| PresentMon non scrive | il processo target dev'essere già in esecuzione; controlla il nome esatto |
| sampling rate rimasto alto | `xperf -setprofint 10000` per tornare al default (lo script lo fa da solo, ma non se lo interrompi con Ctrl+C) |

## Cosa NON fa questa procedura

- non allinea i QPC fra WPR e PresentMon: la correlazione con i frametime è **al secondo**,
  non frame-per-frame;
- non scarica simboli (nessuna richiesta di rete). L'attribuzione è per **modulo**, che è quanto
  serve; per `amdxc64.dll` non esistono comunque simboli pubblici;
- non tocca il gioco, il driver, la shader cache o il registro.
