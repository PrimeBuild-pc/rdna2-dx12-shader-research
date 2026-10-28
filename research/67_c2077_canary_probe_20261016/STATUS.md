# Fase 67 — sonda osservativa per canary non visibile

**Stato: CLOSED — NO_TARGET_BIND_OBSERVED_AFTER_VIEW_TEST.** Nessuna correzione dichiarata.
PID 11348 chiuso: quattro PSO target create ma zero bind/draw target nei comandi osservati,
anche dopo giro della visuale. RGB mask 0xF e sorgente one nelle quattro PSO non bindate.
[Esito dopo giro](r1/after_view/result.json), [log finali](r1/closed/snapshots.json).
Vecchio observer archiviato/rimosso; ShaderLab ora observe. Prosegue la
[fase 68](../68_c2077_backbuffer_catalog_20261016/STATUS.md), selezione da draw verso backbuffer.

## Perché

L'utente vede immagine invariata nella canary fase 66. Ultimo heartbeat del processo chiuso
14612: 5 PSO create, 2033 bind, zero errori clonazione. Questo non supera il gate visivo.
[Negativo preservato](../66_c2077_shader_loader_20261016/canary_r1/negative_snapshot/report.json),
[log finali](../66_c2077_shader_loader_20261016/canary_r1/closed/snapshots.json).

Controlli statici: HASH shader e digest/DXIL distinti; quattro output magenta corretti;
interi payload presenti nel binario installato. SDK sorgente fissato mostra passaggio del
pixel shader al factory e bind sostitutivo successivo al bind originale. Non dimostrano
però output GPU visibile. Ipotesi/predizioni/limiti: [PREREGISTRATION.md](PREREGISTRATION.md).

## Cosa è cambiato

Aggiunto **un solo file nuovo**, `bin/x64/C2077ShaderLab/C2077ShaderProbe.addon64`.
DLL host e ShaderLab **identiche**, bytecode canary **identico**, mode rimasto **canary**.
Installazione a processo assente, pubblicazione atomica, file aggiunto al manifest di
proprietà della fase 66 per la rimozione. [deployment.json](deployment.json), [package.json](package.json).
Non toccati EXE/DLL preesistenti, driver, cache, impostazioni del gioco o Registry/boot.

Sonda [C++](../../tools/c2077_shader_probe.cpp) con guard percorso/SHA EXE e match bytecode
originale esatto. Osserva PSO RT formats/count, write mask, blend e depth; conta binding,
draw direct/indexed/indirect, potenziali bundle e command list inviate alla coda.
Non chiama API GPU di modifica dello stato/creazione/query, non cambia shader e restituisce
sempre false dalle callback draw. Non è un benchmark; aggiunge carico CPU di osservazione.

Aggiornato l'helper esistente per leggere anche log `probe-*` e rimuoverli solo con
nome/experiment corretti, archiviandoli. File sconosciuti conservati. Risolto inoltre
l'ordinamento dei log per PID lessicografico: ora usa la cronologia, per non perdere una
nuova sessione con PID numericamente inferiore. Selftest copre questo caso.

## Verifiche

- PASS build/selftest C++: target matching, device key, rebind non target, reset,
  submission, bundle con ultimo binding differente, draw vuoti, maschere zero, zero RT,
  host errato. Nessun device GPU/host ReShade creato dai test.
- PASS selftest Python: rollback, collisioni, payload cambiato, log probe proprio archiviato,
  log non riconosciuto conservato, ordine cronologico dei log.
- [final_build.log](build/final_build.log), [loader_selfcheck.log](build/loader_selfcheck.log).
- Questi non riproducono automaticamente il sintomo visivo e non costituiscono una
  regression end-to-end GPU. Root cause ancora ignota, non dichiarare fix.

## Prossimo passo manuale

Il giro richiesto è concluso senza bind target osservati; processo ora chiuso. Non insistere
su altre ricerche del vetro. Seguire la fase 68 per un avvio manuale in observe con nuovo
catalogo readonly. Nessun benchmark o shader modificato.

Stato: `python -B tools/c2077_shader_loader.py status` (ora include `probe`).
Rimozione a gioco chiuso: `python -B tools/c2077_shader_loader.py uninstall`, archivia e rimuove
anche il nuovo add-on e i suoi log riconoscibili tramite manifest.

Counter CPU e invii alla coda non provano GPU completion/frammenti visibili. Indirect e
bundle possono rappresentare lavoro solo potenziale. Non attribuire costo/FPS a questi log.
