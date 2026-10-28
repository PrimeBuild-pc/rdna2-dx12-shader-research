// Phase 2T - one instrumentation header for every workload in the hit-rate study.
//
// Inert unless T_DIR is set, so a sample behaves exactly as shipped when it is not being
// measured. What it provides:
//   - up to kRegions timestamp pairs on the direct queue, one per pass under study;
//   - per-frame timing after a warm-up, then a CSV and a summary;
//   - a copy of a chosen render target as the correctness oracle;
//   - process exit, so a measurement never depends on how the window is closed.
//
// Environment:
//   T_DIR     output directory (also switches the probe on)
//   T_WARM    frames to discard before recording       (default 200)
//   T_ITERS   frames to record after the warm-up       (default 500)
#pragma once
#ifndef _CRT_SECURE_NO_WARNINGS
#define _CRT_SECURE_NO_WARNINGS
#endif
#pragma warning(push)
#pragma warning(disable: 4996)
#include <d3d12.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace TProbe
{
    enum { kRegions = 4 };

    inline bool Enabled() { return getenv("T_DIR") != nullptr; }
    inline void Check(bool ok, int code = 81) { if (!ok) ExitProcess(code); }
    inline unsigned EnvU(const char* n, unsigned d)
    {
        const char* v = getenv(n);
        return v && *v ? (unsigned)strtoul(v, nullptr, 10) : d;
    }

    struct State
    {
        ID3D12Device* device = nullptr;
        ID3D12CommandQueue* queue = nullptr;
        ID3D12QueryHeap* heap = nullptr;
        ID3D12Resource* readback = nullptr;
        UINT64 frequency = 0;
        unsigned warm = 200, iters = 500, seen = 0;
        std::vector<double> ns[kRegions];
        bool ready = false, resolved = false;
    };
    inline State& S() { static State s; return s; }

    inline ID3D12Resource* MakeBuffer(ID3D12Device* dev, UINT64 bytes, D3D12_HEAP_TYPE type,
                                      D3D12_RESOURCE_STATES st)
    {
        D3D12_HEAP_PROPERTIES hp = {}; hp.Type = type;
        D3D12_RESOURCE_DESC rd = {};
        rd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER; rd.Width = bytes; rd.Height = 1;
        rd.DepthOrArraySize = 1; rd.MipLevels = 1; rd.SampleDesc.Count = 1;
        rd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        ID3D12Resource* r = nullptr;
        Check(SUCCEEDED(dev->CreateCommittedResource(&hp, D3D12_HEAP_FLAG_NONE, &rd, st,
                                                     nullptr, IID_PPV_ARGS(&r))), 82);
        return r;
    }

    inline void Init(ID3D12Device* dev, ID3D12CommandQueue* queue)
    {
        if (!Enabled() || S().ready) return;
        State& s = S();
        s.device = dev; s.queue = queue;
        s.warm = EnvU("T_WARM", 200); s.iters = EnvU("T_ITERS", 500);
        D3D12_QUERY_HEAP_DESC qd = {};
        qd.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP; qd.Count = 2 * kRegions;
        Check(SUCCEEDED(dev->CreateQueryHeap(&qd, IID_PPV_ARGS(&s.heap))), 83);
        s.readback = MakeBuffer(dev, 2 * kRegions * sizeof(UINT64), D3D12_HEAP_TYPE_READBACK,
                                D3D12_RESOURCE_STATE_COPY_DEST);
        Check(SUCCEEDED(queue->GetTimestampFrequency(&s.frequency)) && s.frequency != 0, 84);
        s.ready = true;
    }

    inline void Begin(ID3D12GraphicsCommandList* cl, unsigned region)
    {
        if (!S().ready || region >= kRegions) return;
        cl->EndQuery(S().heap, D3D12_QUERY_TYPE_TIMESTAMP, 2 * region);
    }
    inline void End(ID3D12GraphicsCommandList* cl, unsigned region)
    {
        if (!S().ready || region >= kRegions) return;
        cl->EndQuery(S().heap, D3D12_QUERY_TYPE_TIMESTAMP, 2 * region + 1);
    }
    // Called once per frame, in the same command list, after the last End().
    inline void Resolve(ID3D12GraphicsCommandList* cl)
    {
        if (!S().ready) return;
        cl->ResolveQueryData(S().heap, D3D12_QUERY_TYPE_TIMESTAMP, 0, 2 * kRegions,
                             S().readback, 0);
        S().resolved = true;
    }

    inline FILE* NewFile(const char* name, const char* mode)
    {
        std::string path = std::string(getenv("T_DIR")) + "/" + name;
        FILE* f = nullptr;
        Check(fopen_s(&f, path.c_str(), mode) == 0 && f != nullptr, 85);
        return f;
    }

    // Copy one render target back and write it raw. Its own allocator, list and fence, so it
    // cannot disturb the sample's recording.
    inline void DumpTarget(ID3D12Resource* target, D3D12_RESOURCE_STATES stateBefore)
    {
        State& s = S();
        if (target == nullptr) return;
        D3D12_RESOURCE_DESC rd = target->GetDesc();
        D3D12_PLACED_SUBRESOURCE_FOOTPRINT fp = {};
        UINT64 total = 0;
        s.device->GetCopyableFootprints(&rd, 0, 1, 0, &fp, nullptr, nullptr, &total);
        ID3D12Resource* rb = MakeBuffer(s.device, total, D3D12_HEAP_TYPE_READBACK,
                                        D3D12_RESOURCE_STATE_COPY_DEST);
        ID3D12CommandAllocator* alloc = nullptr;
        Check(SUCCEEDED(s.device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT,
                                                         IID_PPV_ARGS(&alloc))), 86);
        ID3D12GraphicsCommandList* cl = nullptr;
        Check(SUCCEEDED(s.device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, alloc,
                                                    nullptr, IID_PPV_ARGS(&cl))), 87);
        D3D12_RESOURCE_BARRIER b = {};
        b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; b.Transition.pResource = target;
        b.Transition.StateBefore = stateBefore;
        b.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
        b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        cl->ResourceBarrier(1, &b);
        D3D12_TEXTURE_COPY_LOCATION dst = {}, src = {};
        dst.pResource = rb; dst.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
        dst.PlacedFootprint = fp;
        src.pResource = target; src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
        src.SubresourceIndex = 0;
        cl->CopyTextureRegion(&dst, 0, 0, 0, &src, nullptr);
        Check(SUCCEEDED(cl->Close()), 88);
        ID3D12CommandList* lists[] = { cl };
        s.queue->ExecuteCommandLists(1, lists);
        ID3D12Fence* fence = nullptr;
        Check(SUCCEEDED(s.device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence))), 89);
        HANDLE ev = CreateEvent(nullptr, FALSE, FALSE, nullptr);
        Check(SUCCEEDED(s.queue->Signal(fence, 1)), 90);
        Check(SUCCEEDED(fence->SetEventOnCompletion(1, ev)), 91);
        WaitForSingleObject(ev, INFINITE);
        void* p = nullptr;
        D3D12_RANGE all = { 0, (SIZE_T)total };
        Check(SUCCEEDED(rb->Map(0, &all, &p)) && p != nullptr, 92);
        FILE* f = NewFile("target.bin", "wbx");
        // Strip the row padding the copy footprint requires, so the file is width*height pixels.
        const UINT bpp = 4;
        for (UINT y = 0; y < fp.Footprint.Height; ++y)
            Check(fwrite((const unsigned char*)p + (size_t)y * fp.Footprint.RowPitch, bpp,
                         fp.Footprint.Width, f) == fp.Footprint.Width, 93);
        Check(fclose(f) == 0, 94);
        rb->Unmap(0, nullptr);
        f = NewFile("target.json", "wx");
        Check(fprintf(f, "{\"width\":%u,\"height\":%u,\"format\":%u,\"row_pitch\":%u,"
                         "\"bytes_per_pixel\":%u}",
                      fp.Footprint.Width, fp.Footprint.Height, (unsigned)fp.Footprint.Format,
                      fp.Footprint.RowPitch, bpp) > 0, 95);
        Check(fclose(f) == 0, 96);
    }

    // Called once per frame, after the sample has waited for that frame's GPU work.
    inline void EndFrame(ID3D12Resource* dumpTarget, D3D12_RESOURCE_STATES dumpState)
    {
        State& s = S();
        if (!s.ready || !s.resolved) return;
        UINT64 ts[2 * kRegions] = {};
        void* p = nullptr;
        D3D12_RANGE all = { 0, sizeof(ts) };
        Check(SUCCEEDED(s.readback->Map(0, &all, &p)) && p != nullptr, 97);
        memcpy(ts, p, sizeof(ts));
        s.readback->Unmap(0, nullptr);

        ++s.seen;
        if (s.seen > s.warm)
            for (unsigned r = 0; r < kRegions; ++r)
                if (ts[2 * r + 1] > ts[2 * r])
                    s.ns[r].push_back((double)(ts[2 * r + 1] - ts[2 * r]) * 1e9 / (double)s.frequency);

        if (s.ns[0].size() < s.iters)
            return;

        FILE* f = NewFile("timing.csv", "wx");
        Check(fprintf(f, "frame,region0_ns,region1_ns,region2_ns,region3_ns\n") > 0, 98);
        for (size_t i = 0; i < s.ns[0].size(); ++i)
        {
            Check(fprintf(f, "%zu", i) > 0, 98);
            for (unsigned r = 0; r < kRegions; ++r)
                Check(fprintf(f, ",%.1f", i < s.ns[r].size() ? s.ns[r][i] : 0.0) > 0, 98);
            Check(fprintf(f, "\n") > 0, 98);
        }
        Check(fclose(f) == 0, 99);

        DumpTarget(dumpTarget, dumpState);

        f = NewFile("summary.json", "wx");
        Check(fprintf(f, "{\"pid\":%lu,\"warmup\":%u,\"frames\":%zu,\"timestamp_frequency\":%llu",
                      GetCurrentProcessId(), s.warm, s.ns[0].size(),
                      (unsigned long long)s.frequency) > 0, 99);
        for (unsigned r = 0; r < kRegions; ++r)
        {
            std::vector<double> v = s.ns[r];
            if (v.empty()) { Check(fprintf(f, ",\"region%u_median_ns\":0", r) > 0, 99); continue; }
            for (size_t i = 1; i < v.size(); ++i)
                for (size_t j = i; j > 0 && v[j] < v[j - 1]; --j)
                { double t = v[j]; v[j] = v[j - 1]; v[j - 1] = t; }
            const size_t n = v.size();
            double med = n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
            Check(fprintf(f, ",\"region%u_median_ns\":%.1f,\"region%u_min_ns\":%.1f,"
                             "\"region%u_max_ns\":%.1f,\"region%u_p95_ns\":%.1f",
                          r, med, r, v.front(), r, v.back(), r, v[(n * 19) / 20]) > 0, 99);
        }
        Check(fprintf(f, "}") > 0, 99);
        Check(fclose(f) == 0, 99);
        ExitProcess(0);
    }
}
#pragma warning(pop)
