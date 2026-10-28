# Fase 66 — loader DX12 Cyberpunk

**Stato: CANARY_VISUAL_GATE_FAILED_IN_TESTED_SCENE.**
Setup corrente: ShaderLab **observe**, nessun override shader; catalogo readonly della
[fase 68](../68_c2077_backbuffer_catalog_20261016/STATUS.md) installato, vecchia sonda 67 rimossa.
Control avviato manualmente e accettato dall'utente: «chiuso, immagine normale».
Ultimo heartbeat PID 5396: 5 PSO control create, 1044 bind target, zero errori di clonazione.
[Control r1](runtime_control_r1/RESULT.md), [log finali](runtime_control_r1/closed/snapshot.json).
Impostato mode=canary a gioco chiuso, DLL invariate. Ora avviata manualmente: PID **14612**,
5 PSO canary create, ultimo heartbeat **2033 bind**, zero errori di clonazione; [risultato canary r1](canary_r1/RESULT.md).
L'utente riferisce nessuna superficie rosa, immagine invariata: **gate visivo non superato**.
Processo ora chiuso; aggiunta solo una sonda osservativa, shader/mode/DLL precedenti invariati.
Prossima azione e diagnosi nella [fase 67](../67_c2077_canary_probe_20261016/STATUS.md).
Nessun avvio automatico o nuovo benchmark. Nessuno speedup dimostrato.

## Fatto

- ReShade ufficiale 6.8.0 Full Add-on x64, setup scaricato ma **non eseguito**;
  estratta solo la DLL x64. Versione PE 6.8.0.2155. Provenienza/hash in
  [downloads/provenance.json](downloads/provenance.json) e
  [downloads/extraction.json](downloads/extraction.json).
- SDK API 20 fissato al tag/commit `18deaa52de0c425a78b329e9cb3c497281cd00ec`.
  Revisionati reference, esempio, ricerca add-on, librerie PSO DX12 e bind nativo.
  OptiScaler non necessario: evitati upscaling/FG/spoofing e cambi qualità.
- Add-on minimale compilato localmente: guard su **percorso e SHA-256 EXE**;
  confronto pixel shader per **tutti i byte e dimensione**. Crea una PSO separata dal
  descrittore originale e redirige solo i bind del target. Supporto previsto anche al
  percorso pipeline library, senza sostituire cache. Creazione e bind control ora osservati;
  correttezza visiva e canary ancora da verificare.
- Bytecode original/control/canary della fase 65 incorporato senza cambiamenti;
  [payload_inputs.json](payload_inputs.json). Nessuna nuova trasformazione dello shader.
- Generic Depth/Effect Runtime Sync, effect reload/cache e shortcut overlay disabilitati;
  nessun shader pack, HDR mod o cambiamento delle impostazioni del gioco.
- PASS: selftest C++ selezione/guard/descrittori/host errato; selftest Python mode,
  rollback, collisione, file immutabile cambiato, conservazione file utente sconosciuto.
  [final_build.log](build/final_build.log), [deployment_selfcheck.log](build/deployment_selfcheck.log).
- **PASS ripristino sul target reale:** installazione r0, rimozione, confronto di
  nomi/hash di **84 file preesistenti, 527653806 byte**, identici. Directory propria rimossa.
  Nessun avvio. [filesystem_roundtrip.json](filesystem_roundtrip.json),
  [deployment_r0_removed.json](deployment_r0_removed.json), [filesystem_commands.json](filesystem_commands.json).
- Reinstallato lo stesso pacchetto in **control**. Cinque file nuovi in
  `E:\GOG\Cyberpunk 2077\bin\x64`; nessun file originale sovrascritto.
  [deployment.json](deployment.json), [package.json](package.json).
- EXE e due cache engine ancora agli hash originali; configurazione gioco copiata
  in backup di ricerca, non modificata. Nessuna manipolazione diretta delle cache AMD,
  driver, Registry, boot/sicurezza, Adrenalin o giochi anti-cheat.

## Fiducia e ambiente

Setup: firmatario CN=ReShade ma catena **non attendibile localmente**. DLL host e add-on
locale `NotSigned`. Origine HTTPS ufficiale e integrità verificata non sono una firma
Authenticode valida né prova di build upstream riproducibile. Nessun certificato importato,
execution policy/protezione cambiata. Dettagli in [preflight_windows.json](preflight_windows.json).

**Driver attuale: 32.0.21045.11001**, diverso dal 32.0.21045.5002 delle misure storiche.
RX 6950 XT / Windows 11 build 26200 confermati dal preflight. Non trasferire la baseline
prestazionale di settembre a questa installazione.

## Prossimo passo manuale

Control confermato normale dall'operatore (qualitativo, non equivalenza pixel quantitativa),
la canary è stata eseguita ma non ha prodotto il marker visibile nella scena provata.
PID 14612 chiuso, log finali preservati. Ora la fase 67 richiede un nuovo avvio manuale
con la sola sonda di draw/output aggiunta: stessa canary, nessun cambio qualità o benchmark.
Non cambiare mode/DLL a gioco aperto.
I livelli di evidenza da distinguere nei `C2077ShaderLab/runtime-*.jsonl` sono:

1. `loaded_exe_guard_pass`: add-on inizializzato nel processo atteso;
2. `dx12_pipeline_inits>0`: callback DX12 attive;
3. `matched_original>0`, `cloned_pipelines>0`, `clone_failures=0`: variante accettata come PSO;
4. `bound_calls>0`: bind della PSO target rediretto; non ancora prova di draw/frammenti visibili.

Marker canary esplicitamente non osservato dall'operatore. Risultato negativo/inconclusivo
sull'uso visibile, non prova che il loader sia rotto o che lo shader sia stato eseguito.
Nel control finale sono presenti WARN host di reference count e add-on ancora caricati
in uscita; dettagli e limiti conservati nella [nota canary](canary_r1/README.md). Nessun evento
unloaded finale per il ciclo D3D12: non dichiarare certificato l'intero lifecycle/exit code.
Presenza/costo nel benchmark **sconosciuti**. Nessuna misura prestazionale implicita.
[Preregistrazione](PREREGISTRATION.md).

Comandi di stato/mode/rimozione e limiti: [README.md](README.md).
