// Phase 2Q - exhaustive float32 equivalence probe.
//
//   sweep.exe <shader.dxil> <out.json> [firstPattern] [lastPattern]
//
// Runs the compute shader in sweep.hlsl over a range of float32 bit patterns and reads back the
// reduction. Defaults to the whole of [0,1], i.e. patterns 0x00000000..0x3F800000 inclusive,
// which is every value `1.0 - saturate(...)` can produce. No sampling: every value is visited.
//
// Deliberately minimal: one UAV, one constant buffer, no timing, no rendering. The point is a
// proof over a domain, not a benchmark.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#pragma comment(lib, "d3d12.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "dxguid.lib")

#define HR(x) do { HRESULT _hr = (x); if (FAILED(_hr)) { \
    fprintf(stderr, "FAIL %s -> 0x%08lX (line %d)\n", #x, (unsigned long)_hr, __LINE__); \
    exit(2);} } while(0)

static const UINT kSlots = 16;                 // uint reduction slots
static const UINT kChunk = 1u << 24;           // patterns per dispatch, keeps each one short

static std::vector<unsigned char> readFile(const char* path)
{
    FILE* f = nullptr;
    if (fopen_s(&f, path, "rb") != 0 || !f) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    std::vector<unsigned char> v((size_t)n);
    if (fread(v.data(), 1, (size_t)n, f) != (size_t)n) { fprintf(stderr, "short read\n"); exit(2); }
    fclose(f);
    return v;
}

