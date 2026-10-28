# Phase 2L — Ottimizzazione end-to-end su workload D3D12 reale

RX 6950 XT, driver 32.0.21045.5002. Predictor, measurement memory e criteri di accettazione
di 2J/2K **non modificati**. Nessun gioco multiplayer usato.

Workload: **MiniEngine ModelViewer** (DirectX-Graphics-Samples), scena Sponza, costruito
localmente da sorgente. Dati: [`baseline_profile.csv`](baseline_profile.csv) ·
[`pass_ranking.csv`](pass_ranking.csv) · [`ab_bitonic.csv`](ab_bitonic.csv) ·
[`ab_culling.csv`](ab_culling.csv).
Codice: [`tools/run2l.py`](../../tools/run2l.py) · [`tools/ab2l.py`](../../tools/ab2l.py).

---

## Risposta alla domanda

> **L'AI optimizer produce un miglioramento misurabile dell'applicazione reale, non soltanto
> dello shader isolato?**

**No. Su questo workload il guadagno end-to-end è zero.** Due integrazioni misurate:

| set integrato | pass bersaglio | Δ pass | Δ GPU frame | spread frame |
|---|---|---:|---:|---:|
| `bitonic` (2 shader, micro −79.9% e −51.2%) | Culling & Sorting | **+1.24%** | **−0.27%** | 1.0–1.3% |
| `culling` (2 shader, micro −76.4% e −65.8%) | Culling & Sorting | **+1.83%** | **+0.35%** | 0.4–0.7% |

Nessuna delle due supera il rumore, e in entrambi i casi il *pass bersaglio* è **peggiorato**.

Il risultato è negativo, ma le cause sono state isolate e sono tutte concrete. Sono la parte
utile di questa fase.

## 1. Criterio di scelta del workload, dichiarato prima del profiling

1. D3D12; 2. compila ed esegue con la toolchain locale; 3. workload ripetibile; 4. contiene
shader già nel corpus 2K; 5. **non** scelto in base a quali guadagni microbench contiene.

51 dei 58 shader del corpus 2K vengono da `MiniEngine/Core/Shaders`, quindi il criterio (4)
porta a MiniEngine indipendentemente dai risultati. ModelViewer è l'unico sample eseguibile
di quel progetto e include Sponza (825 MB di asset già nel repo).

Build: MSBuild, toolset v145, configurazione **Profile** (in Release gli scope del profiler
sono compilati via). Ha richiesto il restore dei pacchetti NuGet e l'import di `vcpkg`.

## 2. Strumentazione aggiunta all'applicazione

MiniEngine ha già un profiler GPU annidato con scope nominati. Ho aggiunto quattro cose:

- **modalità benchmark headless**: `ME_BENCH_FRAMES` / `ME_BENCH_WARM` frame senza input, poi
  export ed uscita;
- **export CSV** dell'albero dei timer (nome, profondità, ms GPU/CPU, campioni);
- **media su tutti i frame misurati**: `StatHistory::GetAvg()` media solo sugli **ultimi 64
  frame**, quindi allungare la misura non riduceva il rumore. Con l'accumulo su tutti i frame
  lo spread run-to-run del frame è passato da **18.03% a 1.13%**;
- **VSync disattivo in benchmark, ma passo temporale fisso a 1/60**: senza VSync la GPU non
  resta ferma fra i frame (i clock non oscillano), col passo fisso il lavoro per frame non
  dipende da quanto è andata veloce la GPU nel frame precedente.

Le prime due sono strumentazione; le ultime due sono la differenza fra una misura utilizzabile
e una inutile.

## 3. Baseline e ranking per costo reale

GPU frame **1.0680 ms** (mediana su 7 run, spread 1.13%), 2000 frame misurati dopo 400 di
warm-up, risoluzione della finestra di default.

