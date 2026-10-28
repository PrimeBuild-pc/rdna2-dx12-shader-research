// Phase 2R - instrumentation for the second workload (DirectX-Graphics-Samples,
// D3D12nBodyGravity). Header-only and inert unless NB_DIR is set, so the sample behaves exactly
// as shipped when it is not being measured.
//
// What it does:
//   - times the simulation dispatch with a timestamp pair on the compute queue, per iteration;
//   - counts iterations, discards a warm-up, and after a fixed number writes the timings;
//   - copies the particle buffer back and writes it as float32, which is the correctness oracle
//     for this workload: after a fixed number of deterministic steps the state must match;
//   - then exits the process, so the measurement never depends on how the window is closed.
//
// Environment:
//   NB_DIR     output directory (also switches the probe on)
//   NB_WARM    iterations to discard before recording      (default 200)
//   NB_ITERS   iterations to record after the warm-up      (default 1000)
#pragma once
// The sample builds with warnings-as-errors and the CRT deprecation warnings on; getenv
// is exactly the interface the rest of this project's probes use, so it is allowed here
// rather than switching this one header to _dupenv_s.
#ifndef _CRT_SECURE_NO_WARNINGS
#define _CRT_SECURE_NO_WARNINGS
#endif
#pragma warning(push)
#pragma warning(disable: 4996)
#include <d3d12.h>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace NbProbe
{
    inline bool Enabled() { return getenv("NB_DIR") != nullptr; }
    inline void Check(bool ok, int code = 91) { if (!ok) ExitProcess(code); }

    inline unsigned EnvU(const char* name, unsigned fallback)
    {
        const char* v = getenv(name);
        return v && *v ? (unsigned)strtoul(v, nullptr, 10) : fallback;
    }

    struct State
    {
        ID3D12Device* device = nullptr;
        ID3D12CommandQueue* queue = nullptr;
        ID3D12QueryHeap* heap = nullptr;
        ID3D12Resource* tsReadback = nullptr;
        ID3D12Resource* target = nullptr;      // the buffer the current dispatch writes
        UINT64 frequency = 0;
        unsigned warm = 200, iters = 1000, seen = 0;
        std::vector<double> ns;
        bool ready = false;
    };
    inline State& S() { static State s; return s; }

    inline ID3D12Resource* MakeBuffer(ID3D12Device* dev, UINT64 bytes, D3D12_HEAP_TYPE type,
                                      D3D12_RESOURCE_STATES state)
    {
        D3D12_HEAP_PROPERTIES hp = {}; hp.Type = type;
        D3D12_RESOURCE_DESC rd = {};
        rd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER; rd.Width = bytes; rd.Height = 1;
        rd.DepthOrArraySize = 1; rd.MipLevels = 1; rd.SampleDesc.Count = 1;
        rd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        ID3D12Resource* r = nullptr;
        Check(SUCCEEDED(dev->CreateCommittedResource(&hp, D3D12_HEAP_FLAG_NONE, &rd, state,
                                                     nullptr, IID_PPV_ARGS(&r))));
        return r;
    }

    inline void Init(ID3D12Device* dev, ID3D12CommandQueue* queue)
    {
        if (!Enabled() || S().ready) return;
        State& s = S();
        s.device = dev; s.queue = queue;
        s.warm = EnvU("NB_WARM", 200); s.iters = EnvU("NB_ITERS", 1000);
        D3D12_QUERY_HEAP_DESC qd = {};
        qd.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP; qd.Count = 2;
        Check(SUCCEEDED(dev->CreateQueryHeap(&qd, IID_PPV_ARGS(&s.heap))));
        s.tsReadback = MakeBuffer(dev, 2 * sizeof(UINT64), D3D12_HEAP_TYPE_READBACK,
                                  D3D12_RESOURCE_STATE_COPY_DEST);
        Check(SUCCEEDED(queue->GetTimestampFrequency(&s.frequency)) && s.frequency != 0);
        s.ns.reserve(s.iters);
        s.ready = true;
    }

    inline void SetTarget(ID3D12Resource* r) { if (Enabled()) S().target = r; }

    inline void BeforeDispatch(ID3D12GraphicsCommandList* cl)
    {
        if (!S().ready) return;
        cl->EndQuery(S().heap, D3D12_QUERY_TYPE_TIMESTAMP, 0);
    }

    inline void AfterDispatch(ID3D12GraphicsCommandList* cl)
    {
        if (!S().ready) return;
        cl->EndQuery(S().heap, D3D12_QUERY_TYPE_TIMESTAMP, 1);
        cl->ResolveQueryData(S().heap, D3D12_QUERY_TYPE_TIMESTAMP, 0, 2, S().tsReadback, 0);
    }

    inline FILE* NewFile(const char* name, const char* mode)
    {
        std::string path = std::string(getenv("NB_DIR")) + "/" + name;
        FILE* f = nullptr;
        Check(fopen_s(&f, path.c_str(), mode) == 0 && f != nullptr, 92);
        return f;
    }

    // Copy the particle buffer back and write it as raw float32. Uses its own allocator and
    // list so it cannot disturb the sample's recording, and waits on its own fence.
    inline void DumpParticles(UINT64 bytes)
    {
        State& s = S();
        Check(s.target != nullptr, 93);
        ID3D12Resource* rb = MakeBuffer(s.device, bytes, D3D12_HEAP_TYPE_READBACK,
                                        D3D12_RESOURCE_STATE_COPY_DEST);
        ID3D12CommandAllocator* alloc = nullptr;
        Check(SUCCEEDED(s.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_COMPUTE,
                                                         IID_PPV_ARGS(&alloc))));
        ID3D12GraphicsCommandList* cl = nullptr;
        Check(SUCCEEDED(s.device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_COMPUTE, alloc,
                                                    nullptr, IID_PPV_ARGS(&cl))));
        D3D12_RESOURCE_BARRIER b = {};
        b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; b.Transition.pResource = s.target;
        b.Transition.StateBefore = D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
        b.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
        b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        cl->ResourceBarrier(1, &b);
        cl->CopyResource(rb, s.target);
        Check(SUCCEEDED(cl->Close()));
        ID3D12CommandList* lists[] = { cl };
        s.queue->ExecuteCommandLists(1, lists);
        ID3D12Fence* fence = nullptr;
        Check(SUCCEEDED(s.device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence))));
        HANDLE ev = CreateEvent(nullptr, FALSE, FALSE, nullptr);
        Check(SUCCEEDED(s.queue->Signal(fence, 1)));
        Check(SUCCEEDED(fence->SetEventOnCompletion(1, ev)));
        WaitForSingleObject(ev, INFINITE);
        void* p = nullptr;
        D3D12_RANGE all = { 0, (SIZE_T)bytes };
        Check(SUCCEEDED(rb->Map(0, &all, &p)) && p != nullptr, 94);
        FILE* f = NewFile("particles.bin", "wbx");
        Check(fwrite(p, 1, (size_t)bytes, f) == (size_t)bytes, 95);
        Check(fclose(f) == 0, 96);
        rb->Unmap(0, nullptr);
    }

    // Called once per simulation iteration, after the fence that guarantees the dispatch is done.
    inline void EndIteration(UINT64 particleBytes)
    {
        State& s = S();
        if (!s.ready) return;
        UINT64 ts[2] = {};
        void* p = nullptr;
        D3D12_RANGE all = { 0, sizeof(ts) };
        Check(SUCCEEDED(s.tsReadback->Map(0, &all, &p)) && p != nullptr, 97);
        memcpy(ts, p, sizeof(ts));
        s.tsReadback->Unmap(0, nullptr);

        ++s.seen;
        if (s.seen > s.warm && ts[1] > ts[0])
            s.ns.push_back((double)(ts[1] - ts[0]) * 1e9 / (double)s.frequency);

        if (s.ns.size() < s.iters)
            return;

        std::vector<double> sorted = s.ns;
        for (size_t i = 1; i < sorted.size(); ++i)     // insertion sort, a few thousand entries
            for (size_t j = i; j > 0 && sorted[j] < sorted[j - 1]; --j)
            {
                double t = sorted[j]; sorted[j] = sorted[j - 1]; sorted[j - 1] = t;
            }
        double sum = 0.0;
        for (double v : s.ns) sum += v;
        const size_t n = sorted.size();
        double median = n % 2 ? sorted[n / 2] : 0.5 * (sorted[n / 2 - 1] + sorted[n / 2]);

        FILE* f = NewFile("timing.csv", "wx");
        Check(fprintf(f, "iteration,dispatch_ns\n") > 0);
        for (size_t i = 0; i < s.ns.size(); ++i)
            Check(fprintf(f, "%zu,%.1f\n", i, s.ns[i]) > 0);
        Check(fclose(f) == 0);

        DumpParticles(particleBytes);

        f = NewFile("summary.json", "wx");
        Check(fprintf(f, "{\"pid\":%lu,\"warmup\":%u,\"recorded\":%zu,"
                         "\"timestamp_frequency\":%llu,\"dispatch_ns_median\":%.1f,"
                         "\"dispatch_ns_mean\":%.1f,\"dispatch_ns_min\":%.1f,"
                         "\"dispatch_ns_max\":%.1f,\"dispatch_ns_p05\":%.1f,"
                         "\"dispatch_ns_p95\":%.1f,\"particle_bytes\":%llu}",
                      GetCurrentProcessId(), s.warm, n, (unsigned long long)s.frequency,
                      median, sum / (double)n, sorted.front(), sorted.back(),
                      sorted[n / 20], sorted[(n * 19) / 20],
                      (unsigned long long)particleBytes) > 0);
        Check(fclose(f) == 0);
        ExitProcess(0);
    }
}
#pragma warning(pop)
