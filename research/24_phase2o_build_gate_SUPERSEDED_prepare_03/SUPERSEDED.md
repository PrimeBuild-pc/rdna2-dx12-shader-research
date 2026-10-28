# Attempt 3 of O1 `prepare` — succeeded, SUPERSEDED before any build

**Experiment ID:** `O1_20260906_005422` · workspace `%TEMP%\claude\O1_20260906_005422`.
No build, no application run: **0 experimental cycles consumed.**

This attempt already carried the review fixes (frame 140, preregistered A/B bytecode
SHA-256, measured baseline spread). It is superseded only because two further defects were
found *after* it ran, by rehearsing the DXC half of `build()` offline against this very
workspace — so its `input_hashes.csv` records tool hashes that are no longer the ones that
would execute.

Both defects would have failed stage A, and neither was caught by the code review:

1. **`-MD` puts DXC in dependency-only mode.** With `-MD -MF` on the command line, DXC writes
   the depfile, emits **no** `-Fh` header and **no** `-Fo` object, and still exits 0
   (measured: `no -MD` → `PS.h o.cso`; `-MD -MF deps` → `deps.d` only). `build()` issued one
   combined invocation, so it would have produced no shader header at all. Split into two
   invocations: compile, then dependency scan.
2. **Truncating regex.** `[A-Za-z]:[/\][^\s]+\.(?:hlsl|hlsli)` matches the `hlsl` branch
   first and yields `Common.hlsl` for `Common.hlsli`, so `Path(...).resolve(strict=True)`
   raised `FileNotFoundError`. Now `\.hlsli?(?=\s|$)`. The check was also extracted into
   `buildv.effective_inputs()` so the rehearsal exercises the same code instead of a copy.

Rehearsal result after the fixes: 4 effective inputs (`ModelViewerPS.hlsl`, `Common.hlsli`,
`Lighting.hlsli`, `LightGrid.hlsli`), header bytecode identical to the DXC object,
12 612 bytes, custom hash `52CE6C5E64AB2E82`.

Nothing deleted.
