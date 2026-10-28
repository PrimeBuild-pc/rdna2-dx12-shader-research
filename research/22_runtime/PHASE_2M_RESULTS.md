# Phase 2M — Runtime-First Hot Shader Optimization

RX 6950 XT, driver 32.0.21045.5002. Workload: **MiniEngine ModelViewer / Sponza**, costruito
da sorgente. Nessun gioco multiplayer usato. Phase 2J/2K/2L non modificate retroattivamente.

Dati: [`runtime_inventory.csv`](runtime_inventory.csv) · [`shader_map.csv`](shader_map.csv) ·
[`hot_ranking.csv`](hot_ranking.csv) · [`ab2m_lighting_all_unroll4.csv`](../21_workload/ab2m_lighting_all_unroll4.csv) ·
[`ab2m_lighting_all_loop.csv`](../21_workload/ab2m_lighting_all_loop.csv).
Codice: [`tools/run2l.py`](../../tools/run2l.py) · [`tools/ab2m.py`](../../tools/ab2m.py) ·
[`tools/map2m.py`](../../tools/map2m.py) · `Core/ShaderInventory.{h,cpp}` nell'app.

---

## Risposta alla domanda

> **Partendo dal profiling reale e ottimizzando uno shader realmente hot, riusciamo finalmente
> a ridurre il GPU frame time?**

**No.** Ma per la prima volta il bersaglio era quello giusto, e il motivo per cui non si può
migliorare è stato misurato, non ipotizzato.

| trasformazione su `Lighting.hlsli` (incluso solo da `ModelViewerPS`) | Render Color | GPU frame |
|---|---:|---:|
| `all_unroll4` | **+0.61%** | +0.56% |
| `all_loop` | **+0.36%** | −0.10% |

Nessuna migliora. E la sonda che segue spiega perché nessuna *potrebbe*.

## 1. Ambiente pulito

Prima delle misure: Chrome, Discord, browser e player chiusi e **verificati** a zero processi.
Con Chrome attivo (≈1000 s di CPU cumulativa) i run non sono considerati validi.
Spread run-to-run del GPU frame in ambiente pulito: **0.5–1.4%** su 5–7 run.

## 2. Inventario runtime degli shader realmente eseguiti

Aggiunto all'applicazione `Core/ShaderInventory.{h,cpp}`, agganciato a `SetPipelineState`,
`Dispatch`, `DispatchIndirect`, `DrawInstanced`, `DrawIndexedInstanced` e agli scope del
profiler. Registra per frame: scope → PSO → **hash FNV-1a del bytecode VS/PS/CS** → numero di
chiamate → dimensioni reali di dispatch/draw.

Risultato: **40 istanze shader realmente eseguite**, tutte mappate al sorgente.

### La mappatura va fatta per hash, non per nome

Due volte in questo progetto ho associato uno shader al sorgente per nome o per ipotesi, e due
volte era sbagliato (2L: `BitonicPreSortCS` di un'altra libreria; 2M: la prima lettura del
percorso di rendering). L'inventario registra l'hash del bytecode; `map2m.py` ricalcola lo
stesso FNV-1a sugli array `g_p*` degli header generati dalla build e li confronta.

Il PSO di `Render Color` si chiama **"Sponza: Depth PSO"** perché MiniEngine fa
`m_ModelPSO = m_DepthPSO` e la copia porta con sé il nome. Solo l'hash dice la verità:
`ps=52CE6C5E…` = **`ModelViewerPS`, 12 612 byte** — confermato indipendentemente compilando
lo stesso sorgente con DXC (12 612 byte).

> Nota tecnica: gli header generati da DXC contengono un blocco di disassembly commentato pieno
> di numeri esadecimali. La prima versione dello script li includeva nell'hash e lasciava
> 13 shader su 40 non risolti. Estraendo solo l'inizializzatore dell'array: **40/40 risolti**.

## 3. Ranking per costo reale

GPU frame **1.0680 ms**. I primi pass, con gli shader identificati per hash:

| pass | GPU ms | % frame | call/frame | shader |
|---|---:|---:|---:|---|
| **Render Color** | 0.5202 | **48.71%** | 28.90 | **PS `ModelViewerPS` + VS `ModelViewerVS`** |
| Resolve Image | 0.1017 | 9.53% | 1.00 | CS `TemporalBlendCS` |
| HDR Tone Mapping | 0.0558 | 5.22% | 1.00 | CS `ToneMap2CS` |
| Render Shadow Map | 0.0485 | 4.54% | 4.98 | PS/VS `DepthViewer*` |
| Culling & Sorting | 0.0474 | 4.44% | 2.99 | CS `ParticleBinCulling*`, `ParticleTileCulling` |
| Sharpen or Copy Image | 0.0349 | 3.27% | 1.00 | CS `SharpenTAACS` |
| Opaque (Z PrePass) | 0.0319 | 2.99% | 28.90 | VS `DepthViewerVS` (nessun PS) |

I primi 7 pass fanno il **76%** del frame GPU. Il primo da solo quasi metà.

## 4. Il risultato che conta: `Render Color` non è limitato dallo shader

Due sonde, entrambe non-candidate, servite solo a fissare il tetto di Amdahl **misurandolo**.

| sonda | cosa fa | bytecode PS | Render Color |
|---|---|---:|---:|
| baseline | — | 12 612 B | 0.5141 ms |
| **niente luci locali** | `return` in testa a `ShadeLights` (128 luci puntiformi/coniche) | 8 584 B | **+0.36%** |
| **PS completamente nero** | `mrt.Color = float3(0,0,0)` | ~4 900 B | **+0.66%** |

