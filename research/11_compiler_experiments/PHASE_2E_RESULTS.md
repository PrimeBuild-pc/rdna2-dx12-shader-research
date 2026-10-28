# Phase 2E — Controlled Compiler Optimization Lab

RGA 2.14.2.8 + driver installato (`amdxc64.dll` sha256 `6aaade81…`), target `gfx1030` (Navi 21).
Nessun driver/Registry/cache modificati, nessuna env var persistente, nessun gioco coinvolto.
Codice: [`tools/sc_lab.py`](../../tools/sc_lab.py), [`tools/sc_try.sh`](../../tools/sc_try.sh).

---

## Esito in una riga

**Le 272 `SCOption_*` NON sono impostabili tramite i canali di configurazione del driver.**
Il parser `AMD_SC_OPTIONS`/`AMD_SC_CFG_FILE` espone **solo le 8 opzioni di dump**, che sono
osservative: verificato su 24 compilazioni, **0 cambiano l'ISA**.

La domanda "quale opzione compilatore migliora il codegen" **non è rispondibile** con le leve
trovate. Zero configurazioni promettenti da proporre — dirlo è il risultato.

## 1. Baseline (punto 1 del brief) — completa

Sei shader controllati, stesso target, stessi argomenti, stesso hardware.
Dati completi in [`baseline.csv`](baseline.csv) (include D3D12/PSO/pipeline hash per shader).

| shader | ruolo | VGPR | SGPR | inst | VALU | SALU | mem | branch | bytes | wave |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `s1_simple` | controllo | 8 | 14 | 80 | 5 | 74 | 1 | 0 | 336 | 32 |
| `s2_alu` | ALU-heavy | 24 | 14 | 1994 | 1919 | 74 | 1 | 0 | 9552 | 32 |
| `s3_mem` | memory + LDS | 40 | 14 | 215 | 82 | 119 | 14 | 4 | 1012 | 32 |
| `s4_pressure` | **register pressure** | **144** | 14 | 691 | 564 | 102 | 25 | 0 | 3612 | 32 |
| `s5_divergent` | branching/divergenza | 24 | 14 | 1037 | 854 | 181 | 2 | **40** | 5464 | 32 |
| `s6_texture` | sampling | 72 | 22 | 177 | 70 | 90 | 17 | 0 | 1004 | 32 |

La copertura è buona: VGPR da 8 a 144, istruzioni da 80 a 1994, un caso con 40 branch e uno con
25 accessi memoria. `s4_pressure` a 144 VGPR è esattamente il caso in cui `MINIMIZE_VGPRS` o
`PBQP_REGISTER_ALLOCATION` conterebbero — se fossero raggiungibili.

Nessuno spill in nessuno shader (RGA non riporta scratch), tutti wave32.

## 2. Perché le `SCOption_*` non sono raggiungibili (punto 2)

Ho usato l'oracolo binario stabilito in 2A (nome valido → compila, nome invalido → il backend
DX12 fallisce). Ogni test è un processo RGA separato con timeout.

**Naming testato per `SCOption_MINIMIZE_VGPRS`, tutti KO:**

```
--SCOption_MINIMIZE_VGPRS      --SCOption_MINIMIZE_VGPRS=1    --minimize-vgprs
--MINIMIZE_VGPRS               --sc-option=SCOption_...       --option=20
--sc-options=0x100000          --scoptions=0x100000           --options=0x100000
--flags=0x100000               --opt=20                       --enable=SCOption_...
```

**Evidenza statica che chiude la questione.** Nel binario esistono **due soli**
`options_description`:

| gruppo | contenuto |
|---|---|
| `"CompilerControl options"` | contiene solo il gruppo Dump |
| `"Dump options"` | `dump-prefix`, `dump-all`, `dump-il-text`, `dump-il-binary`, `dump-input-xml`, `dump-sp3-binary`, `dump-separate`, `dump-append-pid` |