int main(int argc, char** argv)
{
    if (argc < 3) { fprintf(stderr, "usage: sweep <shader.dxil> <out.json> [first] [last]\n"); return 1; }
    const UINT first = argc > 3 ? (UINT)strtoul(argv[3], nullptr, 0) : 0x00000000u;
    const UINT last  = argc > 4 ? (UINT)strtoul(argv[4], nullptr, 0) : 0x3F800000u;
    if (last < first) { fprintf(stderr, "empty range\n"); return 1; }

    ID3D12Device* dev = nullptr;
    IDXGIFactory6* factory = nullptr;
    HR(CreateDXGIFactory2(0, IID_PPV_ARGS(&factory)));
    IDXGIAdapter1* adapter = nullptr;
    HR(factory->EnumAdapterByGpuPreference(0, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
                                           IID_PPV_ARGS(&adapter)));
    DXGI_ADAPTER_DESC1 ad = {};
    adapter->GetDesc1(&ad);
    HR(D3D12CreateDevice(adapter, D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&dev)));

    D3D12_COMMAND_QUEUE_DESC qd = {}; qd.Type = D3D12_COMMAND_LIST_TYPE_COMPUTE;
    ID3D12CommandQueue* queue = nullptr;
    HR(dev->CreateCommandQueue(&qd, IID_PPV_ARGS(&queue)));
    ID3D12CommandAllocator* alloc = nullptr;
    HR(dev->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_COMPUTE, IID_PPV_ARGS(&alloc)));
    ID3D12GraphicsCommandList* cl = nullptr;
    HR(dev->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_COMPUTE, alloc, nullptr, IID_PPV_ARGS(&cl)));
    HR(cl->Close());
    ID3D12Fence* fence = nullptr;
    HR(dev->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)));
    HANDLE ev = CreateEvent(nullptr, FALSE, FALSE, nullptr);
    UINT64 fv = 0;

    auto makeBuffer = [&](UINT64 bytes, D3D12_HEAP_TYPE heap, D3D12_RESOURCE_STATES st,
                          bool uav) -> ID3D12Resource* {
        D3D12_HEAP_PROPERTIES hp = {}; hp.Type = heap;
        D3D12_RESOURCE_DESC rd = {};
        rd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER; rd.Width = bytes; rd.Height = 1;
        rd.DepthOrArraySize = 1; rd.MipLevels = 1; rd.SampleDesc.Count = 1;
        rd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;
        rd.Flags = uav ? D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS : D3D12_RESOURCE_FLAG_NONE;
        ID3D12Resource* r = nullptr;
        HR(dev->CreateCommittedResource(&hp, D3D12_HEAP_FLAG_NONE, &rd, st, nullptr, IID_PPV_ARGS(&r)));
        return r;
    };
    ID3D12Resource* reduce = makeBuffer(kSlots * sizeof(UINT), D3D12_HEAP_TYPE_DEFAULT,
                                        D3D12_RESOURCE_STATE_UNORDERED_ACCESS, true);
    ID3D12Resource* upload = makeBuffer(kSlots * sizeof(UINT), D3D12_HEAP_TYPE_UPLOAD,
                                        D3D12_RESOURCE_STATE_GENERIC_READ, false);
    ID3D12Resource* readback = makeBuffer(kSlots * sizeof(UINT), D3D12_HEAP_TYPE_READBACK,
                                          D3D12_RESOURCE_STATE_COPY_DEST, false);
    { void* p = nullptr; D3D12_RANGE none = {0, 0};
      HR(upload->Map(0, &none, &p)); memset(p, 0, kSlots * sizeof(UINT)); upload->Unmap(0, nullptr); }

    D3D12_DESCRIPTOR_HEAP_DESC hd = {};
    hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV; hd.NumDescriptors = 1;
    hd.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    ID3D12DescriptorHeap* heap = nullptr;
    HR(dev->CreateDescriptorHeap(&hd, IID_PPV_ARGS(&heap)));
    D3D12_UNORDERED_ACCESS_VIEW_DESC ud = {};
    ud.ViewDimension = D3D12_UAV_DIMENSION_BUFFER; ud.Format = DXGI_FORMAT_UNKNOWN;
    ud.Buffer.NumElements = kSlots; ud.Buffer.StructureByteStride = sizeof(UINT);
    dev->CreateUnorderedAccessView(reduce, nullptr, &ud, heap->GetCPUDescriptorHandleForHeapStart());

    D3D12_DESCRIPTOR_RANGE range = {};
    range.RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_UAV; range.NumDescriptors = 1;
    D3D12_ROOT_PARAMETER params[2] = {};
    params[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    params[0].DescriptorTable.NumDescriptorRanges = 1;
    params[0].DescriptorTable.pDescriptorRanges = &range;
    params[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;
    params[1].Constants.Num32BitValues = 4;
    D3D12_ROOT_SIGNATURE_DESC rsd = {}; rsd.NumParameters = 2; rsd.pParameters = params;
    ID3DBlob *sig = nullptr, *err = nullptr;
    HR(D3D12SerializeRootSignature(&rsd, D3D_ROOT_SIGNATURE_VERSION_1, &sig, &err));
    ID3D12RootSignature* rs = nullptr;
    HR(dev->CreateRootSignature(0, sig->GetBufferPointer(), sig->GetBufferSize(), IID_PPV_ARGS(&rs)));

    std::vector<unsigned char> cs = readFile(argv[1]);
    D3D12_COMPUTE_PIPELINE_STATE_DESC pd = {};
    pd.pRootSignature = rs; pd.CS.pShaderBytecode = cs.data(); pd.CS.BytecodeLength = cs.size();
    ID3D12PipelineState* pso = nullptr;
    HR(dev->CreateComputePipelineState(&pd, IID_PPV_ARGS(&pso)));

    auto submit = [&](void (*record)(ID3D12GraphicsCommandList*, void*), void* ctx) {
        HR(alloc->Reset()); HR(cl->Reset(alloc, nullptr));
        record(cl, ctx);
        HR(cl->Close());
        ID3D12CommandList* lists[] = { cl };
        queue->ExecuteCommandLists(1, lists);
        HR(queue->Signal(fence, ++fv));
        if (fence->GetCompletedValue() < fv) { HR(fence->SetEventOnCompletion(fv, ev));
                                               WaitForSingleObject(ev, INFINITE); }
    };

    struct ClearCtx { ID3D12Resource *dst, *src; } cc = { reduce, upload };
    submit([](ID3D12GraphicsCommandList* c, void* p) {
        ClearCtx* q = (ClearCtx*)p;
        D3D12_RESOURCE_BARRIER b = {};
        b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; b.Transition.pResource = q->dst;
        b.Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
        b.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_DEST;
        b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        c->ResourceBarrier(1, &b);
        c->CopyResource(q->dst, q->src);
        std::swap(b.Transition.StateBefore, b.Transition.StateAfter);
        c->ResourceBarrier(1, &b);
    }, &cc);

    const UINT64 total = (UINT64)last - first + 1;
    UINT64 done = 0;
    while (done < total)
    {
        const UINT n = (UINT)((total - done) < kChunk ? (total - done) : kChunk);
        const UINT base = first + (UINT)done;
        struct DispatchCtx { ID3D12PipelineState* pso; ID3D12RootSignature* rs;
                             ID3D12DescriptorHeap* heap; UINT base, n; } dc =
            { pso, rs, heap, base, n };
        submit([](ID3D12GraphicsCommandList* c, void* p) {
            DispatchCtx* q = (DispatchCtx*)p;
            ID3D12DescriptorHeap* hs[] = { q->heap };
            c->SetDescriptorHeaps(1, hs);
            c->SetComputeRootSignature(q->rs);
            c->SetPipelineState(q->pso);
            c->SetComputeRootDescriptorTable(0, q->heap->GetGPUDescriptorHandleForHeapStart());
            UINT consts[4] = { q->base, q->n, 0, 0 };
            c->SetComputeRoot32BitConstants(1, 4, consts, 0);
            c->Dispatch((q->n + 255) / 256, 1, 1);
        }, &dc);
        done += n;
        fprintf(stderr, "\r%.1f%%", 100.0 * (double)done / (double)total);
    }
    fprintf(stderr, "\r        \r");

    struct CopyCtx { ID3D12Resource *dst, *src; } cp = { readback, reduce };
    submit([](ID3D12GraphicsCommandList* c, void* p) {
        CopyCtx* q = (CopyCtx*)p;
        D3D12_RESOURCE_BARRIER b = {};
        b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION; b.Transition.pResource = q->src;
        b.Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
        b.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
        b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        c->ResourceBarrier(1, &b);
        c->CopyResource(q->dst, q->src);
    }, &cp);

    UINT out[kSlots] = {};
    { void* p = nullptr; D3D12_RANGE all = {0, kSlots * sizeof(UINT)};
      HR(readback->Map(0, &all, &p)); memcpy(out, p, sizeof(out)); readback->Unmap(0, nullptr); }

    auto asfloat = [](UINT u) { float f; memcpy(&f, &u, 4); return f; };
    char gpu[128] = {};
    WideCharToMultiByte(CP_UTF8, 0, ad.Description, -1, gpu, sizeof(gpu), nullptr, nullptr);

    FILE* f = nullptr;
    if (fopen_s(&f, argv[2], "wx") != 0 || !f) { fprintf(stderr, "output exists: %s\n", argv[2]); return 3; }
    fprintf(f, "{\n  \"gpu\": \"%s\",\n  \"shader_bytes\": %zu,\n"
               "  \"first_pattern\": \"0x%08X\",\n  \"last_pattern\": \"0x%08X\",\n"
               "  \"values_swept\": %llu,\n"
               "  \"first_value\": %.9g,\n  \"last_value\": %.9g,\n"
               "  \"differing\": %u,\n  \"max_ulp\": %u,\n"
               "  \"max_rel_error\": %.9g,\n  \"max_abs_error\": %.9g,\n"
               "  \"nan\": %u,\n  \"posinf\": %u,\n  \"neginf\": %u,\n  \"negative_zero\": %u,\n"
               "  \"zero_mismatch\": %u,\n"
               "  \"slots_raw\": [%u,%u,%u,%u,%u,%u,%u,%u,%u,%u],\n"
               "  \"slots_as_float\": [%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g,%.9g]\n}\n",
            gpu, cs.size(), first, last, (unsigned long long)total,
            asfloat(first), asfloat(last),
            out[0], out[1], asfloat(out[2]), asfloat(out[7]),
            out[3], out[4], out[5], out[6], out[8],
            out[0],out[1],out[2],out[3],out[4],out[5],out[6],out[7],out[8],out[9],
            asfloat(out[0]),asfloat(out[1]),asfloat(out[2]),asfloat(out[3]),asfloat(out[4]),
            asfloat(out[5]),asfloat(out[6]),asfloat(out[7]),asfloat(out[8]),asfloat(out[9]));
    fclose(f);
    printf("swept %llu values: differing %u, max_ulp %u, max_rel %.6g, max_abs %.6g, "
           "nan %u, inf %u/%u, -0 %u, zero-mismatch %u\n",
           (unsigned long long)total, out[0], out[1], asfloat(out[2]), asfloat(out[7]),
           out[3], out[4], out[5], out[6], out[8]);
    return 0;
}