**Azzerare l'intero pixel shader — eliminando campionamento texture, illuminazione,
ombre, tutto — non cambia il tempo del pass.** Il codice del PS scende a un terzo e il pass
resta identico entro il rumore (spread 0.5–0.8%).

Confronto che rende il fatto interpretabile: `Opaque` (Z PrePass) disegna **la stessa geometria
con lo stesso conteggio di draw** (28.90/frame) senza pixel shader e costa 0.032 ms;
`Render Color` costa 0.520 ms, **16×**. Ma quel 16× non sta nell'ALU del pixel shader, perché
rimuoverla non serve a niente.

Resta quindi attribuibile a ciò che il pass fa **oltre** al codice dello shader: scrittura su
render target multipli a 1920×1080, traffico ROP, banda verso le texture, rasterizzazione,
test di profondità. **Nessuna di queste è raggiungibile da una trasformazione sorgente dello
shader**, che è l'unica leva che questo optimizer possiede.

Questo, e non il fallimento delle due trasformazioni, è il risultato di 2M: il bersaglio
giusto è stato individuato correttamente, e si è dimostrato **non ottimizzabile per via
software dello shader**.

## 5. Due difetti dei miei strumenti, trovati e dichiarati

**(a) Build incrementale incoerente → crash.** Dopo aver aggiunto membri alla classe `PSO`,
l'applicazione crashava con access violation (0xC0000005). Causa: Model e ModelViewer non
venivano ricompilati contro il nuovo layout della classe. Risolto con `-t:Rebuild`.
**Conseguenza operativa: dopo ogni modifica a un header condiviso serve un rebuild completo**,
altrimenti si misura un binario corrotto.

**(b) L'oracolo d'immagine è rotto.** Il dump del color buffer che avevo introdotto in 2L
**non riflette l'output del pixel shader**: con il PS forzato a nero il dump è
**byte-identico** al baseline (0.00% di pixel diversi su 8 MB, 115 599 valori distinti in
entrambi — quindi contiene dati veri, ma non quelli giusti).

Conseguenza da registrare con chiarezza: **tutti i verdetti "immagine identica/diversa" di 2L
e della prima parte di 2M vanno scartati.** Non ho una verifica di correttezza a livello di
frame funzionante. Non ne ho inventata una: la dichiaro assente.

Le misure di **tempo** non dipendono da questo bug — vengono dai timer GPU dell'applicazione,
il cui funzionamento è confermato dal fatto che rispondono correttamente ai cambiamenti di
carico misurati in 2L (es. `Culling & Sorting` +1.83%) e dallo spread stabile allo 0.5%.

## 6. Nondeterminismo

Classificazione richiesta dal brief, per quanto misurato finora:

| livello | shader |
|---|---|
| **intrinsecamente non deterministico** | `ParticleBinCullingCS`, `ParticleLargeBinCullingCS`, `ParticlePreSortCS` — lo stesso `.cso` eseguito due volte dà output diverso (2L) |
| **deterministico** | `ToneMapCS` e gli altri shader compute testati in 2K |
| **frame completo** | **non classificabile**: l'oracolo è rotto (punto 5b) |

Per gli shader del primo gruppo il confronto bit-exact del buffer intermedio non è applicabile,
come già stabilito in 2L.

## 7. Limiti dichiarati

- Una sola scena, una sola risoluzione (1920×1080), una sola configurazione grafica.
- `[WaveSize(N)]` non è applicabile ai pixel shader (è compute-only in SM 6.6), quindi la
  trasformazione più spesso accettata in 2K non è disponibile qui.
- Il catalogo meccanico per un PS si riduce agli attributi di ciclo: `Lighting.hlsli` ha
  22 cicli, tutti trasformabili, tutti provati in due direzioni. Non c'è altro di
  meccanicamente verificabile.
- Il "compute replay" con dispatch reali (punto 6 del brief) **non è stato fatto**: i dati per
  farlo ora ci sono (`runtime_inventory.csv` contiene gruppi e conteggi reali per ogni
  dispatch), ma la fase si è fermata prima, perché il pass dominante si è rivelato non
  ottimizzabile e proseguire sui pass minori non avrebbe cambiato la risposta.

## 8. Cosa dice questa fase

La disciplina "profile first" ha funzionato: l'inventario runtime e la mappatura per hash hanno
identificato senza ambiguità lo shader che vale il 48.7% del frame — cosa che né 2K né 2L
sapevano fare. Il problema si è spostato di un livello.

Le tre cose che seguono, in ordine:

1. **Capire cosa limita davvero `Render Color`.** Le sonde escludono l'ALU del pixel shader.
   Servono contatori hardware (RGP, o query di occupancy/ROP) per distinguere fra banda dei
   render target, texture e rasterizzazione. Finché non lo si sa, ottimizzare shader è cieco.
2. **Ammettere che alcune ottimizzazioni non sono trasformazioni di shader.** Ridurre il numero
   di render target, cambiare formato, o sfruttare il depth-equal della Z-PrePass sono modifiche
   dell'applicazione, non del codice HLSL. Sono fuori dalla portata attuale dell'optimizer.
3. **Riparare l'oracolo di correttezza a livello di frame**, o rinunciare esplicitamente a
   validare le trasformazioni end-to-end.
