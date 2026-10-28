# Autonomous session report — 2026-09-05

**Esito: audit completato, autonomia fermata al gate iniziale.**

Audit completo e piano 2O in massimo 8 passi: [CODEX_HANDOFF_AUDIT.md](CODEX_HANDOFF_AUDIT.md). Evidenze: [handoff_audit_20260905/](handoff_audit_20260905/). Registro: [AUTONOMOUS_LOG.md](AUTONOMOUS_LOG.md).

## Cosa è stato fatto

- Ricostruita la storia Phase 1–2N dando precedenza alle falsificazioni più recenti.
- Verificati macchina, toolchain, repository reali in `%TEMP%`, commit, modifiche locali e artefatti generati.
- Ispezionati harness, correttezza, build, MiniEngine, inventario e integrazione GPA.
- Ricalcolato offline il raccordo inventario storico/header: **40/40 associazioni**, ModelViewerPS **12.612 byte**, hash `52CE6C5E64AB2E82`.
- Salvati inventario, SHA-256, diff Git e tlog decodificati; aggiornato `PLAN.md` senza riscrivere i risultati storici.

## Perché l'esecuzione automatica è stata fermata

1. **Build non affidabilmente verificata:** `buildv.py` ignora l'exit code e non boccia sempre un header assente; i runner continuano a usare la build legacy. Manca la dimostrazione nuova sorgente → bytecode → PSO eseguito.
2. **GPA multipass non validato:** 13 passate su frame successivi con stato temporale variabile. Timestep fisso non garantisce workload identico come richiesto dal SDK.
3. **Conclusione hardware eccessiva:** 4,15 milioni di `PSPixelsOut` sono export verso due MRT, non prova di 2× overdraw; TexUnitBusy 94,6% non prova da solo saturazione del filtro né esclude ALU/latency.
4. **Discrepanza ulteriore 2K:** best/oracle premiano anche varianti scartate per correttezza. Il vantaggio “2.5×” va ricalcolato, non assunto come verificato.

Sono condizioni di stop previste dal brief, non ragioni per proseguire comunque con sei tentativi. Il problema di tracking DXC resta da diagnosticare: il tlog degli output è vuoto di percorsi, ma la root cause “timestamp grossolani” non è stata confermata.

## Stato delle ipotesi

| Ipotesi | Verdetto alla chiusura |
|---|---|
| Render Color è un bersaglio hot e usa ModelViewerPS | Supportata dal profiling storico e mapping ricontrollato offline |
| Il limite dominante è il throughput di filtraggio texture | **Non confermata né falsificata**; richiede 2O valida |
| L'ALU è esclusa indipendentemente dalle ablazioni | Non supportata dalle prove disponibili |
| Il readback immagine è rotto | La vecchia prova è ritirata; oracolo ancora da validare con canary runtime |
| La build verificata è già riparata/integrata | Smentito dall'audit del codice corrente |

## Budget e confini

**0/6 cicli GPU, 0 build, 0 benchmark, 0 varianti applicate.** Nessuna nuova misura di tempo, counter, varianza o qualità immagine. Nessuna modifica a sorgenti MiniEngine, script operativi, driver, cache, Registry o sicurezza; nessuna cancellazione, gioco protetto o chiusura di applicazioni personali.

Phase 2O: piano preregistrato ma sospeso. Phase 2P: **non implementata; progettazione successiva rinviata finché 2O non produce evidenza valida**.

## NEXT RECOMMENDED ACTION

Riparare e validare il gate condiviso sorgente → bytecode → PSO runtime con una canary su output nuovi e non distruttivi, prima di raccogliere altri tempi o counter.
