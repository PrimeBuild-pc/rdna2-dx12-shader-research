# CODEX HANDOFF AUDIT — 2026-09-05

## Decisione: STOP prima della Phase 2O sperimentale

**Audit documentale/statico completato; 0 build, 0 benchmark, 0 cicli GPU.** Sono emerse discrepanze critiche nella catena di build e nella validità/interpretazione GPA. Si applicano le condizioni di arresto del brief: non è autorizzato ignorarle per completare sei cicli. La Phase 2O è progettata sotto, non eseguita; la 2P non è implementata né avviata.

Il bersaglio `Render Color → ModelViewerPS` resta fondato. **“Texture-unit throughput bound, ALU esclusa” torna a essere un'ipotesi, non una conclusione confermata.** Questo audit non dimostra che l'ipotesi sia falsa: dimostra che le prove finora usate non bastano.

### Evidenza nuova bloccante

| ID | Finding | Confidenza / conseguenza |
|---|---|---|
| A01 | `buildv.build()` non controlla `returncode`; cerca solo la stringa `error` nell'output. `shader_hash()` restituisce `MANCANTE`, che non causa automaticamente fallimento. | **confirmed**, da sorgente. Può restituire successo senza un artefatto valido. Non è un gate fail-closed. |
| A02 | `ab2l.py`, `ab2m.py`, `gpa2n.py` continuano a usare la build legacy, non `buildv`. Nessun confronto obbligatorio sorgente → bytecode → hash del PSO osservato nel nuovo processo. | **confirmed**. La presenza del wrapper non equivale alla riparazione della pipeline. |
| A03 | GPA raccoglie 31 counter su 13 frame successivi; il SDK richiede lo stesso workload in tutte le passate. Il frame avanza, TAA/jitter e stato temporale sono attivi; non esiste replay congelato. | **confirmed** per l'assenza del requisito. Entità dell'errore numerico **non misurata**. I counter storici non autorizzano un verdetto causale. |
| A04 | `PSPixelsOut` conta export per render target. Lo shader scrive `SV_Target0` e `SV_Target1`. 4.147.204 export ≈ 2×1920×1080 non dimostrano 2× overdraw. | **confirmed**: definizione nel CSV enumerato e nella documentazione SDK. La precedente inferenza di overdraw è ritirata. |
| A05 | `TexUnitBusy` include fetch, cache e memoria: “busy” non prova emissione al massimo throughput di filtraggio. Manca una misura PS ALU/occupancy capace di escludere le alternative. | **confirmed** per semantica e copertura; classificazione hardware precedente **non confermata**. |
| A06 | `measure2k.evaluate().stats()` e `oracle` includono i delta di varianti `SCARTATA` nel miglior risultato. La memoria kNN usa anche i loro delta come rendimento. | **confirmed**. Il numero 2.5× di 2K va ricalcolato con reward correctness-aware; non è una stima validata del risparmio per ottimizzazioni accettabili. |

## 1. Ambito, metodo e preservazione

Lettura di `CLAUDE.md`, `PLAN.md`, report di ricerca da Phase 1 a 2N, dati CSV/JSON e codice dei percorsi rilevanti; confronto Git locale con HEAD upstream dei due clone, inventario filesystem, versioni live, hash degli artefatti, decodifica dei log MSBuild già presenti. Nessun fetch, checkout, reset, clean, installazione di dipendenze, compilazione o avvio del workload.

I risultati più recenti che falsificano quelli vecchi prevalgono. I vecchi report sono conservati, non riscritti: questo documento e l'avviso in `PLAN.md` costituiscono l'errata corrente. “Confirmed” in questo audit significa verificato nel sorgente/dato/documento indicato, **non** nuova riproduzione GPU delle performance storiche.

Evidenze salvate in [`handoff_audit_20260905/`](handoff_audit_20260905/):

- `file_inventory.csv`, `inventory_summary.json`: inventario completo dei file esistenti nelle aree enumerate, con dimensioni e mtime; non una lettura integrale di ogni file vendor.
- `dxs_git.txt`, `dxs_diff.patch`, `ffx_git.txt`, `ffx_diff.patch`: commit, remote, modifiche tracked/untracked/ignored e diff locale rispetto al commit upstream già disponibile; **non** confronto con l'ultimo HEAD remoto.
- `artifact_hashes.csv`: SHA-256 completo di strumenti/sorgenti/report selezionati, header e binari attuali. Identifica lo stato attuale, non certifica retroattivamente quale binario girasse in ogni run storico.
- `dxc.command.txt`, `dxc.read.txt`, `dxc.write.txt`: copie UTF-8 dei tlog UTF-16 di Model.
- `environment_inventory.json`: inventario live del 2026-09-05 16:40:31 +02:00.

