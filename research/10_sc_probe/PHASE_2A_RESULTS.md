# Phase 2A/2B/2C — Il parser SC della build retail è ATTIVO

Data: 2026-09-04. Driver 32.0.21045.5002, `amdxc64.dll` sha256 `6aaade81…`.
Nessun driver, Registry, file di sistema o shader cache modificati. Nessuna env var persistente.
Fortnite non coinvolto.

---

## Esito in una riga

**`AMD_SC_OPTIONS` e `AMD_SC_CFG_FILE` sono realmente consumate dalla build retail installata**,
e il dump del compilatore funziona: abbiamo ottenuto `shader hash → input del compilatore (XML) →
ISA RDNA2 + statistiche`, senza toccare un solo byte firmato.

## 1. Correzione di metodo: perché non ho usato Steel Nomad

Il piano era canary + ProcMon su Steel Nomad. Non ha funzionato, per due motivi miei e uno
dell'ambiente:

| problema | causa | esito |
|---|---|---|
| 3DMark non parte mai | il mio script lo lanciava direttamente, ma è la build **Epic** (EOSSDK) e gira su una **JVM** (`E:\3DMark\jre\bin\javaw.exe`) che resta in attesa dell'autenticazione. Anche non elevato: 60 s con `MainWindowHandle=0` e 0.2 s di CPU | script sbagliato |
| sistema in ginocchio | ProcMon avviato **senza filtri** durante il caricamento di 3DMark: **2.1 GB di PML in 8 minuti**; anche `/Terminate` si impianta | script sbagliato |
| processi appesi | `Get-Process 3DMark*` non vedeva `javaw.exe` | diagnosi mia sbagliata |

Ripulito tutto (`taskkill` su `Procmon64.exe` ×2 e `javaw.exe`; nessun driver `PROCMON*`
residuo, nessun riavvio necessario).

**Strumento sostitutivo: Radeon GPU Analyzer in modalità DX12.** RGA compila HLSL usando il
**driver installato** — quindi carica `amdxc64.dll` — in pochi secondi, headless e ripetibile.
Prova che usa il driver reale:

```
; D3D12 Shader Hash 0xc28eae37456cdd71ed419ab4a7f3b56e
; API PSO Hash 0x70d880b202450aa6
; Driver Internal Pipeline Hash 0x3ac6c6613eeade46
  asic(GFX10_3)  sgpr_count(14)  vgpr_count(16)  wave_size(32)
```

`GFX10_3` = RDNA2 = la GPU installata. Il messaggio d'errore di RGA quando il backend fallisce
lo dice esplicitamente: *"cannot retrieve the list of targets supported by the driver. Consider
adding --offline … amdxc64.dll that is bundled with the tool"* — cioè in modalità normale usa
**quello di sistema**, non quello incluso.

**E ProcMon non serve più**: il rilevatore è deterministico e migliore — se il parser è vivo,
un'opzione invalida deve far fallire l'inizializzazione. Zero overhead, zero GB di log.

## 2. La prova che il parser è vivo (2A)

Shader di test: [`shader/cs.hlsl`](shader/cs.hlsl), compute, 8 iterazioni di sin/cos.
Comando identico in tutti i run, varia **solo** l'environment, process-local.

| # | `AMD_SC_OPTIONS` | esito |
|---|---|---|
| A | *(non impostata)* | **OK** — ISA prodotto |
| B | `""` (vuota) | **OK** |
| C | `--dump-prefix=C:/temp/scdump_` (nome **valido**) | **OK** |
| D | `--opzione-inventata` | **KO** — backend DX12 fallito |
| E | `--dump-prefx=x` (**typo di una lettera** su un nome valido) | **KO** |

Il discriminante è **esclusivamente la validità del nome dell'opzione**: `dump-prefix` passa,
`dump-prefx` no. Non è "una env var qualsiasi rompe il driver" — è parsing vero, con
validazione dei nomi. Confidenza: **confirmed**.

## 3. Sintassi del file di configurazione (2B)

Stesso metodo su `AMD_SC_CFG_FILE`, variando il **contenuto** del file:

| contenuto | esito | conclusione |
|---|---|---|
| *(vuoto)* | OK | file letto senza errori |
| `# commento` | **OK** | `#` è la comment syntax |
| `; commento` | **KO** | `;` **non** è comment syntax |
| `dump-prefix=<path>` | **OK** | formato `chiave=valore` |
| `dump-prefix = <path>` | **OK** | spazi attorno a `=` ammessi |
| `--dump-prefix=<path>` | **KO** | **niente `--` nel file** (i `--` valgono solo in `AMD_SC_OPTIONS`) |
| `opzione-inesistente=1` | **KO** | nomi validati anche da file |
| `[CompilerControl]` + chiave | **KO** | nessuna sezione con quel nome |

È il comportamento di `boost::program_options::parse_config_file`, coerente con l'analisi
statica (cluster boost, `unrecognised option '%canonical_option%'`).

Booleane: `dump-all=true` e `dump-all=1` sono **entrambe accettate**.

## 4. Primo esperimento di dump riuscito (2C)

