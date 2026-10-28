# GPUPerfAPI phase 2N numerical-validity audit

**Date:** 2026-09-06

**Offline query provenance:** the pass-count query was run offline against the local GPUPerfAPI 4.4.5 Counter Library (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\bin\GPUPerfAPICounters-x64.dll`) through a virtual DirectX 12/discrete-counter context using device identity `1002:73A5:C0`; the virtual-context and scheduling APIs used are declared in `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:282-302` and `:477-491`, and the device identity is recorded in `C:\Users\Lorenzo\Downloads\driver mod\research\00_inventory\gpu_info.json:3-9`.

**What is needed to answer the texture-filter question:** because no enumerated discrete counter separates texture-filter rate from cache/latency and pixel-shader ALU, answering whether `Render Color` is filtering-throughput limited requires a controlled A/B that changes only sampler filtering/aniso while holding shader bytecode, textures, coordinates and sample calls fixed under a valid one-pass capture or frozen replay, plus a PS-ALU-sensitive measurement or controlled ALU ablation (for example an authorized RGP/SQTT capture) (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpa_counters.csv:2-146`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:8-148,196-243`; `C:\Users\Lorenzo\Downloads\driver mod\research\CODEX_HANDOFF_AUDIT.md:223-226`).

**Raw-counter qualification:** it is **VERIFIED** that `kGpaOpenContextEnableHardwareCountersBit` asks GPA to expose raw hardware counters (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\api_functions\gpa_opencontext.rst.txt:92-99`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_types.h:190-205`), but this audit did **not** re-enumerate a live DX12 context with that flag. Therefore, the more specific claim that this Navi21/driver combination would expose useful raw `SQ` or `TA` events hidden by the default context is an **INFERENCE**, not a verified result; the SDK merely defines `SQ` and `TA` as possible hardware blocks (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:44-60`). Even if exposed, their names, semantics, scheduling and ability to discriminate filter throughput would have to be verified from the actual flagged enumeration rather than assumed.

## Executive verdict

**The phase-2N CSV is not numerically valid as one coherent 31-counter measurement.** GPA scheduled the set across 13 passes, but the implementation advances to a new rendered frame for each pass. GPA explicitly requires an identical GPU workload in every pass (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\usage.rst.txt:441-457`). `GpaProfiler::EndFrame` increments `g_Pass` and returns until all requested passes have elapsed (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:222-231`), while `GameCore` calls `EndFrame`/`BeginFrame` on successive loop iterations (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GameCore.cpp:149-178`).

The workload is not temporally frozen. `ModelViewer::Startup` enables motion blur, TAA, HDR, adaptive exposure and SSAO (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\ModelViewer\ModelViewer.cpp:147-154`). Presentation increments the frame index and calls `TemporalEffects::Update` (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\Display.cpp:532-536`); that update changes the TAA frame index, ping-pong index and Halton jitter (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\TemporalEffects.cpp:76-107`). Adaptive exposure generates a histogram and updates the exposure buffer when enabled (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\PostEffects.cpp:326-372`). No state restoration or replay between GPA passes is present in the inspected GPA frame path (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GameCore.cpp:165-178`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:171-181,222-231`).

This does **not** prove that every individual scalar is wrong. It means values whose underlying events were scheduled into different passes cannot safely be combined as if they described one identical workload, so they cannot exclude competing bottlenecks or establish the causal conclusion that `Render Color` is texture-filter-throughput limited. The handoff audit classifies the missing identical-workload requirement as confirmed while explicitly stating that the magnitude of the numerical error was not measured (`C:\Users\Lorenzo\Downloads\driver mod\research\CODEX_HANDOFF_AUDIT.md:183-215`).

## 1. Exact enabled 31-counter set

The exact order of `kCounters` is (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:66-78`):

