# Control r1 — PSO acceptance and binding confirmed

Avvio manuale utente dopo installazione; utente comunica «pronto». PID attuale **5396**,
percorso EXE atteso, mode **control**. Nessun avvio o benchmark automatico dell'agente.

Snapshot di ricerca read-only, a lunghezza fissata prima della lettura, da log ancora aperti:
[snapshots.json](snapshots.json). Sono copie parziali live, non log definitivi della sessione.
[status.json](status.json) registra lo stato letto subito dopo lo snapshot.

## Risultati osservati

Log attivo `runtime-5396-134366570938610954.jsonl`:

- `loaded_exe_guard_pass` presente;
- **5316** init pipeline DX12 osservate;
- **5** match sul bytecode originale esatto;
- **5** PSO control create con successo;
- **0** errori di clonazione;
- **406** bind target, dopo il primo evento `first_target_bind`;
- **60230** callback present: contatore di chiamate, **non FPS o numero di frame validato**.

La prima lettura del turno era ancora a 4 cloni/0 bind; durante il controllo dei log
sono comparsi il quinto clone e i bind. Il precedente zero non viene dichiarato un bug.

Il primo piccolo log dello stesso PID termina `unloaded` con tutti i contatori a zero.
ReShade.log mostra inizializzazione D3D11 transiente, unload dell'add-on e successivo
reload alla creazione del device D3D12. Il secondo log è quello attivo con le evidenze sopra.
Nessuna fusione artificiale dei due cicli di vita.

Host caricato dal proxy previsto, SDK API 20, GPU RX 6950 XT, runtime ReShade con configurazione
propria, swapchain 2560x1440. Nel log host c'è **un WARN su reference count IDXGIFactory2
inconsistente (4)** durante startup; nessun ERROR nel campione. Il WARN è conservato e non
attribuito a una causa non dimostrata; zero errori riguarda il contatore di clonazione.

## Verdetto e limite

**CONTROL_PSO_ACCEPT_BIND_CONFIRMED — VISUAL_CONFIRMATION_PENDING.**

Provati caricamento add-on, guard EXE, riconoscimento del bytecode, creazione della PSO
control e invocazione del bind rediretto. Questo **non** prova completamento GPU, draw,
frammenti visibili, correttezza pixel o costo del pass. Nessun guadagno di performance.

Richiesto all'utente di confermare immagine normale e chiudere il gioco. Solo dopo tale
conferma e verifica del processo chiuso, attivare canary per un nuovo avvio manuale nella
stessa scena. Non modificare mode/DLL a processo aperto. Nessuna nuova cattura ETW/PresentMon.

## Aggiornamento dopo chiusura

L'utente conferma «chiuso, immagine normale». Processo assente verificato, archiviati i
[log finali](closed/snapshot.json): ultimo heartbeat 5360 init, 5 match/cloni, zero errori
clonazione e 1044 bind. Riscontro visivo qualitativo accettato, non equivalenza pixel.
Il log D3D12 non termina con unloaded; i WARN host in uscita restano conservati e non
risolti causalmente. Mode canary impostata a processo chiuso senza cambiare i binari;
[preparazione canary](../canary_r1/preparation.json). Nessun avvio automatico.
