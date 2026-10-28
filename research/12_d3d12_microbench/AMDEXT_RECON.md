# Ricognizione statica: `AmdExtD3DCreateInterface` / AMD AGS

Solo analisi statica su copie e conoscenza documentale. **Nessuna patch, nessuna modifica di
bitmask, nessuna esecuzione di codice del driver oltre alle normali compilazioni RGA.**

---

## 1. Lo stub è un forwarder puro

`C:\Windows\System32\amdxc64.dll` (142 736 B) è in realtà `amdxcstub64.dll` del DriverStore.
Analisi delle stringhe e degli export:

| | |
|---|---|
| Export | `AmdExtD3DCreateInterface`, `AmdGetDxcModuleHandle` — **due, nient'altro** |
| GUID testuali | **nessuna** |
| Stringhe di capability/compilatore | **nessuna** |
| Resto delle stringhe | solo RTTI MSVC, sezioni PE, import di `kernel32` |

Non contiene logica: carica l'UMD vero e inoltra. Le interfacce sono definite dentro
`amdxc64.dll` (82 MB), e le loro IID sono binarie — senza header pubblici non le si può mappare
a nomi con certezza, e **non le ho indovinate**.

## 2. Cosa espone davvero l'estensione, dal binario

Nel UMD ci sono **59 simboli `AmdExt*`**. Il quadro è netto: sono **intrinsics di shader e
operazioni di memoria**, non controlli del compilatore.

| famiglia | esempi (dal binario) |
|---|---|
| Atomiche a 32/64 bit | `AmdExtAtomicAddAtAddr`, `AmdExtAtomic64CmpXchgAtAddr`, `AmdExtAtomicAddAtAddrSystemScope` |
| Atomiche float | `AmdExtAtomicFMaxAtAddr`, `AmdExtAtomicFMinAtAddr`, `AmdExtAtomicLdsFMax/FMin` |
| Load costanti | `AmdExtConstantLoadDwordAtAddr`, `AmdExtConstantLoad64AtAddr` |
| Memoria device | `AmdExtDeviceMemoryAcquire`, `AmdExtDeviceMemoryRelease` |
| Thread ID | `AmdExtDispatchThreadIdFlat`, `AmdExtFlattenedThreadIdInGroupCompute` |
| Canale UAV | **`AmdExtD3DShaderIntrinsicsUAV`** |
| Creazione interfaccia | `AmdExtD3DCreateInterface` |

Conteggi di stringhe correlate: `WaveScan` 60, `ShaderIntrinsic` 11, `Ballot` 10, `AtomicU64` 5,
`WaveReduce` 1. Cioè: wave ops, ballot, scan, reduce — **operazioni che uno shader può
invocare**, esposte tramite uno slot UAV dedicato (`AmdExtD3DShaderIntrinsicsUAV`), il
meccanismo classico delle DirectX shader extension AMD.

## 3. Risposta alle quattro domande

**Quali API DX12 espone.** Creazione di un'interfaccia di estensione sul device
(`AmdExtD3DCreateInterface`) e un insieme di **intrinsics utilizzabili dagli shader** —
atomiche estese (incluse 64-bit e float min/max), load costanti, wave ops (ballot/scan/reduce),
ID di thread flat, acquire/release di memoria device. Il canale verso lo shader è uno slot UAV
riservato.

**Esiste un compiler control pubblico o semi-pubblico?** **No, dall'evidenza raccolta.** Fra i
59 simboli `AmdExt*` non ce n'è nessuno che nomini opzioni, flag, ottimizzazioni, register
allocation o scheduling. Nessuna stringa collega l'estensione alle 272 `SCOption_*` o al parser
`AMD_SC_OPTIONS` studiato nella fase 2E.

**Può influenzare wave size, shader compiler o codegen?** Solo **indirettamente e a livello di
sorgente**: usare un intrinsic (una wave op, un'atomica 64-bit) cambia il codice che il
compilatore riceve, quindi cambia l'ISA. Ma non c'è alcuna leva per dire al compilatore *come*
compilare. La wave size resta controllabile solo da HLSL con `[WaveSize(N)]` (SM 6.6) — la via
già usata e misurata in questa fase.

**Espone solo capability/intrinsics?** **Sì**, per quanto risulta da questa analisi:
capability + intrinsics, più la creazione dell'interfaccia. È coerente con quello che AGS
(AMD GPU Services), la libreria pubblica AMD, offre da sempre: informazioni su GPU e driver,
registrazione dell'applicazione, e appunto le shader extension/intrinsics.

> **Dichiarazione di fonte.** La parte su AGS come progetto pubblico è **conoscenza generale**,
> non verificata in questa sessione: non ho fatto richieste di rete e AGS non è installato sul
> sistema (nessun `amd_ags_x64.dll` trovato). Tutto ciò che riguarda i 59 simboli e lo stub è
> invece **verificato staticamente sul binario installato**. Se questa distinzione conta per una
> decisione, la parte AGS va confermata sulla documentazione ufficiale.

## 4. Conseguenza per il progetto

Questa strada **non riapre** l'accesso alle leve di codegen chiuso in 2E. L'estensione AMD è
un'API per *scrivere shader più potenti*, non per *pilotare il compilatore*.

Resta però interessante per un motivo diverso e concreto: gli intrinsics (wave ops, atomiche
float, load costanti) sono leve **lato sorgente** che cambiano l'ISA in modo verificabile, e
ora abbiamo un banco che ne misura l'effetto reale in nanosecondi. Se in futuro si vorrà
ottimizzare uno shader specifico, quella è una leva legittima, pubblica e senza rischi di firma.
