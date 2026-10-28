# Canary r1 — CANARY_PSO_ACCEPT_BIND_CONFIRMED, VISUAL_PENDING

Avvio manuale utente, comunicazione «pronto», PID attuale **14612**, EXE atteso.
Non riutilizzati i log del control PID 5396. Nessun avvio/benchmark/cattura GPU dell'agente.

Copie a lunghezza fissata dei log live in [live_snapshot_1/snapshots.json](live_snapshot_1/snapshots.json).
[Verifica](live_snapshot_1/verification.json):

- guard EXE passato, mode **canary**;
- **5239** callback init DX12;
- **5** match bytecode originale e **5** cloni PSO creati;
- **0** errori di clonazione;
- **544** bind target, evento first_target_bind presente;
- **31436** callback present, non frame/FPS validati;
- hash DLL host/add-on identici al pacchetto congelato;
- nessun ERROR nel log host copiato, un WARN IDXGIFactory2 reference count (4) allo startup.

Il primo breve ciclo add-on nello stesso PID termina unloaded con contatori zero;
è separato dal secondo ciclo D3D12 attivo, come nel control. Non fondere i cicli.

Provati riconoscimento originale, scelta della variante canary, creazione PSO e invocazione
del bind rediretto. **Marker visivo non ancora riferito dall'utente né catturato.**
Questo non prova da solo draw/frammenti visibili, completamento GPU o un guadagno prestazionale.
Richiesto all'operatore se nella scena vede vetri/superfici rosa-fucsia. Lasciato mode canary
invariato durante il processo attivo; nessuna modifica a DLL, cache o impostazioni grafiche.
Dopo risposta/riscontro, chiusura manuale prima di ritorno a control/observe o rimozione.

## Riscontro negativo e chiusura

L'utente riferisce «no, nessuna superficie rosa rispetto a prima. immagine invariata».
**Gate visivo non superato nella scena provata.** [Negativo preservato](negative_snapshot/report.json).
PID 14612 poi chiuso; [log finali](closed/snapshots.json), ultimo heartbeat 7883 init,
5 cloni, zero errori clonazione, 2033 bind. I controlli statici in `diagnosis/` confermano
payload corretto/distinto e incorporato, non il frame finale. Causa non stabilita.
A processo chiuso è stata aggiunta una sola sonda osservativa senza cambiare shader o mode;
[prossimo esperimento fase 67](../../67_c2077_canary_probe_20261016/STATUS.md).