| # | pass | GPU ms | % frame | shader | nel corpus 2K |
|---:|---|---:|---:|---|---|
| 1 | Render Color | 0.5202 | **48.71%** | pixel/vertex shader | **no** |
| 2 | Resolve Image | 0.1017 | 9.53% | `TemporalBlendCS` | sì, 0 varianti accettate |
| 3 | Generate SSAO | 0.0774 | 7.25% | `AoRender*`, `AoPrepareDepthBuffers*`, `AoBlur*` | in parte |
| 4 | Particle Render | 0.0647 | 6.06% | vedi Culling & Sorting | |
| 5 | HDR Tone Mapping | 0.0558 | 5.22% | `ToneMapCS` | sì, 0 accettate |
| 6 | Render Shadow Map | 0.0485 | 4.54% | grafica | no |
| 7 | Culling & Sorting | 0.0474 | 4.44% | `ParticleBinCulling*`, `ParticleLargeBinCulling*` | sì |
| 8 | Z PrePass | 0.0400 | 3.75% | grafica | no |
| 9 | Sharpen or Copy Image | 0.0349 | 3.26% | `ResolveTAACS`/`SharpenTAACS` | sì, 0 accettate |
| 10 | Generate Bloom | 0.0256 | 2.40% | `BloomExtract*`, `DownsampleBloom*`, `UpsampleAndBlur` | sì |
| 11 | MotionBlur | 0.0251 | 2.35% | `MotionBlur*` | sì |
| 12 | Particle Update | 0.0240 | 2.24% | `ParticleUpdateCS`, `ParticleSpawnCS` | sì |
| 13 | Update Exposure | 0.0122 | 1.15% | `AdaptExposureCS`, `ExtractLumaCS` | sì |

**Il tetto di Amdahl è basso e va detto subito**: il pass più grosso, che da solo è metà del
frame GPU, è composto da pixel e vertex shader — **fuori dal corpus 2K, che è solo compute**.
Tutti i pass compute raggiungibili sommano circa il **33%** del frame.

## 4. Prima integrazione: il bersaglio non veniva eseguito

Scelta per costo: `Culling & Sorting` (4.44%), dove la memoria delle misure aveva i guadagni
più grandi (`Bitonic32PreSortCS` −79.93%, `Bitonic32InnerSortCS` −51.18%).

Risultato: **Δ frame −0.27%**, dentro il rumore. Indagando:

- `BitonicPreSortCS` e `BitonicInnerSortCS`, quelli con −77.43% e −42.14% in 2K, vengono da
  **`Libraries/D3D12RaytracingFallback`**, non da MiniEngine: l'applicazione non li contiene
  nemmeno.
- `ParticleEffectManager` chiama `BitonicSort::Sort(..., IsPartiallyPreSorted=true, ...)`:
  con quel flag **il PreSort non viene mai dispatchato**.
- Ho aggiunto uno scope `ScopedTimer(L"Bitonic Sort")` dentro `BitonicSort::Sort`: **non
  compare mai nel profilo**. La chiamata sta in `RenderSprites`, ma la scena usa il percorso
  **tiled rendering** (`EnableTiledRendering` di default), quindi `RenderSprites` non viene
  chiamata affatto.
- `Bitonic64*CS.hlsl` sono `#include` di `Bitonic32*CS.hlsl` con una define: hanno **0 cicli
  propri**, quindi la trasformazione testuale non li tocca.

> **Ho ottimizzato shader che l'applicazione non esegue.** Il microbenchmark non poteva
> saperlo: misura uno shader compilabile, non uno shader raggiunto.

## 5. Le bocciature di correttezza di 2K erano falsi negativi

Gli shader effettivamente eseguiti da `Culling & Sorting` — `ParticleBinCullingCS`,
`ParticleLargeBinCullingCS` — in 2K erano stati **scartati per correttezza**
(`fuori_tolleranza`, max rel 0.38 e 0.18).

Controllo fatto in questa fase: ho misurato **lo stesso identico `.cso` due volte** con nomi
diversi nella stessa esecuzione.

| shader | stesso binario, due esecuzioni | max rel |
|---|---|---:|
| `ParticleBinCullingCS` | **output DIVERSO** | 3.85e−01 |
| `ParticleLargeBinCullingCS` | **output DIVERSO** | 1.85e−01 |
| `ParticlePreSortCS` | **output DIVERSO** (byte) | 0 |
| `ToneMapCS` | identico | 0 |

Questi shader sono **non deterministici di per sé** (append buffer e atomiche con ordine di
scrittura non garantito). Il gate numerico di 2K stava misurando la loro nondeterminatezza,
non l'effetto della trasformazione. **12.5% di scarto per correttezza in 2K include falsi
negativi di questa natura, e non avevo mai testato il caso.**

Correzione meccanica e a costo zero, da adottare: **prima di giudicare una variante, misurare
la baseline due volte.** Se la baseline non è deterministica, il gate numerico non è
applicabile e serve un altro oracolo.

## 6. Seconda integrazione: il guadagno si inverte

