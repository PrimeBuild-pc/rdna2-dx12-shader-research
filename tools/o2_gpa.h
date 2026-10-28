// O2 only: read raw GPUPerfAPI counters around the real "Render Color" scope.
//
// Deliberately not a patch of Core/GpaProfiler.cpp. That one ignores ten GPA return codes,
// registers command lists after some scopes have already begun, never calls Shutdown, and
// silently shrinks the counter set when GpaEnableCounterByName fails. Every one of those turns
// a broken capture into a plausible-looking number. Here any GPA failure kills the process.
//
// Environment:
//   ME_O2_DIR      output directory (also switches the module on)
//   ME_O2_SET      file with one counter name per line ('#' comments)
//   ME_O2_FIRST    first frame to sample (default 140, after all 128 shadow slices)
//   ME_O2_SAMPLES  samples per pass, taken on consecutive frames (default 8)
//   ME_O2_PASSES   optional: required pass count; the run aborts if GPA reports another value
#pragma once
#include "CommandContext.h"
#include "Display.h"
#include "GraphicsCore.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "gpu_performance_api/gpu_perf_api.h"

namespace O2Gpa
{
    typedef GpaStatus (*PFN_Init)(GpaInitializeFlags);
    typedef GpaStatus (*PFN_Destroy)();
    typedef GpaStatus (*PFN_OpenCtx)(void*, GpaOpenContextFlags, GpaContextId*);
    typedef GpaStatus (*PFN_CloseCtx)(GpaContextId);
    typedef GpaStatus (*PFN_CreateSession)(GpaContextId, GpaSessionSampleType, GpaSessionId*);
    typedef GpaStatus (*PFN_DeleteSession)(GpaSessionId);
    typedef GpaStatus (*PFN_Session)(GpaSessionId);
    typedef GpaStatus (*PFN_EnableByName)(GpaSessionId, const char*);
    typedef GpaStatus (*PFN_U32)(GpaSessionId, GpaUInt32*);
    typedef GpaStatus (*PFN_Enabled)(GpaSessionId, GpaUInt32, GpaUInt32*);
    typedef GpaStatus (*PFN_CtrName)(GpaSessionId, GpaUInt32, const char**);
    typedef GpaStatus (*PFN_CtrType)(GpaSessionId, GpaUInt32, GpaDataType*);
    typedef GpaStatus (*PFN_BeginCmd)(GpaSessionId, GpaUInt32, void*, GpaCommandListType, GpaCommandListId*);
    typedef GpaStatus (*PFN_EndCmd)(GpaCommandListId);
    typedef GpaStatus (*PFN_BeginSample)(GpaUInt32, GpaCommandListId);
    typedef GpaStatus (*PFN_EndSample)(GpaCommandListId);
    typedef GpaStatus (*PFN_ResultSize)(GpaSessionId, GpaUInt32, size_t*);
    typedef GpaStatus (*PFN_Result)(GpaSessionId, GpaUInt32, size_t, void*);
    typedef const char* (*PFN_StatusStr)(GpaStatus);

    struct State
    {
        HMODULE lib = nullptr;
        PFN_Init Init; PFN_Destroy Destroy;
        PFN_OpenCtx OpenCtx; PFN_CloseCtx CloseCtx;
        PFN_CreateSession CreateSession; PFN_DeleteSession DeleteSession;
        PFN_Session BeginSession, EndSession, IsComplete;
        PFN_EnableByName EnableByName;
        PFN_U32 PassCount, NumEnabled;
        PFN_Enabled EnabledIndex;
        PFN_CtrName CtrName; PFN_CtrType CtrType;
        PFN_BeginCmd BeginCmd; PFN_EndCmd EndCmd;
        PFN_BeginSample BeginSample; PFN_EndSample EndSample;
        PFN_ResultSize ResultSize; PFN_Result Result;
        PFN_StatusStr StatusStr;

        GpaContextId ctx = nullptr;
        GpaSessionId session = nullptr;
        GpaCommandListId list = nullptr;
        void* list_ptr = nullptr;
        bool sampled = false;
        std::vector<std::string> names;
        std::vector<GpaDataType> types;
        unsigned pass = 0, passes = 0, sample = 0, samples = 8;
        unsigned long long first = 140;
        bool started = false, done = false;
        std::string dir;
    };
    inline State& S() { static State s; return s; }

    inline bool Enabled() { return getenv("ME_O2_DIR") != nullptr; }

    inline void Fail(const char* what, GpaStatus st)
    {
        // Fail-closed and diagnosable: leave the reason on disk, then stop. Never continue with
        // a partially configured session, which is how a broken capture becomes a "result".
        FILE* f = nullptr;
        std::string p = S().dir + "/gpa_failure.txt";
        if (fopen_s(&f, p.c_str(), "w") == 0 && f)
        {
            fprintf(f, "%s: status %d (%s)\n", what, (int)st,
                    S().StatusStr ? S().StatusStr(st) : "?");
            fclose(f);
        }
        fprintf(stderr, "[O2] %s: status %d\n", what, (int)st);
        ExitProcess(82);
    }
    inline void Check(const char* what, GpaStatus st)
    {
        if (st != kGpaStatusOk) Fail(what, st);
    }
    inline void Require(bool ok, const char* what)
    {
        if (!ok) Fail(what, kGpaStatusErrorFailed);
    }

