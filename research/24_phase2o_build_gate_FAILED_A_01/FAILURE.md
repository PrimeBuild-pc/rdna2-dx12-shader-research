# Stage A, attempt 1 — FAILED at the MSBuild gate

**Experiment ID:** `O1_20260906_005913` · workspace `%TEMP%\claude\O1_20260906_005913`

**What happened:** DXC compiled and verified the shader correctly (12 612 bytes, the
preregistered SHA-256, 4 effective inputs). MSBuild then failed and the gate **rejected the
build instead of continuing** — the behaviour finding A01 said was missing:

```
process failed (1): research/24_phase2o_build_gate/build_logs/A/msbuild.log
```

**Cause (confirmed, from the compiler):**

```
O1Probe.h(17,31): error C7525: inline variables require at least '/std:c++17'
    [.../MiniEngine/Core/Core.vcxproj]
```

`inline constexpr uint64_t kCaptureFrame = 140;` — my own instrumentation. MiniEngine builds
with the MSVC default (C++14), where inline variables do not exist. It is the only error in
the log; nothing else in the probe failed to compile.

**Fix:** `enum : uint64_t { kCaptureFrame = 140 };`. An enumerator is C++11-clean and, unlike
a namespace-scope `constexpr` in a header, raises no internal-linkage question when used from
`inline` functions across translation units.

**Two secondary defects this exposed, both fixed:** a retry of a stage would have crashed
before reaching the compiler, because `buildv.build()` requires a *new* stage directory
(`mkdir(exist_ok=False)`) and `run_o1.stage()` wrote the source snapshot with mode `"xb"`.
Stage directories now carry an attempt number, and the snapshot is compared instead of
rewritten when it already exists.

**Cycle accounting:** this consumed one MSBuild run. It produced **no measurement, no GPU
workload, no counter and no image**, so it does not consume one of the six experimental
cycles of §7 — but it is recorded here rather than quietly retried. Nothing deleted.
