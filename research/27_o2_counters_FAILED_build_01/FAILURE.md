# O2 build, attempt 1 — FAILED at the build gate

**Experiment ID:** `O2_20260906_013657`. Rejected by `buildv` with exit code 1, no run performed.

```
O2Gpa.h(23,10): error C1083: Cannot open include file:
  'gpu_performance_api/gpu_perf_api.h'  [Model.vcxproj]
```

**Cause (confirmed from the project files):** the GPA include directory is declared only in
`Core/Core.vcxproj:456`. O2 makes `Model` (via `SponzaRenderer.cpp`) and `ModelViewer` compile
`O2Gpa.h` too, and neither project had that path.

**Second defect found while fixing it:** `ModelViewer.cpp` called `O2Gpa::OnContextBegin` and
`O2Gpa::OnContextEnd` but the instrumentation never added `#include "O2Gpa.h"` there. It would
have failed on the next line even with the include path fixed.

**Fixes:** the GPA include directory now goes into `PropertySheets/Build.props`, which all four
projects import, and the O2 header is included in `ModelViewer.cpp`.

**Also checked, and fine:** `gpu_perf_api.h` defines `USE_GPA 1` unless `DISABLE_GPA` is set,
so the real declarations are used and not the stub.

**Cycle accounting:** one MSBuild run, **no GPU work, no counters, no measurement**. Does not
consume one of the six experimental cycles. Nothing deleted.
