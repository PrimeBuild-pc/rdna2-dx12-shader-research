# Phase 1.5-B — AMD UMD settings / tunings investigation

Read-only. Nessun binario modificato, nessun file creato nel driver store o nel package,
nessuna chiave di registro scritta, nessun export invocato.
Artefatti: `umd_identity.json`, `sc_options.csv` (272 righe), `config_surfaces.csv`.
Script: [`tools/umd_static.py`](../../tools/umd_static.py), [`tools/xref_fast.py`](../../tools/xref_fast.py).

---

## 1. Identificazione dell'istanza reale

Fonte di verità usata: la chiave che il runtime D3D12 legge davvero per l'adapter attivo.

```
HKLM\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\0000
  DriverDesc        = AMD Radeon RX 6950 XT
  DriverVersion     = 32.0.21045.5002
  MatchingDeviceId  = PCI\VEN_1002&DEV_73A5&SUBSYS_05041043&REV_C0
  UserModeDriverName = [0] ...\B026363\atidx9loader64.dll    (D3D9)
                       [1] ...\B026363\amdxx64.dll           (D3D10)
                       [2] ...\B026363\amdxx64.dll           (D3D11)
                       [3] ...\B026363\amdxc64.dll           (D3D12)  <<<
```

| | |
|---|---|
| Path | `C:\Windows\System32\DriverStore\FileRepository\u0203303.inf_amd64_e5876a26758f154c\B026363\amdxc64.dll` |
| Size | 82 422 960 B |
| **SHA-256** | `6aaade81651ffcdd19849fb3355aca5e4e7de5392a2120927e6defffb529b4b4` |
| FileVersion | 8.18.10.0500 · FileDescription "AMD DX12 UMD" |
| Firma | Signed — Advanced Micro Devices |
| DriverStore | `u0203303.inf_amd64_e5876a26758f154c`, sottocartella `B026363` |
| ImageBase | `0x180000000` · sezioni notevoli: **`.detourc` / `.detourd`** (Microsoft Detours linkato dentro) |

Il package 26.9.1 del progetto (`u0203729`/`B026432`, sha `6c42f438…`) è una **revisione
diversa**: tutta l'analisi qui è fatta sulla copia **installata**.

**Limite dichiarato:** questa è evidenza di *configurazione*, non di *caricamento*. Conferma
che il runtime D3D12 punta a questo file, non che Fortnite l'abbia in memoria. La conferma
runtime (module list del processo) arriva con la cattura ETW della parte A, che registra gli
eventi di image load: la colonna `module_path` di `amdxc64_hot_offsets.csv` la produce
automaticamente. Nel dry-run l'ho già visto funzionare su `dwm.exe` → `amdxx64.dll` risolto
esattamente a quel percorso `B026363`.

Lavoro svolto su una copia in scratchpad (hash verificato identico).

---

## 2. `GetSettingsBlobsAllDecoded` — **è uno stub vuoto**

RVA `0x14dd90`. Codice completo:

```
0x0014dd90   xor  eax, eax
0x0014dd92   ret
0x0014dd93   int3 ...        (padding)
```

Restituisce 0 e basta. Nessun argomento usato, nessuno stato globale, nessun side effect.

**Non serve determinarne la firma e non ha senso chiamarla.** La tua cautela era giusta come
principio; il risultato è che la funzione non fa nulla in questa build. Il probe standalone
proposto nel prompt **non va costruito**: non produrrebbe alcun dato.

## 3. `GetSettingsBlobsAll` — reale, ma richiede il driver inizializzato

RVA `0x1bda40`. Ricostruzione dal disassemblato:

```c
// firma dedotta (Microsoft x64, non stdcall/thiscall)
uint32_t GetSettingsBlobsAll(void* outBuffer /*RCX, può essere NULL*/,
                             uint32_t bufferSize /*EDX*/);
```

Comportamento:

- `RCX == NULL` → modalità "query size": accumula in `EBP` (inizializzato a 8) la dimensione
  necessaria e la restituisce in EAX. È il classico pattern query-size-then-fill.
- `RCX != NULL` → `RSI = RCX+8` (cursore di scrittura), `R15 = RCX+size` (limite), controllo
  `cmp rdi, r15 / ja` prima di ogni scrittura: **non scrive oltre il buffer**.