Non esiste nessun'altra stringa `* options` riconducibile al compilatore SC (le altre trovate —
`Generic Options`, `Color Options`, `print-options` — appartengono al **CommandLine registry di
LLVM** usato dal percorso DXIL/raytracing, non al parser SC).

E la tabella dei 272 nomi serve al **reporting**, non all'input: nel binario c'è il formato di
stampa

```
u32SCOptions[0] = 0x%08X
```

cioè le SCOption sono una **bitmask di uint32 stampata nel dump**, e i nomi servono a
decodificarla. Coerente con la tabella indicizzata trovata in 2D (indice = bit).

**Seconda leva testata e scartata: `AMD_DXCP_TEST_OPTIONS`.** Accetta `chiave=valore` (una sola
coppia: con `,`, `;` o spazio fallisce) e **non valida i nomi** (`NomeInventatoXYZ=1` → OK),
quindi è un dizionario di override generico. Ma le settings che conosce sono tutte **feature
Adrenalin**, non codegen:

```
AntiStuttering  TurboSync  Tessellation  VSyncControl  FsrOverride
Chil_* (Chill)  Dlg_* (Anti-Lag)  Bst_* (Boost)  Ris_* (Sharpening)  RTBst_*  FreMux12*
```

Fuori dai vincoli del progetto (le impostazioni Adrenalin sono già configurate a mano) e
comunque irrilevanti per l'ISA. `EnableGlobalSettingsDumping=1` è accettato ma non produce
alcun file; `GlobalSettingsDumpFile=<path>` fa sempre fallire il backend, anche con path senza
spazi e con backslash. Non sono riuscito a ottenere il dump delle global settings.

## 3. One-variable-at-a-time (punto 3) — controllo negativo

Le uniche opzioni esistenti, una alla volta, su tutti e 6 gli shader.
Risultati completi in [`compiler_option_results.csv`](compiler_option_results.csv).

| Shader | Option | Value | ISA changed | ΔInst | ΔVGPR | ΔSGPR | ΔSpills | Notes |
|---|---|---|---|---|---|---|---|---|
| tutti e 6 | `dump-all` | 1 | **no** | 0 | 0 | 0 | 0 | codegen identico |
| tutti e 6 | `dump-il-text` | 1 | **no** | 0 | 0 | 0 | 0 | codegen identico |
| tutti e 6 | `dump-input-xml` | 1 | **no** | 0 | 0 | 0 | 0 | codegen identico |
| tutti e 6 | `dump-separate` | 1 | **no** | 0 | 0 | 0 | 0 | codegen identico |

**0 su 24 cambiano l'ISA** (confronto su SHA-256 del disassemblato con gli offset di encoding
rimossi). È il risultato atteso — sono opzioni di output — e serve da **controllo negativo**:
dimostra che la pipeline di misura rileverebbe una differenza se ci fosse, e che le opzioni
raggiungibili non sono leve di ottimizzazione.

## 4. Ranking (punto 4) — vuoto, e perché

**Nessuna configurazione promettente.** Non ne propongo cinque inventate: le opzioni che
cambierebbero il codegen esistono nel binario ma non sono esposte da nessun canale di
configurazione che io abbia trovato. Le vie rimaste per raggiungerle sono tutte fuori dai
vincoli del progetto o non verificate:

| via | stato |
|---|---|
| parser `AMD_SC_OPTIONS` / file | **esclusa con evidenza**: espone solo dump-* |
| `AMD_DXCP_TEST_OPTIONS` | **esclusa**: solo feature Adrenalin |
| `DXCTuningsFileName` (KMD) | **chiusa in fase 1.5**: è del kernel driver, file inesistenti |
| API di estensione `AmdExtD3DCreateInterface` | **non esplorata** — potrebbe esporre un percorso di compilazione con flag |
| patch binaria del default della bitmask | **vietata** dai vincoli (invalida la firma del catalogo) |

## 5. Correzioni a cose che avevo detto prima

