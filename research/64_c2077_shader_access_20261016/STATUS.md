# Cyberpunk — accesso concreto agli shader, 2026-10-16

**Direzione:** esperimenti su shader applicativi reali; nessuna modifica ai driver firmati.
Lorenzo chiede di passare a tentativi concreti e reversibili. Il precedente vincolo di non avviare nuovi benchmark resta rispettato.

**Avanzamento successivo:** [fase 65 — round-trip e canary](../65_c2077_dxil_roundtrip_20261016/STATUS.md). Tre shader ricostruiti con IR identico e validazione esterna; creata una canary `glass` con quattro operandi modificati e repacking solo su copie. Il prossimo gate è il loader/runtime autorizzato, non ripetere questa estrazione. Le attività elencate sotto descrivono il punto di partenza storico.

## Fatto

1. SHA-256 dei due contenitori installati verificati **prima** dell'analisi e della copia; coincidono con l'inventario del 7 settembre.
2. Copie locali in `copies/`, hash identici; tutta l'analisi binaria è sulle copie.
3. Inventariati **19950 contenitori DXBC con chunk DXIL**, con framing/chunk/bounds verificati:
   - `shader_final.cache`: 19037;
   - `staticshader_final.cache`: 913.
4. Per stage: **5238 pixel**, **13983 vertex**, **661 compute**, **68 library**. Sono occorrenze, non necessariamente shader unici o attivi nel benchmark. Modelli 6.0 / 6.2 / 6.3 / 6.5.
5. Estratto un contenitore per ciascuno dei quattro stage presenti, con offset, size e SHA-256. **Un pixel e un compute sono stati disassemblati correttamente dal DXC già installato**, exit 0 e stderr vuoto. IR reale disponibile in `extracted/*.ll`.

Non è una nuova ricerca per filename: i contenitori sono stati effettivamente letti e due payload riconosciuti da DXC.

## Evidenze

- `probe_containers.py`: probe riproducibile, test sintetici su framing valido/troncato/offset errato; rifiuta di sovrascrivere risultati.
- `probe_results.json`: hash, offset e framing di tutte le occorrenze.
- `extraction.json`: stage, provenance dei quattro bytecode estratti, comando/exit/hash DXC.
- `extracted/`: bytecode e disassembly del pixel/compute; nessuno applicato al gioco.

Hash dei contenitori originali/copie:

```text
shader_final.cache        339145371a3b5aaa08eb4ef82d558f445b632e28603ee0f3b4860270dfc3ccfa
staticshader_final.cache  bff160947aba8df144200247adc39b44c26322360628d875f7c7218ad26c59ff
```

## Prossimo esperimento concreto

**Prima rendere dimostrabile una modifica al bytecode, poi attribuirle un effetto nel gioco.**

1. Round-trip offline di uno dei bytecode estratti: ricostruzione/validazione senza cambiare semantica; non chiamare un semplice dump “recompilazione riuscita”.
2. Individuare un meccanismo applicativo di sostituzione realmente supportato e reversibile. Attualmente **non ancora dimostrato**: estrarre DXIL non prova che il gioco accetti un contenitore ricostruito. Non sostituire cache installate o DLL/driver per supposizione.
3. Una sola canary/variante identificabile, con originale/hash/ripristino e riscontro che il gioco stia usando proprio quella. Poi un'ipotesi piccola di ottimizzazione sull'IR reale, con oracle dell'immagine.
4. Misure runtime/A-B solo quando si riapre esplicitamente la fase di test. Nessun guadagno promesso prima di averlo misurato.

Non assegnare nomi di pass o un costo ai primi shader estratti: mancano ancora mapping runtime e timing. Le copie sono materiale di lavoro, **non una variante di gioco pronta da installare**. La modifica minima può essere anche un esperimento negativo documentato, senza dover trovare per forza uno speedup.