    inline unsigned long long EnvU(const char* name, unsigned long long dflt)
    {
        const char* v = getenv(name);
        return v ? strtoull(v, nullptr, 10) : dflt;
    }

    inline void Initialize(ID3D12CommandQueue* queue)
    {
        if (!Enabled()) return;
        State& s = S();
        s.dir = getenv("ME_O2_DIR");
        s.first = EnvU("ME_O2_FIRST", 140);
        s.samples = (unsigned)EnvU("ME_O2_SAMPLES", 8);

        s.lib = LoadLibraryA("GPUPerfAPIDX12-x64.dll");
        Require(s.lib != nullptr, "LoadLibrary GPUPerfAPIDX12-x64.dll");
#define O2GET(field, sym) s.field = (decltype(s.field))GetProcAddress(s.lib, sym); \
                          Require(s.field != nullptr, "GetProcAddress " sym)
        O2GET(StatusStr, "GpaGetStatusAsStr");
        O2GET(Init, "GpaInitialize");            O2GET(Destroy, "GpaDestroy");
        O2GET(OpenCtx, "GpaOpenContext");        O2GET(CloseCtx, "GpaCloseContext");
        O2GET(CreateSession, "GpaCreateSession");O2GET(DeleteSession, "GpaDeleteSession");
        O2GET(BeginSession, "GpaBeginSession");  O2GET(EndSession, "GpaEndSession");
        O2GET(IsComplete, "GpaIsSessionComplete");
        O2GET(EnableByName, "GpaEnableCounterByName");
        O2GET(PassCount, "GpaGetPassCount");     O2GET(NumEnabled, "GpaGetNumEnabledCounters");
        O2GET(EnabledIndex, "GpaGetEnabledIndex");
        O2GET(CtrName, "GpaGetCounterName");     O2GET(CtrType, "GpaGetCounterDataType");
        O2GET(BeginCmd, "GpaBeginCommandList");  O2GET(EndCmd, "GpaEndCommandList");
        O2GET(BeginSample, "GpaBeginSample");    O2GET(EndSample, "GpaEndSample");
        O2GET(ResultSize, "GpaGetSampleResultSize"); O2GET(Result, "GpaGetSampleResult");
#undef O2GET

        Check("GpaInitialize", s.Init(kGpaInitializeDefaultBit));
        // The hardware-counter bit is the whole point: the derived set cannot separate
        // pixel-stage ALU from texture work. See research/26_gpa_hwcounters/.
        Check("GpaOpenContext", s.OpenCtx(queue, kGpaOpenContextEnableHardwareCountersBit, &s.ctx));
        Check("GpaCreateSession",
              s.CreateSession(s.ctx, kGpaSessionSampleTypeDiscreteCounter, &s.session));

        const char* setPath = getenv("ME_O2_SET");
        Require(setPath != nullptr, "ME_O2_SET not set");
        FILE* f = nullptr;
        Require(fopen_s(&f, setPath, "r") == 0 && f != nullptr, "cannot open ME_O2_SET");
        char line[512];
        unsigned wanted = 0;
        while (fgets(line, sizeof(line), f))
        {
            std::string n(line);
            while (!n.empty() && (n.back() == '\n' || n.back() == '\r' || n.back() == ' ')) n.pop_back();
            if (n.empty() || n[0] == '#') continue;
            ++wanted;
            // Every requested counter must be enabled. A silently smaller set measures
            // something other than what was asked for.
            Check("GpaEnableCounterByName", s.EnableByName(s.session, n.c_str()));
        }
        fclose(f);
        Require(wanted > 0, "empty counter set");

        GpaUInt32 enabled = 0;
        Check("GpaGetNumEnabledCounters", s.NumEnabled(s.session, &enabled));
        Require(enabled == wanted, "enabled counter count differs from the requested set");
        for (GpaUInt32 i = 0; i < enabled; ++i)
        {
            GpaUInt32 idx = 0;
            Check("GpaGetEnabledIndex", s.EnabledIndex(s.session, i, &idx));
            const char* nm = nullptr;
            Check("GpaGetCounterName", s.CtrName(s.session, idx, &nm));
            GpaDataType dt;
            Check("GpaGetCounterDataType", s.CtrType(s.session, idx, &dt));
            s.names.push_back(nm ? nm : "?");
            s.types.push_back(dt);
        }

        GpaUInt32 passes = 0;
        Check("GpaGetPassCount", s.PassCount(s.session, &passes));
        Require(passes > 0, "GpaGetPassCount returned zero");
        s.passes = passes;
        unsigned long long expect = EnvU("ME_O2_PASSES", 0);
        Require(expect == 0 || expect == passes, "pass count differs from ME_O2_PASSES");

        Check("GpaBeginSession", s.BeginSession(s.session));
        s.started = true;

        std::string p = s.dir + "/gpa_session.txt";
        if (fopen_s(&f, p.c_str(), "w") == 0 && f)
        {
            fprintf(f, "counters=%u\npasses=%u\nsamples_per_pass=%u\nfirst_frame=%llu\n",
                    enabled, passes, s.samples, s.first);
            fclose(f);
        }
    }

