# C2077-DXIL-CANARY-001 — preregistrazione offline

## Obiettivo

Dimostrare una modifica controllata e validabile al **bytecode reale** del gioco, non uno speedup.
Nessun file installato del gioco/driver/cache verrà sostituito. Nessun benchmark o avvio del gioco.

## Candidato e provenienza

- Copia `research/64_c2077_shader_access_20261016/copies/shader_final.cache`, SHA-256 `339145371a3b5aaa08eb4ef82d558f445b632e28603ee0f3b4860270dfc3ccfa`.
- Shader GUID decimale **15973390170752892218**, blob offset **69985495**, size **23102**.
- SHA-256 bytecode originale `c8755b8ac5d61f208d02e0fda1c3bbed2c7e0a15f59c9edbb0f8c559925828b9`.
- Stringa di compilazione decodificata: `glass CompiledTechnique [Index: 0, Pass 'renderstage_transparent', PassIndex: 0, Fallback: 0, RenderStageContext: [ID: 18, VF: MeshStatic; Discarded]`.
- Stage pixel confermato dal DXIL/DXC. I nomi degli slot pixel/vertex nel reader WolvenKit risultano invertiti rispetto ai token DXIL di questa cache: il parser usa slot A/B neutrali.
- Selezionato come materiale applicativo riconoscibile per una futura canary, **non perché dimostrato costoso o attivo nel benchmark**.

## Unica modifica intenzionale

Nell'IR, soltanto le quattro chiamate `dx.op.storeOutput.f32` per **signature ID 0**, componenti RGBA, restituiscono **(1,0,1,1)** anziché i valori originali. Signature ID 1, discard, risorse, cbuffer, signature e resto del modulo restano invariati.

È un marker magenta all'uscita del render target 0 sui frammenti sopravvissuti al discard. Blending e postprocessing possono modificarne l'aspetto finale: non è promesso che tutto lo schermo diventi magenta. Non è una trasformazione corretta per produzione e non si misura come ottimizzazione.

## Controlli richiesti prima di dichiarare successo offline

1. Controllo ricostruito non modificato: IR normalizzato identico all'originale; parti SFI0/ISG1/OSG1/PSV0 identiche.
2. Canary: differenza IR limitata alle quattro chiamate preregistrate; stesse parti di interfaccia; validazione esterna Microsoft `dxil.dll` con flags default, mai `-Vd`.
3. Controlli negativi: IR sintatticamente errato e opcode DXIL non valido respinti, senza output accettato; rifiuto di sovrascrivere un output esistente.
4. Repacking **solo di copie di ricerca**: no-op byte-identico all'originale; nella variante cambiano soltanto un record/payload e gli offset/dimensioni noti del footer. Conteggi/GUID/metadata e tutti gli altri shader invariati.
5. Hash degli originali installati e delle copie ancora identici al baseline.

## Cosa NON prova il successo offline

Non prova caricamento del contenitore ricostruito da parte del gioco, attivazione del PSO, frame corretto, costo del pass o miglioramento prestazionale. Per l'esecuzione nel gioco serve prima un meccanismo di caricamento consentito dai vincoli del progetto e un ripristino verificato. La sostituzione delle cache installate e la patch di DLL/driver restano escluse.