```text
 1 GPUTime
 2 GPUBusy
 3 PSBusy
 4 PSTime
 5 VsGsBusy
 6 VsGsTime
 7 PSPixelsOut
 8 PSExportStalls
 9 PrimitiveAssemblyBusy
10 PrimitivesIn
11 CulledPrims
12 ClippedPrims
13 PAStalledOnRasterizer
14 TexUnitBusy
15 TexAveAnisotropy
16 DepthStencilTestBusy
17 ZUnitStalled
18 DBMemRead
19 DBMemWritten
20 CBMemRead
21 CBMemWritten
22 CBSlowPixelPct
23 L0CacheHit
24 L1CacheHit
25 L2CacheHit
26 FetchSize
27 WriteSize
28 MemUnitBusy
29 MemUnitStalled
30 WriteUnitStalled
31 LocalVidMemBytes
```

The frozen audit snapshot contains the same list at `C:\Users\Lorenzo\Downloads\driver mod\research\handoff_audit_20260905\instrumentation_snapshot\GpaProfiler.cpp:66-78`. Read-only SHA-256 inspection found the live and frozen `.cpp` copies identical, and likewise found the two `.h` copies identical; the corresponding declaration is at `C:\Users\Lorenzo\Downloads\driver mod\research\handoff_audit_20260905\instrumentation_snapshot\GpaProfiler.h:15-31`.

## 2. Local GPA 4.4 multipass requirement

The local documentation states:

> “If the number of passes is greater than one, you will need to execute an identical GPU workload once for each pass.”

It continues by requiring the same sample ID to identify the same workload in every pass and recommends selecting a single-pass counter set when repeating the operations is impossible or impractical (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\usage.rst.txt:441-457`).

For DirectX 12, the same section says this typically means recording the same command list more than once, calling `GpaBeginCommandList` for every pass, and beginning and ending samples around the same workloads (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\usage.rst.txt:447-452`). The public header describes pass count as the number of times “the same sequence” must be repeated while GPA measures a different compatible counter set on each pass (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api.h:943-962`).

The preserved phase-2N report says that the 31 counters require 13 passes but claims that advancing a fixed-timestep application repeats the same frame (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\PHASE_2N_RESULTS.md:36-48`). That claim is false: fixed timestep makes a sequence potentially repeatable; it does not make consecutive frames identical. The code advances temporal state as documented above (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\Display.cpp:532-536`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\TemporalEffects.cpp:76-107`).

## 3. Pass-count APIs and offline result

### Main profiling API

The exact signature is (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api.h:945-962`):

```cpp
GpaStatus GpaGetPassCount(
    GpaSessionId gpa_session_id,
    GpaUInt32* number_of_passes);
```

The API returns the required passes for the counters currently enabled on a previously created session (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\api_functions\gpa_getpasscount.rst.txt:9-26`). It returns `kGpaStatusErrorSessionNotFound` for an unknown session and `kGpaStatusErrorContextNotOpen` when the session's parent context is not open (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\api_functions\gpa_getpasscount.rst.txt:28-42`). Thus the main `GpaGetPassCount` entry point is a live-context/session query, not a standalone arbitrary-name calculator.

### Offline Counter Library equivalent

GPUPerfAPI 4.4.5 also provides (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:477-491`):

```cpp
GpaStatus GpaCounterLibGetPassCount(
    const GpaCounterContext gpa_virtual_context,
    const GpaUInt32* gpa_counter_indices,
    GpaUInt32 gpa_counter_count,
    GpaUInt32* number_of_pass_req);
```

`GpaCounterLibOpenCounterContext` creates a virtual context from API, sample type, hardware identity/attributes and context flags, without requiring a live graphics command queue (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:282-302`). The hardware-info structure contains vendor ID, device ID, revision ID and optional hardware attributes (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:143-153`). Therefore an arbitrary subset of counters supported by that virtual hardware/API/sample-type context can be scheduled without running the application or a GPU workload.

The read-only offline query against `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\bin\GPUPerfAPICounters-x64.dll`, using DX12, `kGpaSessionSampleTypeDiscreteCounter` and `1002:73A5:C0`, returned:

```text
GpaCounterLibOpenCounterContext: kGpaStatusOk
GpaCounterLibGetNumCounters:     kGpaStatusOk, 145 counters
GpaCounterLibGetPassCount:       kGpaStatusOk, 13 passes for the enabled 31
```

The returned count agrees with the preserved phase-2N statement (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\PHASE_2N_RESULTS.md:46-48`). The phase-2N enumerator independently records the use of a live DX12 context and session to enumerate 145 default-context counters (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpaenum.cpp:48-103`).

The offline result is useful but does not remove the runtime obligation. The Counter Library documentation notes that its virtual-context path cannot check the driver version (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:518-530`). The actual application must therefore check and log the status and result of its live `GpaGetPassCount` call for the exact successfully enabled set. It currently ignores the status (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:149-156`).

## 4. Derived versus raw hardware counters and one-pass subsets

### Classification of all 145 enumerated counters

The enumerator calls `GpaOpenContext` with `kGpaOpenContextDefaultBit` (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpaenum.cpp:85-88`). It does not add `kGpaOpenContextEnableHardwareCountersBit`, whose value and purpose are defined at `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_types.h:190-205`.

