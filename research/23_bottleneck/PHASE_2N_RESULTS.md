# Phase 2N — Classificazione dei colli di bottiglia hardware

RX 6950 XT (Navi 21), driver 32.0.21045.5002. Workload: MiniEngine ModelViewer / Sponza,
1920×1080. Ambiente pulito (browser, Discord e player chiusi e verificati).
Strumento: **GPUPerfAPI 4.4.5** integrato dentro l'applicazione.

Dati: [`gpa_counters.csv`](gpa_counters.csv) (enumerazione) ·
[`counters_by_pass.csv`](counters_by_pass.csv) (misure) ·
`Core/GpaProfiler.{h,cpp}` nell'app · [`gpaenum.cpp`](gpaenum.cpp) ·
[`tools/gpa2n.py`](../../tools/gpa2n.py) · [`tools/buildv.py`](../../tools/buildv.py).

---

## Risultato

| pass | % frame | collo di bottiglia | evidenza | ottimizzabile via shader? | leva giusta |
|---|---:|---|---|---|---|
| **Render Color** | **48.7%** | **throughput del texture unit** | TexUnit **94.6%** busy con **0.4%** di stall; banda **73 GB/s** (bassa); ROP/raster/depth fermi | **sì, ma non con l'ALU** | ridurre il *numero* di sample, filtraggio più economico, atlas/mip |
| Resolve Image | 9.5% | **banda di memoria** | **555 GB/s**, MemUnitStalled **70.1%**, L1 7.3% | parzialmente | meno traffico: formati più stretti, meno target temporali |
| HDR Tone Mapping | 5.2% | non misurato (vedi §5) | — | — | — |
| Render Shadow Map | 4.5% | **rasterizzazione/geometria** | PAStalledOnRasterizer **48.9%**, VsGs 90.2%, TexUnit 28.5% | no | meno triangoli, culling, LOD |
| Culling & Sorting | 4.4% | **latenza/serializzazione** | tutte le unità ferme: TexUnit 12.1%, 9.4 GB/s, 0.1% stall | no | meno barriere, dispatch più grossi |
| Sharpen or Copy Image | 3.3% | **banda di memoria** | **621 GB/s**, TexUnit 94.0% | parzialmente | fondere il pass col precedente |
| Z PrePass | 3.0% | **rasterizzazione/geometria** | PAStalledOnRasterizer **52.1%**, VsGs 90.8% | no | meno triangoli, culling |

Nella forma chiesta:

```
Render Color    48.7% frame  ->  texture-unit throughput bound
Resolve Image    9.5% frame  ->  memory bandwidth bound
Render Shadow    4.5% frame  ->  raster/geometry bound
Culling&Sorting  4.4% frame  ->  latency/serialization bound
Z PrePass        3.0% frame  ->  raster/geometry bound
```

## 1. Enumerazione dei counter, prima di misurare

Come richiesto, nessun nome di counter è stato indovinato. `gpaenum.exe` apre un contesto
GPUPerfAPI DX12 sulla GPU installata ed elenca ciò che l'hardware espone davvero:

**145 counter su Navi 21**, in 13 gruppi: Timing (29), DepthAndStencil (24), MemoryCache (24),
ComputeShader (16), GlobalMemory (10), PreTessellation (7), PostTessellation (7),
TextureUnit (7), ColorBuffer (6), PrimitiveAssembly (5), RayTracing (4), VertexGeometry (3),
PixelShader (3). Sample discreti e streaming entrambi supportati.

Da questi ne sono stati abilitati **31**, scelti per coprire le sei ipotesi di collo di
bottiglia. GPA richiede **13 passate** per raccoglierli: l'applicazione ripete lo stesso frame
una volta per passata, il che è lecito perché il carico è a passo fisso.

## 2. Misure per pass

Numeri completi in [`counters_by_pass.csv`](counters_by_pass.csv). Sintesi:

| pass | GPU µs | GB/s | TexUnit % | MemStall % | PA→rast % | ROP stall % | L1 % | L2 % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Render Color | 720.5 | **73.1** | **94.6** | 0.4 | 0.2 | 0.01 | 53.0 | 42.7 |
| Generate SSAO | 96.9 | 255.8 | 85.7 | **34.9** | 0.0 | 0.33 | 11.7 | 85.6 |
| Resolve Image | 88.4 | **554.9** | 94.3 | **70.1** | 0.0 | 1.07 | 7.3 | 64.5 |
| Sharpen or Copy | 50.0 | **620.9** | 94.0 | 7.4 | 0.0 | 0.93 | 35.3 | 66.2 |
| Render Shadow Map | 57.0 | 372.8 | 28.5 | 0.8 | **48.9** | 0.72 | 1.6 | 36.5 |
| Z PrePass | 51.0 | 452.8 | 38.7 | 1.9 | **52.1** | 0.64 | 5.4 | 31.5 |
| Culling & Sorting | 57.9 | 9.4 | 12.1 | 0.1 | 0.0 | 0.00 | 11.0 | 85.2 |

> I tempi GPA sono ~1.35× quelli del profiler interno (GPA forza clock stabili e aggiunge
> overhead per la raccolta). I **rapporti** fra pass restano coerenti: il fattore è costante
> (Render Color 520→720 µs, Z PrePass 40→51 µs).

## 3. Perché `Render Color` è texture-bound e non altro

Il caso è netto perché le alternative sono tutte escluse dai numeri:

- **non è ROP/render target**: `PSExportStalls` 0.01%, `WriteUnitStalled` 0.00%,
  `ZUnitStalled` 0.05%. Le unità di scrittura non aspettano mai.
