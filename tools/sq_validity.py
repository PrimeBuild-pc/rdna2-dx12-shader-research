"""Validity gate for per-shader-engine SQ counters.

MEASURED problem: SQ counters are sometimes returned corrupted for individual shader engine
instances - observed on SE0 and SE2, in three different sessions and counter sets. The
signature is unmistakable: several events on that instance read exactly 0 while another event
on the same instance carries a value belonging to a different event (e.g.
SQ_PS0_PERF_SEL_INSTS_SALU holding SQ_PS0_PERF_SEL_ITEM_CYCLES_VALU's value, matching a
different session bit for bit).

The four shader engines are symmetric and, when healthy, agree to about 2%. So a run in which
one instance disagrees wildly with its siblings is rejected rather than averaged in.

    python -B tools/sq_validity.py <gpa_results.csv> [...]
"""
import csv
import re
import statistics
import sys
from pathlib import Path

# Healthy spread between shader engines, measured across O2/O3 runs, is <= 2.2%. This is a
# corruption detector, not a precision gate, so it is deliberately loose.
MAX_RATIO = 1.25


def check(path):
    rows = list(csv.DictReader(Path(path).open(encoding="utf-8")))
    by = {}
    for r in rows:
        by.setdefault(r["counter"], {})[int(r["sample"])] = float(r["value"])
    data = {c: [v[i] for i in sorted(v)] for c, v in by.items()}

    groups = {}
    for name in data:
        m = re.fullmatch(r"SQ(?:_([A-Z]{2}))?(\d+)_(PERF_SEL_.+)", name)
        if m:
            groups.setdefault((m.group(1) or "ALL", m.group(3)), {})[int(m.group(2))] = name
    problems = []
    for (mask, event), inst in sorted(groups.items()):
        med = {i: statistics.median(data[n]) for i, n in inst.items()}
        vals = list(med.values())
        if max(vals) == 0:
            continue  # an event that is legitimately zero on every instance
        lo, hi = min(vals), max(vals)
        if lo == 0 or hi / lo > MAX_RATIO:
            problems.append((mask, event, {i: med[i] for i in sorted(med)}))
    return problems, len(groups)


def main(paths):
    bad = 0
    for p in paths:
        problems, n = check(p)
        status = "OK" if not problems else f"REJECT ({len(problems)}/{n} events inconsistent)"
        print(f"{status:42s} {p}")
        for mask, event, med in problems:
            per = "  ".join(f"SE{i}={v:,.0f}" for i, v in med.items())
            print(f"    {mask}/{event}: {per}")
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
