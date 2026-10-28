# Artefatti offline — 16 ottobre 2026

Report canonico: [OFFLINE_ATTRIBUTION_20261016.md](../../OFFLINE_ATTRIBUTION_20261016.md).
Nessuna cattura nuova: tutti gli input sono le acquisizioni storiche di settembre.

## Usare questi risultati

- `events_v2.tsv`, `events_v2.schemas.tsv`, `extract_v2.log`: estrazione canonica raw QPC / TDH. `status=0`, zero errori sulle proprietà.
- `analysis/`: CPU, scheduler, clock e controlli correnti.
- **Solo `analysis/gpu/`**: replay GPU corretto e validato.
- `cpu_profile.txt`, `cpu_cswitch.txt`, `dpc_isr.txt`: report nativi sulla finestra benchmark.
- `stacks_CSwitch.txt`, `stacks_ReadyThread.txt`: HTML nativi con stack precisi realmente utilizzabili.
- `analysis/broad_profile_not_validated_cpu_sampling_*`: **diagnostica, non caller/costi CPU sampled validati**.
- `verification.log`, `analysis/*validation.json`, `artifact_manifest.json`: verifiche e hash.
- `*.command.json`, `build_reader.cmd`, `build_reader_v2.log`: comandi e provenienza del reader.
- `symbol_provenance.json`, `symbols/`, `symcache/`: PDB pubblici corrispondenti alla traccia, cache solo locale al progetto.
- `sources/`: testo di riferimento Intel PresentMon, commit `e13fce6acdb55a808fd8318175a56863e532d95f`; non eseguito.

`schema_probe.txt` è un dump xperf dei primi 200 ms: solo validazione di decoder/orologio, non un benchmark. `stack_diagnostic_smoke/` rilegge offline lo smoke storico: anche senza filtro PID, SampledProfile/SampleProf/PerfInfo non producono stack utilizzabili. Non attribuirne i risultati alla finestra del benchmark.

## Tentativi conservati ma NON validi come risultati

- `events.tsv` / `extract.log`: reader preliminare, sostituito da v2 con metadati dei thread e probe indipendente.
- `analysis_failed_image_metadata/`: parsing interrotto su un opcode Image non Load; non completato.
- `analysis/gpu_failed_array_context/`: parsing interrotto; gli eventi di signal possono contenere un array di context.
- `analysis/gpu_superseded_wait_pointer_lifetime/` e `analysis/gpu_superseded_scalar_array_enum/`: replay intermedi **scartati**; inversione WAIT/SIGNAL e join di puntatore non validato. Non usare le loro classificazioni o latenze.
- `analysis/rejected_profile_filter/`: prime etichette “sampled” respinte nell'audit del filtro `Profile`; non prove CPU sampled.
- `pm_relative*`, `pm251_relative*`: replay PresentMon che non ha prodotto un CSV valido. Exit 0 non è sufficiente.

La copia ufficiale `PresentMon-2.5.1-x64.exe` è stata verificata tramite digest della release e firma Intel valida; non installata e usata soltanto con `--etl_file`. La versione installata era nel frattempo diventata 2.6.0. Nessuna sessione live avviata o fermata.