The SDK explicitly says that GPA exposes derived counters by default and exposes raw hardware counters directly only when the hardware-counter flag is added (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\api_functions\gpa_opencontext.rst.txt:92-99`). `GpaCounterInfo` contains an `is_derived_counter` flag and either a derived-counter record or raw-hardware-counter record (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:182-200`).

The offline virtual-context query of `GpaCounterLibGetCounterInfo` classified the saved 145-name enumeration as:

```text
DERIVED counters:     145
RAW HARDWARE counters: 0
```

This is consistent with the enumerator's default context and the SDK's documented flag semantics (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpaenum.cpp:85-117`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\api_functions\gpa_opencontext.rst.txt:92-99`). Consequently, the phrase “145 hardware counters” is inaccurate if it means raw hardware events: `gpa_counters.csv` contains 145 public derived counters (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpa_counters.csv:1-146`).

### Underlying raw-block dependencies for all 145

The names below are the exact names in `C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpa_counters.csv:2-146`. Their raw block sets were returned by the local `GpaCounterLibGetCounterInfo` implementation in `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\bin\GPUPerfAPICounters-x64.dll`, using the structures at `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:155-200`. The block identifiers themselves are defined at `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:44-104`. A derived counter may depend on multiple raw blocks.

| Raw block set | Derived counters |
|---|---|
| TIMESTAMP | GPUTime, ExecutionDuration, ExecutionStart, ExecutionEnd |
| CPF | GPUBusy, GPUBusyCycles |
| CPF + GEDIST | TessellatorBusy |
| GEDIST | TessellatorBusyCycles |
| CPF + SPI | VsGsBusy, PreTessellationBusy, PostTessellationBusy, PSBusy, CSBusy |
| SPI | VsGsBusyCycles, PreTessellationBusyCycles, PostTessellationBusyCycles, PSBusyCycles, CSBusyCycles, CSThreadGroupsLaunched, CSWavefrontsLaunched |
| CPF + SPI + TIMESTAMP | VsGsTime, PreTessellationTime, PostTessellationTime, PSTime, CSTime |
| GESE + SPI | GSVerticesOut, PreTessVerticesIn, PostTessPrimsOut |
| SPI + SQ | VsGsVALUInstCount, VsGsSALUInstCount, PreTessVALUInstCount, PreTessSALUInstCount, PreTessVALUBusyCycles, PreTessSALUBusyCycles, PostTessVALUInstCount, PostTessSALUInstCount, PostTessVALUBusyCycles, PostTessSALUBusyCycles, CSThreadGroupSize |
| CPF + SPI + SQ | PreTessVALUBusy, PreTessSALUBusy, PostTessVALUBusy, PostTessSALUBusy |
| CPF + PA | PrimitiveAssemblyBusy, PAStalledOnRasterizer |
| PA | PrimitiveAssemblyBusyCycles, PrimitivesIn, CulledPrims, ClippedPrims, PAStalledOnRasterizerCycles |
| SX | PSPixelsOut, PSExportStallsCycles |
| CPF + SX | PSExportStalls |
| SQ | CSThreadsLaunched, CSVALUInsts, CSVALUUtilization, CSSALUInsts, CSVFetchInsts, CSSFetchInsts, CSVWriteInsts, CSGDSInsts, CSLDSInsts, CSALUStalledByLDSCycles, CSLDSBankConflictCycles, ScalarCacheHit, ScalarCacheRequestCount, ScalarCacheHitCount, ScalarCacheMissCount, InstCacheHit, InstCacheRequestCount, InstCacheHitCount, InstCacheMissCount |
| CPF + SQ | CSALUStalledByLDS, CSLDSBankConflict |
| CPF + TA | TexUnitBusy, MemUnitBusy |
| TA | TexUnitBusyCycles, TexTriFilteringPct, TexTriFilteringCount, NoTexTriFilteringCount, TexVolFilteringPct, TexVolFilteringCount, NoTexVolFilteringCount, TexAveAnisotropy, MemUnitBusyCycles |
| CPF + DB | DepthStencilTestBusy, ZUnitStalled |
| DB | DepthStencilTestBusyCycles, HiZTilesAccepted, HiZTilesAcceptedCount, HiZTilesRejectedCount, PreZTilesDetailCulled, PreZTilesDetailCulledCount, PreZTilesDetailSurvivingCount, PreZSamplesPassing, PreZSamplesFailingS, PreZSamplesFailingZ, PostZSamplesPassing, PostZSamplesFailingS, PostZSamplesFailingZ, ZUnitStalledCycles, DBMemRead, DBMemWritten |
| SC | HiZQuadsCulled, HiZQuadsCulledCount, HiZQuadsAcceptedCount, PreZQuadsCulled, PreZQuadsCulledCount, PreZQuadsSurvivingCount, PostZQuads, PostZQuadCount |
| CB | CBMemRead, CBColorAndMaskRead, CBMemWritten, CBColorAndMaskWritten, CBSlowPixelPct, CBSlowPixelCount |
| TCP | L0CacheHit, L0CacheRequestCount, L0CacheHitCount, L0CacheMissCount, L0TagConflictReadStalledCycles, L0TagConflictWriteStalledCycles, L0TagConflictAtomicStalledCycles, MemUnitStalledCycles |
| GL1C | L1CacheHit, L1CacheRequestCount, L1CacheHitCount, L1CacheMissCount |
| GL2C | L2CacheHit, L2CacheMiss, L2CacheRequestCount, L2CacheHitCount, L2CacheMissCount, FetchSize, WriteSize, WriteUnitStalledCycles |
| CPF + TCP | MemUnitStalled |
| CPF + GL2C | WriteUnitStalled |
| EA | LocalVidMemBytes, PcieBytes |
| TD | RayTriTests, RayBoxTests, TotalRayTests, RayTestsPerWave |

### Offline pass-count results for the current set

The local Counter Library scheduler returned the following individual pass counts for currently enabled counters that cannot participate in any one-pass subset because they already require multiple passes alone:

```text
PSBusy                    2
PSTime                    3
VsGsTime                  2
PrimitiveAssemblyBusy     2
CulledPrims               2
TexAveAnisotropy          5
```

These results were obtained through `GpaCounterLibGetPassCount` as declared at `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:477-491`, against `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\bin\GPUPerfAPICounters-x64.dll` and the recorded identity `C:\Users\Lorenzo\Downloads\driver mod\research\00_inventory\gpu_info.json:3-9`.

`GPUTime` requires one pass alone, but the offline scheduler returned two passes when it was paired with any other member of the current set. Exhaustive subset queries over the current 31 found this largest 10-counter one-pass subset:

```text
GPUBusy
VsGsBusy
PrimitivesIn
ClippedPrims
PAStalledOnRasterizer
DepthStencilTestBusy
ZUnitStalled
CBMemRead
CBMemWritten
WriteUnitStalled
```

The scheduler returned one pass for this set and no one-pass 11-counter subset among the current 31. The query contract is documented at `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:477-516`.

That cardinality-maximal set is not useful for the texture-filter causal question because it omits texture/cache counters. Requiring `TexUnitBusy`, the largest one-pass subset found contained seven counters:

```text
TexUnitBusy
GPUBusy
VsGsBusy
PrimitivesIn
ClippedPrims
PAStalledOnRasterizer
MemUnitBusy
```

Requiring both `TexUnitBusy` and `L2CacheHit`, the largest found subset contained five counters:

```text
TexUnitBusy
L2CacheHit
GPUBusy
PrimitivesIn
MemUnitBusy
```

The offline scheduler also returned two passes for `TexUnitBusy` paired with any one of `TexTriFilteringPct`, `TexTriFilteringCount`, `NoTexTriFilteringCount`, `TexVolFilteringPct`, `TexVolFilteringCount` or `NoTexVolFilteringCount`, and six passes for `TexUnitBusy` plus `TexAveAnisotropy`. Those filtering names and their semantics are documented at `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:135-148`.

### What determines pass count on RDNA2

**INFERENCE grounded in the scheduler interface and returned dependencies:** pass count is determined by expansion of public derived counters into raw events, the compatibility and finite event capacity of each hardware block, timing-query requirements, API and sample type, device/revision/hardware attributes, context flags and the live driver/context. It is not determined merely by the count of public counters or their documentation group. The SDK exposes `GpaCounterLibGetCountersByPass` specifically to reveal how the corresponding raw counters are scheduled (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:493-516`). The local documentation gives no static rule such as “one documented group equals one pass”; it requires querying after enabling the actual set (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\usage.rst.txt:441-457`).

## 5. Counters relevant to the texture-filter causal question

### Filtering-related counters actually enumerated

The exact filtering-related names in the 145-counter enumeration are (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpa_counters.csv:68-76`):

