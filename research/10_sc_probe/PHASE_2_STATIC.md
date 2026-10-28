# Phase 2B/2C/2D — ricostruzione statica del parser SC (pre-canary)

Analisi su copia di `amdxc64.dll` installato, sha256 `6aaade81…`. Read-only.
Nessun driver, Registry, file di sistema o shader cache toccati. Nessuna env var impostata.
Strumenti: [`tools/umd_func.py`](../../tools/umd_func.py) (risoluzione funzioni via `.pdata`).

Questa analisi è stata fatta **prima** del canary di 2A perché rende il test interpretabile:
dice *quando* aspettarsi la lettura e *quante volte*.

---

## 1. Struttura del parser (2B)

### Catena di chiamata

```
0x58b9f0   costruisce "CompilerControl options" + legge le 3 sorgenti   (3547 byte)
   ^
0x58c820   lazy-init singleton: cmp [rsi],0 / jne -> costruisce UNA SOLA VOLTA  (917 byte)
   ^
0x58dcdf, 0x58dd46, 0x58dd95, 0x58ddaf, 0x58dedf, 0x58df2e, 0x58e721, 0x58ec1a   (8 call sites)
```

**Nessun gate di build.** In `0x58c820` non c'è nessun `if (internal_build)` / `if (debug)`:
c'è solo un doppio controllo `cmp qword ptr [rsi], 0` + `jne` con lock (`call 0x5954f0` due
volte) — il pattern classico di un singleton con lazy init. Confidenza: **strong**.

**Conseguenza pratica per il canary**: la configurazione viene letta **una sola volta per
processo**, alla prima invocazione. Se la shader cache è calda e non viene compilato nulla, il
parser potrebbe non essere mai invocato — e l'assenza di accessi al file **non proverebbe** che
il meccanismo è morto. È l'ambiguità principale del test 2A, ed è documentata prima di eseguirlo.

### Le tre sorgenti di configurazione, con il codice

```asm
; 1) file di configurazione
0x58bbfb   lea  rcx, ["AMD_SC_CFG_FILE"]
0x58bc02   call 0x79b844                  ; getenv-like: nome in RCX, char* o NULL in RAX
0x58bc07   lea  rbx, ["amdsc.ini"]        ; default
0x58bc0e   test rax, rax
0x58bc11   cmovne rbx, rax                ; se la env var c'e', usa quel path

; 2) environment con prefisso
0x58bde6   lea  rdx, ["AMD_SC_"]          ; lunghezza 7 passata in r8d
0x58bdf0   call 0x17ccf40                 ; scansione dell'environment per prefisso

; 3) stringa di opzioni
0x58c286   lea  rcx, ["AMD_SC_OPTIONS"]
0x58c28d   call 0x79b844                  ; stesso getenv-like
```

Tre sorgenti indipendenti, tutte **environment/file**, nessuna nel Registry.
Il gruppo si chiama `"CompilerControl options"`; i messaggi d'errore boost
(`unrecognised option '%canonical_option%'`) sono nello stesso cluster di stringhe.

## 2. Opzioni di dump (2C) — nomi, tipi, descrizioni esatte

Definite in **`0x58ada0`** (768 byte), gruppo `"Dump options"`. Il pattern per ogni opzione è:

```asm
call 0x5952b0                 ; crea il value_semantic (typed_value<bool>, 0xb8 byte)
lea  r9,  [descrizione]       ; 4o arg
mov  r8,  rax                 ; 3o arg = semantic
lea  rdx, [nome-opzione]      ; 2o arg = nome
call 0x17227b0                ; options_description_easy_init::operator()
```

| # | opzione | tipo | descrizione (stringa nel binario) | RVA def |
|---|---|---|---|---|
| 1 | `dump-prefix` | **string** | "Common prefix for dump files (may contain path with forward slashes)" | `0x58af55` |
| 2 | `dump-all` | bool | "Dump input and output shader with related data in text format" | `0x58af76` |
| 3 | `dump-il-text` | bool | "Dump IL text only" | `0x58af97` |
| 4 | `dump-il-binary` | bool | "Dump IL binary only" | `0x58afb8` |
| 5 | `dump-input-xml` | bool | "Dump entire SC input in machine readable XML format" | `0x58afd9` |
| 6 | `dump-sp3-binary` | bool | "Dump sp3 binary only" | `0x58affa` |
| 7 | `dump-separate` | bool | "Dump into a separate .txt file for each shader" | `0x58b01b` |
| 8 | `dump-append-pid` | bool | "Append process ID to dump file name" | `0x58b03c` |

**Tipi — evidenza.** Sette opzioni condividono la factory `0x5952b0`; `dump-prefix` ne usa una
diversa, costruita inline a `0x58aec2`. Entrambe allocano 0xb8 byte con due vtable pointer
(`boost::program_options::typed_value<T>`), **ma con vtable diverse** → tipi diversi.
Combinato con le descrizioni ("Common prefix … may contain path"), `dump-prefix` è una **stringa**
e le altre sette sono **booleane**. Confidenza: **strong**.

**Default di `dump-prefix`**: i campi stringa della struttura vengono inizializzati vuoti
(capacità SSO 0xf, byte 0 a offset 0x18/0x40/0x68) e **non ho trovato una chiamata
`default_value`**. Quindi il default è verosimilmente **vuoto**, non `"amdsc"`. La stringa
`amdsc` presente a `0x471367c` è adiacente ma ha un altro uso — **non l'ho collegata**, e non la
spaccio per il default.