Le sole scritture della sessione riguardano questi output di audit, i report richiesti e `PLAN.md`. Nessun file eliminato, nessuna modifica a driver/cache/Registry/security, nessuna applicazione personale chiusa, nessun gioco protetto aperto. Nessuna analisi binaria nuova: i binari attuali sono stati soltanto identificati tramite hash/versione. I sorgenti MiniEngine e gli script operativi non sono stati modificati.

## 2. Stato reale di macchina, toolchain e repository

### Macchina e strumenti

| Elemento | Verifica corrente |
|---|---|
| GPU | RX 6950 XT, PCI `VEN_1002&DEV_73A5`, Navi21/RDNA2 |
| Driver **installato** | **32.0.21045.5002** |
| Package conservato nel progetto | **32.0.21045.9003**, distinto dall'installato; evidenza storica INF/inventory |
| CPU / RAM | Ryzen 7 5800X3D / circa 32 GiB; X570 da inventario storico |
| OS | Windows 11 Pro 10.0.26200 |
| MSBuild | VS18 Community, `18.9.1.35102`, `.../MSBuild/Current/Bin/MSBuild.exe` |
| C++ | directory toolchain installata `14.51.36231`; script richiedono `PlatformToolset=v145` |
| DXC Windows SDK | SDK `10.0.26100.0/x64/dxc.exe`, file version `1.8.2502.11` |
| GPUPerfAPI | `%TEMP%/claude/gpa/4_4`, DLL `4.4.0.5`; la denominazione “4.4.5” dei report non è la file version |
| Python | Python311 locale, pandas/numpy/scipy già disponibili; nessuna nuova dipendenza |
| PresentMon | CLI 2.5.1 nel percorso documentato; servizio presente nello snapshot, non avviato/fermato dall'audit |
| AMD tools | RGP/RGA/RDS/RMV/RRA e CLI `rga.exe` nella directory suite **annidata due volte** `RadeonDeveloperToolSuite-2026-05-28-1806/...` |
| Spazio libero | C: ~163 GB, E: ~242 GB al momento dell'inventario |

Non confondere il DXC del Windows SDK con quello distribuito dentro RGA. I tlog registrano gli argomenti DXC, non il percorso/hash del compiler che fu effettivamente eseguito: l'identità completa del compilatore è ancora un requisito per la prossima build verificata.

Lo snapshot per nomi browser/Discord/player/giochi/encoder ha trovato soltanto `PresentMonService`. **Non è una misura di idle CPU/GPU**, né un controllo continuo di clock/termica. Nessun ambiente “pulito” viene certificato per un benchmark che non è stato eseguito.

### Layout effettivo

La root non è un repository Git. Parti essenziali vivono in `%TEMP%`, non nel progetto:

| Area | Posizione | File / dimensione enumerati |
|---|---|---|
| Progetto | `C:/Users/Lorenzo/Downloads/driver mod` | 4.821 / ~5.397 MiB |
| Microsoft DXS | `%TEMP%/claude/src/dxs` | 4.394 / ~3.244 MiB |
| FidelityFX | `%TEMP%/claude/src/ffx` | 470 / ~7,43 MiB |
| GPA | `%TEMP%/claude/gpa` | 183 / ~20,45 MiB |
| Run/backup MiniEngine | `%TEMP%/claude/l2` | 60 / ~237,42 MiB |

Conteggi rilevati prima di completare gli output di questo audit. `%TEMP%` è un rischio di conservazione: non effettuare cleanup. La root contiene package AMD, suite strumenti, Ghidra, Procmon e Sigcheck; `research/` conserva le fasi 00–23 e `tools/` i driver Python/PowerShell/shell. Wukong era bloccato per mancata installazione nei documenti; non è stato cercato né lanciato durante questo audit. Il workload autorizzato dal brief corrente è l'app open-source controllata MiniEngine.

### Microsoft DirectX-Graphics-Samples