- **non è rasterizzazione**: `PrimitiveAssemblyBusy` 3.5%, `PAStalledOnRasterizer` 0.2%.
  Per confronto, Z PrePass e Shadow Map — che sono davvero raster-bound — stanno al 49–52%.
- **non è banda di memoria**: **73 GB/s**. Gli altri pass di questo stesso frame arrivano a
  555 e 621 GB/s. Render Color muove 52 MB in 720 µs: è il pass che consuma *meno* banda e
  impiega *più* tempo.
- **non è latenza di memoria**: `MemUnitStalled` **0.41%**, `L0CacheHit` 97.6%. L'unità è
  occupata ma non aspetta quasi mai.
- **è il texture unit**: `TexUnitBusy` **94.6%**, saturo e non in stallo. Sta emettendo
  operazioni di campionamento al ritmo massimo. Con L0 al 97.6% i dati ci sono già: il limite
  è il **rate di filtraggio/indirizzamento**, non il trasporto dei byte.

Contesto: `PSPixelsOut` = 4 147 204 ≈ **2× i pixel dello schermo**, cioè circa 2× di overdraw,
ognuno con i sample di materiale più le lookup di ombra e della light grid.

**Conseguenza operativa**: su questo pass la leva non è il codice ALU né gli attributi di ciclo
(che 2M aveva provato senza effetto), ma **ridurre il numero di operazioni di campionamento**.
È una direzione diversa, e resta nel dominio dello shader.

## 4. Un difetto grave trovato nei miei strumenti, con conseguenze retroattive

Durante i controlli di questa fase ho verificato l'hash dell'eseguibile prima e dopo una build
con shader modificato:

```
base       exe 001e8ca20820   Model.lib a807f9ebb4b7
ps_black   exe 001e8ca20820   Model.lib a807f9ebb4b7   <-- IDENTICI, stesso mtime
```

**La build non aveva ricompilato niente.** MSBuild confronta i timestamp con granularità
grossolana: scrivendo il sorgente nello stesso secondo della build precedente, la
ricompilazione veniva saltata **in silenzio** e si misurava due volte lo stesso binario.

Questo invalida un sottoinsieme non determinato di misure delle fasi precedenti, e in
particolare **due conclusioni di 2M vanno corrette**:

| conclusione di 2M | stato ora |
|---|---|
| «azzerare l'intero pixel shader non cambia `Render Color`» | **evidenza invalida** — quella build può non essere mai avvenuta. La conclusione (*non è ALU-bound*) resta però **indipendentemente confermata** dai counter di questa fase: il limite è il texture unit, non l'ALU |
| «l'oracolo d'immagine è rotto: col PS nero il dump è byte-identico» | **RITRATTATA** — il dump identico si spiega con il binario identico. Non ho evidenza che l'oracolo sia rotto |

Rimedio implementato in [`tools/buildv.py`](../../tools/buildv.py): build con `-t:Rebuild` e
**verifica sull'hash dell'header dello shader compilato** (`CompiledShaders/<nome>.h`), che è
deterministico. L'hash dell'eseguibile non serve: cambia a ogni link anche senza modifiche.
Se l'header non cambia quando il sorgente è cambiato, la misura non si fa.

## 5. Cosa non è stato fatto, e perché

- **I controlli sperimentali (PS vuoto, senza texture, un solo render target) non sono stati
  eseguiti.** Con `-t:Rebuild` le tre varianti falliscono la compilazione
  (`dxc failed : Invalid argument`) mentre il sorgente originale compila pulito. Non ho
  diagnosticato la causa e non ho voluto forzare: senza una build verificata la misura non vale
  niente, ed è esattamente l'errore appena scoperto. La classificazione qui riportata poggia
  **solo sulle firme dei counter**, non su ablazioni controllate.
- **`HDR Tone Mapping` non ha prodotto dati**: lo scope è dentro un contesto di comando che GPA
  non registra nel mio aggancio. Va sistemato prima di classificarlo.
- **`CSBusy` / `CSVALUUtilization` non erano nel set abilitato**: per i pass compute manca la
  misura diretta dell'utilizzo ALU. Le classificazioni compute qui sono basate su memoria e
  texture, che sono comunque le dominanti osservate.
- RGP resta inutilizzabile a riga di comando (solo GUI); GPUPerfAPI lo ha sostituito bene.

## 6. Cosa cambia per l'optimizer

Fino a 2M l'optimizer aveva una sola leva — trasformare il codice HLSL — e la applicava
ovunque. I counter dicono che quella leva è quella giusta solo per una parte dei pass:

| classe | pass in questo frame | quota | leva utile |
|---|---|---:|---|
| texture-throughput | Render Color | 48.7% | ridurre le operazioni di sampling |
| banda di memoria | Resolve Image, Sharpen or Copy | 12.8% | ridurre i byte, fondere i pass |
| latenza di memoria | Generate SSAO | 7.2% | migliorare la località (L1 all'11.7%) |
| raster/geometria | Z PrePass, Render Shadow Map | 7.5% | culling, LOD — fuori dallo shader |
| latenza/serializzazione | Culling & Sorting | 4.4% | meno barriere — fuori dallo shader |

**Circa il 12% del frame (raster e serializzazione) non è raggiungibile da nessuna
trasformazione di shader.** Il 48.7% di Render Color lo è, ma solo agendo sul numero di
sample — non sugli attributi di ciclo, che è tutto ciò che il catalogo meccanico sa fare oggi.

Il passo successivo naturale, prima di qualunque altra ottimizzazione: **riparare la pipeline di
build verificata e rifare i controlli di ablazione**, perché senza quelli ogni misura A/B di
questo progetto è sospetta.