`cfg/d_true.ini`:
```ini
dump-prefix=C:/Users/Lorenzo/Downloads/driver mod/research/10_sc_probe/dump/sc_
dump-all=true
```

Output prodotto dal driver in `dump/`:

| file | dimensione | contenuto |
|---|---:|---|
| `sc__dx12_backend.exe_amdxc64.dll.txt` | 319 KB | dump testuale: input, ISA, statistiche |
| `sc__…_0acc2a8d4f292ab4_00.xml` | 34.7 KB | `SC_INPUT` serializzato |
| `sc__…_0acc2a8d4f292ab4_01.xml` | 34.7 KB | idem, indice 01 |
| `sc__…_5d5f5ab46522df91_00.xml` | 30.9 KB | |
| `sc__…_751c51e02027565c_00.xml` | 34.7 KB | |
| `sc__…_d0c14d589761f9cf_00.xml` | 31.6 KB | |

**Il naming è `<prefix>_<processo>_<modulo>_<shader hash 64 bit>_<indice>.xml`.**

Gli XML sono `boost_serialization` della struttura **`SC_INPUT`** — esattamente i tipi `_SC_*`
trovati negli export nella fase 1B, ora confermati a runtime:

```xml
<boost_serialization signature="serialization::archive" version="17">
<SC_INPUT class_id="0" version="1543508994">
  <scver>scver: 519176dd465be29bc7b98d06f0276623e9837564 (HEAD)</scver>
  <instructionSet>24</instructionSet>
  <pInShader class_id="1" …>
```

Il `.txt` contiene, per ogni shader:

```
; ----------------- Input shader ------------------
Shader ID: 0x0ebd919557dc4adf273f1127b272f00b
; ------------- SC_SRCSHADER Dump ------------------
; compileFlag         = 0x00000084
; Output shader
; -------- Disassembly --------------------
shader main / asic(GFX10) / type(PS)
; Optimization Report      -> Intent = SI_OPT_INTENT_UNSET
; Shader Stats             -> NumInst, uNumVALUInst, uNumSALUInst, uNumInterpInst,
;                             uNumCompilerSpills, uNumCompilerVectorSpills/ScalarSpills,
;                             Phase3_VGPR, Phase3_SGPR, …
; SCML Model Decision Stats
; Scheduler stats
; SPI_SHADER_PGM_RSRC2_PS = 0x00000004
```

Rilevanti per il progetto: **`uNumCompilerSpills` / `VectorSpills` / `ScalarSpills`**,
`Phase3_VGPR`/`Phase3_SGPR`, l'`Optimization Report` con il campo `Intent`, e le
**`SCML Model Decision Stats`** — che è il modello ML citato da
`SCOption_GFX10_ENABLE_ML_MODEL_FOR_PS_WAVESIZE_CHOICE`.

## 5. La catena che cercavamo

```
shader hash (D3D12 / PSO / driver-internal / SC Shader ID)
     -> SC_INPUT serializzato in XML          (dump-input-xml / dump-all)
     -> ISA RDNA2 disassemblato               (dump-all)
     -> statistiche: VGPR, SGPR, spill, occupancy, decisioni scheduler
```

Ottenuta **senza modificare alcun file firmato**, senza injection, senza toccare la shader
cache e senza Registry. È il "meccanismo di configurazione già previsto dal driver" che
cercavamo dalla fase 1B.

## 6. Cosa NON è stato fatto (e resta aperto)

- **Nessuna opzione di ottimizzazione attivata.** `MINIMIZE_VGPRS`, PBQP, scheduler, wave size:
  non toccate, come da istruzioni.
- **Nessun test su Steel Nomad.** Tutto è stato fatto con RGA. Che il parser sia attivo *anche*
  quando l'UMD è caricato da un gioco/benchmark è **plausibile ma non dimostrato**: RGA usa lo
  stesso `amdxc64.dll`, ma il percorso di inizializzazione potrebbe differire.
- Non so se `AMD_SC_OPTIONS` accetti più opzioni separate da spazio, né come si comporti la
  terza sorgente (prefisso `AMD_SC_` sulle singole variabili).
- Il default di `dump-prefix` resta non verificato (senza prefisso i file dove finiscono?).
- Non ho verificato se un'opzione invalida faccia fallire allo stesso modo **un gioco**: su RGA
  è innocuo, in un gioco significherebbe compilazione shader fallita. **Da trattare con
  prudenza**: qualunque test futuro con env var va fatto solo su workload sacrificabili.

## 7. Prossimo passo naturale (non eseguito)

Ripetere il dump su **Steel Nomad**, che è l'unico modo per legare gli shader reali di un
workload al loro ISA e costo. Serve però lanciare 3DMark **ereditando l'ambiente**: dato che è
la build Epic su JVM, la via praticabile è avviare l'Epic Games Launcher da una shell con le
env var impostate, oppure lanciare `javaw` direttamente con l'ambiente giusto — da verificare.

Solo dopo, e solo su Steel Nomad (CV 0.11%, MDD 0.17%), avrebbe senso passare alle opzioni che
toccano il codegen.