- **`AMD_SC_OPTIONS` funziona eccome.** Avevo scritto che "non produce file": era falso. I dump
  c'erano, finiti nel posto sbagliato — **`AMD_SC_OPTIONS` splitta sugli spazi**, e il mio
  `--dump-prefix=C:/Users/.../driver mod/...` si spezzava su "driver mod", producendo file
  `driver_*` in `C:\Users\Lorenzo\Downloads\`. Ripuliti.
- **Il default di `dump-prefix` è `amdsc`**, non vuoto come avevo concluso dall'analisi statica:
  senza prefisso i file escono come `amdsc_dx12_backend.exe_amdxc64.dll*` **nella CWD del
  processo**. La stringa `amdsc` a `0x471367c` era davvero il default.
- Le opzioni di dump sono `typed_value<bool>`, non `bool_switch`: **richiedono sempre `=valore`**
  (`--dump-all` da solo fallisce, `--dump-all=1` funziona).
- Esiste una sintassi **per-shader**: `<hash-esadecimale>.<opzioni>` (regex
  `((0[xX])?[[:xdigit:]]+)\.(.+)`), accettata dal parser. Utile per limitare i dump a un singolo
  shader in un carico reale.

## 6. Phase 2F — design (non implementata)

RGA misura il **codegen**, non la velocità. Nessun miglioramento prestazionale è dichiarato qui.

Dato che le leve del *driver* non sono accessibili, 2F cambia scopo: da "verifica che l'ISA
migliore sia più veloce" a **banco di misura riutilizzabile** che renda misurabile qualunque
leva troviamo in futuro — incluse quelle che agiscono sull'input invece che sul driver.

**Cosa costruire**

- Eseguibile D3D12 standalone, ~400 righe, nessuna dipendenza esterna: crea device sulla
  6950 XT, compila i PSO dagli stessi 6 shader, alloca i buffer, esegue N dispatch.
- Misura con **timestamp query** (`ID3D12QueryHeap` `D3D12_QUERY_TYPE_TIMESTAMP` +
  `GetClockCalibration`/`GetTimestampFrequency`) attorno al solo dispatch: **GPU time in ns**,
  non FPS.
- Protocollo: warm-up scartato, K ripetizioni, riporta mediana e MAD, non la media.
- Stampa CSV: `shader, variant, dispatches, gpu_ns_median, gpu_ns_mad, cv_pct`.
- Prima cosa da fare **prima** di qualunque confronto: misurare la varianza run-to-run del banco
  stesso, come fatto per Steel Nomad (che ha CV 0.11%). Senza quella soglia nessun risultato è
  interpretabile.

**Leve che 2F potrebbe realmente testare** (agiscono sull'input, non sul driver, e sono tutte
sotto il nostro controllo):

1. **`[WaveSize(32)]` / `[WaveSize(64)]`** in HLSL (SM 6.6) — l'equivalente *legittimo* di
   `SCOption_GFX10_FORCE_WAVE32/64_SCHEDULING`, senza toccare il driver. È la leva più
   interessante su RDNA2.
2. Attributi `[unroll]` / `[loop]` e loro grado.
3. Flag di ottimizzazione DXC (`-O0..-O3`, `-Zi`, `precise`).
4. Riscrittura mirata dello shader ad alta pressione (`s4_pressure`, 144 VGPR) per ridurre i
   VGPR e vedere l'effetto reale su occupancy e tempo.
5. Numero di thread per gruppo (`numthreads`), che interagisce con occupancy e LDS.

Nessuna richiede il parser del driver, e tutte producono ISA diversa in modo verificabile con la
pipeline di 2E già funzionante.

## File prodotti

```
research/11_compiler_experiments/
├── shaders/s1..s6.hlsl              6 shader controllati
├── baseline.csv                     baseline completa, 6 shader x ~20 metriche
├── variants_raw.csv                 24 compilazioni con opzione singola
├── compiler_option_results.csv      diff baseline vs variante (formato richiesto)
└── PHASE_2E_RESULTS.md
tools/sc_lab.py                      lab riutilizzabile (baseline | sweep)
tools/sc_try.sh                      oracolo di validità di un'opzione
```