```text
TexUnitBusy
TexUnitBusyCycles
TexTriFilteringPct
TexTriFilteringCount
NoTexTriFilteringCount
TexVolFilteringPct
TexVolFilteringCount
NoTexVolFilteringCount
TexAveAnisotropy
```

The six tri/volume counters report whether or how many pixels received those specific filtering modes, while `TexAveAnisotropy` reports average applied anisotropy (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:135-148`). They do not report general texture sample count, filtered texels per clock, address-pipe utilization, filter-pipe utilization or achieved filter throughput.

`TexUnitBusy` and `TexUnitBusyCycles` report texture-unit activity “with all extra fetches and any cache or memory effects taken into account” (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:35-38`). They are therefore not pure filtering-rate counters.

The current 31-counter instrumentation enables only `TexUnitBusy` and `TexAveAnisotropy` from that filtering-related set; it does not enable the tri/volume filtering counts (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:66-78`).

### Cache and latency discriminants

The enumerated cache/latency-related counters include (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpa_counters.csv:109-142`):

```text
L0CacheHit
L0CacheRequestCount
L0CacheHitCount
L0CacheMissCount
L0TagConflictReadStalledCycles
L0TagConflictWriteStalledCycles
L0TagConflictAtomicStalledCycles
L1CacheHit
L1CacheRequestCount
L1CacheHitCount
L1CacheMissCount
L2CacheHit
L2CacheMiss
L2CacheRequestCount
L2CacheHitCount
L2CacheMissCount
MemUnitStalled
MemUnitStalledCycles
FetchSize
LocalVidMemBytes
```