- Legge un **puntatore globale a `0x4bbf1b0` (.data)**. Se è NULL salta tutto e, se il buffer è
  ≥ 8 byte, scrive un header `{ dword 1, dword 0 }` e restituisce 8.
- Se non è NULL, itera su una lista chiamando metodi **virtuali** dell'oggetto:
  `vtbl[0](this, &size)` → puntatore ai dati; `vtbl[0x08]` → byte; `vtbl[0x10]` → dword;
  `vtbl[0x18]` → qword. Per ogni blob scrive un record
  `{ dword sizeAligned, dword sizeRaw, byte, dword, qword, payload… }` allineato a 8.

**Conclusione operativa:** il valore utile dipende interamente dal globale a `0x4bbf1b0`, che
viene popolato durante l'inizializzazione del driver (adapter/device). Da un processo che fa
solo `LoadLibrary` + `GetProcAddress`, quel globale è NULL e la funzione restituisce
`{version=1, count=0}`, 8 byte. Innocua ma inutile.

Quindi: **niente probe standalone.** Per ottenere i blob servirebbe un device D3D12 creato,
cioè un'applicazione grafica vera — a quel punto conviene la strada §5, che non richiede
codice nostro.

## 4. `DXCTuningsFileName` — è un meccanismo del **kernel-mode driver**, non dell'UMD

Ricerca della stringa su tutti i binari grafici installati (ASCII e UTF-16):

| binario | `DXCTuningsFileName` | `ABCDTuningsFileName` | `amdxc64z` |
|---|:---:|:---:|:---:|
| `amdxc64.dll` (UMD DX12) | **0** | **0** | 0 |
| `amdxc64.so` (UMD WSL) | 0 | 0 | 0 |
| `amdxcstub64.dll` | 0 | 0 | 0 |
| `amdxcffx64.dll` | 0 | 0 | 0 |
| `amdxx64.dll` | 0 | 0 | 0 |
| **`amdkmdag.sys`** | **1 (UTF-16)** | **1 (UTF-16)** | 0 |

Catena verificata nel registro **vivo**:

```
INF installato u0203303.INF, riga 4038:
  [ati2mtag_KMD_DS]  AddService = amduw23g-203303-6af680f4 ...
  AddReg = ati2mtag_ServiceSettings
  ServiceBinary = %13%\B026363\amdkmdag.sys

  [ati2mtag_ServiceSettings]
  HKR,Parameters,DXCTuningsFileName,%REG_SZ%,"amdxc64z.dll;amdxc32z.dll"

-> HKLM\SYSTEM\CurrentControlSet\Services\amduw23g-203303-6af680f4\Parameters
     DXCTuningsFileName  = amdxc64z.dll;amdxc32z.dll      (PRESENTE, live)
     ABCDTuningsFileName = amdxc64d.dat;amdxc32d.dat;amdxc64b.dat;amdxc32b.dat
     DCHUVen = 4098 · CloudProfilesSupported = 1 · DmaRemappingCompatible = 3
```

`HKR` in una sezione `AddService` è la **chiave del servizio**, non quella della classe device:
per questo la Fase 1B non l'aveva trovata sotto `...\Class\{4d36e968…}\0000\Parameters`
(quella sottochiave non esiste). Rettifica registrata.

`amdxc64z.dll`, `amdxc64d.dat`, `amdxc64b.dat`: **non esistono da nessuna parte** su questo
sistema (ricerca su tutto `C:\Windows`), né nel package.

**Verdetto: strada da abbandonare.** Il nome della chiave non compare nel UMD DX12, quindi
l'UMD non la legge. La legge `amdkmdag.sys`, cioè kernel mode. Anche ammesso di capire il
formato, si tratterebbe di far caricare al KMD un file che non esiste per progetto — rischio
di stabilità alto, guadagno ignoto, e fuori dai vincoli del progetto. **Non la perseguo.**

## 5. Quello che invece esiste davvero: la config del compilatore shader via env/file

