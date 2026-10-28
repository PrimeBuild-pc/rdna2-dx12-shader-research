#!/bin/bash
# Oracolo: dato AMD_SC_OPTIONS in $1, dice se il parser lo accetta (OK) o no (KO).
set -u
cd "$(dirname "$0")/.."
RGA="RadeonDeveloperToolSuite-2026-05-28-1806/RadeonDeveloperToolSuite-2026-05-28-1806/rga.exe"
S=research/10_sc_probe/shader/cs.hlsl
T=$(mktemp -d)
AMD_SC_OPTIONS="$1" timeout 120 "$RGA" -s dx12 -c gfx1030 --cs "$S" --cs-entry main \
   --cs-model cs_6_0 --rs-macro RS --isa "$T/isa.txt" > "$T/o.txt" 2>&1
if grep -q succeeded "$T/o.txt"; then echo "OK   $1"; else echo "KO   $1"; fi
rm -rf "$T"