Their documented meanings are cache requests/hits/misses, tag-conflict stalls, memory-unit stalls and traffic—not filtering rate (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:196-243`). `MemUnitBusy` explicitly includes `MemUnitStalled`, so a high busy value is not independently evidence of useful throughput (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:235-240`).

In the historical `Render Color` output, `TexUnitBusy` and `MemUnitBusy` are exactly equal at `94.609951`, while `MemUnitStalled` is `0.414793` (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\c_Render_Color.csv:15-16,29-30`). The offline counter-info mapping shows that both busy counters depend on `CPF + TA`, so they are not two independent confirmations of a filtering bottleneck (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:182-200`; local mapping reported in section 4 above).

### Missing pixel-shader ALU discriminator

The enumeration has only three counters in the `PixelShader` group: `PSPixelsOut`, `PSExportStalls` and `PSExportStallsCycles` (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpa_counters.csv:49-51`). The timing group adds `PSBusy`, `PSBusyCycles` and `PSTime`, which report the presence/duration of pixel-shader work, not vector/scalar ALU saturation (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:29-31`).

The available `VsGsVALUInstCount`/`VsGsSALUInstCount` counters apply to VS/GS (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:45-54`). The `PreTess*` and `PostTess*` counters apply to tessellation pipelines (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:56-84`). The `CSVALU*`, `CSSALU*` and related counters apply to compute shaders (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:110-132`). None is a general pixel-shader VALU/SALU utilization, instruction, busy-cycle or occupancy counter.

### Causal conclusion

**VERIFIED:** no counter among the saved 145-name discrete enumeration directly discriminates texture-filter rate from texture-cache/latency and pixel-shader ALU. Filtering composition can be observed with the tri/volume/aniso counters, and cache behavior can be observed with the cache/stall counters, but the enumeration lacks both a direct filter-throughput metric and a PS-specific ALU metric (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpa_counters.csv:2-146`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:8-148,196-243`).

Therefore the historical statements that `TexUnitBusy=94.6%` means the unit was issuing sampling operations at its maximum rate and that ALU was independently excluded do not follow from the documented semantics (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\PHASE_2N_RESULTS.md:68-90`). This conclusion was already challenged by the handoff audit, which notes that `TexUnitBusy` includes memory/cache effects and `PSBusy` does not mean ALU saturation (`C:\Users\Lorenzo\Downloads\driver mod\research\CODEX_HANDOFF_AUDIT.md:195-215`). A valid causal answer needs the controlled discriminating experiment stated at the top of this report.

