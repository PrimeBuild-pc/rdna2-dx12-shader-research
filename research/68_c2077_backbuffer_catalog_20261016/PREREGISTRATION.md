# C2077-BACKBUFFER-PROBE-001 — candidato scelto dai draw, non dalla cache

Fase 67: anche dopo giro visuale richiesto all'operatore, zero bind/draw del target nei
comandi osservati (PID 11348, poi chiuso). Non continuare la ricerca casuale del vetro.
La causa del precedente canary senza marker resta ignota; non dichiarare il loader rotto.

## Variazione prima del prossimo avvio

- Verificato gioco chiuso, ShaderLab impostato **observe**: nessuna sostituzione shader.
- Archiviare/rimuovere solo il vecchio osservatore proprietario C2077ShaderProbe.addon64,
  previo confronto SHA con manifest; conservarne binario e log. Non cancellare sorgenti/raw.
- Aggiungere un osservatore readonly C2077BackbufferProbe.addon64 con stesso guard EXE
  percorso/SHA, SDK API 20 già fissato. Nessun driver/cache/EXE/DLL preesistente/setting toccato.
- Nessuna API GPU di modifica stato, creazione risorse, shader override, query o timing.
  Callback draw/render-pass sempre false. Nuovo add-on e log riconoscibili nel rollback.

## Segnale cercato

Registrare risorse reali restituite da get_back_buffer delle swapchain DX12 e dimensioni/formati.
Ai bind RTV e begin render pass risolvere **RTV0 -> risorsa** con get_resource_from_view.
Solo quando tale identità coincide con un backbuffer conosciuto, associare i draw osservati
alla PSO pixel corrente: SHA-256 dell'intero bytecode, dimensione, maschera/blend/depth/formato,
direct/indexed/indirect e riferimenti nelle submission delle command list.

Questo seleziona un percorso verso un backbuffer reale, non una correlazione di nomi/formati.
Non dimostra completamento GPU, frammenti, visibilità finale o che il draw sia l'ultimo.
Triangolo con 3 vertici/1 istanza è solo un indizio di fullscreen, non prova geometrica.

Dopo i log, cercare lo SHA esatto nell'inventario offline fase 64 (19950 occorrenze, 8340
hash distinti). Solo dopo match e ispezione bytecode/interfaccia scegliere un nuovo candidato.
Non costruire una nuova canary prima di tale selezione. Se manca il match, non inventare GUID.

## Limiti, fissati prima del runtime

- Catalogo raster pixel. Scritture compute/UAV, copie e risoluzioni possono produrre l'immagine
  finale senza draw RTV: zero candidati non prova assenza di lavoro o errore del gioco.
- Bundle con RTV ereditati non classificati nei singoli draw: contatore di copertura separato.
- Indirect è potenziale (argomenti/count GPU non letti). Predicazione, clip/scissor, depth,
  discard, compositing e draw successivi restano possibili.
- Risorse di tutte le swapchain DX12 sono distinte; usare dimensioni/formati per discriminare
  la finestra principale, non equiparare ogni swapchain al frame del gioco.
- Osservazione CPU con lock/hashing/log: non misura FPS/costo shader e può perturbare il gioco.

## Test e loop

Prima di installare: selftest di correlazione risorsa/device, reset/rebind, resize/rimozione
backbuffer, draw vuoti, submission e SHA256/host guard. CPU only, niente host ReShade/device GPU.
Selftest rollback log backbuffer proprietari e conservazione sconosciuti. Controllo statico
assenza chiamate API GPU mutanti; ispezione PE x64/export e hash installato.

Poi un normale avvio **manuale** della stessa partita/scena; nessun benchmark o cattura automatica.
Il test visivo end-to-end unattended manca ancora. Nessuna correzione/prestazione dichiarata.