Sbloccati dal punto 5, ho integrato `all_unroll4` sui due shader di culling realmente eseguiti.

**Amdahl calcolato prima**: `Culling & Sorting` = 4.31% del frame; anche un −76% su tutto il
pass darebbe al massimo **−3.3% di frame**.

Misurato: **pass +1.83%, frame +0.35%**. Il −76.4% del microbenchmark è diventato una
regressione.

Le cause plausibili, in ordine di forza dell'evidenza:

1. **Le dimensioni di dispatch sono diverse di ordini di grandezza.** Il microbenchmark 2K
   dispatcha ~1 M thread con risorse finte; l'applicazione usa `DispatchIndirect` con conteggi
   derivati dai dati, e in questa scena le particelle sono poche. Uno shader che a 1 M thread
   è latency-bound, a poche centinaia di thread è dominato dal costo di lancio.
2. **I dati sono diversi.** In 2K il constant buffer è riempito con valori plausibili ma
   inventati; i cicli di culling sono guidati dai dati, quindi il numero di iterazioni reale
   non ha niente a che vedere con quello misurato.
3. `[unroll(4)]` aumenta il codice e i registri: con pochi wave in volo il costo si vede,
   il beneficio (più operazioni indipendenti in volo) no.

Non ho modificato il microbenchmark per far coincidere i numeri.

## 7. L'oracolo di correttezza a livello di frame non regge

Avevo verificato che il frame finale fosse bit-exact deterministico e l'avevo usato come
oracolo: 3 run identiche, poi 4 run identiche a 2000 frame.

**Con 6 run la build non modificata produce 2 hash distinti** (5× `d9d52bd0`, 1× `eb49a983`).
Il frame **non** è deterministico: lo è quasi sempre. I miei test precedenti erano
semplicemente troppo corti.

Conseguenza onesta: **tutti i verdetti "immagine DIVERSA" di questa fase sono
ininterpretabili** — non distinguono la trasformazione dalla nondeterminatezza dell'app. Serve
un confronto con tolleranza su molte esecuzioni, che non ho costruito.
È coerente con il punto 5: gli shader di culling sono nondeterministici e alimentano il render.

## 8. Confronto microbenchmark ↔ workload reale

| shader | micro 2K | pass reale | trasferimento |
|---|---:|---:|---|
| `Bitonic32PreSortCS` | −79.93% | **mai eseguito** | nessuno |
| `Bitonic32InnerSortCS` | −51.18% | **mai eseguito** | nessuno |
| `ParticleBinCullingCS` | −76.43% (falso scarto) | **+1.83%** sul pass | **invertito** |
| `ParticleLargeBinCullingCS` | −65.75% (falso scarto) | idem | **invertito** |

Zero su quattro. Il microbenchmark, così com'è, **non predice** il comportamento nel frame.

## 9. Limiti dichiarati

- Una sola scena, una sola configurazione, una sola risoluzione. Con più particelle o a
  risoluzione maggiore il bilancio dei pass cambierebbe.
- `[WaveSize(N)]` — la trasformazione più spesso accettata in 2K — richiede shader model 6.6;
  l'applicazione compila a **6.2**. Non l'ho testata: alzare il modello avrebbe cambiato il
  codegen della baseline, e volevo un A/B a configurazione invariata. È un vincolo reale di
  integrazione, non un dettaglio.
- Il tempo di frame è dominato dai pixel shader, che il corpus 2K (solo compute) non copre.
- Le misure per-pass hanno spread 2–8%; solo il frame totale scende sotto l'1%.

## 10. Cosa dice questa fase

La catena `applicazione → profilo → scelta → ottimizzazione → ricompilazione → misura` **è
stata percorsa per intero e funziona come infrastruttura**. Quello che non funziona è il
passaggio dal microbenchmark al frame, e ora se ne conoscono i motivi precisi.

Le tre correzioni che servono prima di rifare questa fase, in ordine di importanza:

1. **Profilare prima, misurare dopo.** Il corpus va costruito dagli shader che il workload
   *esegue*, con le loro *vere* dimensioni di dispatch, non da quelli che compilano.
2. **Testare la determinatezza della baseline** prima di applicare qualunque gate numerico,
   sia sullo shader sia sul frame.
3. **Riprodurre nel microbenchmark il dispatch reale** (conteggi indiretti inclusi), altrimenti
   il numero misurato riguarda un carico che non esiste.

Solo dopo queste tre ha senso parlare di workload commerciali.
