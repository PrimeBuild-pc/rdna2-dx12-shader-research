//
// Phase 2N - GPUPerfAPI dentro MiniEngine. Vedi GpaProfiler.h.
//
// Modello richiesto da GPA: BeginSession -> per ogni command list BeginCommandList
// (subito dopo l'apertura, prima di altri comandi) -> BeginSample/EndSample -> EndCommandList
// -> EndSession. Servono piu' passate: l'app ripete lo stesso frame, che a passo fisso e'
// deterministico.
//
#include "pch.h"
#include "GpaProfiler.h"
#include "CommandContext.h"
#include <string>
#include <vector>
#include <map>
#include <cstdio>
#include <cstdarg>
#include "gpu_performance_api/gpu_perf_api.h"

namespace GpaProfiler
{
    bool Enabled = false;

    namespace
    {
        typedef GpaStatus(*PFN_Init)(GpaInitializeFlags);
        typedef GpaStatus(*PFN_Destroy)();
        typedef GpaStatus(*PFN_Open)(void*, GpaOpenContextFlags, GpaContextId*);
        typedef GpaStatus(*PFN_Close)(GpaContextId);
        typedef GpaStatus(*PFN_CreateSession)(GpaContextId, GpaSessionSampleType, GpaSessionId*);
        typedef GpaStatus(*PFN_DeleteSession)(GpaSessionId);
        typedef GpaStatus(*PFN_EnableByName)(GpaSessionId, const char*);
        typedef GpaStatus(*PFN_PassCount)(GpaSessionId, GpaUInt32*);
        typedef GpaStatus(*PFN_Session)(GpaSessionId);
        typedef GpaStatus(*PFN_BeginCmdList)(GpaSessionId, GpaUInt32, void*, GpaCommandListType, GpaCommandListId*);
        typedef GpaStatus(*PFN_EndCmdList)(GpaCommandListId);
        typedef GpaStatus(*PFN_BeginSample)(GpaUInt32, GpaCommandListId);
        typedef GpaStatus(*PFN_EndSample)(GpaCommandListId);
        typedef GpaStatus(*PFN_ResultSize)(GpaSessionId, GpaUInt32, size_t*);
        typedef GpaStatus(*PFN_Result)(GpaSessionId, GpaUInt32, size_t, void*);
        typedef GpaStatus(*PFN_NumEnabled)(GpaSessionId, GpaUInt32*);
        typedef GpaStatus(*PFN_EnabledIndex)(GpaSessionId, GpaUInt32, GpaUInt32*);
        typedef GpaStatus(*PFN_CounterStr)(GpaSessionId, GpaUInt32, const char**);
        typedef GpaStatus(*PFN_DataType)(GpaSessionId, GpaUInt32, GpaDataType*);

        HMODULE g_Lib = nullptr;
        PFN_Init pInit; PFN_Destroy pDestroy; PFN_Open pOpen; PFN_Close pClose;
        PFN_CreateSession pCreateSession; PFN_DeleteSession pDeleteSession;
        PFN_EnableByName pEnable; PFN_PassCount pPassCount;
        PFN_Session pBeginSession, pEndSession, pIsComplete;
        PFN_BeginCmdList pBeginCmd; PFN_EndCmdList pEndCmd;
        PFN_BeginSample pBeginSample; PFN_EndSample pEndSample;
        PFN_ResultSize pResultSize; PFN_Result pResult;
        PFN_NumEnabled pNumEnabled; PFN_EnabledIndex pEnabledIndex;
        PFN_CounterStr pName; PFN_DataType pDataType;

        GpaContextId g_Ctx = nullptr;
        GpaSessionId g_Session = nullptr;
        std::wstring g_Target;
        GpaUInt32 g_Passes = 0, g_Pass = 0;
        bool g_SessionOpen = false, g_Done = false;
        // command list aperte a GPA in questa passata
        std::map<CommandContext*, GpaCommandListId> g_Lists;
        GpaCommandListId g_SampleList = nullptr;
        int g_SamplesThisPass = 0;

