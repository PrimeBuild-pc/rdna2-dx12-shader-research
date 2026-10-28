"""Regenerate/check the four fullscreen runs, preserving raw data and prior analyses.

    python -B tools/c2077_scaling_check.py

The 720p one-frame uncertainty is an explicit post-diagnosis policy, not a
preregistered gate and not an exact frame-identity claim.
"""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

from c2077_native import analyze, match, selfcheck
from pmparse import FT, load

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/62_c2077_fullscreen_scaling"
NATIVE = Path.home() / "Documents/CD Projekt Red/Cyberpunk 2077/benchmarkResults"
RUNS = dict(fs1440_r1="21-00-10", fs1080_r1="21-05-02",
            fs720_r1="21-08-37", fs1440_r2="21-12-24")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    selfcheck()
    frozen = json.loads((BASE / "v2_provenance/input_sha256.json").read_text())
    for path, digest in frozen.items():
        assert sha(path) == digest, f"Historical input changed: {path}"
    spec = importlib.util.spec_from_file_location(
        "native_before", BASE / "v2_provenance/c2077_native.before.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    docs, diagnostics, gates = {}, {}, {}
    for name, stamp in RUNS.items():
        run = BASE / name
        native = NATIVE / f"benchmark_2026-09-08_{stamp}"
        metadata = json.loads((run / "metadata.json").read_text())
        d = load(run / "presentmon.csv")
        y = pd.read_csv(native / "frames.csv", skipinitialspace=True)["Frame time (ms)"].to_numpy(float)
        x = d[FT].to_numpy(float)
        a, r = old.match(x, y)
        size = min(1000, len(y)//3)
        original_checks = []
        for offset in (0, len(y)//2-size//2, len(y)-size):
            pos, score = old.match(x, y[offset:offset+size])
            original_checks.append(dict(native_offset=offset, row=pos,
                                        lag=int(pos-offset-a), correlation=score))
        q = d.CPUStartQPCTime.to_numpy(float)
        span = q[len(y)-1:] - q[:len(q)-len(y)+1]
        b = int(np.argmin(abs(span-y[:-1].sum())))
        diagnostics[name] = dict(original_global_row=a, original_correlation=r,
                                 original_block_checks=original_checks,
                                 proposed_duration_only_locator_row=b,
                                 proposed_locator_error_ms=float(span[b]-y[:-1].sum()))
        if name == "fs720_r1":
            assert any(c["lag"] != 0 for c in original_checks), "Original failure not reproduced"
        dest = run / "native_analysis_v2"
        if not dest.exists():
            with (run / "native_analysis_v2.log").open("x", encoding="utf-8") as log:
                with contextlib.redirect_stdout(log):
                    analyze(run, native, "native_analysis_v2", int(name == "fs720_r1"))
        doc = json.loads((dest / "analysis.json").read_text())
        for path, digest in doc["source_sha256"].items():
            assert sha(path) == digest, f"Stale analysis/source: {path}"
        assert doc["alignment"]["first_row"] == match(x, y)[0]
        assert doc["alignment"]["max_block_lag"] == int(name == "fs720_r1")
        matched = load(dest / "matched_frames.csv")
        expected = d.iloc[a:a+len(y)].reset_index(drop=True)
        assert len(matched) == len(y)
        for col in (FT, "CPUStartQPCTime", "MsCPUBusy", "MsGPUBusy", "MsGPUWait", "MsCPUWait"):
            assert np.array_equal(matched[col], expected[col]), (name, col)
        full = doc["full_benchmark"]
        assert abs(full["avg_fps"] - 1000/matched[FT].mean()) < 1e-10
        assert abs(full["duration_s"] - doc["alignment"]["qpc"]["duration_s"]) < 1e-6
        assert len(d) == metadata["rows_in_csv"] and metadata["presentmon_returncode"] == 0
        modes = d.PresentMode.value_counts().to_dict()
        streams = d[["ProcessID", "SwapChainAddress"]].drop_duplicates().to_dict("records")
        assert len(streams) == 1 and set(modes) == {"Hardware: Independent Flip"}
        assert set(d.AllowsTearing) == {1} and set(d.SyncInterval) == {0}
        assert doc["game"]["windowMode"] == 2
        refresh = [metadata[s]["gpu"]["CurrentRefreshRate"] for s in ("before", "after")]
        assert refresh == [360, 360]
        gates[name] = dict(present_modes=modes, streams=streams, refresh_hz=refresh,
                           window_mode=2, rows=len(d))
        docs[name] = doc
    variable = {"renderWidth", "renderHeight", "averageFps", "minFps", "maxFps", "time", "frameNumber"}
    configs = [{k: v for k, v in d["game"].items() if k not in variable} for d in docs.values()]
    assert all(c == configs[0] for c in configs)
    assert all(g["streams"] == gates["fs1440_r1"]["streams"] for g in gates.values())
    first, mid, low, last = [docs[r] for r in RUNS]
    fps = lambda d: d["full_benchmark"]["avg_fps"]
    ft = lambda d: d["full_benchmark"]["ft_avg_ms"]
    signal = lambda d, s: d["signals"][s]["mean_ms"]
    drift = 100*(fps(last)/fps(first)-1)
    assert abs(drift) <= 0.5
    pixels = np.array([d["game"]["renderWidth"]*d["game"]["renderHeight"] / 1e6
                       for d in (first, mid, low)])
    fits = {}
    for key in ("frametime", "MsGPUBusy"):
        values = np.array([ft(d) if key == "frametime" else signal(d, key) for d in (first, mid, low)])
        slope, intercept = np.polyfit(pixels, values, 1)
        endpoint_prediction = float(values[2]+(values[0]-values[2])*(pixels[1]-pixels[2])/(pixels[0]-pixels[2]))
        fits[key] = dict(intercept_ms=float(intercept), slope_ms_per_Mpx=float(slope),
                         residual_ms=(values-(intercept+slope*pixels)).tolist(),
                         endpoint_1080_prediction_ms=endpoint_prediction,
                         endpoint_1080_residual_ms=float(values[1]-endpoint_prediction),
                         endpoint_1080_residual_pct=float(100*(values[1]/endpoint_prediction-1)))
    predictions = {}
    for key, predicted in (("MsGPUBusy", 3.76), ("MsCPUBusy", 5.22)):
        measured = signal(low, key)
        predictions[key] = dict(predicted_ms=predicted, measured_ms=measured,
                                error_ms=measured-predicted, error_pct=100*(measured/predicted-1))
    predictions["MsGPUWait"] = dict(predicted_above_ms=0.196, measured_ms=signal(low, "MsGPUWait"),
                                    direction_pass=signal(low, "MsGPUWait") > 0.196)
    predictions["mapping"] = dict(predicted_first_row=6416, measured_first_row=low["alignment"]["first_row"],
                                   predicted_last_row=18357, measured_last_row=low["alignment"]["last_row"],
                                   exact_prediction_pass=False,
                                   note="Global optimum with explicit +/-1 frame uncertainty; not exact identity")
    stats = dict(drift_fps_pct=drift, fps_gain_720_vs_1440_pct=100*(fps(low)/fps(first)-1),
                 fps_gain_720_vs_1080_pct=100*(fps(low)/fps(mid)-1),
                 gpu_busy_over_frametime={name: signal(d, "MsGPUBusy")/ft(d) for name, d in docs.items()},
                 gpu_wait_720_vs_1080_ratio=signal(low, "MsGPUWait")/signal(mid, "MsGPUWait"))
    result = dict(gates=gates, native_summary_settings_equal_except_resolution_and_results=True,
                  diagnostics=diagnostics, predictions_720=predictions, descriptive_statistics=stats,
                  fits=fits, immutable_inputs_verified=len(frozen),
                  policy="Post-diagnosis bounded window uncertainty only at 720p. No frame-level or ETW-loss proof.",
                  verdict="1440p: strong GPU-dominant evidence. 720p: strong non-GPU pacing/feeding evidence, probable CPU/submission limit. CPU vs driver not identified. No measured hard FPS ceiling or shader speedup bound.",
                  runs={name: {k: d[k] for k in ("full_benchmark", "signals", "alignment")} for name, d in docs.items()},
                  script_sha256=sha(__file__))
    (BASE / "scaling_analysis_v2.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    table = []
    for name, d in docs.items():
        f = d["full_benchmark"]
        table.append(f'| {name} | {fps(d):.3f} | {ft(d):.4f} | {signal(d, "MsGPUBusy"):.4f} | '
                     f'{signal(d, "MsCPUBusy"):.4f} | {signal(d, "MsGPUWait"):.4f} | {signal(d, "MsCPUWait"):.4f} |')
    tails = []
    for name, d in docs.items():
        f = d["full_benchmark"]
        tails.append(f'| {name} | {f["ft_p95_ms"]:.3f} | {f["ft_p99_ms"]:.3f} | '
                     f'{f["fps_1pct_low_time"]:.2f} | {f["fps_01pct_low_time"]:.2f} | {f["spikes"]} | {f["severe_spikes"]} |')
    report = f'''# Cyberpunk fullscreen scaling — verdetto v2

## Verdetto

**1440p prevalentemente GPU-bound (evidenza forte); 720p limitato soprattutto da
alimentazione/pacing non-GPU, compatibile con CPU/submission (probabile).
Questi CSV NON separano CPU del gioco da driver, né dimostrano un difetto del driver.**

La GPU occupa circa il {100*stats["gpu_busy_over_frametime"]["fs1440_r1"]:.1f}% del frametime a 1440p
contro il {100*stats["gpu_busy_over_frametime"]["fs720_r1"]:.1f}% a 720p; GPUWait cresce di
{stats["gpu_wait_720_vs_1080_ratio"]:.2f} volte rispetto al 1080p. Sono rapporti di timing PresentMon,
NON utilizzo device misurato: GPUWait non è tutto l'idle globale, CPUBusy non è campionamento
CPU e può includere pacing/back-pressure. Il cambio di regime è supportato anche dallo
scaling a present path invariato, non dalla sola disuguaglianza CPUBusy > GPUBusy.

## Dati completi, senza trim

| Run | FPS | Frame ms | GPUBusy ms | CPUBusy ms | GPUWait ms | CPUWait ms |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table)}

| Run | p95 ms | p99 ms | 1% low FPS | 0,1% low FPS | Spike | Severi |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(tails)}

Low = reciproco del tempo medio dei frame peggiori che coprono l'1% / 0,1% del tempo
totale (definizione pmparse). Spike: frame > 2x mediana locale centrata di 21 frame E
almeno 2 ms oltre la mediana; severo: > 3x mediana E almeno 8 ms assoluti.
Le finestre storiche tagliate restano separate e mantengono la definizione legacy N/(tultimo-tprimo).
Le analisi v2 complete usano N/somma degli N intervalli.

## Gate e provenienza

Tutte e quattro: 100% Hardware: Independent Flip, tearing=1, SyncInterval=0,
windowMode=2, stesso PID e swapchain, 360 Hz prima/dopo nei metadata. I campi dei summary
nativi coincidono salvo risoluzione e risultati; non sono una verifica di impostazioni
che i summary non registrano. PresentMon exit 0, conteggi CSV verificati.
Deriva FPS 1440p r2/r1 **{drift:.3f}%**, entro il gate preesistente di 0,5%.
Due ancore non provano deriva monotona né misurano separatamente rumore e deriva;
n=1 a 1080/720p, niente intervalli di confidenza run-to-run né MDE preso dalla serie borderless.
Nessun fit include la vecchia baseline borderless. Telemetria clock/termica assente.

{len(frozen)} hash di raw, risultati nativi, analisi storiche e pmparse verificati invariati.
Backup dello script originale e proposta precedente in `v2_provenance/`.
Ogni `native_analysis_v2/analysis.json` contiene hash input/codice e controlli di allineamento.

## Diagnosi dell'errore e correzioni effettive

Il benchmark nativo del 720p è `benchmark_2026-09-08_21-08-37` (11942 frame).
Riprodotto il difetto originale: picco globale **6415**, primo blocco **6414**,
blocchi centrale/finale a offset globale 6415. Allungare i blocchi a un terzo NON basta:
il primo resta un frame indietro. Non è un picco rivale lontano; la diagnosi precedente
"finestra troppo corta, traccia certamente completa" era troppo forte.

La localizzazione dalla sola durata QPC proposta è non univoca: sceglie 2815 anziché
2859 a 1440p r1, 7237 anziché 7360 a 1440p r2, e 6414 a 720p. **Non adottata come gate.**
QPC viene invece verificato alla posizione trovata: `diff(QPC) = FrameTime[:-1]`
(v2 misura intervalli in avanti), continuità entro 1 us su tutta la cattura e durata
QPC della finestra inclusiva dell'ultimo intervallo. Non modifica `pmparse.py` né i raw.
Questa verifica esclude buchi CSV di intervalli non nulli, NON perdita ETW a monte.

Implementati: durata N-intervalli, cross-check nativo 0,05% FPS / 0,5 s,
`--out-name`, margini del picco fuori +/-50 frame (minimo diagnostico 0,05), tre terzi
completi della traccia. Accordo esatto resta il default. Solo 720p usa esplicitamente
`--max-block-lag 1`, con QPC obbligatorio e sensibilità dei risultati alle finestre
6414/6415/6416. Non vengono eliminati, interpolati o ricuciti frame.
**Questa è una policy post-diagnosi per statistiche aggregate con incertezza di un frame,
non il superamento del vecchio gate esatto e non un matching causale frame-per-frame.**

Finestra centrale 720p **6415–18356, indici zero-based senza header**;
la predizione esatta 6416–18357 è smentita, benché rientri nella sensibilità +/-1.
Il mapping nativo è giusto; l'identità esatta dei singoli frame resta non dimostrata.
Durata {low["full_benchmark"]["duration_s"]:.7f} s, FPS {fps(low):.6f}.
Le tre finestre danno FPS fra {min(s["avg_fps"] for s in low["alignment"]["boundary_sensitivity"]):.6f}
e {max(s["avg_fps"] for s in low["alignment"]["boundary_sensitivity"]):.6f};
la conclusione aggregata non dipende dalla scelta di uno di questi bordi.

## Predizioni 720p: verifica, senza trasformare approssimazioni in soglie

- GPUBusy previsto **3,76 ms**, misurato **{signal(low, "MsGPUBusy"):.4f} ms**:
  errore **{predictions["MsGPUBusy"]["error_pct"]:+.2f}%**. Il numero NON è accurato;
  resta però molto sotto 5,38 ms, non vicino all'alternativa GPU satura ~5,2 ms.
- CPUBusy previsto **5,22 ms**, misurato **{signal(low, "MsCPUBusy"):.4f} ms**:
  errore **{predictions["MsCPUBusy"]["error_pct"]:+.2f}%**, coerente. Essendo circa
  FrameTime-CPUWait, non è una prova indipendente di lavoro CPU effettivo.
- GPUWait previsto **>0,196 ms**, misurato **{signal(low, "MsGPUWait"):.4f} ms**: direzione confermata.
- Mapping esatto/QPC locator: smentiti come sopra. FPS ~185,82: confermato a livello aggregato.

## Modelli e cosa non si può concludere

Per frametime, il 1080p è {fits["frametime"]["endpoint_1080_residual_ms"]:+.4f} ms
({fits["frametime"]["endpoint_1080_residual_pct"]:+.2f}%) rispetto alla retta 1440–720:
modello lineare unico non adeguato. Per GPUBusy il residuo corrispondente è
{fits["MsGPUBusy"]["endpoint_1080_residual_ms"]:+.4f} ms
({fits["MsGPUBusy"]["endpoint_1080_residual_pct"]:+.2f}%). Fit e residui completi nel JSON;
nessuna intercetta viene identificata con il costo CPU/driver.

**Ritirata la precedente interpretazione C=4,81–5,38 ms come prima misura del costo CPU
e ~186 FPS come tetto rigido.** Anche 1080→720 migliora ancora di
{stats["fps_gain_720_vs_1080_pct"]:.2f}%; qui c'è un limite non-GPU crescente, non un plateau
isolato sperimentalmente. Il +{stats["fps_gain_720_vs_1440_pct"]:.2f}% rispetto al 1440p è
il guadagno MISURATO cambiando risoluzione, non un guadagno shader dimostrato né un suo limite superiore.

La ricerca GPU/shader a 1440p ha senso come prossimo bersaglio, ma nessun pass/shader
specifico o guadagno è provato. Per attribuire il limite basso a gioco vs UMD/driver vs
sincronizzazione serve WPR CPU+GPU con stack e code, in cattura di attribuzione separata.
Non necessaria per il verdetto di regime qui sopra; non avviata automaticamente.
Nessuna modifica a gioco, driver, cache, registro o impostazioni. Nessun click richiesto.

## Riproduzione

`python -B tools/c2077_scaling_check.py`

Rigenera le directory v2 mancanti, verifica hash e risultati se già presenti, non le
sovrascrive; aggiorna questo report e `scaling_analysis_v2.json`. Selfcheck sintetici
in `tools/c2077_native.py`: traccia esatta/rumorosa, ambiguità, lag ammesso/non ammesso,
frame mancanti nel CSV, QPC e durata N-intervalli. Il check reale riproduce il difetto
originale e verifica tutti i frame/campi copiati nelle quattro nuove finestre.
'''
    (BASE / "VERDICT_V2.md").write_text(report, encoding="utf-8")
    for path, digest in frozen.items():
        assert sha(path) == digest, f"Historical input changed: {path}"
    print(json.dumps(dict(predictions=predictions, stats=stats, inputs_verified=len(frozen)), indent=2))
    print("PASS: four native_analysis_v2, immutable inputs, synthetic and real-data checks")


if __name__ == "__main__":
    main()
