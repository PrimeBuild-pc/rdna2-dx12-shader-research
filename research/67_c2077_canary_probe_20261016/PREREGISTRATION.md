# C2077-SHADER-PROBE-001 — osservazione mirata dopo canary negativa

La canary fase 66 è stata caricata/creata/bindata, ma l'utente riferisce **nessuna superficie
rosa, immagine invariata**. Il gate visivo NON è passato. Report e log originali conservati
nella fase 66 `canary_r1/negative_snapshot/`. Il presente documento precede installazione e
avvio della nuova sonda; non è la preregistrazione di una correzione o di un benchmark.

## Fatti già controllati, non ipotesi di successo

- Original/control/canary hanno HASH shader, digest DXBC e payload DXIL distinti.
- Quattro output SV_Target0 della canary sono RGBA (1,0,1,1).
- I tre payload completi sono presenti nella DLL compilata; hash installato identico alla
  copia ispezionata. Assembly/validazione esterna fase 65 rimangono acquisiti.
- Il sorgente SDK 6.8.0 fissato mostra passaggio del pixel shader ricevuto a CreateGraphicsPipelineState,
  e bind callback dopo SetPipelineState originale; il bind API scrive la PSO sostitutiva sul comando nativo.
- Questi fatti non provano shader effettivamente eseguito, frammenti o colore visibile.

## Ipotesi e predizioni, ordine diagnostico

1. **Output non visibile:** se RT0 non esiste, la maschera esclude RGB o il blending ignora
   il sorgente, forzare RGB su SV_Target0 non garantisce il marker. Registrare numero/formati
   RT, maschere e blend/depth della sola PSO con bytecode originale esatto.
2. **Bind senza lavoro utile/osservabile:** se non seguono draw o command list con lavoro
   inviate alla coda, il contatore bind non prova uso sul frame. Osservare direct/indexed,
   indirect noti/sconosciuti, bundle e submission, senza inserire comandi GPU.
3. **Percorso di sostituzione diverso da quello atteso:** i primi controlli statici riducono
   la plausibilità di bytecode identico/mancante, ma non certificano ISA o stato GPU effettivo.
   Se i precedenti controlli non discriminano, servirà un riscontro GPU/immagine ulteriore,
   non dichiarare risolto o cancellare le cache.

## Unica variazione sperimentale

Aggiungere **un add-on osservatore separato** `C2077ShaderProbe.addon64`, SDK API 20 già
revisionato, con stesso guard percorso/SHA EXE e match tutti i byte del pixel shader.
Nessuna modifica alla DLL ShaderLab, al bytecode canary, al mode canary, a driver/cache,
impostazioni del gioco, Registry o boot. Nessun effect/HDR/upscaler o nuovo installer.

L'osservatore non chiama API di creazione risorse/pipeline, bind, draw, query GPU o timing.
Callback draw restituiscono sempre false (non sopprimono comandi). Log `probe-PID-time.jsonl`
nella stessa directory nuova; rollback conserva e rimuove solo log con nome/experiment attesi.
Installazione solo dopo processo Cyberpunk assente, file nuovo pubblicato atomicamente e
aggiunto al manifest di proprietà esistente. Se esiste già un file omonimo, rifiutare.

## Copertura e limiti

- Il tracker segue PSO source osservate, reset/distruzione command list, sostituzioni di
  binding e ultimo binding esplicito dei bundle; non legge lo stato reale del driver.
- Draw diretti con count/instance zero sono separati. Indirect con max count positivo e
  firme sconosciute sono **potenziali**, non numero di draw eseguiti.
- Bundle con binding ereditato sono marcati come potenziale lavoro; non si ricostruiscono
  i singoli draw ereditati. Submission è chiamata CPU osservata, non GPU completion.
- Callback mancanti/bypassate, predicazione, culling, discard, depth/stencil e compositing
  restano possibili. Zero counter da solo non prova assenza di lavoro GPU.
- Mutex/log modificano il carico CPU: **nessuna misura FPS/performance** consentita da questa sonda.

## Loop e test

Il sintomo esatto rimane un oracle manuale, già negativo nella run canary. Non esiste qui
un test unattended capace di riprodurre/asserire il fotogramma finale: mancano coppia di
immagini/camera deterministica e prova GPU. I test unitari non vengono spacciati per tale loop.

Prima di installare: selftest C++ stato/overwrite/reset/device key/bundle/submission/empty
counts, descrittori con write mask zero e RT count zero, guard host errato; selftest Python
rollback log probe e conservazione file non riconosciuti, ordine cronologico dei log.
Nessun test crea device GPU o carica l'host ReShade. Nessuna correzione dichiarata.

Poi un avvio **manuale** della stessa partita/scena per raccogliere i nuovi log. Nessun
benchmark o cattura automatica. Interpretare solo le predizioni supportate dai log e
fermarsi quando serve davvero una cattura GPU/immagine, senza scegliere nuove canary alla cieca.
