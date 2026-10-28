# C2077-DXIL-CANARY-002 — candidato selezionato dal backbuffer

Prima di costruzione varianti e qualsiasi applicazione runtime. Non è un'ottimizzazione.

## Selezione fissata da evidenza fase 68

PID manuale 276, observe (zero shader override). PSO serial 243: draw diretti da 3 vertici,
1 istanza, RTV0 risolto nella risorsa backbuffer reale DX12 2560x1440 R8G8B8A8_UNORM;
mask RGBA 0xF, blend off, depth off. Nella copia live: 27928 draw e riferimenti nelle
submission. Counter CPU, non prova di GPU completion/costo o che nessun draw successivo
sovrascriva i pixel. Altro candidato alpha-blended non selezionato.

SHA bytecode **1642c9e5c2f2bca229198fc354cf8e5bd712f26baa467a6392f7c5125abc9d4c**,
4995 byte; **una** corrispondenza nell'inventario offline:
`staticshader_final.cache` copia fase 64, offset **10816877**, hash intero cache verificato
`bff160947aba8df144200247adc39b44c26322360628d875f7c7218ad26c59ff`.
Estratto originale da copia in fase 68 `selected_fullscreen/`, SHA intero uguale al runtime.
Non ripacchettare/installare la cache statica; il suo parser non è necessario per bytecode
in memoria. Nessun GUID applicativo inventato.

## Varianti

- **Originale** invariato e validato esternamente con DLL Microsoft SDK fissate fase 65.
- **Control:** round-trip intero LLVM IR identico (newline normalizzati), firme/PSV/SFI
  payload identici, container non necessariamente byte-identico, validazione esterna.
- **Canary:** solo RGB dei tre storeOutput SV_Target0 sostituiti con (1,0,1).
  Alpha è già 1 e resta 1: **tre operandi modificati**, non quattro. Nessun altro opcode,
  input/resource/cbuffer/metadata/interface cambiato. Un solo output SV_Target0.
- Nessuna trasformazione prestazionale o modifica al dither/gamma/trasferimento colore.
  Non classificare il nome del pass dal solo cbuffer o filename.

## Gate

1. Offline: assemble/validate/revalidate/dump, IR control identico, differenza canary esatta
   e parti interfaccia identiche. Selfcheck mutatore: alpha intatta, shader output1 intatto,
   store duplicati rifiutati. Output nuovi senza sovrascrivere originali o varianti storiche.
2. Solo a gioco chiuso preparare eventualmente il loader con nuovo target exact-bytes,
   provenienza/build/manifest/rollback separati. Vecchio glass non è la nuova canary.
3. Prima **control** con avvio manuale e immagine normale; poi chiusura, canary e nuovo avvio
   manuale nella stessa scena. La canary può rendere l'intera immagine 3D **magenta uniforme**
   (HUD eventuale sopra): alterazione diagnostica intenzionale, non preset per giocare.
4. Log/PID/module hash devono riferirsi al nuovo target. Bind/draw/queue non sono marker
   visivo: serve riscontro operatore, idealmente immagine. Senza marker esito non superato.
5. Ripristino observe/control o rimozione solo a gioco chiuso; nessun hot-unload, nessuna
   cache sostituita, driver/Registry/boot/Adrenalin/anti-cheat non toccati.

Nessun avvio, benchmark o cattura GPU automatico. Nessuno speedup o correttezza quantitativa
immagine attestata dal solo controllo qualitativo. Prima di prestazioni serve una fase nuova.