Questa è la scoperta della fase. Dentro `amdxc64.dll` c'è un parser di opzioni
**boost::program_options** completo, con messaggi d'errore (`unrecognised option
'%canonical_option%'`), gruppi ("CompilerControl options", "Dump options"), separatori `--` e
`=`, e queste sorgenti:

| nome | tipo | RVA stringa | xref confermato | confidenza |
|---|---|---|---|---|
| `AMD_SC_OPTIONS` | env var | `0x4714db8` | `0x58c286 lea rcx` | strong |
| `AMD_SC_CFG_FILE` | env var | `0x4714da8` | `0x58bbfb lea rcx` → helper `0x79b844` | strong |
| `amdsc.ini` | file (default) | `0x4714dc8` | `0x58bc07 lea rbx; cmovne rbx,rax` | strong |
| `AMD_SC_` | prefisso env | `0x4714cd8` | — | probable |
| `AMD_DXCP_TEST_OPTIONS` | env var | `0x3bd62d0` | `0x26c11f lea rcx` → stesso helper | strong |
| `EnableGlobalSettingsDumping` | settings key | `0x3bd6288` | `0x26acc9 lea rdx` → vcall `[rax+0x20]` | strong |
| `GlobalSettingsDumpFile` | settings key | `0x3bd62a8` | `0x26ad47 lea rdx` → vcall `[rax+0x20]`, buffer `0x100` | strong |
| `AMD_CONFIG_DIR` | env var | `0x26c25d0` | `0x2f4c1a lea rcx` | strong |
| `amdPalSettings.cfg` | file | `0x2620800` | nessun `lea` diretto | probable |

Il pattern decisivo, a `0x58bbfb`:

```
lea  rcx, [AMD_SC_CFG_FILE]
call 0x18179b844            ; helper getenv-like: nome in RCX, char* o NULL in RAX
lea  rbx, [amdsc.ini]       ; default
test rax, rax
cmovne rbx, rax             ; se la env var e' impostata, usa quel path
```

Lo **stesso helper** `0x79b844` è chiamato a `0x26c126` con `AMD_DXCP_TEST_OPTIONS`, seguito da
un parser che spezza su `0x3d` (`=`): formato `chiave=valore`. Il binario è a CRT statico, quindi
l'helper è un `getenv` linkato staticamente (gli import kernel32 espongono solo le varianti
wide `GetEnvironmentVariableW` / `GetEnvironmentStringsW`) — per questo lo classifico **strong**
e non *confirmed*.

`EnableGlobalSettingsDumping` / `GlobalSettingsDumpFile` non sono env var: sono **nomi di
impostazione** letti tramite un provider di settings (`obj->vtbl[0x20](this, name, …, out)`),
con destinazione un buffer da 0x100 byte. La funzione che li legge (`0x26aca0`) è protetta da
un `vtbl[0x20]` iniziale con `cmp eax,1`: c'è una **condizione di abilitazione** che non ho
ancora identificato. Da chiarire prima di provarci.

### Il catalogo delle opzioni del compilatore

272 stringhe `SCOption_*` (elenco completo in `sc_options.csv`), referenziate da un array
contiguo di `const char*` in `.rdata` (~`0x2722000`, passo 8 byte) — cioè una tabella indicizzata
per ID di opzione, il pattern di un lookup nome→opzione.

| categoria | n | esempi |
|---|---:|---|
| hw_workaround | 48 | `SCOption_GFX10_DEGGIGXX0_8654_BACK_COMPAT_MTYPE` |
| memory_lds_cache | 34 | `SCOption_BUFFER_LOAD_TO_LDS`, `SCOption_AVOID_LDS_BANK_CONFLICT_ONCHIP_TESS` |
| float_precision | 23 | `SCOption_USE_FMA_FOR_MAD`, `SCOption_FLUSH_F64_DENORMS`, `SCOption_GFX9_EXPERIMENTAL_USE_MORE_D16` |
| optimization_pass | 19 | `SCOption_AGGRESSIVE_HOIST`, `SCOption_DISABLE_LOOP_UNROLLING`, `SCOption_SELECTIVE_INLINE`, `SCOption_IF_CONVERSION_HEURISTIC` |
| scheduling | 19 | `SCOption_LIVENESS_BASED_INSTRUCTION_SCHEDULING`, `SCOption_POST_RA_INSTRUCTION_SCHEDULING`, `SCOption_LATENCY_CODE_MOTION` |
| **register_allocation** | 10 | **`SCOption_MINIMIZE_VGPRS`**, `SCOption_PBQP_REGISTER_ALLOCATION`, `SCOption_W64_MINIMIZE_REG_BANK_CONFLICTS`, `SCOption_R1200_DISABLE_REGISTER_PACKING` |
| **wave_size_occupancy** | 9 | **`SCOption_GFX10_FORCE_WAVE64_SCHEDULING_FOR_CS`**, `SCOption_GFX10_FORCE_WAVE32_SCHEDULING_FOR_PS`, `SCOption_GFX10_ENABLE_SUBVECTOR`, `SCOption_GFX10_ENABLE_ML_MODEL_FOR_PS_WAVESIZE_CHOICE` |
| debug | 3 | `SCOption_TEST_MODE_0..2` |
| other | 107 | |

Le famiglie `GFX10*` / `R1000*` / `R1100*` sono quelle rilevanti per RDNA2 (gfx10.3).

Esiste anche un blocco di opzioni di **dump** con descrizioni leggibili: `dump-input-xml`
("Dump entire SC input in machine readable XML format"), `dump-il-text`, `dump-sp3-binary`,
`dump-separate`, `dump-prefix`, `dump-append-pid`, e il formato `Shader_%016llx`. Cioè il
compilatore sa **esportare l'input e l'ISA di ogni shader su file, per shader hash**.

Se funziona, questo è precisamente il pezzo mancante della catena che cercavamo:

```
shader hash  →  ISA dumpato dal driver  →  costo GPU misurato (RGP / Steel Nomad)
```

e lo otterremmo **senza injection, senza hook e senza toccare un solo byte firmato**.

## 6. Cosa NON so ancora (e non ho tirato a indovinare)

- Se `AMD_SC_OPTIONS` / `AMD_SC_CFG_FILE` siano **attive nella build retail** o gated da un
  flag interno. Le stringhe e il parser ci sono; la condizione di abilitazione non l'ho isolata.
- La sintassi esatta accettata (nomi `SCOption_*` interi? senza prefisso? `--nome=valore`?).
- Quale sia la condizione `cmp eax,1` che protegge `EnableGlobalSettingsDumping`.
- Se `.detourc`/`.detourd` significhi che il UMD hooka funzioni del processo ospite: la sequenza
  in `OpenAdapter12` (`call A; call B; mov rcx,rax; call C; lea rdx,[X]; mov rcx,rsi; call D;
  call E; test eax,eax`) corrisponde a `DetourTransactionBegin / GetCurrentThread /
  DetourUpdateThread / DetourAttach / DetourTransactionCommit`, ma è **strong**, non confirmed.
- Il significato semantico delle 272 opzioni: i nomi suggeriscono, non dimostrano.

## 7. Prossimo passo consigliato per questo ramo — e i suoi rischi

Il test decisivo è a costo quasi nullo: impostare `AMD_SC_CFG_FILE` (o `AMD_SC_OPTIONS`) **solo
nell'ambiente di un processo di test**, con una sintassi volutamente sbagliata, e vedere se il
driver reagisce (messaggio `unrecognised option`, log, crash del solo processo di test) oppure
ignora del tutto. Reazione ⇒ il meccanismo è vivo; silenzio ⇒ gated e la strada si chiude.

Vincoli da rispettare quando lo faremo:

- Variabile impostata **solo per il processo figlio**, mai a livello utente o sistema.
- **Mai su Fortnite o Warzone.** Un'app con anti-cheat che si trova env var AMD non standard
  nel proprio ambiente è esattamente il tipo di anomalia da non introdurre. Il banco è
  Steel Nomad, e meglio ancora Wukong quando sarà installato.
- Nessuna scrittura in `%LOCALAPPDATA%\AMD`, nel DriverStore o nel registro.
- Se il driver dovesse dumpare file, farlo in una directory di lavoro nostra via `dump-prefix`.

Non l'ho eseguito: modificare l'ambiente di un processo grafico è un cambiamento di
comportamento del driver, e mi hai chiesto di fermarmi al decision gate.
