#!/bin/bash
# Estrae i frametime PresentMon dagli ETL gia' catturati.
# Stesso ETL -> stesso orologio dei CPU sample: correlazione frame-per-frame possibile.
PM="/c/Program Files/Intel/PresentMon/PresentMonConsoleApplication/PresentMon-2.5.1-x64.exe"
cd "/c/Users/Lorenzo/Downloads/driver mod"
for etl in research/08_etw_fortnite/raw/fortnite-run*.etl; do
  out="${etl%.etl}-presentmon.csv"
  [ -s "$out" ] && { echo "skip $out"; continue; }
  echo "=== $etl -> $out"
  "$PM" --etl_file "$etl" --process_name FortniteClient-Win64-Shipping.exe \
        --output_file "$out" --qpc_time --no_console_stats 2>&1 | tail -4
  ls -la "$out" 2>/dev/null || echo "  !! nessun output"
done
