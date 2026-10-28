# Shader Lab — uso e rimozione

Canary fase 66 conclusa senza marker visibile per l'operatore; non dichiarare successo.
Installazione corrente **observe**, senza shader override, con il catalogo readonly della
[fase 68](../68_c2077_backbuffer_catalog_20261016/STATUS.md). Il precedente osservatore specifico
fase 67 è archiviato/rimosso: seguire la nuova procedura, senza cercare altre canary a caso.
**Niente benchmark.** Non è un'ottimizzazione.

I comandi seguenti si eseguono dalla root `driver mod`. Non avviano o terminano processi.

```text
python -B tools/c2077_shader_loader.py status
```

Lo stato legge log propri e PID attuali. `bound_calls` non prova draw/GPU completion;
nessun contatore è un dato di performance. Target glass potrebbe non apparire nella scena.

## Canary, solo dopo controllo accettato

Già impostata nella sessione corrente. Il comando, come riferimento per successivi cambi
mode, si usa solo a gioco chiuso:

```text
python -B tools/c2077_shader_loader.py mode canary
```

Riaprire manualmente la stessa partita/scena. Questa variante deve alterare il vetro
riconosciuto verso magenta; non è destinata a giocare normalmente né a misurare uno speedup.
Se non compare, conservare il risultato negativo: non dichiarare il gate superato.
Tornare a `mode control` oppure `mode observe` a gioco chiuso. Observe non crea/sostituisce PSO.
**Niente hot-reload/unload dell'add-on mentre il gioco è aperto.**

## Ripristino

A gioco chiuso, anche dopo un crash:

```text
python -B tools/c2077_shader_loader.py uninstall
```

Rimuove solo file nuovi di cui il manifest attesta la creazione; prima li archivia in
`research/66_c2077_shader_loader_20261016/rollback-*`. Conserva i log propri riconoscibili.
Se un payload immutabile è stato sostituito da un altro mod, si ferma prima delle cancellazioni.
I file utente sconosciuti vengono lasciati al loro posto. Non ripristina/sovrascrive EXE,
DLL originali, salvataggi, impostazioni o cache; confronta hash degli originali e segnala derive.
Non usa backup delle cache come materiale da reinstallare.

Il manifest rimosso resta come evidenza; non cancellarlo per reinstallare alla cieca.
Ripristino reale già verificato in r0 prima dell'installazione corrente.

## File aggiunti al gioco

```text
bin/x64/dxgi.dll                          ReShade ufficiale x64 byte-identico all'estratto
bin/x64/ReShade.ini                      configurazione nuova, nessun effetto
bin/x64/C2077ShaderLab/C2077ShaderLab.addon64
bin/x64/C2077ShaderLab/C2077BackbufferProbe.addon64  catalogo fase 68 (sostituisce la sonda 67)
bin/x64/C2077ShaderLab/mode.txt           control / canary / observe, letto solo all'avvio
bin/x64/C2077ShaderLab/preset.ini         preset vuoto
```

Directory nuove `C2077ShaderLab/empty` e `C2077ShaderLab/effect-cache` confinano percorsi
ReShade. Dopo l'avvio sono previsti `ReShade.log`, `C2077ShaderLab/runtime-*.jsonl`
e ora `C2077ShaderLab/backbuffer-*.jsonl` (i precedenti `probe-*` sono storici). Il rollback li archivia/rimuove
solo con formato del nome ed experiment attesi; i file sconosciuti restano.
Non distribuire proxy/add-on ad altri giochi; vietati Fortnite/Warzone/anti-cheat.

## Build e verifiche senza gioco

```text
research\66_c2077_shader_loader_20261016\build.cmd
python -B tools/c2077_shader_loader.py selfcheck
```

Header incorporato generato da payload con hash in `payload_inputs.json` e conservato in
`build/shader_payloads.hpp`; percorso/hash EXE fissati, quindi non è un loader generico.
Il build non aggiorna automaticamente il manifest di distribuzione: non reinstallare una
build cambiata senza rivedere package/hash/preregistrazione. I test non caricano l'host ReShade,
non creano device GPU e non provano la compatibilità con Cyberpunk.

Limite di fiducia: host upstream non firmato, setup con catena non attendibile localmente;
nessuna modifica al trust store o alle protezioni Windows. [Stato completo](STATUS.md).
