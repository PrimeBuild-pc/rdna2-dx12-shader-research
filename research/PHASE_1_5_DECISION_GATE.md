# Phase 1.5 — Decision gate

Aggiornato **2026-09-04 (2)**. Ramo A (ETW): **CHIUSO** — 4 catture, l'ultima con PresentMon
valido (→ [`08_etw_fortnite/RESULTS.md`](08_etw_fortnite/RESULTS.md)).
Ramo B (settings UMD): **completo**, non ancora testato a runtime.
ETL cancellati dopo l'analisi (~50 GB); CSV derivati conservati.

Nessun driver modificato, nessun tuning file creato, shader cache non toccata, nessun
esperimento anti-cheat, nessun export invocato, nessuna variabile d'ambiente impostata.

Dettagli: [`08_etw_fortnite/RESULTS.md`](08_etw_fortnite/RESULTS.md) ·
[`08_etw_fortnite/fortnite_etw_analysis.md`](08_etw_fortnite/fortnite_etw_analysis.md) ·
[`09_umd_settings/umd_settings_analysis.md`](09_umd_settings/umd_settings_analysis.md)

---

## Le tre cose che hanno spostato il quadro

1. **`GetSettingsBlobsAllDecoded` è `xor eax,eax; ret`** — uno stub vuoto. Il probe standalone
   non va costruito: non produrrebbe niente. `GetSettingsBlobsAll` è invece reale
   (`uint32_t f(void* buf, uint32_t size)`, pattern query-size-then-fill) ma dipende da un
   globale popolato solo dall'init del driver: da un host che fa solo `LoadLibrary` ritorna
   `{version=1, count=0}`.

2. **`DXCTuningsFileName` è un meccanismo del kernel-mode driver, non dell'UMD.** La stringa non
   esiste in `amdxc64.dll` (né ASCII né UTF-16); esiste **solo** in `amdkmdag.sys`. È viva nel
   registro sotto la chiave del *servizio*
   (`Services\amduw23g-203303-6af680f4\Parameters`) — non sotto la classe device, motivo per cui
   la Fase 1B non l'aveva trovata. I file puntati non esistono da nessuna parte. **Strada chiusa.**

3. **Esiste davvero un'interfaccia di configurazione del compilatore shader, ed è
   environment/file-based.** Dentro l'UMD DX12 c'è un parser boost::program_options completo con
   `AMD_SC_OPTIONS`, `AMD_SC_CFG_FILE` (fallback `amdsc.ini`), `AMD_DXCP_TEST_OPTIONS`,
   `AMD_CONFIG_DIR`, `EnableGlobalSettingsDumping` / `GlobalSettingsDumpFile`, e un catalogo di
   **272 opzioni `SCOption_*`** in una tabella di puntatori indicizzata — fra cui
   `SCOption_MINIMIZE_VGPRS`, `SCOption_GFX10_FORCE_WAVE64_SCHEDULING_FOR_CS`,
   `SCOption_LIVENESS_BASED_INSTRUCTION_SCHEDULING`, `SCOption_PBQP_REGISTER_ALLOCATION`.
   Più un blocco di opzioni di **dump** (`dump-input-xml`, `dump-il-text`, `dump-sp3-binary`,
   `dump-prefix`, nomi file `Shader_%016llx`).

   Nessuna di queste tocca un file firmato. È esattamente il "meccanismo di configurazione già
   previsto dal driver" che cercavamo — e in più il dump per shader hash è il pezzo mancante
   della catena `shader hash → ISA → costo GPU`.

   **Non è ancora dimostrato che siano attive nella build retail.** Il parser c'è, la condizione
   di abilitazione non l'ho isolata.

---

## Tabella di decisione

