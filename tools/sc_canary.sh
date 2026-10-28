#!/bin/bash
# Phase 2A - canary del parser SC del driver AMD, via RGA (niente 3DMark, niente ProcMon).
#
# Sostituisce sc_probe.ps1, rimosso perche' sbagliato: lanciava 3DMark direttamente (build
# Epic su JVM: non parte) e avviava ProcMon senza filtri (2.1 GB in 8 min, sistema bloccato).
#
# Rilevatore: se il parser e' vivo, un nome di opzione INVALIDO fa fallire il backend DX12.
# Nessuna env var persistente: sono tutte process-local.
set -u
cd "$(dirname "$0")/.."
RGA="RadeonDeveloperToolSuite-2026-05-28-1806/RadeonDeveloperToolSuite-2026-05-28-1806/rga.exe"
D=research/10_sc_probe
run() { # $1=tag  (env gia' impostato dal chiamante)
  rm -rf "$D/o_$1"; mkdir -p "$D/o_$1"
  timeout 240 "$RGA" -s dx12 -c gfx1030 --cs "$D/shader/cs.hlsl" --cs-entry main \
      --cs-model cs_6_0 --rs-macro RS --isa "$D/o_$1/isa.txt" > "$D/o_$1/o.txt" 2>&1
  grep -q succeeded "$D/o_$1/o.txt" && echo "  OK  $1" || echo "  KO  $1"
}
echo "baseline (nessuna env var):";                 run baseline
echo "nome valido   (--dump-prefix=...):";          AMD_SC_OPTIONS="--dump-prefix=C:/temp/x_" run valid
echo "nome invalido (--opzione-inventata):";        AMD_SC_OPTIONS="--opzione-inventata"      run invalid
echo
echo "Atteso se il parser e' ATTIVO: OK / OK / KO"
