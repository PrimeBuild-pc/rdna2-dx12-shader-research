# Fase 68 — catalogo shader da draw verso backbuffer

**Stato: READONLY_BACKBUFFER_CATALOG_INSTALLED — RUNTIME_PENDING.**
Nessun avvio automatico, shader override o benchmark. Root cause della canary precedente ignota.

## Cambio di approccio

La fase 67 termina con zero bind/draw target nei comandi osservati anche dopo il breve giro
visuale. Non chiedere altri giri o ricerche di vetri per quel candidato. Log finali del PID
11348 chiuso in [fase 67 closed](../67_c2077_canary_probe_20261016/r1/closed/snapshots.json).
Non estendere l'assenza osservata a ogni scena/GPU o cancellare i precedenti bind delle altre run.

A processo assente:

- ShaderLab impostato **observe**: nessuna creazione/sostituzione delle PSO shader;
- vecchio osservatore C2077ShaderProbe.addon64 verificato, archiviato e rimosso;
- aggiunto C2077BackbufferProbe.addon64, readonly con guard EXE/percorso/SHA;
- host ReShade e ShaderLab agli hash invariati. Driver/cache/file originali non manipolati.

[deployment.json](deployment.json), [package.json](package.json), [preregistrazione](PREREGISTRATION.md).
Vecchio observer conservato in `removed_probe/`; manifest proprietà fase 66 aggiornato,
quindi `uninstall` rimuove anche il nuovo file/log riconosciuti a processo chiuso.

## Cosa osserva

[Sorgente](../../tools/c2077_backbuffer_probe.cpp): risorse vere restituite dalla swapchain,
identità RTV0->risorsa, PSO pixel corrente, SHA-256 intero bytecode e draw CPU che puntano
al backbuffer. Formati/maschere/blend/depth, indizi di triangolo fullscreen e riferimenti
nelle submission della command list. Riconosce OMSetRenderTargets e BeginRenderPass.
Gestisce resize, reset e cambio binding; non inserisce comandi GPU, copie, query o timing.

Contatori non provano GPU completion, pixel visibili o che un draw sia l'ultimo sul frame.
Scritture compute/UAV/copie e bundle con RTV ereditati sono limiti dichiarati, non falsi
"zero lavoro". Mutex/hash/log perturbano la CPU: nessun confronto FPS da questo strumento.

## Offline e verifiche

- Preparato `offline_shader_index.json`: **8340 SHA distinti / 19950 occorrenze** dalle copie
  fase 64. Servirà a ricondurre uno shader effettivamente osservato al bytecode originale,
  non a sceglierlo prima del runtime. La ricerca successiva deve verificare hash/file/offset.
- PASS selftest C++: risorsa/device, offscreen vs backbuffer, rebind, reset, resize,
  rimozione swapchain, draw vuoti, submission, SHA256 noto e buffer host >16 MB, host errato.
- PASS selftest Python: archivio/rimozione log backbuffer propri e conservazione sconosciuti,
  oltre ai precedenti casi. Nessun device GPU/host ReShade avviato dai selftest.
- Source check API GPU mutanti assenti, PE x64/export e hash installati verificati.
  [final_build.log](build/final_build.log), [loader_selfcheck.log](build/loader_selfcheck.log).
- Non esiste ancora una regression unattended del fotogramma finale. Nessun fix/speedup.

## Prossima azione manuale

Avviare normalmente Cyberpunk e caricare una partita/scena usuale, attendere 10–15 secondi,
poi comunicare «pronto». **Non cercare il fucsia: observe non modifica alcuno shader.**
Niente benchmark. Leggere nuovi log/PID `backbuffer-*`; `python -B tools/c2077_shader_loader.py status`
ora include il campo `backbuffer`. I vecchi log canary/target non sono dati della nuova sessione.

Prima di nuova canary: verificare candidati realmente osservati nei draw verso backbuffer,
maschere e contesto, collegamento SHA al cache offline e interfaccia. Non promettere che
il solo shader pixel catalogato sia un collo di bottiglia o visibile senza ulteriore oracle.