## 6. Command-list ordering, unchecked returns and shutdown

### Command-list registration ordering

The verified call sequence for a named direct context is:

```text
CommandContext::Begin
  -> EngineProfiling::BeginBlock
     -> NestedTimingTree::PushProfilingMarker
        -> GpaProfiler::BeginScope
  -> GpaProfiler::OnContextBegin
```

`CommandContext::Begin` calls `EngineProfiling::BeginBlock` at line 84 and only afterward calls `GpaProfiler::OnContextBegin` at line 86 (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\CommandContext.cpp:79-87`). `BeginBlock` calls `NestedTimingTree::PushProfilingMarker` (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\EngineProfiling.cpp:486-489`), which calls `GpaProfiler::BeginScope` (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\EngineProfiling.cpp:558-564`). `BeginScope` requires the context already to exist in `g_Lists` and otherwise logs “scope su command list non registrata” (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:203-212`). Registration occurs too late.

`ComputeContext::Begin` has an additional defect: it calls `EngineProfiling::BeginBlock` but never calls `GpaProfiler::OnContextBegin` (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\CommandContext.cpp:90-98`). `PostEffects::Render` creates its context through `ComputeContext::Begin` (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\PostEffects.cpp:479-488`), and `ProcessHDR` creates the `HDR Tone Mapping` scope on that context (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\PostEffects.cpp:375-379`). This explains why that scope was not registered for GPA.

`CommandContext::Finish` ends the profiling block before `OnContextFinish`, so its end order is internally consistent (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\CommandContext.cpp:135-150`). However, `CommandContext::Flush` executes and resets the command list without a corresponding GPA end/re-register hook (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\CommandContext.cpp:100-132`).

### Unchecked GPA return paths

The following return statuses are ignored in `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp`:

| File:line | GPA call | Consequence |
|---|---|---|
| `GpaProfiler.cpp:123` | `GpaGetNumEnabledCounters` | Status ignored; the default zero can masquerade as no enabled counters. |
| `GpaProfiler.cpp:128` | `GpaGetEnabledIndex` | Status ignored; the default index zero may be used. |
| `GpaProfiler.cpp:129` | `GpaGetCounterName` | Status ignored; an empty/default name may be emitted. |
| `GpaProfiler.cpp:130` | `GpaGetCounterDataType` | Status ignored; the default `kGpaDataTypeUint64` may decode a failed query incorrectly. |
| `GpaProfiler.cpp:152` | `GpaGetPassCount` | Status ignored; `g_Passes` can remain zero and collection still becomes enabled. |
| `GpaProfiler.cpp:163` | `GpaDeleteSession` | Status ignored. |
| `GpaProfiler.cpp:164` | `GpaCloseContext` | Status ignored. |
| `GpaProfiler.cpp:165` | `GpaDestroy` | Status ignored. |
| `GpaProfiler.cpp:199` | `GpaEndCommandList` | Status ignored and the list entry is erased anyway. |
| `GpaProfiler.cpp:217` | `GpaEndSample` | Status ignored; the sample is cleared and counted anyway. |

All exact call sites are visible together at `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:112-134,149-165,184-231`.

Two further paths inspect a return value but do not fail closed:

- `GpaEnableCounterByName` failures only reduce `nOk`; the application continues with a silently smaller counter set and does not log which names failed (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:149-156`).
- `GpaIsSessionComplete` treats every non-OK status as “not complete,” so `kGpaStatusErrorResultNotReady` cannot be distinguished from a real error before or after the polling loop (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:112-122`; documented status semantics at `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\api_functions\gpa_issessioncomplete.rst.txt:28-43`).

The calls whose statuses are checked are `GpaInitialize`, `GpaOpenContext`, `GpaCreateSession`, `GpaBeginSession`, `GpaBeginCommandList`, `GpaBeginSample`, `GpaEndSession`, `GpaGetSampleResultSize` and `GpaGetSampleResult` (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:138-148,171-190,203-230`). Those checks do not compensate for the unchecked paths above.