    // True while this frame is one of the frames that must carry a sample.
    inline bool Measuring()
    {
        State& s = S();
        if (!Enabled() || s.done || !s.started) return false;
        unsigned long long fc = Graphics::GetFrameCount();
        return fc >= s.first && fc < s.first + (unsigned long long)s.passes * s.samples;
    }

    inline void OnContextBegin(CommandContext& ctx)
    {
        if (!Measuring()) return;
        State& s = S();
        Require(s.list == nullptr, "command list registered twice in one frame");
        s.list_ptr = ctx.GetCommandList();
        Check("GpaBeginCommandList",
              s.BeginCmd(s.session, s.pass, s.list_ptr, kGpaCommandListPrimary, &s.list));
    }

    inline void OnContextEnd(CommandContext&)
    {
        State& s = S();
        if (!s.list) return;
        Check("GpaEndCommandList", s.EndCmd(s.list));
        s.list = nullptr;
        s.list_ptr = nullptr;
    }

    // RAII around exactly the Render Color block, so the sample cannot outlive it.
    struct Scope
    {
        bool active = false;
        explicit Scope(CommandContext& ctx)
        {
            if (!Measuring()) return;
            State& s = S();
            Require(s.list != nullptr, "Render Color reached on an unregistered command list");
            // CommandContext::Flush executes and resets the list without any GPA hook. In this
            // configuration SSAO::AsyncCompute is off so the flush before Render Color does not
            // run, but that is checked here rather than assumed.
            Require(s.list_ptr == ctx.GetCommandList(),
                    "command list changed between registration and Render Color");
            Check("GpaBeginSample", s.BeginSample(s.sample, s.list));
            active = true;
        }
        ~Scope()
        {
            if (!active) return;
            Check("GpaEndSample", S().EndSample(S().list));
            S().sampled = true;
        }
    };

    inline void Collect();

    // Returns true once results are written, so the caller can end the run.
    inline bool EndFrame()
    {
        State& s = S();
        if (!Enabled() || s.done || !s.started) return false;
        if (!Measuring()) return false;
        Require(s.list == nullptr, "command list still open at end of frame");
        // A measuring frame that produced no sample would leave the pass incomplete forever.
        Require(s.sampled, "measuring frame ended without a Render Color sample");
        s.sampled = false;
        if (++s.sample < s.samples) return false;
        s.sample = 0;
        if (++s.pass < s.passes) return false;
        Check("GpaEndSession", s.EndSession(s.session));
        Collect();
        s.done = true;
        return true;
    }

    inline void Collect()
    {
        State& s = S();
        // The session completes asynchronously; poll instead of assuming, and never treat a
        // non-OK status as "not ready yet".
        for (int spin = 0; ; ++spin)
        {
            GpaStatus st = s.IsComplete(s.session);
            if (st == kGpaStatusOk) break;
            Require(st == kGpaStatusResultNotReady, "GpaIsSessionComplete returned an error");
            Require(spin < 200000, "session did not complete");
            Sleep(1);
        }
        std::string p = s.dir + "/gpa_results.csv";
        FILE* f = nullptr;
        Require(fopen_s(&f, p.c_str(), "w") == 0 && f != nullptr, "cannot write gpa_results.csv");
        // No frame column, on purpose: when passes>1 one sample id spans a different frame in
        // every pass and GPA merges them. Printing a single frame number would assert exactly
        // the workload identity that O2 exists to test.
        fprintf(f, "sample,passes,counter,type,value\n");
        for (unsigned id = 0; id < s.samples; ++id)
        {
            size_t bytes = 0;
            Check("GpaGetSampleResultSize", s.ResultSize(s.session, id, &bytes));
            Require(bytes == s.names.size() * sizeof(GpaUInt64), "unexpected sample result size");
            std::vector<GpaUInt64> raw(s.names.size());
            Check("GpaGetSampleResult", s.Result(s.session, id, bytes, raw.data()));
            for (size_t c = 0; c < s.names.size(); ++c)
            {
                if (s.types[c] == kGpaDataTypeFloat64)
                {
                    double d;
                    memcpy(&d, &raw[c], sizeof(d));
                    fprintf(f, "%u,%u,%s,f64,%.17g\n", id, s.passes, s.names[c].c_str(), d);
                }
                else
                {
                    fprintf(f, "%u,%u,%s,u64,%llu\n", id, s.passes, s.names[c].c_str(),
                            (unsigned long long)raw[c]);
                }
            }
        }
        fclose(f);
        Check("GpaDeleteSession", s.DeleteSession(s.session));
        Check("GpaCloseContext", s.CloseCtx(s.ctx));
        Check("GpaDestroy", s.Destroy());
        s.session = nullptr; s.ctx = nullptr;
    }
}
