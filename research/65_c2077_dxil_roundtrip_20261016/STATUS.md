# Cyberpunk — round-trip e prima canary DXIL

**Experiment ID:** `C2077-DXIL-CANARY-001` · **2026-10-16**  
**Stato:** **PASS_OFFLINE**. Bytecode modificato e validato; **non applicato al gioco**.

## Risultato concreto

È stata costruita una prima variante del pixel shader del materiale **glass**, pass `renderstage_transparent`, MeshStatic/Discarded, PassIndex 0. La provenienza è nei record di compilazione della cache, non dedotta dal filename.

La canary cambia **soltanto quattro operandi**, l'RGBA del render target 0, in **(1,0,1,1)**. Discard, risorse, cbuffer, altre istruzioni e target 1 restano invariati. È un marker diagnostico, **non un'ottimizzazione né un'immagine corretta per produzione**. Blending/postprocessing possono alterare il colore finale.

- GUID shader: `15973390170752892218`.
- Originale: [glass_original.dxil](glass_original.dxil), SHA-256 `c8755b8ac5d61f208d02e0fda1c3bbed2c7e0a15f59c9edbb0f8c559925828b9`.
- Canary: [r1/glass_canary.dxil](r1/glass_canary.dxil), **23050 byte**, SHA-256 `9da6f87440e40e8d42a4f6bc2afba073a6675d0ddffec91805426142a4e085db`.
- [Preregistrazione](PREREGISTRATION.md), [risultati e diff esatto](r1/result.json), [IR canary](r1/glass_canary.ll).

Non è dimostrato che questo shader sia attivo o costoso nel benchmark. È un bersaglio applicativo identificato per verificare in futuro il percorso di sostituzione.

## Round-trip e validazione reale

Usati `IDxcAssembler`, `IDxcContainerBuilder` e il **validatore esterno Microsoft dxil.dll**, flags default, mai `-Vd`. SDK già installato, firme Microsoft valide e hash fissati in [toolchain_signatures.json](toolchain_signatures.json). Nessuna DLL modificata o installata.

| Controllo | Originale byte | Ricostruito byte | IR LLVM | Interfaccia SFI0/ISG1/OSG1/PSV0 |
|---|---:|---:|---|---|
| Pixel iniziale | 5702 | 5642 | Identico | Identica |
| Compute iniziale | 6864 | 6788 | Identico | Identica |
| Glass selezionato | 23102 | 23042 | Identico | Identica |

IR confrontato per l'intero modulo, metadata inclusi, normalizzando soltanto i terminatori di riga. Il bytecode **non** è bit-identico: il serializer produce bitcode/digest diversi, anche a IR identico. La correttezza dell'immagine e l'accettazione del driver/gioco non si deducono automaticamente da questo confronto.

L'assembler aggiungeva una parte `STAT` assente dagli originali: rimossa esplicitamente tramite ContainerBuilder. Il tentativo CLI `-Qstrip_reflect` non l'aveva rimossa e non è usato nel risultato finale. Il builder emette un warning di firma sul contenitore intermedio; **dopo** la serializzazione viene eseguita la validazione esterna, ottenendo output con digest DXIL non nullo e seconda validazione riuscita. Non è firma Authenticode di un driver.

### Controlli negativi eseguiti

1. IR sintatticamente errato: rifiutato, nessun output accettato.
2. Opcode DXIL **999**: assembler capace di produrre il contenitore, ma **validatore esterno lo respinge** con `validation_status_hresult=0x80aa0009` e messaggio `DXILOpCode must be [0..258]`. Quindi non stiamo usando una validazione fittizia.
3. Tentativo di sovrascrittura di un output: rifiutato; hash del file già esistente invariato.

Complessivamente **21 subprocess registrati** nel runner, inclusi i negativi attesi; selfcheck del parser/repacker e della trasformazione PASS.

## Repacking provato, solo su copie di ricerca

Il parser del main `shader_final.cache` RDHS v10 attraversa **19037 shader** e **19647 record di compilazione**, con sentinelle, bounds e sezioni verificati.

