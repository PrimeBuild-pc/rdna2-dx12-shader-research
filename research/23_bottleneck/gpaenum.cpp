// Phase 2N - enumera i performance counter hardware REALMENTE esposti dalla GPU.
//
// Il brief dice: "non indovinare nomi di counter". Questo apre un contesto GPUPerfAPI
// DX12 sulla GPU installata e stampa nome, gruppo, tipo e descrizione di ogni counter.
//
//   gpaenum.exe [out.csv]

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <cstdio>
#include <string>
#include "gpu_performance_api/gpu_perf_api.h"

#pragma comment(lib, "d3d12.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "dxguid.lib")

#define HR(x) do { HRESULT _h=(x); if (FAILED(_h)) { fprintf(stderr,"FAIL %s 0x%08lX riga %d\n", \
    #x,(unsigned long)_h,__LINE__); return 2; } } while(0)

typedef GpaStatus (*PFN_Init)(GpaInitializeFlags);
typedef GpaStatus (*PFN_Open)(void*, GpaOpenContextFlags, GpaContextId*);
typedef GpaStatus (*PFN_CreateSession)(GpaContextId, GpaSessionSampleType, GpaSessionId*);
typedef GpaStatus (*PFN_NumCounters)(GpaSessionId, GpaUInt32*);
typedef GpaStatus (*PFN_CounterStr)(GpaSessionId, GpaUInt32, const char**);
typedef GpaStatus (*PFN_UsageType)(GpaSessionId, GpaUInt32, GpaUsageType*);
typedef GpaStatus (*PFN_SampleTypes)(GpaContextId, GpaContextSampleTypeFlags*);
typedef GpaStatus (*PFN_GetVersion)(GpaUInt32*, GpaUInt32*, GpaUInt32*, GpaUInt32*);

static const char* UsageName(GpaUsageType u)
{
    switch (u)
    {
    case kGpaUsageTypeRatio: return "ratio";
    case kGpaUsageTypePercentage: return "percentuale";
    case kGpaUsageTypeCycles: return "cicli";
    case kGpaUsageTypeMilliseconds: return "ms";
    case kGpaUsageTypeBytes: return "byte";
    case kGpaUsageTypeItems: return "conteggio";
    case kGpaUsageTypeKilobytes: return "KB";
    case kGpaUsageTypeNanoseconds: return "ns";
    default: return "?";
    }
}

int main(int argc, char** argv)
{
    const char* outPath = argc > 1 ? argv[1] : "gpa_counters.csv";

    HMODULE lib = LoadLibraryA("GPUPerfAPIDX12-x64.dll");
    if (!lib) { fprintf(stderr, "GPUPerfAPIDX12-x64.dll non caricata (%lu)\n", GetLastError()); return 1; }
    auto Init = (PFN_Init)GetProcAddress(lib, "GpaInitialize");
    auto Open = (PFN_Open)GetProcAddress(lib, "GpaOpenContext");
    auto CreateSession = (PFN_CreateSession)GetProcAddress(lib, "GpaCreateSession");
    auto NumCounters = (PFN_NumCounters)GetProcAddress(lib, "GpaGetNumCounters");
    auto CName = (PFN_CounterStr)GetProcAddress(lib, "GpaGetCounterName");
    auto CGroup = (PFN_CounterStr)GetProcAddress(lib, "GpaGetCounterGroup");
    auto CDesc = (PFN_CounterStr)GetProcAddress(lib, "GpaGetCounterDescription");
    auto CUsage = (PFN_UsageType)GetProcAddress(lib, "GpaGetCounterUsageType");
    auto SampleTypes = (PFN_SampleTypes)GetProcAddress(lib, "GpaGetSupportedSampleTypes");
    auto GetVer = (PFN_GetVersion)GetProcAddress(lib, "GpaGetVersion");
    if (!Init || !Open || !CreateSession || !NumCounters || !CName) {
        fprintf(stderr, "export GPA mancanti\n"); return 1;
    }
    if (GetVer) { GpaUInt32 a=0,b=0,c=0,d=0; GetVer(&a,&b,&c,&d);
                  printf("GPUPerfAPI %u.%u.%u build %u\n", a,b,c,d); }

    IDXGIFactory6* fac = nullptr; HR(CreateDXGIFactory2(0, IID_PPV_ARGS(&fac)));
    IDXGIAdapter1* ad = nullptr; ID3D12Device* dev = nullptr; DXGI_ADAPTER_DESC1 des{};
    for (UINT i = 0; fac->EnumAdapterByGpuPreference(i, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
                                                     IID_PPV_ARGS(&ad)) != DXGI_ERROR_NOT_FOUND; ++i) {
        ad->GetDesc1(&des);
        if (des.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) { ad->Release(); continue; }
        if (SUCCEEDED(D3D12CreateDevice(ad, D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(&dev)))) break;
        ad->Release(); ad = nullptr;
    }
    if (!dev) { fprintf(stderr, "nessun device D3D12\n"); return 2; }
    wprintf(L"GPU: %s\n", des.Description);

    D3D12_COMMAND_QUEUE_DESC qd{}; qd.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    ID3D12CommandQueue* q = nullptr; HR(dev->CreateCommandQueue(&qd, IID_PPV_ARGS(&q)));

    if (Init(kGpaInitializeDefaultBit) != kGpaStatusOk) { fprintf(stderr, "GpaInitialize KO\n"); return 3; }
    GpaContextId ctx = nullptr;
    GpaStatus st = Open(q, kGpaOpenContextDefaultBit, &ctx);
    if (st != kGpaStatusOk) { fprintf(stderr, "GpaOpenContext KO (%d)\n", (int)st); return 3; }

    if (SampleTypes) {
        GpaContextSampleTypeFlags t = 0; SampleTypes(ctx, &t);
        printf("tipi di sample supportati: 0x%X%s%s\n", t,
               (t & kGpaContextSampleTypeDiscreteCounter) ? "  [contatori discreti]" : "",
               (t & kGpaContextSampleTypeStreamingCounter) ? "  [streaming]" : "");
    }

    GpaSessionId ses = nullptr;
    st = CreateSession(ctx, kGpaSessionSampleTypeDiscreteCounter, &ses);
    if (st != kGpaStatusOk) { fprintf(stderr, "GpaCreateSession KO (%d)\n", (int)st); return 3; }

    GpaUInt32 n = 0;
    if (NumCounters(ses, &n) != kGpaStatusOk) { fprintf(stderr, "GpaGetNumCounters KO\n"); return 3; }
    printf("counter disponibili: %u\n", n);

    FILE* f = nullptr;
    if (fopen_s(&f, outPath, "w") != 0 || !f) { fprintf(stderr, "non posso scrivere %s\n", outPath); return 4; }
    fprintf(f, "index,name,group,usage,description\n");
    for (GpaUInt32 i = 0; i < n; ++i) {
        const char *nm = "", *gr = "", *ds = "";
        GpaUsageType u = kGpaUsageTypeItems;
        CName(ses, i, &nm);
        if (CGroup) CGroup(ses, i, &gr);
        if (CDesc) CDesc(ses, i, &ds);
        if (CUsage) CUsage(ses, i, &u);
        std::string d(ds ? ds : "");
        for (auto& c : d) if (c == ',') c = ';';
        fprintf(f, "%u,%s,%s,%s,%s\n", i, nm ? nm : "", gr ? gr : "", UsageName(u), d.c_str());
    }
    fclose(f);
    printf("scritto %s\n", outPath);
    return 0;
}
