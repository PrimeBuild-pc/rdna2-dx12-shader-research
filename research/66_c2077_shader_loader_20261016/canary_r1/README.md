# Canary r1 — VISUAL_GATE_NOT_PASSED_IN_TESTED_SCENE

Utente: «chiuso, immagine normale». Processi Cyberpunk assenti prima del cambio mode.
Control accettato dall'operatore come immagine normale: controllo qualitativo, non confronto
pixel quantitativo. Log finali archiviati in [control closed](../runtime_control_r1/closed/snapshot.json).
Ultimo heartbeat control: 5360 init DX12, 5 match/PSO create, zero errori di clonazione,
1044 bind target. Non esiste evento finale unloaded per il ciclo D3D12 attivo; non dedurre
un lifecycle GPU completo o un exit code da questo heartbeat.

Il log host finale contiene i WARN già conservati: IDXGIFactory2 reference count (4)
allo startup, IDXGISwapChain4 reference count (1) in chiusura e add-on ancora caricati
con avviso di possibile crash in uscita. Termina con `Finished exiting`; processo assente.
Non è stata dimostrata la causa dei WARN né certificata l'assenza di crash tramite exit code.
Non equiparare questi WARN al contatore di errori di clonazione, che resta zero.

Impostato **solo** `bin/x64/C2077ShaderLab/mode.txt` a `canary`, con CLI già prevista.
DLL host/add-on agli hash invariati, EXE verificato dalla CLI; nessun nuovo build o cambio
bytecode. Aggiornato il manifest di deployment, non il pacchetto installazione congelato.
Comando e controlli: [mode_command.json](mode_command.json), [preparation.json](preparation.json).

## Prossima azione

Avvio manuale concluso, PID 14612 chiuso: 5 PSO canary, ultimo heartbeat 2033 bind,
zero errori di clonazione; [risultato negativo e snapshot](RESULT.md). L'utente non vede alcun
cambio rosa/fucsia. Non reinterpretare i bind come successo visivo. Ora è installata solo una
sonda osservativa aggiuntiva: [fase 67](../../67_c2077_canary_probe_20261016/STATUS.md).
Niente benchmark o cambi di qualità; seguire la fase 67 per il prossimo avvio mirato.

Leggere **nuovi** log con nuovo PID e `mode=canary`, non riusare il PID 5396 del control.
Servono clone/bind positivi senza errori e riscontro visivo. Zero marker resta risultato
negativo/inconclusivo, non prova di uso visibile dello shader. Nessuno speedup misurato.
Dopo la verifica, ritorno a control/observe o rimozione, solo a processo chiuso.
