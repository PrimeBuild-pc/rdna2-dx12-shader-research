#!/bin/bash
cd "/c/Users/Lorenzo/Downloads/driver mod"
PY=/c/Users/Lorenzo/AppData/Local/Programs/Python/Python311/python
for n in 1 2 3; do
  etl=$(ls research/08_etw_fortnite/raw/fortnite-run$n-*.etl 2>/dev/null | head -1)
  [ -z "$etl" ] && { echo "run$n: ETL mancante"; continue; }
  echo "=== run$n: $etl ($(du -h "$etl"|cut -f1)) ==="
  PYTHONIOENCODING=utf-8 $PY tools/etw_analyze.py "$etl" research/08_etw_fortnite/run$n \
     --process FortniteClient-Win64-Shipping.exe
  echo "=== run$n done: $(date) ==="
done
