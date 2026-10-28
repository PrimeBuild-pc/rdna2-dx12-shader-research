# Roadmap — what is left to do

State at pause: 2026-10-28. Ranked by expected value per hour. Each item says what "done" looks
like, so negative results count as progress.

## 1. Finish the Cyberpunk visible canary (phase 69) — highest value

**Why:** every later shader experiment on the game depends on proving that a swapped shader
actually reaches the screen. The first canary (phase 66, "glass" shader) was cloned and bound
2033 times but produced no visible change; phase 67 showed that PSO was not bound to any draw in
the observed session. Phase 68 then found a better target by watching draws into the real back
buffer.

**Target:** PSO serial 243, pixel shader SHA-256
`1642c9e5c2f2bca229198fc354cf8e5bd712f26baa467a6392f7c5125abc9d4c` (4995 bytes), full-screen
triangle, writes RGBA straight to the 2560×1440 R8G8B8A8_UNORM back buffer, blend and depth off.
It sits at offset 10816877 of `staticshader_final.cache` (cache SHA-256 `bff16094…59ff`).

**Steps** (from [the preregistration](../research/69_c2077_visible_canary_20261017/PREREGISTRATION.md)):

1. Extract the original bytecode from *your own copy* of the game's static shader cache, and check
   its SHA-256 matches. (Game data is not in this repo.)
2. Build a **control** (full LLVM IR round trip, IR identical) and a **canary** (only the RGB of the
   three `storeOutput SV_Target0` replaced with 1,0,1; alpha stays 1) with
   [tools/dxil_roundtrip.cpp](../tools/dxil_roundtrip.cpp). Validate both with the Microsoft
   external validator.
3. With the game closed, point the phase-66 add-on ([tools/c2077_shader_addon.cpp](../tools/c2077_shader_addon.cpp),
   managed by [tools/c2077_shader_loader.py](../tools/c2077_shader_loader.py)) at the new target.
   Run control first (image must be normal), then canary (the 3D image should turn uniform magenta).
4. **Done when:** an operator sees (ideally screenshots) the magenta image with the canary and a
   normal one with control. If not, record a negative and investigate why before any optimisation.

## 2. One real transformation on a real game shader

Only after item 1 passes. Pick a shader that is both *observed* in draws and *expensive*. That
needs GPU timing per draw, which this project never got for the game:

- Try an RGP capture of the Cyberpunk benchmark (Radeon Developer Tool Suite). Check what RGP's
  profiling mode does to clocks first.
- Map RGP's expensive events to shader hashes via the phase-68 offline index
  (8340 unique SHAs / 19,950 occurrences, `research/68_.../offline_shader_index.json`).
- Then: ISA-driven hypothesis → correctness oracle → preregistered A/B, same method as 2P.

**Done when:** an accepted transformation with image correctness and an A/B beyond measured noise,
or a documented reason why none qualifies.

## 3. Open measurement questions (lower value)

- **Sampled CPU callers in the WPR trace** were never validated (WPA's sampled export stops at
  `[Root]`; the broad `Profile` filter is ambiguous). CSwitch/ReadyThread stacks do work.
  Needs the original ETL (not published; contact the author or capture a new, lighter trace).
- **How much of the 112 → 82.6 FPS drop is tracing overhead?** A lighter WPR profile (fewer
  stack-walk providers) on the same benchmark would answer it.
- **2O's binding unit:** on MiniEngine, VALU (96.6%) and the texture addresser (93.6%) are
  co-saturated. A factorial ALU × texture design was proposed but never run.
- **2P occupancy share:** how much of the −41% came from occupancy versus removed work; two
  attempts failed (`LEVEL_WAVES` counter looked broken).
- **Never done from the original plan:** shader-cache forensics with Procmon (1C), cold vs warm
  cache runs (1D), Black Myth: Wukong as a controlled workload (1F), Warzone shader preloading (1I).

## 4. Infrastructure that would make all of the above cheaper

- An **unattended image oracle** for the game (screenshot + compare) so canary/control checks don't
  need an operator watching.
- A **PresentMon launch wrapper** that writes `experiment_metadata.json` for every run (manual
  runs were common).
- Re-baseline on the **current driver**: all September numbers are on 32.0.21045.5002; by October
  the system had 32.0.21045.11001. Do not pool across drivers.

## Things not worth reopening (without new evidence)

- Compiler options through `AMD_SC_OPTIONS` / `SCOption_*` — closed in 2E with a negative control.
- `DXCTuningsFileName` / `amdxc64z.dll` — KMD-side, file does not exist.
- More tuning of the frozen MiniEngine PoC (2P/2Q/2R) — it is frozen on purpose.
- Re-running the Cyberpunk scaling series or the WPR alignment — both are complete and validated.