- Sostituzione no-op del payload originale: cache **byte-identica** all'input.
- Copia con controllo ricostruito e copia con canary: rilette correttamente; **19036 altri payload identici**, GUID/parametri e metadata di compilazione invariati.
- Aggiornati soltanto size del record e size/offset noti del footer; campi ignoti conservati, non trattati come checksum conosciuti.
- [r1/shader_final.control.offline.cache](r1/shader_final.control.offline.cache) e [r1/shader_final.canary.offline.cache](r1/shader_final.canary.offline.cache) sono **artefatti offline, non un pacchetto da installare**. Accettazione dei campi/hash interni da parte del gioco non verificata.
- Cache installata e copie originali ancora con hash di settembre. Nessun file installato modificato, nessun avvio del gioco, nessun benchmark.

### Correzione importante al reader di riferimento

I nomi `PixelShader` / `VertexShader` del reader WolvenKit non coincidono con i token DXIL di questa cache: lo slot A è vertex in tutti i 19647 record; lo slot B è pixel in 17083 e zero in 2564. Il nostro parser usa nomi neutrali A/B e conferma lo stage leggendo il bytecode. Vedere [cache_metadata_validation.json](cache_metadata_validation.json). Il primo mapping basato sulle etichette upstream è conservato come `target_cache_mapping_upstream_labels_unverified.json`, **non** come associazione valida.

## Meccanismo nel gioco: limite e decisione necessaria

Non è stata trovata, nelle fonti verificate, una funzione REDmod documentata che carichi questo DXIL arbitrario. La documentazione REDmod descrive archivi, script, tweak e audio; le pagine “shader” sui `.mt` descrivono materiali e parametri, non provano sostituzione del programma DXIL. Questo non è una prova universale di impossibilità.

Il vincolo permanente del progetto esclude la sostituzione delle cache installate: **non è stata usata come scorciatoia**.

È stato individuato un **possibile percorso alternativo**: un loader DX12/add-on tramite ReShade/RenoDX, capace di sostituire shader senza patchare il driver o i file cache. La fonte RenoDX dichiara shader replacement e usa l'add-on system di ReShade; il codice include il percorso D3D12. **Nessuna compatibilità Cyberpunk già provata, nessun loader scaricato/installato/eseguito, bundle non ancora revisionato per l'installazione**.

La prossima azione runtime richiede quindi **autorizzazione specifica al loader/hooking nel solo processo Cyberpunk**, revisione della versione esatta, manifest dei soli nuovi file, rimozione verificabile e guardia sul bytecode originale. Mai Fortnite/Warzone, mai driver/Registry/boot. Prima si prova il controllo non modificato, poi la canary e il contatore di hit; una scena normale avviata manualmente può bastare, **nessun benchmark automatico**.

**Gate di ottimizzazione:** solo dopo aver verificato che il gioco utilizzi la variante si passa a una trasformazione semanticamente corretta e a misure A/B. Nessuno speedup affermato da questa canary.

## Riproduzione

```text
research\65_c2077_dxil_roundtrip_20261016\build.cmd
python -B tools/c2077_shader_cache.py
python -B tools/c2077_shader_experiment.py --selfcheck
python -B tools/c2077_shader_experiment.py research/65_c2077_dxil_roundtrip_20261016/NUOVA_RUN
```

Il runner rifiuta una directory già esistente e output esterni a questa fase. Ogni comando positivo usa il recorder già presente `buildv.run_checked`; i negativi registrano comando/exit e verificano che non sia rimasto un output accettato. Per altre cache/versioni il formato deve essere verificato di nuovo; lo static cache non è supportato dal repacker.

## Fonti

- SDK Windows locale `dxcapi.h`: contratti `IDxcAssembler`, `IDxcContainerBuilder`, `IDxcValidator`; header e DLL già installati, nessun codice di loader online eseguito.
- [WolvenKit reader](sources/ShaderCacheReader.cs) e [layout](sources/ShaderStructs.cs), snapshot/hash in [provenance](sources/provenance.json). Usati come riferimento e verificati contro i bytes, non compilati/eseguiti.
- [REDmod deploy](sources/redmod_deploy.md), [shader/material docs](sources/modding_shaders_readme.md), provenienza salvata in `sources/*provenance.json`.
- [RenoDX README](sources/renodx_README.md) e sorgente shader come sola evidenza di fattibilità del percorso add-on; [provenienza](sources/renodx_provenance.json). Non è una raccomandazione di installare automaticamente un binario.
