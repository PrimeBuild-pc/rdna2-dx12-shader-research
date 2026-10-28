import csv
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
RUNS = ROOT / "research" / "29_o4_sampler" / "runs"
VARIANTS = ("s_base", "s_aniso1", "s_aniso16", "s_point", "s_bilinear")
KS = (1, 2, 4, 6, 8, 10, 12, 14, 16)


def read_run(name):
    return read_path(RUNS / name / "gpa_results.csv", name)


def read_path(path, name):
    rows = {}
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            sample = int(row["sample"])
            counter = row["counter"]
            value = float(row["value"])
            assert math.isfinite(value)
            assert counter not in rows.setdefault(sample, {})
            rows[sample][counter] = value
    assert sorted(rows) == list(range(len(rows))), (name, sorted(rows))
    return [rows[i] for i in sorted(rows)]


def ta_sum(sample, suffix):
    names = [f"TA{i}_PERF_SEL_{suffix}" for i in range(80)]
    assert all(name in sample for name in names)
    return sum(sample[name] for name in names)


def median(values):
    return statistics.median(values)


def percent(value, base):
    return 100.0 * (value / base - 1.0)


dose = {}
for variant in VARIANTS:
    samples = read_run(f"{variant}_aniso_r1")
    assert len(samples) == 8
    per_sample_buckets = {
        k: [ta_sum(sample, f"ANISO_{k}_CYCLE_QUADS") for sample in samples]
        for k in KS
    }
    buckets = {k: median(values) for k, values in per_sample_buckets.items()}
    mip_buckets = {
        k: median([ta_sum(sample, f"MIP_{k}_CYCLE_QUADS") for sample in samples])
        for k in (1, 2)
    }
    cycles_per_sample = [
        sum(k * per_sample_buckets[k][sample_index] for k in KS)
        for sample_index in range(len(samples))
    ]
    dose[variant] = {
        "samples": len(samples),
        "buckets": buckets,
        "quads_from_bucket_medians": sum(buckets.values()),
        "cycles_from_bucket_medians": sum(k * buckets[k] for k in KS),
        "median_per_sample_cycles": median(cycles_per_sample),
        "median_tex_ave_anisotropy": median([s["TexAveAnisotropy"] for s in samples]),
        "mip_buckets": mip_buckets,
        "mip_cycles": mip_buckets[1] + 2 * mip_buckets[2],
    }

response_per_process = {}
response = {}
for variant in VARIANTS:
    response_per_process[variant] = {}
    for rep in (1, 2, 3):
        samples = read_run(f"{variant}_resp_r{rep}")
        assert len(samples) == 32
        values = {
            "TA_BUSY": median([ta_sum(s, "TA_BUSY") for s in samples]),
            "ANISO_1_CYCLE_QUADS": median(
                [ta_sum(s, "ANISO_1_CYCLE_QUADS") for s in samples]
            ),
            "GPUTime": median([s["GPUTime"] for s in samples]),
            "GPUBusyCycles": median([s["GPUBusyCycles"] for s in samples]),
        }
        response_per_process[variant][rep] = values
    response[variant] = {
        metric: median([response_per_process[variant][rep][metric] for rep in (1, 2, 3)])
        for metric in ("TA_BUSY", "ANISO_1_CYCLE_QUADS", "GPUTime", "GPUBusyCycles")
    }

n95 = {}
for metric in response["s_base"]:
    values = [response_per_process["s_base"][rep][metric] for rep in (1, 2, 3)]
    pairwise = [
        100.0 * abs(values[i] - values[j]) / min(values[i], values[j])
        for i in range(3) for j in range(i + 1, 3)
    ]
    n95[metric] = {"pairwise_pct": pairwise, "max_pct": max(pairwise)}

dose_delta = {
    variant: percent(dose[variant]["cycles_from_bucket_medians"],
                     dose["s_base"]["cycles_from_bucket_medians"])
    for variant in VARIANTS
}
response_delta = {
    variant: {metric: percent(value, response["s_base"][metric])
              for metric, value in response[variant].items()}
    for variant in VARIANTS
}

report = {
    "dose": dose,
    "dose_delta_pct": dose_delta,
    "response_per_process": response_per_process,
    "response_median": response,
    "response_delta_pct": response_delta,
    "n95": n95,
    "threshold_if_GPUTime_pct": max(2.0, 3.0 * n95["GPUTime"]["max_pct"]),
    "threshold_if_GPUBusyCycles_pct": max(2.0, 3.0 * n95["GPUBusyCycles"]["max_pct"]),
}

o3_runs = ROOT / "research" / "28_o3_material_ablation" / "runs"
o3 = {}
for variant in ("mat0", "mat3"):
    per_process = []
    for rep in (1, 2, 3):
        samples = read_path(o3_runs / f"{variant}_resp_r{rep}" / "gpa_results.csv",
                            f"{variant}_resp_r{rep}")
        assert len(samples) == 32
        per_process.append(median([ta_sum(s, "TA_BUSY") for s in samples]))
    o3[variant] = median(per_process)
report["o3_ta_busy"] = {
    "mat0": o3["mat0"],
    "mat3": o3["mat3"],
    "mat3_delta_pct": percent(o3["mat3"], o3["mat0"]),
}

print(json.dumps(report, indent=2, sort_keys=True))