### Shutdown path

`GpaProfiler::Shutdown` is declared at `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.h:15-20` and defined at `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:160-167`. No call to it exists in the inspected MiniEngine sources. The application termination path calls `TerminateApplication`, then `Graphics::Shutdown`, and returns (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GameCore.cpp:212-214`); `TerminateApplication` idles the GPU, calls game cleanup and shuts down input, but not GPA (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GameCore.cpp:52-59`). Thus `GpaProfiler::Shutdown()` may never run on the inspected path.

## Final classification

- **VERIFIED — invalid multipass composition:** the 31-counter set requires 13 passes, while the instrumentation advances through different rendered frames and does not restore temporal inputs/history between passes (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:222-231`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GameCore.cpp:165-178`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\usage.rst.txt:441-457`).
- **VERIFIED — counter type:** all 145 saved default-context names are public derived counters; none is a raw hardware counter (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpaenum.cpp:85-117`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\api_functions\gpa_opencontext.rst.txt:92-99`).
- **VERIFIED — missing causal discriminator:** the enumeration has neither a direct texture-filter-throughput/rate counter nor a PS-specific ALU utilization/instruction/occupancy counter (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\gpa_counters.csv:2-146`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\graphics_counter_tables_gfx103.rst.txt:8-148,196-243`).
- **VERIFIED — instrumentation defects:** command-list registration is ordered after some scope begins, compute contexts are not registered by `ComputeContext::Begin`, multiple GPA statuses are ignored, and the inspected shutdown path does not call `GpaProfiler::Shutdown` (`C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\CommandContext.cpp:79-98`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GpaProfiler.cpp:112-231`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\src\dxs\MiniEngine\Core\GameCore.cpp:212-214`).
- **INFERENCE — individual scalar accuracy:** individual historical values may be numerically plausible, but their errors cannot be bounded from the preserved data because the raw events were sampled on non-identical frames (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\counters_by_pass.csv:1-32`; `C:\Users\Lorenzo\Downloads\driver mod\research\CODEX_HANDOFF_AUDIT.md:183-215`).
- **INFERENCE — raw SQ/TA availability:** the hardware-counter flag is documented to expose raw counters, but useful Navi21 `SQ`/`TA` events were not actually re-enumerated in this audit and must not be invented (`C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\help\_sources\api_functions\gpa_opencontext.rst.txt:92-99`; `C:\Users\Lorenzo\AppData\Local\Temp\claude\gpa\4_4\include\gpu_performance_api\gpu_perf_api_counters.h:44-104`).

**Final verdict:** phase 2N cannot support the causal bottleneck classifications in `PHASE_2N_RESULTS.md`. The counter data must be reacquired using either a genuinely identical replay across passes or a runtime-checked one-pass counter set, with every GPA status handled fail-closed (`C:\Users\Lorenzo\Downloads\driver mod\research\23_bottleneck\PHASE_2N_RESULTS.md:14-90`; `C:\Users\Lorenzo\Downloads\driver mod\research\CODEX_HANDOFF_AUDIT.md:183-227`).