| Path | Evidence | Potential | Difficulty | Next step |
|---|---|---|---|---|
| **Fortnite CPU / AMD UMD** | **CHIUSO.** Thread del percorso critico identificato quantitativamente (`MsCPUBusy` x fps = 0.9098 core; TID 18844 = 0.9152 core, scarto 0.6%; il thread con il 26% di `amdxc64` vale 0.4373 core → escluso). Su quel thread `amdxc64.dll` = **2.1%**, riprodotto identico su 2 sessioni indipendenti e 4 run. Il percorso critico e' all'**84% `ntoskrnl.exe`**, in 3 pagine | **Nullo per questo target**: 2.1% ≈ 0.03 ms/frame. Un −25% del costo UMD varrebbe 0.5% del frametime, contro una MDD del 2.2% → non misurabile | — | **Nessuno.** Non spendere altro tempo sull'UMD *per Fortnite Performance Mode*. Resta valida la mappa del codice caldo (204 pagine, top-10 = 29.4%) per altri carichi |
| **AMD hidden settings** | `AMD_SC_OPTIONS` / `AMD_SC_CFG_FILE` → helper getenv con fallback `amdsc.ini`, xref confermati a `0x58bbfb`/`0x58c286` (**strong**); 272 `SCOption_*` in tabella di puntatori (**confirmed** come dato, semantica **probable**); `EnableGlobalSettingsDumping` letta via provider di settings, dietro un `cmp eax,1` non identificato (**strong**) | **Alto se attivo**: tuning del codegen e dump ISA per shader hash senza toccare nulla di firmato. **Nullo se gated** | Bassa per il test di esistenza; media per la sintassi | Test di reazione a costo quasi nullo: env var con sintassi volutamente errata, **solo su Steel Nomad**, mai su Fortnite/Warzone. Reazione ⇒ vivo; silenzio ⇒ chiuso |
| **DX12 compiler / codegen** | Compilatore statically-linked in `amdxc64.dll` (6 import, tutti Windows, zero dipendenze AMD — **confirmed**); serializzatori Boost/XML di `_SC_COMPILE_FLAGS`, `_SC_CACHE_POLICY`, `_E_SC_SI_OPT_MINIMIZE_VGPRS_STRATEGY`; Steel Nomad GPU-bound al 99.9% con rumore ±0.11% | **Alto sui carichi GPU-bound**, ~nullo su Fortnite Performance (15% di headroom GPU) | Alta senza la leva settings; **media se `AMD_SC_OPTIONS` è attiva** | Dipende dal ramo settings. Se vivo: A/B su Steel Nomad, dove 0.2% è già misurabile. Se morto: serve Ghidra mirato, e solo dopo l'ETW |
| **Shader / cache** | 515 MB in `DxcCache`, 63 file in `DxCache` (censiti, **non ispezionati**); `ShaderCache@Scpc@@` e `ShaderCacheDecorator@Scpc@@` presenti nell'UMD (**confirmed** come stringa); opzioni di dump per shader hash `Shader_%016llx` (**strong**); nessuna evidenza di stutter da compilazione nelle 7 run Fortnite — ma erano tutte a **cache calda** | **Medio-alto**: è la via per la catena `shader hash → cache blob → ISA → costo`. Il caso cold-cache non è mai stato misurato | Media | Dopo il gate ETW: baseline hash/size della cache, ProcMon su un avvio, poi cold vs warm. Cancellazione **manuale, decisa da te**. Backup per copia prima di tutto |

---

## Raccomandazione (aggiornata 2026-09-04)

**1. Una cattura di chiusura da 60 s.** `.\tools\capture_etw.ps1 -Run 4 -Seconds 60 -ProfInt 2441`
— lo script ora avvia PresentMon su una sessione ETW dedicata (`-PresentMonSession`), che era
la causa dei CSV mancanti. Serve solo a decidere fra 2% e 27%, ed è l'ultima cosa che manca
per chiudere il ramo A.

**2. In parallelo, il test di reazione di `AMD_SC_OPTIONS` su Steel Nomad** — costa quasi nulla
e se il meccanismo è vivo cambia la natura dell'intero progetto: da reverse engineering di un
binario da 82 MB a uso di un'interfaccia di configurazione che AMD ha già previsto.

**Non fare ancora**: Ghidra a tappeto, tuning file, esperimenti sulla cache, qualunque env var
su Fortnite o Warzone.