        // Selezione fatta dopo aver ENUMERATO i counter reali (145 su Navi 21)
        const char* kCounters[] = {
            "GPUTime", "GPUBusy", "PSBusy", "PSTime", "VsGsBusy", "VsGsTime",
            "PSPixelsOut", "PSExportStalls",
            "PrimitiveAssemblyBusy", "PrimitivesIn", "CulledPrims", "ClippedPrims",
            "PAStalledOnRasterizer",
            "TexUnitBusy", "TexAveAnisotropy",
            "DepthStencilTestBusy", "ZUnitStalled", "DBMemRead", "DBMemWritten",
            "CBMemRead", "CBMemWritten", "CBSlowPixelPct",
            "L0CacheHit", "L1CacheHit", "L2CacheHit",
            "FetchSize", "WriteSize", "MemUnitBusy", "MemUnitStalled", "WriteUnitStalled",
            "LocalVidMemBytes",
        };

        struct Row { std::string name; double value; };
        std::vector<Row> g_Results;

        // l'applicazione e' windowed: printf non si vede. Diagnostica su file.
        void Log(const char* fmt, ...)
        {
            const char* lp = getenv("ME_GPA_LOG");
            FILE* f = nullptr;
            if (!lp || fopen_s(&f, lp, "a") != 0 || !f) return;
            va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
            fputc('\n', f); fclose(f);
        }

        bool LoadLib()
        {
            g_Lib = LoadLibraryA("GPUPerfAPIDX12-x64.dll");
            if (!g_Lib) return false;
#define GET(v, n) v = (decltype(v))GetProcAddress(g_Lib, n); if (!v) return false;
            GET(pInit, "GpaInitialize") GET(pDestroy, "GpaDestroy") GET(pOpen, "GpaOpenContext")
            GET(pClose, "GpaCloseContext") GET(pCreateSession, "GpaCreateSession")
            GET(pDeleteSession, "GpaDeleteSession") GET(pEnable, "GpaEnableCounterByName")
            GET(pPassCount, "GpaGetPassCount") GET(pBeginSession, "GpaBeginSession")
            GET(pEndSession, "GpaEndSession") GET(pIsComplete, "GpaIsSessionComplete")
            GET(pBeginCmd, "GpaBeginCommandList") GET(pEndCmd, "GpaEndCommandList")
            GET(pBeginSample, "GpaBeginSample") GET(pEndSample, "GpaEndSample")
            GET(pResultSize, "GpaGetSampleResultSize") GET(pResult, "GpaGetSampleResult")
            GET(pNumEnabled, "GpaGetNumEnabledCounters") GET(pEnabledIndex, "GpaGetEnabledIndex")
            GET(pName, "GpaGetCounterName") GET(pDataType, "GpaGetCounterDataType")
#undef GET
            return true;
        }

        void Collect()
        {
            for (int i = 0; i < 20000 && pIsComplete(g_Session) != kGpaStatusOk; ++i)
                Sleep(1);
            if (pIsComplete(g_Session) != kGpaStatusOk) { Log("[GPA] sessione non completata"); return; }
            size_t sz = 0;
            GpaStatus st = pResultSize(g_Session, 0, &sz);
            if (st != kGpaStatusOk || sz == 0) { Log("[GPA] ResultSize KO %d sz=%zu", (int)st, sz); return; }
            std::vector<char> buf(sz);
            st = pResult(g_Session, 0, sz, buf.data());
            if (st != kGpaStatusOk) { Log("[GPA] GetSampleResult KO %d", (int)st); return; }
            GpaUInt32 nEnabled = 0; pNumEnabled(g_Session, &nEnabled);
            const GpaUInt64* u = (const GpaUInt64*)buf.data();
            const GpaFloat64* f = (const GpaFloat64*)buf.data();
            for (GpaUInt32 i = 0; i < nEnabled; ++i)
            {
                GpaUInt32 idx = 0; pEnabledIndex(g_Session, i, &idx);
                const char* nm = ""; pName(g_Session, idx, &nm);
                GpaDataType dt = kGpaDataTypeUint64; pDataType(g_Session, idx, &dt);
                double v = (dt == kGpaDataTypeFloat64) ? (double)f[i] : (double)u[i];
                g_Results.push_back({ nm ? nm : "", v });
            }
            Log("[GPA] raccolti %u counter", nEnabled);
        }
    }

