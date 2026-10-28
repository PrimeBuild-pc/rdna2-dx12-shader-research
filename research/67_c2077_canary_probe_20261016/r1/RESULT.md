# Probe r1 — PARTIAL, TARGET_NOT_BOUND_IN_OBSERVED_COMMANDS

Nuovo avvio manuale, PID **11348**, mode canary. Sonda e ShaderLab inizializzati;
primo breve ciclo D3D11 unloaded distinto dal successivo ciclo D3D12 attivo.
Copie live a lunghezza fissata: [snapshots.json](snapshots.json).

Prima copia: 5445 init, 4 PSO target note, **0 bind target**, nessun draw/indirect/bundle
attribuito al target né submission con lavoro target. Callback draw globali e submission
presenti in quantità: la sonda riceve eventi, ma ciò non certifica copertura completa.
Non calcolare FPS dai contatori. Snapshot e controllo più tardo in
[partial_analysis.json](partial_analysis.json), [status_after_metadata_review.json](status_after_metadata_review.json).
Il controllo più tardo è ancora a zero bind target.

## Stato PSO effettivamente osservato

Quattro PSO create, non ancora viste bindate nella sessione:

- RT count 1 o 3; RT0 R16G16B16A16_FLOAT oppure R11G11B10_FLOAT;
- RGB write mask RT0 **0xF**, sorgente RGB **one**, operazione **add**;
- destinazione RGB **source1_color**, cioè dual-source blending;
- depth test attivo, depth write disabilitato.

Decodifica verificata con gli enum SDK fissati. Per queste quattro PSO sono contraddette
le ipotesi specifiche RT0 inesistente/RGB mask zero/fattore sorgente zero. Non è esclusa
occlusione/discard/compositing né ricostruita la quinta PSO bindata nelle run precedenti.
I due output SV_Target0/1 non dimostrano due render target indipendenti: source1_color
usa il secondo output come fattore di blend. Non confondere output shader e RT attivi.

## Prossima osservazione

Richiesto all'utente di restare nella stessa sessione, tornare in partita non in pausa e
girare brevemente la visuale nella stessa zona per 10–15 s, poi comunicare «fatto».
Nessun riavvio/benchmark o ricerca casuale di nuove canary. Serve prima registrare il caso
con bind target per discriminare draw/submission e stato colore corrispondente.

Causa del precedente marker assente **non identificata**. Nessuna modifica live a mode,
DLL o shader. Non dichiarare che il target non sia mai eseguito sulla GPU sulla sola base
di zero counter CPU; risultato limitato ai comandi osservati in questa sessione.

## Dopo il giro e chiusura

Utente «fatto», poi gioco chiuso verificato. [Snapshot dopo giro](after_view/result.json):
5907 init, quattro PSO note, zero bind/draw/lavoro target osservati; gli altri contatori
sono callback CPU, non misure GPU/FPS. [Log finali](closed/snapshots.json).
Nessun ulteriore giro richiesto. Causa della vecchia canary non stabilita; il caso con bind
precedentemente osservato non è stato riprodotto nella presente scena.
Sonda specifica archiviata/rimossa, ShaderLab observe, nuovo catalogo readonly della
[fase 68](../../68_c2077_backbuffer_catalog_20261016/STATUS.md) installato a processo chiuso.