**Consumer.** Ogni opzione è letta da funzioni distinte, il che conferma che non sono decorative:

| opzione | funzioni consumer |
|---|---|
| `dump-all` | `0x58ccc0`, `0x58d8b0`, `0x58e920`, `0x58ea90`, `0x58ee10`, `0x58f040` |
| `dump-separate` | `0x58dfd0`, `0x58e920`, `0x58ea90`, `0x58f8f0` |
| `dump-il-text` | `0x58ccc0`, `0x58e920` |
| `dump-il-binary` | `0x58ccc0` |
| `dump-input-xml` | `0x58ee10`, `0x58f040` |
| `dump-sp3-binary` | `0x58d8b0` |
| `dump-append-pid` | `0x58dfd0`, `0x58f8f0` |
| `dump-prefix` | `0x597e90` |

Stringhe correlate già individuate: `Shader_%016llx`, `_il.bin`, `_sp3.bin`, `.xml`,
`_%016llx_%02u`, `Input shader`, `Output shader`, `Shader ID: `.
Il naming per **shader hash a 64 bit** è coerente con l'obiettivo `shader hash → IL → ISA`.

> **Nessuna di queste otto opzioni tocca il codegen** secondo le loro descrizioni: sono output.
> Ma finché il canary non dimostra che il parser è vivo, non le attivo.

## 3. Catalogo delle 272 `SCOption_*` (2D)

File: [`../09_umd_settings/sc_options.csv`](../09_umd_settings/sc_options.csv) — 272 righe.

**Struttura scoperta**: le 272 stringhe sono puntate da un **array contiguo di `const char*`**
in `.rdata`, base RVA **`0x2722060`**, stride 8, 272 entry.
**L'indice nell'array è l'ID dell'opzione**:

```
[  0] SCOption_C0        [  1] SCOption_C1  ...  [  4] SCOption_C4
[  5] SCOption_R1000_DISABLE_INDEXED_RESOURCE_TYPE_CHECK
[ 20] SCOption_MINIMIZE_VGPRS
```

La base della tabella è referenziata da 4 funzioni: **`0x58ada0`** (la stessa che registra le
Dump options), `0x58ccc0`, `0x5d8590`, `0x879950`. Che la tabella sia usata dalla funzione di
costruzione delle `options_description` è l'indizio più forte che **le SCOption siano esposte
come opzioni del parser**, non solo come stringhe di debug. Confidenza: **probable**.

| categoria | n |
|---|---:|
| other | 104 |
| hw_workaround | 48 |
| memory_lds_cache | 34 |
| float_precision | 24 |
| optimization_pass | 19 |
| scheduling | 19 |
| register_allocation | 12 |
| wave_size_occupancy | 9 |
| debug | 3 |

### RDNA2 (gfx10.3) — le più interessanti

62 opzioni hanno un prefisso `GFX10*`/`R1000*`, 34 sono di altre architetture, 176 sono generiche.
Fra quelle potenzialmente rilevanti per RDNA2 nelle categorie che contano:

| idx | opzione |
|---:|---|
| 178 | `SCOption_GFX10_CS_DEFAULT_WAVE64_FOR_64_THREADS` |
| 179/180 | `SCOption_GFX10_ENABLE_SUBVECTOR`, `…_SHARED_VGPRS` |
| 184/185 | `SCOption_GFX10_FORCE_WAVE32_SCHEDULING`, `…WAVE64_SCHEDULING` |
| 186/187 | `…FORCE_WAVE32_SCHEDULING_FOR_PS`, `…FORCE_WAVE64_SCHEDULING_FOR_CS` |
| 190 | `SCOption_GFX10_DISABLE_CLAUSES` |
| 192 | `SCOption_GFX10_ENABLE_ML_MODEL_FOR_PS_WAVESIZE_CHOICE` |
| 213 | `SCOption_GFX10_ENABLE_SCML_PHASE3_FOR_INSTRUCTION_SCHEDULING` |
| 20 | `SCOption_MINIMIZE_VGPRS` (generica) |

**Limite dichiarato dell'euristica**: la classificazione per architettura è fatta per
sottostringa. `GFX101` (gfx10.1, RDNA1) viene catturato dal filtro `GFX10`, e RDNA2 è gfx10.3:
la colonna `rdna2_relevant` va letta come *candidato*, non come certezza. Le mappature
`R1000→GFX10`, `R1100→GFX11`, `R1200→GFX12` sono **inferenze dal prefisso**, non verificate.

### Cosa NON è determinato in 2D

`datatype` (marcato *probable: boolean*), `default`, `range/enum` e l'effetto reale di ciascuna
opzione restano **non determinati**. Servirebbe il codice del loop che registra la tabella e dei
punti di consumo, funzione per funzione. I nomi suggeriscono, non dimostrano.

## 4. Stato e prossimo passo

| fase | stato |
|---|---|
| 2B struttura parser | **fatta** (staticamente) |
| 2C opzioni di dump | **fatta**: 8 nomi, tipi, descrizioni, consumer |
| 2D catalogo 272 opzioni | **fatto** per nome/indice/categoria; tipi e default no |
| **2A canary a runtime** | **da eseguire** — richiede Steel Nomad dalla GUI |

Il canary è l'unico passo che può dire se tutto questo è **vivo nella build retail**.
Finché non lo è, nessuna opzione viene attivata.