    void Initialize(void* commandQueue)
    {
        const char* scope = getenv("ME_GPA_SCOPE");
        if (!scope || !commandQueue) return;
        Log("[GPA] Initialize, queue=%p", commandQueue);
        if (!LoadLib()) { Log("[GPA] DLL non caricata err=%lu", GetLastError()); return; }
        if (pInit(kGpaInitializeDefaultBit) != kGpaStatusOk) { Log("[GPA] Initialize KO"); return; }
        if (pOpen(commandQueue, kGpaOpenContextDefaultBit, &g_Ctx) != kGpaStatusOk) {
            Log("[GPA] OpenContext KO"); return; }
        if (pCreateSession(g_Ctx, kGpaSessionSampleTypeDiscreteCounter, &g_Session) != kGpaStatusOk) {
            Log("[GPA] CreateSession KO"); return; }
        int nOk = 0;
        for (const char* c : kCounters)
            if (pEnable(g_Session, c) == kGpaStatusOk) ++nOk;
        pPassCount(g_Session, &g_Passes);
        wchar_t wbuf[128]; size_t n = 0;
        mbstowcs_s(&n, wbuf, scope, _TRUNCATE);
        g_Target = wbuf;
        Log("[GPA] scope \"%s\": %d counter, %u passate", scope, nOk, g_Passes);
        Enabled = true;
    }

    void Shutdown()
    {
        if (!Enabled) return;
        if (g_Session) pDeleteSession(g_Session);
        if (g_Ctx) pClose(g_Ctx);
        if (pDestroy) pDestroy();
        Enabled = false;
    }

    bool Done() { return g_Done; }

    void BeginFrame()
    {
        if (!Enabled || g_Done) return;
        if (!g_SessionOpen)
        {
            GpaStatus st = pBeginSession(g_Session);
            if (st != kGpaStatusOk) { Log("[GPA] BeginSession KO %d", (int)st); g_Done = true; return; }
            g_SessionOpen = true;
            Log("[GPA] sessione avviata");
        }
        g_SamplesThisPass = 0;
    }

    void OnContextBegin(CommandContext* ctx)
    {
        if (!Enabled || g_Done || !g_SessionOpen || !ctx) return;
        GpaCommandListId id = nullptr;
        GpaStatus st = pBeginCmd(g_Session, g_Pass, ctx->GetCommandList(),
                                 kGpaCommandListPrimary, &id);
        if (st != kGpaStatusOk) { Log("[GPA] BeginCommandList KO %d pass=%u", (int)st, g_Pass); return; }
        g_Lists[ctx] = id;
    }

    void OnContextFinish(CommandContext* ctx)
    {
        if (!Enabled || !ctx) return;
        auto it = g_Lists.find(ctx);
        if (it == g_Lists.end()) return;
        pEndCmd(it->second);
        g_Lists.erase(it);
    }

    void BeginScope(const wchar_t* name, CommandContext* ctx)
    {
        if (!Enabled || g_Done || !ctx || !name || g_Target != name) return;
        if (g_SamplesThisPass != 0) return;          // un solo sample per passata
        auto it = g_Lists.find(ctx);
        if (it == g_Lists.end()) { Log("[GPA] scope su command list non registrata"); return; }
        GpaStatus st = pBeginSample(0, it->second);
        if (st != kGpaStatusOk) { Log("[GPA] BeginSample KO %d", (int)st); g_Done = true; return; }
        g_SampleList = it->second;
    }

    void EndScope(const wchar_t* name, CommandContext* ctx)
    {
        if (!Enabled || g_Done || !g_SampleList || !name || g_Target != name) return;
        pEndSample(g_SampleList);
        g_SampleList = nullptr;
        ++g_SamplesThisPass;
    }

    void EndFrame()
    {
        if (!Enabled || g_Done || !g_SessionOpen) return;
        if (g_SamplesThisPass == 0) return;          // passata senza sample: non conta
        ++g_Pass;
        if (g_Pass < g_Passes) return;
        GpaStatus st = pEndSession(g_Session);
        if (st != kGpaStatusOk) { Log("[GPA] EndSession KO %d", (int)st); g_Done = true; return; }
        Collect();
        g_Done = true;
    }

    void Dump(const char* path)
    {
        if (g_Results.empty()) { Log("[GPA] nessun risultato da scrivere"); return; }
        FILE* fp = nullptr;
        if (fopen_s(&fp, path, "w") != 0 || !fp) return;
        fprintf(fp, "counter,value\n");
        for (auto& r : g_Results)
            fprintf(fp, "%s,%.6f\n", r.name.c_str(), r.value);
        fclose(fp);
        Log("[GPA] scritto %s (%zu counter)", path, g_Results.size());
    }
}