Remote `https://github.com/microsoft/DirectX-Graphics-Samples.git`; HEAD **`213dd4fd4918ea009dd8f35adee1aff1f2ecaba4`**, commit “Add ASD Runtime doc and update readme (#969)”. Clone sparse/partial; nessun aggiornamento remoto eseguito.

Dieci file tracked modificati rispetto a HEAD, **177 inserimenti / 3 rimozioni**:

- `Core/BitonicSort.cpp`: scope dedicato di timing.
- `Core/CommandContext.{cpp,h}`: hook GPA e inventario draw/dispatch/PSO.
- `Core/Core.vcxproj`: include GPA assoluto e sorgenti di strumentazione.
- `Core/Display.cpp`: VSync disattivato in benchmark, timestep 1/60.
- `Core/EngineProfiling.{cpp,h}`: accumulo su tutti i frame, reset e dump CSV, hook degli scope.
- `Core/GameCore.cpp`: controllo benchmark via environment, inventario, GPA e readback del colore.
- `Core/PipelineState.{cpp,h}`: hash/size del bytecode VS/PS/CS in Finalize.

Untracked: `Core/GpaProfiler.{cpp,h}`, `Core/ShaderInventory.{cpp,h}`, due DLL GPA in `ModelViewer/`. Build, Packages e vcpkg sono ignored, non assenti. Nessuna modifica staged. **`Model/Shaders/ModelViewerPS.hlsl` e `Lighting.hlsli` coincidono attualmente con HEAD upstream.** Non c'è una variante shader attualmente attiva nel sorgente di questi due file.

### FidelityFX SDK

Remote `https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK.git`; HEAD **`60f4ea81909200d8542eca14dccb2628b763a9a3`**, “AMD FSR SDK 2.3.0”; sparse `*.hlsl`, `*.h`. Stato tracked/untracked pulito. È un corpus di shader reali, **non** un'app FidelityFX completa profilata end-to-end.

## 3. Storia ricostruita e verdetti che restano validi

| Fase / fonte primaria | Risultato e stato corrente |
|---|---|
| 1A/1B — inventory, driver map | Package diverso da installato; UMD DX12 e compilatore integrato identificati mediante INF/export/dependency, non filename. Non serve ripartire dalla decompilazione del driver. |
| 1E — `04_benchmarks/analysis/` | Parser PresentMon con definizioni di low/stutter e varianza. Steel Nomad ±0,11%, Fortnite ±1,3% sono baseline **storiche**, non soglie trasferibili a MiniEngine. |
| 1.5 / ETW — `08_etw_fortnite/RESULTS.md` | Il report finale supera i documenti “capture in attesa”: UMD CPU ~2,1% del percorso critico, ~0,03 ms/frame. Direzione UMD CPU Fortnite chiusa per scarso potenziale. ETL originali storicamente eliminati, CSV derivati conservati: riproducibilità limitata. |
| 2A–2E — `10_sc_probe/`, `11_compiler_experiments/`, `13_scoptions_static/` | Parser/config e dump shader funzionano; 272 `SCOption_*` non diventano automaticamente switch optimizer pubblici. Niente nuova pesca di nomi o Registry probing. |
| 2F–2G — microbench/optimizer | Primi guadagni non vanno letti come superiorità al default. La baseline e il duty cycle erano problematici. |
| 2H — `15_robustness/PHASE_2H_RESULTS.md` | Falsifica il “−30% oltre il default” di 2G: confronto contro `[unroll]` esplicito. Corregge inizializzazione SRV, warm-up a tempo, submission continua. Scheduling-load: evidenza storica strong, non nuovo counter proof. |
| 2I — `18_ai_search/best_variants.md` | 9/23 varianti accettate; `bdiv__hoist_parity` ~−69,5% strict su workload sintetico. Riduzione divergenza, non la prima ipotesi di parallelismo memoria. Null paired SE ~0,049%; niente generalizzazione a giochi. |
| 2J — `19_predictor/predictor_vs_random.md` | Guidato budget 2 contro random 8 (~4×), in quel corpus; memoria misurata prevale sulle euristiche. Non è speedup del frame. |
| 2K — `20_real/REAL_GENERALIZATION.md` | 58 shader misurabili, split 34/24, dati e dispatch sintetici. “2.5×” è ora **da ricalcolare** per A06; accettazioni per singola variante non sono automaticamente tutte annullate da questo bug di scoring. |
| 2L — `21_workload/PHASE_2L_RESULTS.md` | App Sponza costruita e profilata; shader molto veloci nel microbench spesso non eseguiti dall'app. “Zero gain end-to-end” non è prova universale: un sottoinsieme indeterminato delle A/B è coinvolto dal rebuild non verificato riconosciuto in 2N. |
| 2M — `22_runtime/PHASE_2M_RESULTS.md` | Mappatura per hash utile e ricontrollata offline. Ablazione “PS nero non cambia costo”, esclusione ALU e “nessuna ottimizzazione sorgente possibile” **non valide**. “Oracolo immagine rotto” è già ritirato da 2N; questo non significa oracolo validato. |
| 2N — `23_bottleneck/PHASE_2N_RESULTS.md` | 145 counter enumerati, CSV di 31 counter su scope. Build stale riconosciuta, controlli di ablazione non validamente conclusi. Classificazioni hardware da ridurre a ipotesi per A03–A05. “Niente ALU indipendentemente confermato” non regge. |

### Limiti nuovi del corpus e della correttezza

`bench.cpp` è il banco sintetico con input SRV deterministico, timestamp GPU e warm-up a tempo. `bench_selfcheck.py` è il precedente controllo da riutilizzare, non da saltare né eseguire ciecamente con i vecchi percorsi di output.

`bench2.cpp` sintetizza binding e risorse per shader arbitrari. Non ricostruisce lo stato dell'app: CB con pattern float generico non è uno schema di costanti tipato del workload; texture/UAV/counter condivisi non hanno un reset esplicito dello stato per ogni variante. “Dispatch pulito” nel commento della verifica non significa ripristino delle risorse dopo warm-up/misure. Il dump verifica un prefisso del buffer più una regione del primo subresource di una texture, non tutti gli output. `err_metrics()` reinterpreta tutto come float32, anche dati UINT; controlla presenza NaN/Inf, ma non distingue +Inf da −Inf. Un verdetto `strict` qui non equivale a correttezza semantica completa di HLSL arbitrario.

La differenza tra due esecuzioni dello stesso shader non prova da sola nondeterminismo **intrinseco** dello shader: aliasing delle risorse sintetiche, races, stato accumulato e input non rappresentativi vanno separati. Non usare tale etichetta per disabilitare il gate.

Verifica diretta del database 2K: 216 righe, 207 `valid=si`, 9 `no_workload_mismatch`; 27 righe `SCARTATA:fuori_tolleranza`. Fra le righe REAL_VALIDATION ancora `valid=si`, l'evaluator usa come rendimento anche:

- `AdaptExposureCS_main/all_unroll4`: **−3,282%**, scartata.
- `ParticlePreSortCS_main/all_unroll4`: **−34,008%**, scartata.
- `LinearizeDepthCS_main/wave32` e `wave64`: **+0,184% / +8,890%**, scartate.

`validation_results.csv` attribuisce infatti −34,01% a `mem_best_B1` di ParticlePreSort mentre `mem_hits_B1=0`. Le colonne hit usano `accepted=SI`; le colonne best/oracle no. È una discrepanza osservabile nei dati, non un sospetto astratto. Conservare i rifiuti come costo/fallimento della ricerca, non premiarli come speedup utilizzabili. Non ho rigenerato né sovrascritto i risultati storici.

## 4. Build MiniEngine: catena effettiva e punti deboli

### Percorso del codice realmente rilevante

`ModelViewer/ModelViewer.cpp` definisce `LEGACY_RENDERER` → usa `Model/SponzaRenderer.cpp` → include `CompiledShaders/ModelViewerPS.h` → `m_ModelPSO.SetPixelShader(g_pModelViewerPS, sizeof(...))` → `GraphicsPSO::Finalize()` calcola l'hash del bytecode → `SetPipelineState`/draw registrano il PSO nell'inventario.

Sorgente PS: **`MiniEngine/Model/Shaders/ModelViewerPS.hlsl`**. Include risolti nel tlog: `Common.hlsli`, `Lighting.hlsli`, `LightGrid.hlsli`, tutti della stessa directory Model/Shaders. Non intervenire su un omonimo di Core o sulla via alternativa non attiva del renderer.

Configurazione corrente degli script: `Profile / x64 / v145`. Eseguibile atteso:

`%TEMP%/claude/src/dxs/MiniEngine/Build/x64/Profile/Output/ModelViewer/ModelViewer.exe`

CWD richiesta: `MiniEngine/ModelViewer`, dove stanno gli asset e le DLL GPA.

Il comando DXC preservato per il PS è, con radice assoluta abbreviata qui ma non nel tlog:

```text
/nologo /E"main" /T ps_6_2 /D _GAMING_DESKTOP=1
/Fh ".../Build/x64/Profile/Output/Model/CompiledShaders/ModelViewerPS.h"
/Vn "g_pModelViewerPS" -HV 2021 .../Model/Shaders/ModelViewerPS.hlsl
```

Non compare `/I` esplicito né un override `-O3` in questo comando; gli include locali sono registrati da `dxc.read`. Il corpus standalone 2K usa invece **cs_6_6, -O3**, non automaticamente gli stessi parametri del PS runtime.

### Cosa si è verificato offline

Ricalcolando gli hash **solo sull'inizializzatore dell'array** (non sull'hex nei commenti di disassembly), le **40 associazioni scope/stage/hash** dell'inventario storico trovano tutte un header attuale. Sono **37 righe CSV e 37 hash unici**, non 40 shader unici. `ModelViewerPS`: **12.612 byte**, hash inventario **`52CE6C5E64AB2E82`**.

L'algoritmo runtime/map usa seed `1469598103934665603`, diverso dall'offset basis standard FNV-1a-64. È coerente tra i due lati, ma un tool FNV standard non darà lo stesso hash. SHA-256 completo resta la provenienza crittografica; il custom hash serve al raccordo con l'inventario.

**Questo è un controllo header attuale ↔ CSV storico. Non dimostra** che una modifica nuova sia stata compilata, linkata ed eseguita. Né la sola dimensione 12.612 byte né il nome del PSO bastano.

### Cosa non è riparato

- `buildv` usa SHA-256 troncato dell'intero header, non bytecode estratto; non certifica l'entry point né lo stage runtime. Un commento/sorgente irrilevante può cambiare senza cambiare codice: usare una canary semanticamente osservabile per la prova di propagazione, non “ogni modifica testuale deve cambiare DXIL”.
- Mancano controllo return code, header assente/ambiguo e confronto runtime obbligatorio. `expect_change` è opzionale; se entrambi header prima/dopo sono assenti il comportamento dipende dal parametro passato.
- L'hash dell'EXE è utile come metadata, non come prova primaria: può cambiare al link senza cambiare shader.
- `dxc.write.1.tlog` corrente contiene chiavi dei sorgenti ma **nessun percorso di output**. È un indizio importante di tracking incompleto. La spiegazione “timestamp nello stesso secondo” presente in 2N **non è una root cause dimostrata dall'audit**: diagnosticare il task DXC effettivo prima di attribuirla a granularità del filesystem.
- `-t:Rebuild` esegue anche Clean: con il divieto corrente di eliminazione non va lanciato sulla build esistente. Servono output intermedi/finali nuovi e isolati, senza fallback a Clean dei vecchi file; verificare che tutti i progetti referenziati ereditino l'isolamento.
- I vecchi runner cancellano CSV/log e riusano backup/output fissi. `real2k.compile_one()` accetta l'esistenza del `.cso`, senza validare il return code: rischio di risultato stale se riusato un percorso. Non eseguirli senza correggere il percorso condiviso e usare directory univoche.
- `gpa2n.no_tex` cambia soltanto la macro per tre texture materiali e introduce una costante float4 dove gli originali sono float3: non è una rimozione di ogni fetch e potrebbe generare conversioni/diagnostica. Non è stata compilata qui; non attribuire ad essa senza prova l'errore storico `dxc failed: Invalid argument`.
- `ps_black` sovrascrive solo Color, **Normal rimane live**. Non è “PS completamente vuoto”. `one_rt` cambia l'output HLSL, non garantisce da sola dimezzamento del traffico dell'intero pass/pipeline.

## 5. Inventario runtime e profiler interno

Il mapping per bytecode è la parte riutilizzabile migliore. I nomi dei PSO sono fuorvianti: `m_ModelPSO = m_DepthPSO` copia il nome, quindi “Sponza: Depth PSO” può eseguire il PS colore.

Limiti da correggere prima di usarlo come gate di esecuzione:

1. `ShaderInventory` conserva PSO/scope globali. Il mutex evita data race sulle strutture, non rende la semantica per-context/per-thread. `SetPipelineState` può fare early-return, lasciando l'ultimo PSO globale di un altro contesto. Il rischio è confermato nel design; una misattribuzione concreta di Render Color non è stata dimostrata.
2. `DispatchIndirect` registra la chiamata, **non** i gruppi negli argomenti GPU. `ExecuteIndirect` generico non è completamente coperto. Non c'è ancora il dataset necessario a un replay compute reale.
3. `NextFrame()` viene chiamato anche prima del break finale che salta `UpdateApplication`. È coerente con **299/300 = 0,9967** nelle chiamate/frame. L'accumulo dei timer, raccolto all'inizio dell'update, ha inoltre latenza da verificare nei confini warm-up/finale.
4. Render Color nel CSV contiene ~**33,8866 draw/frame** sommando entrambe le righe; i **28,90** del report sono una delle due componenti, non l'intero scope.
5. La somma dei timer di livello 1 è un **proxy dei pass strumentati**, non automaticamente la durata critica del frame se ci sono overlap/async/gap. L'export corrente contiene medie per scope, non serie per-frame per p95/p99 e low.
6. Il benchmark è windowed e il codice continua a chiamare `GameInput::Update()` e `EngineTuning::Update()`: “headless senza input” è una descrizione eccessiva. `ShowWindow` resta attivo. Non interagire con la finestra durante i run; per il replay servono input congelati davvero.

## 6. GPUPerfAPI: osservazioni, validità e interpretazione

### Campionamento

`GpaProfiler.cpp` abilita 31 nomi già enumerati (bene), ma esegue una sessione multipass avanzando la passata ad ogni frame campionato. Il commento “passo fisso = stesso frame” è errato: ripetibilità di una sequenza e identità dei frame della sequenza sono proprietà diverse. `ModelViewer::Startup` abilita TAA/motion blur/HDR adaptation/SSAO; `TemporalEffects::Update` fa avanzare frame index/jitter. Nessun ripristino degli input e delle history tra passate è visibile.

La documentazione locale `gpa/4_4/help/usage.html` richiede lo stesso workload GPU in ogni passata, oppure una scelta di counter che richieda una sola passata. Il numero di passate deve essere ottenuto dal SDK per il set effettivo, non indovinato. Un programma che produce un CSV non certifica quel requisito.

L'ordine `CommandContext::Begin → BeginBlock → GPA OnContextBegin` fa arrivare alcuni scope prima della registrazione command list. Questo spiega il caso HDR Tone Mapping non catturato. Flush/reset non ha hook corrispondenti; diversi return code GPA non sono controllati, e `Shutdown()` non ha chiamata dal percorso GameCore ispezionato. I fallimenti devono invalidare il run, non sembrare un risultato negativo.

**Precisazione importante sul log conservato:** i messaggi `scope su command list non registrata` vengono **prima** di `sessione avviata`; sono coerenti con il warm-up, non prova che la sessione Render Color abbia perso i sample. Il log termina con 31 counter scritti in un file chiamato `gpa_Render_Color_one_rt.csv`: il nome non attesta che la variante one_rt sia stata compilata/eseguita. Non lo conto come ablazione valida.

### Dato storico Render Color

Da `23_bottleneck/c_Render_Color.csv`:

| Counter | Valore |
|---|---:|
| GPUTime | 720.480 ns = 720,480 µs |
| TexUnitBusy | 94,609951% |
| MemUnitBusy | **94,609951%**, esattamente uguale; non due conferme indipendenti |
| MemUnitStalled | 0,414793% |
| PSBusy | 99,0291% |
| PSExportStalls / PAStalledOnRasterizer | 0,011790% / 0,206388% |
| L0 / L1 / L2 hit | 97,631836% / 53,013699% / 42,655425% |
| FetchSize / WriteSize | 32.687.296 / 19.943.840 byte |
| PSPixelsOut | 4.147.204 export |

Il rapporto `(FetchSize+WriteSize)/GPUTime` è ~73 GB/s secondo la definizione di quei counter. **Non è da solo misura di saturazione fisica GDDR6** né prova di assenza di latenza: su Navi21 bisogna distinguere i livelli della memoria e Infinity Cache, oltre alla composizione multipass. Un hit-rate aggregato alto non esclude dipendenze seriali o accessi critici.

`TexUnitBusy` significa attività comprensiva di effetti memoria/cache, non un contatore di throughput utile massimo. `PSBusy` significa lavoro PS presente, non ALU saturata. Nei 145 counter enumerati non c'è una coppia generale PS VALUBusy/SALUBusy/occupancy da inventare; quelli compute o pre/post tessellation non si applicano automaticamente al PS. Se necessari, dichiarare il limite GPA e ricorrere a un'acquisizione RGP controllata/GUI autorizzata, non creare nomi fittizi.

Le basse percentuali di export/raster stall suggeriscono priorità investigative, non eliminano tutte le alternative. Le classificazioni degli altri pass e il fattore “GPA ~1,35× costante” restano osservazioni da rivalidare; non trasferire delta fra clock/instrumentation differenti e non affermare che il 12% del frame sia assolutamente inaccessibile a qualunque trasformazione shader.

## 7. Phase 2O — piano preregistrato, massimo 8 passi / 6 cicli

**Piano sospeso al gate iniziale per A01–A03.** Nessuna delle soglie seguenti è un risultato già misurato. Dopo la risoluzione esplicita dello stop, massimo sei cicli; una failure conta nel budget e viene registrata, non sostituita senza traccia.

1. **Gate e preservazione, prima dei cicli.** Congelare metadata e copie hashate dei sorgenti/strumenti, identificare gli output univoci fuori dalle build esistenti e un manifest per experiment ID. Nessun delete/Clean degli artefatti vecchi. Correggere una sola pipeline condivisa fail-closed e instradarvi tutti i caller usati; return code, output atteso univoco, bytecode estratto, hash runtime e policy di ripristino obbligatori. Test piccolo senza GPU: errore processo, header assente, invariato e hash inatteso devono essere rifiutati. Tetto cumulativo 8 GB di nuovi output, pausa prima del superamento; niente task oltre il budget senza nuova autorizzazione.
2. **Ciclo O1 — propagazione build, non performance.** Ipotesi: una canary semanticamente osservabile e compilabile nel PS live arriva al PSO. Baseline → canary Color mantenendo MRT/layout → baseline ripristinata, con log DXC completo, SHA-256 sorgente/include/header/bytecode/EXE e inventario di un processo nuovo. PASS soltanto se il bytecode cambia, il draw Render Color usa esattamente l'hash atteso e il ripristino riottiene l'hash baseline. Confronto immagine target-aware deve rilevare la canary; baseline uguale non basta. Un hash inatteso/stale o compilazione non diagnosticabile ferma la sessione.
3. **Ciclo O2 — null, frame e GPA validi.** Ipotesi: identità del workload e varianza sono verificabili. Correggere conteggio frame e attribuzione per-context nella via usata. Congelare camera, jitter, RNG, luci, costanti, history e risorse lette/scritte oppure scegliere set GPA con `GpaGetPassCount=1`; single-pass non sostituisce la ripetibilità A/B. Controllare successi SDK e confini sample/list. Minimo sei blocchi indipendenti A/A, 400 warm-up + 1.200 frame misurati come punto di partenza, intervallo equivalente per ogni run. Salvare serie per-frame tramite export limitato o PresentMon+parser esistente; statistiche GPU scope separate. Nessuna chiusura di processi personali: interferenza significativa → run invalido/pausa. Se null o replay non passano, stop.
4. **Ciclo O3 — campionamento materiali.** Ablazione diagnostica, non candidata: sostituire separatamente i sample materiali con valori float3 appropriati, lasciando invariati geometria/MRT e, per quanto possibile, flusso luci/ombre. SHA/runtime gate per ogni variante. Verificare nel bytecode su copia quali sample sono davvero rimossi; DCE di ALU dipendente è un confondente da registrare. Ipotesi: ridurre questa componente del lavoro texture riduce il tempo Render Color e i segnali di lavoro texture coerenti. Misurare tempi senza GPA e counter in sessioni separate validate.
5. **Ciclo O4 — sample d'ombra.** Intervento indipendente dal materiale: percorso PCF direzionale a meno tap, con stesso output MRT, draw e illuminazione locale. Confronto col baseline originario, non con O3 cumulato; controllare il ramo realmente compilato e le operazioni sample residue. Ipotesi e previsione: dose inferiore di sample, tempo inferiore oltre soglia, variazioni counter coerenti. Diverso output visivo è atteso e etichettato come ablazione. Una riduzione con meno ALU/branch non isola ancora il throughput del filtro.
6. **Ciclo O5 — discriminante filtro vs altre cause.** Se necessario dopo O3/O4, cambiare solo costo di filtraggio/aniso del sampler mantenendo coordinate, texture, sample call e shader; qui hash PS **deve restare uguale**, mentre lo stato sampler deve avere provenienza diversa. È una prova app-level, non una trasformazione optimizer. Enumerare `TexAveAnisotropy`/counter filtraggio disponibili e scegliere pass set valido. Null del sampler se il baseline non usa effettivamente il filtro previsto → risultato non informativo, non falsificazione. Un controllo MRT/ALU può sostituire questo ciclo soltanto preregistrandone prima motivo e confondenti.
7. **Ciclo O6 — replica o falsificazione mirata.** Ripetere in ordine inverso l'intervento più discriminante su processi indipendenti e baseline ripristinata; verificare assenza di carry-over. Non allargare a nuovi shader/scenari per ottenere un vincitore. Fermarsi prima se già ottenute due conferme causali indipendenti, oppure falsificazione convincente. Se il budget finisce senza discrimine, esito **inconclusivo**, non “texture confermata”.
8. **Chiusura.** Dopo ogni ciclo appendere ipotesi, ID, metadata, delta/incertezza, counter e qualità di misura, correttezza, confondenti, file e verdetto in `AUTONOMOUS_LOG.md`; aggiornare `PLAN.md`. Report finale con un solo `NEXT RECOMMENDED ACTION`. Solo dopo una 2O valida si può **progettare** 2P sulla leva dimostrata e sul gate di qualità, senza implementarla. In caso di stop metodologico la prossima azione resta la riparazione, non 2P.

### Criteri comuni fissati prima dei risultati

- **Unità statistica:** run/processo/blocco appaiato, non ogni frame trattato come osservazione indipendente. Per intervento almeno sei blocchi A/B con ordine AB/BA bilanciato; stesso warm-up, durata e workload. GPU time Render Color primario; frame GPU strumentato e frametime PresentMon secondari.
- **Soglia effetto:** riduzione media del tempo maggiore di `max(2%, 3 × N95)`, con N95 = percentile 95 dei delta assoluti A/A per-run di O2. Intervallo di confidenza 95% appaiato interamente sotto zero; nessun outlier eliminato post hoc per rendere significativo il risultato. Se precisione insufficiente nei limiti del budget, inconclusivo.
- **Metriche:** media/mediana, p95/p99 frametime, 1% e 0,1% low secondo `04_benchmarks/analysis/METHOD.md`, stutter = frametime >2× mediana mobile di 21 frame **e** eccedenza ≥2 ms, più conteggio/durata run. Non ricavare questi percentili dal CSV delle sole medie di scope.
- **Causalità:** due interventi indipendenti, entrambi con provenienza verificata e riduzione effettiva del lavoro previsto, effetto replicato, draw/MRT/geometria e altri carichi controllati, counter semanticamente coerenti. Due counter correlati o due repliche della stessa ablazione non sono due cause indipendenti. La rimozione di sample insieme ad ALU prova al massimo un costo del percorso combinato; per affermare **throughput di filtraggio** serve il discriminante con ALU/flusso sostanzialmente invariati.
- **Falsificazione:** riduzione sostanziale verificata del lavoro texture senza effetto oltre rumore in due controlli informativi, insieme a una causa alternativa positivamente sostenuta, falsifica la dominanza texture per questo scenario. Un solo no-op, errore di build o shader compilato ma non eseguito non falsifica nulla.
- **Correttezza:** mantenere le categorie storiche strict/riassociazione e relative soglie; non allentarle dopo aver visto i risultati. Float: controlli finiti e NaN/Inf con segno, tipo/scala corretti; integer: confronto integer, non reinterpretazione float. Workload/thread coverage è un gate distinto. Oracolo immagine con formato DXGI, dimensioni, row pitch e target registrati, baseline/baseline e canary; history e frame indice identici. Output intenzionalmente diverso nelle ablazioni = **diagnostic_only**, mai variante accettata nell'optimizer. Nessuna selezione end-to-end senza un gate di qualità funzionante.
- **Stop immediato:** pipeline unreliable, nuovo handoff mismatch fondamentale, replay/counter non validabili, operazioni unsafe, necessità di toccare driver/giochi protetti/security/Registry, superamento budget. Preservare i file; ripristino del sorgente controllato e verificato, nessun cleanup distruttivo.

## 8. Conclusione dell'audit

Il progetto ha già imparato correttamente a profilare prima di ottimizzare e a mappare per bytecode. Non occorre riaprire tuning del driver, euristiche universali wave32/wave64, AST generalista o shader scelti solo perché veloci nel microbench.

La lacuna decisiva è sperimentale: **non esiste ancora una catena fail-closed che dimostri quale variante viene eseguita con counter raccolti su workload valido**. La prima azione ad alto valore è mettere in sicurezza quella catena in output nuovi, non cercare un guadagno né implementare 2P.
