# Attempt 2 of O1 `prepare` — succeeded, then SUPERSEDED before any build

**Experiment ID:** `O1_20260906_004007` · 2026-09-06 00:40 · workspace
`%TEMP%\claude\O1_20260906_004007`

`prepare` completed correctly (2,121 GB copied and SHA-256 verified, 16/16 patches applied,
output redirection confirmed). **No build and no application run were ever performed against
it**, so it consumed no experimental cycle.

Superseded because an independent adversarial review of the O1 tooling, run in parallel,
found defects that change what `prepare` must bake into the workspace and the manifest:

1. `buildv.py` proved propagation via `CL.read.1.tlog`. **Measured on the real historical
   tlog: 3134 header entries, zero under the build output tree** — MSBuild's file tracker
   excludes the output and package directories, so the generated shader header can never
   appear there. The check would have produced a spurious FAIL. (Same root cause as the
   empty `dxc.write.1.tlog` the audit flagged; it is *not* timestamp granularity.)
   Replaced by a direct check: the verified bytecode must appear **exactly once** in
   `Model.lib` and in `ModelViewer.exe`. Confirmed to hold on the historical artifacts.
2. Stages A and B were built with `expected=None`, so B accepted *any* bytecode differing
   from A. The manifest now preregisters the exact bytecode SHA-256 of A and B, compiled
   offline by DXC during `prepare`.
3. Capture frame was 7. `Sponza::RenderLightShadows` copies **one** of `MaxLights=128`
   shadow slices per frame, so at frame 7 the shadow array is 121/128 unrendered and its
   content changes every frame. Capture moved to frame 140.
4. The baseline image was gated at 1 ULP. `FillLightGridCS.hlsli` assigns per-tile light
   slots with `InterlockedAdd` and `Lighting.hlsli` accumulates `colorSum` in that order:
   float summation order varies between runs. This is a **confirmed mechanism** for the
   "2 distinct image hashes over 6 runs" observed in phase 2L. The baseline is now
   *measured* over 3 runs and the canary must exceed that spread by 20x.

Nothing deleted. Superseded by the next `prepare`.
