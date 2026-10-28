# C2077-SHADER-LOADER-001 — gate runtime, non performance

Registrazione precedente a installazione e avvio runtime. Autorizzazione in chat: procedere
con loader/hooking nel solo Cyberpunk; download necessari consentiti, ReShade/OptiScaler proposti.
Nessun benchmark o avvio del gioco automatico. Fortnite/Warzone esclusi.

## Pacchetto fissato

- Host ufficiale ReShade **6.8.0 Full Add-on x64**, estratto dal setup senza eseguirlo:
  https://reshade.me/downloads/ReShade_Setup_6.8.0_Addon.exe
- Setup SHA-256 `afe4c8f13048306307983b8b3d41d5bf00a86820440b0e57dea10950e1176445`.
- SDK/tag 6.8.0 commit `18deaa52de0c425a78b329e9cb3c497281cd00ec`, API 20.
- Manifest pacchetto: [package.json](package.json), SHA-256
  `5936eb516a44e1d88723a6ee6262bc94cf325bd03724126c9a18ae56fa438967`.
- Configurazione iniziale **control**. Nessun effect pack, HDR mod, OptiScaler,
  frame generation, spoofing GPU, modifiche a risoluzione/impostazioni del gioco.
- Add-on proprio: [c2077_shader_addon.cpp](../../tools/c2077_shader_addon.cpp).
  Carica solo in `E:\GOG\Cyberpunk 2077\bin\x64\Cyberpunk2077.exe`, SHA-256
  `a7de82945c03e041fc7339fcf9066224d98db2f5d80fea50f7947bb350a60991`.
- Rifiuto degli altri processi verificato dal selftest; nessun caricamento del vero host
  ReShade nei selftest. Non copiare il proxy in altri giochi.

**Limite di fiducia:** setup con firmatario CN=ReShade ma catena non attendibile localmente;
DLL host `NotSigned`. Add-on locale non firmato. Provenienza HTTPS ufficiale, ZIP/CRC,
versione e hash verificati, ma non equivalgono a una catena Authenticode valida né a una
build riproducibile del binario upstream. Nessuna importazione certificati, disattivazione
protezioni, modifica di execution policy, boot o Registry.

## Metodo e vincoli

Shader glass già validato nella fase 65: originale esatto
`c8755b8ac5d61f208d02e0fda1c3bbed2c7e0a15f59c9edbb0f8c559925828b9`.
Controllo e canary incorporati byte-identici ai payload fase 65; hash in
[payload_inputs.json](payload_inputs.json). Canary RGBA target 0 `(1,0,1,1)`, quattro
operandi cambiati; diagnostica deliberatamente non corretta come immagine di produzione.

L'add-on osserva `init_pipeline` (anche pipeline library DX12). Solo se il pixel shader
corrisponde per **dimensione e tutti i byte**, copia la descrizione transiente, cambia
il solo bytecode pixel e crea una PSO separata con il medesimo layout. La PSO originale
non viene mutata. `bind_pipeline` redirige esclusivamente gli handle originali riconosciuti.
Il bind API `all` evita modifiche implicite a blend constant/topology del percorso
`all_graphics` dell'SDK. Distruzione accoppiata alla PSO originale; mutex protegge il
clone durante il bind. Errori di creazione lasciano utilizzare l'originale.

Nessuna patch/sostituzione di EXE, DLL preesistenti, driver o cache. Solo cinque file nuovi
nel bin/x64 e directory proprie; proxy pubblicato per ultimo con rename sullo stesso volume.
ReShade Generic Depth/Effect Runtime Sync ed effect reload/cache disabilitati; shortcut overlay
spenti. Cache/preset propri confinati alla nuova directory. I normali scritti nativi del gioco
/driver, dopo eventuale avvio manuale, non sono una manipolazione diretta delle cache.

## Sequenza e criteri, fissati prima del runtime

1. Build e selftest C++: original/control/canary, stage non pixel, bytes/dimensione non
   corrispondenti, descrittori duplicati/null e host sbagliato. Selftest Python di installazione,
   mode, archivio/rimozione, collisioni, payload cambiato e conservazione file utente sconosciuti.
2. **r0 filesystem:** installazione a gioco chiuso, verifica hash, rimozione e confronto di
   nomi/hash preesistenti nel target reale. Archiviare stato e ripristino; nessun avvio.
3. **r1:** reinstallare lo stesso pacchetto, control; attendere avvio manuale di una normale
   partita. Non usare PID storici, non avviare benchmark/catture.
4. Registrare `loaded_exe_guard_pass`, `dx12_pipeline_inits`, `matched_original`,
   `cloned_pipelines`, `clone_failures`, `bound_calls` nei nuovi runtime-*.jsonl.
   Solo con `cloned_pipelines>0`, `bound_calls>0`, assenza di errori e immagine giudicata
   normale dall'operatore, passare al test canary dopo chiusura del gioco.
5. Canary: nuovo avvio manuale nella stessa scena con vetro. Cercare tintura magenta
   e log dello stesso shader. Init/clone/bind provano livelli diversi, **non provano da soli
   un draw eseguito o frammenti visibili**. Senza marker osservato non dichiarare completato
   il gate visivo. Nessuna presenza/costo nel benchmark assunto.
6. Tornare a control/observe o rimuovere tutto con script manifest-owned, a gioco chiuso.
   Non hot-reloadare/disabilitare l'add-on durante una partita. Conservare raw e insuccessi.

Driver letto nel preflight attuale: **32.0.21045.11001**, non il 32.0.21045.5002 delle
misure di settembre. Nessun confronto FPS con quelle misure. Ottimizzazione e A/B
prestazionale sono fasi successive, non autorizzate automaticamente da questo test funzionale.
