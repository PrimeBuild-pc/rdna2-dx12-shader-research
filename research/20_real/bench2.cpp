// Phase 2K - banco D3D12 GENERICO per compute shader reali.
//
//   bench2.exe <out.csv> <reps> <dpm> <dumpdir|-> <binds> <gx> <gy> <gz> name:file.cso ...
//
// `binds` descrive le risorse che lo shader dichiara, lette dal disassembly DXIL:
//   b0,b1            constant buffer
//   s0               sampler
//   t3=2d.f32        Texture2D    (dim . formato elemento)
//   t4=ro.struct     StructuredBuffer   / ro.byte = ByteAddressBuffer / ro.f32 = Buffer tipizzato
//   u0=rw.byte       RWByteAddressBuffer / rw.struct / rw.f32
//   u1=2d.f32        RWTexture2D
//   t7=2darray.f32   Texture2DArray
//
// Tutte le varianti in una invocazione condividono i binding: sono lo stesso shader con
// trasformazioni diverse. Protocollo di misura identico a bench.cpp (raffica continua).

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <cmath>

#pragma comment(lib, "d3d12.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "dxguid.lib")

#define HR(x) do { HRESULT _hr = (x); if (FAILED(_hr)) { \
    fprintf(stderr, "FAIL %s -> 0x%08lX (riga %d)\n", #x, (unsigned long)_hr, __LINE__); exit(2);} } while(0)

static const UINT kSlots = 16;            // b0..b15, t0..t15, u0..u15
static const UINT kSamplers = 8;
static const UINT kTexW = 1024, kTexH = 1024, kTexArr = 4;
static const UINT64 kBufElems = 4u * 1024u * 1024u;      // 64 MB
static const UINT64 kBufBytes = kBufElems * 16u;

struct Bind { char reg; UINT slot; std::string dim, fmt; };

static std::vector<std::string> split(const std::string& s, char c) {
    std::vector<std::string> o; size_t p = 0, q;
    while ((q = s.find(c, p)) != std::string::npos) { o.push_back(s.substr(p, q - p)); p = q + 1; }
    o.push_back(s.substr(p)); return o;
}

static std::vector<Bind> parseBinds(const std::string& s) {
    std::vector<Bind> v;
    if (s == "-" || s.empty()) return v;
    for (auto& tok : split(s, ',')) {
        if (tok.empty()) continue;
        Bind b{}; b.reg = tok[0];
        size_t eq = tok.find('=');
        std::string num = (eq == std::string::npos) ? tok.substr(1) : tok.substr(1, eq - 1);
        b.slot = (UINT)atoi(num.c_str());
        if (eq != std::string::npos) {
            auto d = split(tok.substr(eq + 1), '.');
            b.dim = d[0]; b.fmt = d.size() > 1 ? d[1] : "f32";
        }
        if (b.slot < kSlots) v.push_back(b);
    }
    return v;
}

static std::vector<char> readFile(const std::string& p) {
    FILE* f = fopen(p.c_str(), "rb");
    if (!f) { fprintf(stderr, "non trovo %s\n", p.c_str()); exit(2); }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    std::vector<char> b(n);
    if (fread(b.data(), 1, n, f) != (size_t)n) { fclose(f); exit(2); }
    fclose(f); return b;
}

static ID3D12Resource* makeBuf(ID3D12Device* dev, UINT64 bytes, D3D12_HEAP_TYPE heap,
                               D3D12_RESOURCE_STATES st, D3D12_RESOURCE_FLAGS fl) {
    D3D12_HEAP_PROPERTIES hp{}; hp.Type = heap;
    D3D12_RESOURCE_DESC rd{};
    rd.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    rd.Width = bytes; rd.Height = 1; rd.DepthOrArraySize = 1; rd.MipLevels = 1;
    rd.Format = DXGI_FORMAT_UNKNOWN; rd.SampleDesc.Count = 1;
    rd.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR; rd.Flags = fl;
    ID3D12Resource* r = nullptr;
    HR(dev->CreateCommittedResource(&hp, D3D12_HEAP_FLAG_NONE, &rd, st, nullptr, IID_PPV_ARGS(&r)));
    return r;
}

static ID3D12Resource* makeTex(ID3D12Device* dev, UINT arr, DXGI_FORMAT f) {
    D3D12_HEAP_PROPERTIES hp{}; hp.Type = D3D12_HEAP_TYPE_DEFAULT;
    D3D12_RESOURCE_DESC rd{};
    rd.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    rd.Width = kTexW; rd.Height = kTexH; rd.DepthOrArraySize = (UINT16)arr; rd.MipLevels = 1;
    rd.Format = f; rd.SampleDesc.Count = 1;
    rd.Layout = D3D12_TEXTURE_LAYOUT_UNKNOWN;
    rd.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS;
    ID3D12Resource* r = nullptr;
    HR(dev->CreateCommittedResource(&hp, D3D12_HEAP_FLAG_NONE, &rd,
        D3D12_RESOURCE_STATE_UNORDERED_ACCESS, nullptr, IID_PPV_ARGS(&r)));
    return r;
}

static double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    size_t n = v.size();
    return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

int main(int argc, char** argv) {
    if (argc < 10) {
        fprintf(stderr, "uso: bench2.exe out.csv reps dpm dumpdir binds gx gy gz name:cso ...\n");
        return 1;
    }
    const char* outCsv = argv[1];
    const int reps = atoi(argv[2]), dpm = atoi(argv[3]);
    const std::string dumpDir = argv[4];
    auto binds = parseBinds(argv[5]);
    const UINT gx = (UINT)atoi(argv[6]), gy = (UINT)atoi(argv[7]), gz = (UINT)atoi(argv[8]);
    // name:cso[:gx:gy:gz] - i dispatch per variante servono alle varianti numthreads,
    // che devono restare nella STESSA raffica appaiata del riferimento.
    struct Var { std::string name, file; UINT gx, gy, gz; };
    std::vector<Var> vars;
    for (int i = 9; i < argc; ++i) {
        auto f = split(argv[i], ':');
        if (f.size() < 2) { fprintf(stderr, "spec malformata: %s\n", argv[i]); return 1; }
        Var v{ f[0], f[1], gx, gy, gz };
        if (f.size() >= 5) { v.gx = (UINT)atoi(f[2].c_str()); v.gy = (UINT)atoi(f[3].c_str());
                             v.gz = (UINT)atoi(f[4].c_str()); }
        vars.push_back(v);
    }

    IDXGIFactory6* fac = nullptr; HR(CreateDXGIFactory2(0, IID_PPV_ARGS(&fac)));
    IDXGIAdapter1* ad = nullptr; ID3D12Device* dev = nullptr; DXGI_ADAPTER_DESC1 ades{};
    for (UINT i = 0; fac->EnumAdapterByGpuPreference(i, DXGI_GPU_PREFERENCE_HIGH_PERFORMANCE,
                                                     IID_PPV_ARGS(&ad)) != DXGI_ERROR_NOT_FOUND; ++i) {
        ad->GetDesc1(&ades);
        if (ades.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) { ad->Release(); continue; }
        if (SUCCEEDED(D3D12CreateDevice(ad, D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(&dev)))) break;
        ad->Release(); ad = nullptr;
    }
    if (!dev) { fprintf(stderr, "nessun device D3D12\n"); return 2; }

    D3D12_COMMAND_QUEUE_DESC qd{}; qd.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    ID3D12CommandQueue* q = nullptr; HR(dev->CreateCommandQueue(&qd, IID_PPV_ARGS(&q)));
    UINT64 tsFreq = 0; HR(q->GetTimestampFrequency(&tsFreq));
    ID3D12CommandAllocator* alloc = nullptr;
    HR(dev->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&alloc)));
    ID3D12GraphicsCommandList* cl = nullptr;
    HR(dev->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, alloc, nullptr, IID_PPV_ARGS(&cl)));
    HR(cl->Close());
    ID3D12Fence* fence = nullptr; HR(dev->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)));
    HANDLE ev = CreateEventW(nullptr, FALSE, FALSE, nullptr); UINT64 fv = 0;
    auto flush = [&](DWORD ms) -> bool {
        HR(q->Signal(fence, ++fv));
        if (fence->GetCompletedValue() < fv) {
            HR(fence->SetEventOnCompletion(fv, ev));
            if (WaitForSingleObject(ev, ms) != WAIT_OBJECT_0) return false;
        }
        return true;
    };

    // --- risorse condivise -------------------------------------------------
    ID3D12Resource* cb = makeBuf(dev, 64 * 1024, D3D12_HEAP_TYPE_UPLOAD,
                                 D3D12_RESOURCE_STATE_GENERIC_READ, D3D12_RESOURCE_FLAG_NONE);
    {   // valori benigni: niente zeri, che possono far degenerare i cicli guidati da costanti
        float* m = nullptr; D3D12_RANGE nr{ 0, 0 }; HR(cb->Map(0, &nr, (void**)&m));
        for (UINT i = 0; i < 16 * 1024; ++i) {
            UINT r = i * 2654435761u; float u = float((r >> 8) & 0xFFFF) / 65535.0f;
            m[i] = (i % 8 == 0) ? 1024.0f : (0.25f + 0.5f * u);
        }
        cb->Unmap(0, nullptr);
    }
    ID3D12Resource* srvBuf = makeBuf(dev, kBufBytes, D3D12_HEAP_TYPE_DEFAULT,
        D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE, D3D12_RESOURCE_FLAG_NONE);
    ID3D12Resource* uavBuf = makeBuf(dev, kBufBytes, D3D12_HEAP_TYPE_DEFAULT,
        D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    ID3D12Resource* cnt = makeBuf(dev, 4096, D3D12_HEAP_TYPE_DEFAULT,
        D3D12_RESOURCE_STATE_UNORDERED_ACCESS, D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    ID3D12Resource* texF = makeTex(dev, kTexArr, DXGI_FORMAT_R32G32B32A32_FLOAT);
    ID3D12Resource* texU = makeTex(dev, kTexArr, DXGI_FORMAT_R32G32B32A32_UINT);
    {   // inizializza il buffer SRV con dati noti (come in bench.cpp)
        ID3D12Resource* up = makeBuf(dev, kBufBytes, D3D12_HEAP_TYPE_UPLOAD,
            D3D12_RESOURCE_STATE_GENERIC_READ, D3D12_RESOURCE_FLAG_NONE);
        float* m = nullptr; D3D12_RANGE nr{ 0, 0 }; HR(up->Map(0, &nr, (void**)&m));
        for (UINT64 i = 0; i < kBufElems; ++i) {
            float t = float(i % 1024) * (1.0f / 1024.0f) + 0.25f;
            m[i * 4 + 0] = t; m[i * 4 + 1] = 1.0f - t; m[i * 4 + 2] = t * 0.5f - 0.25f; m[i * 4 + 3] = 1.0f;
        }
        up->Unmap(0, nullptr);
        HR(alloc->Reset()); HR(cl->Reset(alloc, nullptr));
        D3D12_RESOURCE_BARRIER b{}; b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        b.Transition.pResource = srvBuf; b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        b.Transition.StateBefore = D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
        b.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_DEST;
        cl->ResourceBarrier(1, &b);
        cl->CopyResource(srvBuf, up);
        std::swap(b.Transition.StateBefore, b.Transition.StateAfter);
        cl->ResourceBarrier(1, &b);
        HR(cl->Close());
        ID3D12CommandList* L[] = { cl }; q->ExecuteCommandLists(1, L);
        if (!flush(60000)) { fprintf(stderr, "init timeout\n"); return 3; }
        up->Release();
    }

    // --- heap di descrittori: [b0..b15][t0..t15][u0..u15] -------------------
    D3D12_DESCRIPTOR_HEAP_DESC hd{};
    hd.Type = D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV; hd.NumDescriptors = 3 * kSlots;
    hd.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    ID3D12DescriptorHeap* heap = nullptr; HR(dev->CreateDescriptorHeap(&hd, IID_PPV_ARGS(&heap)));
    D3D12_DESCRIPTOR_HEAP_DESC hs{};
    hs.Type = D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER; hs.NumDescriptors = kSamplers;
    hs.Flags = D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE;
    ID3D12DescriptorHeap* sheap = nullptr; HR(dev->CreateDescriptorHeap(&hs, IID_PPV_ARGS(&sheap)));
    const UINT inc = dev->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV);
    const UINT sinc = dev->GetDescriptorHandleIncrementSize(D3D12_DESCRIPTOR_HEAP_TYPE_SAMPLER);
    auto cpuAt = [&](UINT i) {
        D3D12_CPU_DESCRIPTOR_HANDLE h = heap->GetCPUDescriptorHandleForHeapStart();
        h.ptr += (SIZE_T)i * inc; return h; };

    // default validi ovunque: CBV, SRV raw, UAV raw
    for (UINT i = 0; i < kSlots; ++i) {
        D3D12_CONSTANT_BUFFER_VIEW_DESC c{}; c.BufferLocation = cb->GetGPUVirtualAddress();
        c.SizeInBytes = 64 * 1024; dev->CreateConstantBufferView(&c, cpuAt(i));
    }
    auto rawSRV = [&](UINT i) {
        D3D12_SHADER_RESOURCE_VIEW_DESC d{}; d.Format = DXGI_FORMAT_R32_TYPELESS;
        d.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
        d.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
        d.Buffer.NumElements = (UINT)(kBufBytes / 4); d.Buffer.Flags = D3D12_BUFFER_SRV_FLAG_RAW;
        dev->CreateShaderResourceView(srvBuf, &d, cpuAt(kSlots + i)); };
    auto rawUAV = [&](UINT i, ID3D12Resource* counter) {
        D3D12_UNORDERED_ACCESS_VIEW_DESC d{}; d.Format = DXGI_FORMAT_R32_TYPELESS;
        d.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
        d.Buffer.NumElements = (UINT)(kBufBytes / 4); d.Buffer.Flags = D3D12_BUFFER_UAV_FLAG_RAW;
        dev->CreateUnorderedAccessView(uavBuf, counter, &d, cpuAt(2 * kSlots + i)); };
    for (UINT i = 0; i < kSlots; ++i) { rawSRV(i); rawUAV(i, nullptr); }
    for (UINT i = 0; i < kSamplers; ++i) {
        D3D12_SAMPLER_DESC sd{}; sd.Filter = D3D12_FILTER_MIN_MAG_MIP_LINEAR;
        sd.AddressU = sd.AddressV = sd.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
        sd.MaxLOD = D3D12_FLOAT32_MAX;
        D3D12_CPU_DESCRIPTOR_HANDLE h = sheap->GetCPUDescriptorHandleForHeapStart();
        h.ptr += (SIZE_T)i * sinc; dev->CreateSampler(&sd, h);
    }
    // sovrascrive con il tipo giusto i soli slot dichiarati dallo shader
    for (auto& b : binds) {
        bool isU32 = (b.fmt == "u32" || b.fmt == "i32");
        ID3D12Resource* tex = isU32 ? texU : texF;
        DXGI_FORMAT tf = isU32 ? DXGI_FORMAT_R32G32B32A32_UINT : DXGI_FORMAT_R32G32B32A32_FLOAT;
        if (b.reg == 't') {
            if (b.dim == "2d" || b.dim == "2darray") {
                D3D12_SHADER_RESOURCE_VIEW_DESC d{}; d.Format = tf;
                d.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
                if (b.dim == "2d") { d.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2D; d.Texture2D.MipLevels = 1; }
                else { d.ViewDimension = D3D12_SRV_DIMENSION_TEXTURE2DARRAY;
                       d.Texture2DArray.MipLevels = 1; d.Texture2DArray.ArraySize = kTexArr; }
                dev->CreateShaderResourceView(tex, &d, cpuAt(kSlots + b.slot));
            } else if (b.fmt == "struct") {
                D3D12_SHADER_RESOURCE_VIEW_DESC d{}; d.Format = DXGI_FORMAT_UNKNOWN;
                d.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
                d.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
                d.Buffer.NumElements = (UINT)kBufElems; d.Buffer.StructureByteStride = 16;
                dev->CreateShaderResourceView(srvBuf, &d, cpuAt(kSlots + b.slot));
            } else if (b.fmt == "f32" || b.fmt == "u32" || b.fmt == "i32") {
                D3D12_SHADER_RESOURCE_VIEW_DESC d{}; d.Format = tf;
                d.ViewDimension = D3D12_SRV_DIMENSION_BUFFER;
                d.Shader4ComponentMapping = D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING;
                d.Buffer.NumElements = (UINT)kBufElems;
                dev->CreateShaderResourceView(srvBuf, &d, cpuAt(kSlots + b.slot));
            }
        } else if (b.reg == 'u') {
            if (b.dim == "2d" || b.dim == "2darray") {
                D3D12_UNORDERED_ACCESS_VIEW_DESC d{}; d.Format = tf;
                if (b.dim == "2d") d.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2D;
                else { d.ViewDimension = D3D12_UAV_DIMENSION_TEXTURE2DARRAY; d.Texture2DArray.ArraySize = kTexArr; }
                dev->CreateUnorderedAccessView(tex, nullptr, &d, cpuAt(2 * kSlots + b.slot));
            } else if (b.fmt == "struct") {
                D3D12_UNORDERED_ACCESS_VIEW_DESC d{}; d.Format = DXGI_FORMAT_UNKNOWN;
                d.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
                d.Buffer.NumElements = (UINT)kBufElems; d.Buffer.StructureByteStride = 16;
                if (b.dim == "rwcnt") d.Buffer.CounterOffsetInBytes = 0;
                dev->CreateUnorderedAccessView(uavBuf, b.dim == "rwcnt" ? cnt : nullptr, &d,
                                               cpuAt(2 * kSlots + b.slot));
            } else if (b.fmt == "f32" || b.fmt == "u32" || b.fmt == "i32") {
                D3D12_UNORDERED_ACCESS_VIEW_DESC d{}; d.Format = tf;
                d.ViewDimension = D3D12_UAV_DIMENSION_BUFFER;
                d.Buffer.NumElements = (UINT)kBufElems;
                dev->CreateUnorderedAccessView(uavBuf, nullptr, &d, cpuAt(2 * kSlots + b.slot));
            }
        }
    }

    // --- root signature: una tabella CBV/SRV/UAV + una tabella sampler -----
    D3D12_DESCRIPTOR_RANGE rng[3]{};
    rng[0].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_CBV; rng[0].NumDescriptors = kSlots;
    rng[0].BaseShaderRegister = 0; rng[0].OffsetInDescriptorsFromTableStart = 0;
    rng[1].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SRV; rng[1].NumDescriptors = kSlots;
    rng[1].BaseShaderRegister = 0; rng[1].OffsetInDescriptorsFromTableStart = kSlots;
    rng[2].RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_UAV; rng[2].NumDescriptors = kSlots;
    rng[2].BaseShaderRegister = 0; rng[2].OffsetInDescriptorsFromTableStart = 2 * kSlots;
    D3D12_DESCRIPTOR_RANGE srng{};
    srng.RangeType = D3D12_DESCRIPTOR_RANGE_TYPE_SAMPLER; srng.NumDescriptors = kSamplers;
    D3D12_ROOT_PARAMETER rp[2]{};
    rp[0].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    rp[0].DescriptorTable.NumDescriptorRanges = 3; rp[0].DescriptorTable.pDescriptorRanges = rng;
    rp[0].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
    rp[1].ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    rp[1].DescriptorTable.NumDescriptorRanges = 1; rp[1].DescriptorTable.pDescriptorRanges = &srng;
    rp[1].ShaderVisibility = D3D12_SHADER_VISIBILITY_ALL;
    D3D12_ROOT_SIGNATURE_DESC rsd{}; rsd.NumParameters = 2; rsd.pParameters = rp;
    ID3DBlob* sig = nullptr; ID3DBlob* errb = nullptr;
    if (FAILED(D3D12SerializeRootSignature(&rsd, D3D_ROOT_SIGNATURE_VERSION_1, &sig, &errb))) {
        fprintf(stderr, "root signature non serializzabile\n"); return 2;
    }
    ID3D12RootSignature* rs = nullptr;
    HR(dev->CreateRootSignature(0, sig->GetBufferPointer(), sig->GetBufferSize(), IID_PPV_ARGS(&rs)));

    D3D12_QUERY_HEAP_DESC qhd{}; qhd.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP; qhd.Count = 2 * reps;
    ID3D12QueryHeap* qh = nullptr; HR(dev->CreateQueryHeap(&qhd, IID_PPV_ARGS(&qh)));
    ID3D12Resource* rb = makeBuf(dev, 2 * reps * sizeof(UINT64), D3D12_HEAP_TYPE_READBACK,
                                 D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_FLAG_NONE);
    const UINT64 kVerify = 4u << 20;
    // La maggior parte di questi shader scrive su RWTexture2D, non sul buffer: senza il
    // dump della texture la verifica di correttezza sarebbe vuota.
    const UINT kTexVerifyW = 256, kTexVerifyH = 256;
    const UINT64 kTexVerify = (UINT64)kTexVerifyW * kTexVerifyH * 16u;
    ID3D12Resource* vrb = makeBuf(dev, kVerify, D3D12_HEAP_TYPE_READBACK,
                                  D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_FLAG_NONE);
    ID3D12Resource* trb = makeBuf(dev, kTexVerify, D3D12_HEAP_TYPE_READBACK,
                                  D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_FLAG_NONE);
    bool usesTexU = false;
    for (auto& b : binds)
        if (b.reg == 'u' && (b.dim == "2d" || b.dim == "2darray")) usesTexU = true;
    ID3D12Resource* dumpTex = nullptr;
    for (auto& b : binds)
        if (b.reg == 'u' && (b.dim == "2d" || b.dim == "2darray"))
            dumpTex = (b.fmt == "u32" || b.fmt == "i32") ? texU : texF;

    FILE* out = fopen(outCsv, "w");
    fprintf(out, "variant,groups_x,groups_y,groups_z,dispatch_per_measure,reps,"
                 "ns_median,ns_mean,ns_sd,cv_pct,pso_create_ms,warm_iters\n");

    for (auto& v : vars) {
        auto blob = readFile(v.file);
        D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};
        pd.pRootSignature = rs; pd.CS.pShaderBytecode = blob.data(); pd.CS.BytecodeLength = blob.size();
        ID3D12PipelineState* pso = nullptr;
        LARGE_INTEGER qf, q0, q1; QueryPerformanceFrequency(&qf); QueryPerformanceCounter(&q0);
        HRESULT hr = dev->CreateComputePipelineState(&pd, IID_PPV_ARGS(&pso));
        QueryPerformanceCounter(&q1);
        double psoMs = 1000.0 * double(q1.QuadPart - q0.QuadPart) / double(qf.QuadPart);
        if (FAILED(hr)) { fprintf(stderr, "  %s: PSO non creabile (0x%08lX)\n",
                                  v.name.c_str(), (unsigned long)hr); continue; }

        auto burst = [&](std::vector<double>& into) -> bool {
            HR(alloc->Reset()); HR(cl->Reset(alloc, nullptr));
            ID3D12DescriptorHeap* heaps[] = { heap, sheap };
            cl->SetDescriptorHeaps(2, heaps);
            cl->SetPipelineState(pso);
            cl->SetComputeRootSignature(rs);
            cl->SetComputeRootDescriptorTable(0, heap->GetGPUDescriptorHandleForHeapStart());
            cl->SetComputeRootDescriptorTable(1, sheap->GetGPUDescriptorHandleForHeapStart());
            for (int b = 0; b < reps; ++b) {
                cl->EndQuery(qh, D3D12_QUERY_TYPE_TIMESTAMP, 2 * b);
                for (int d = 0; d < dpm; ++d) cl->Dispatch(v.gx, v.gy, v.gz);
                cl->EndQuery(qh, D3D12_QUERY_TYPE_TIMESTAMP, 2 * b + 1);
            }
            cl->ResolveQueryData(qh, D3D12_QUERY_TYPE_TIMESTAMP, 0, 2 * reps, rb, 0);
            HR(cl->Close());
            ID3D12CommandList* L[] = { cl }; q->ExecuteCommandLists(1, L);
            if (!flush(20000)) return false;
            UINT64* t = nullptr; D3D12_RANGE rr{ 0, (SIZE_T)(2 * reps * sizeof(UINT64)) };
            HR(rb->Map(0, &rr, (void**)&t));
            into.clear();
            for (int b = 0; b < reps; ++b)
                into.push_back(double(t[2 * b + 1] - t[2 * b]) / double(tsFreq) * 1e9 / dpm);
            D3D12_RANGE nw{ 0, 0 }; rb->Unmap(0, &nw);
            return true;
        };

        const char* wenv = getenv("BENCH_WARM_MS");
        const double warmMs = wenv ? atof(wenv) : 500.0;
        LARGE_INTEGER wf, w0, w1; QueryPerformanceFrequency(&wf); QueryPerformanceCounter(&w0);
        std::vector<double> ns; int warm = 0; bool okrun = true;
        for (;;) {
            std::vector<double> cur;
            if (!burst(cur)) { okrun = false; break; }
            QueryPerformanceCounter(&w1);
            double el = 1000.0 * double(w1.QuadPart - w0.QuadPart) / double(wf.QuadPart);
            if (el >= warmMs) { ns = cur; break; }
            ++warm;
            if (warm > 100000) { ns = cur; break; }
        }
        if (!okrun || ns.empty()) {
            fprintf(stderr, "  %s: TIMEOUT o esecuzione fallita\n", v.name.c_str());
            pso->Release(); fclose(out); return 4;
        }
        double mean = 0; for (double x : ns) mean += x; mean /= ns.size();
        double sd = 0; for (double x : ns) sd += (x - mean) * (x - mean);
        sd = std::sqrt(sd / (ns.size() - 1));
        double med = median(ns);
        printf("  %-44s med %10.1f ns  CV %6.3f%%  pso %.2f ms  warm %d\n",
               v.name.c_str(), med, 100.0 * sd / mean, psoMs, warm);
        fprintf(out, "%s,%u,%u,%u,%d,%d,%.1f,%.1f,%.1f,%.4f,%.3f,%d\n",
                v.name.c_str(), gx, gy, gz, dpm, (int)ns.size(), med, mean, sd,
                100.0 * sd / mean, psoMs, warm);
        fflush(out);

        if (dumpDir != "-") {          // verifica: un dispatch pulito, poi copia del buffer UAV
            HR(alloc->Reset()); HR(cl->Reset(alloc, nullptr));
            ID3D12DescriptorHeap* heaps[] = { heap, sheap };
            cl->SetDescriptorHeaps(2, heaps);
            cl->SetPipelineState(pso); cl->SetComputeRootSignature(rs);
            cl->SetComputeRootDescriptorTable(0, heap->GetGPUDescriptorHandleForHeapStart());
            cl->SetComputeRootDescriptorTable(1, sheap->GetGPUDescriptorHandleForHeapStart());
            cl->Dispatch(v.gx, v.gy, v.gz);
            D3D12_RESOURCE_BARRIER ub{}; ub.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV;
            ub.UAV.pResource = uavBuf; cl->ResourceBarrier(1, &ub);
            D3D12_RESOURCE_BARRIER tb{}; tb.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            tb.Transition.pResource = uavBuf;
            tb.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
            tb.Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
            tb.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
            cl->ResourceBarrier(1, &tb);
            cl->CopyBufferRegion(vrb, 0, uavBuf, 0, kVerify);
            std::swap(tb.Transition.StateBefore, tb.Transition.StateAfter);
            cl->ResourceBarrier(1, &tb);
            if (dumpTex) {
                D3D12_RESOURCE_BARRIER xb{}; xb.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
                xb.Transition.pResource = dumpTex; xb.Transition.Subresource = 0;
                xb.Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
                xb.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
                cl->ResourceBarrier(1, &xb);
                D3D12_TEXTURE_COPY_LOCATION src{}, dst{};
                src.pResource = dumpTex; src.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
                src.SubresourceIndex = 0;
                dst.pResource = trb; dst.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
                dst.PlacedFootprint.Offset = 0;
                dst.PlacedFootprint.Footprint.Format = (dumpTex == texU)
                    ? DXGI_FORMAT_R32G32B32A32_UINT : DXGI_FORMAT_R32G32B32A32_FLOAT;
                dst.PlacedFootprint.Footprint.Width = kTexVerifyW;
                dst.PlacedFootprint.Footprint.Height = kTexVerifyH;
                dst.PlacedFootprint.Footprint.Depth = 1;
                dst.PlacedFootprint.Footprint.RowPitch = kTexVerifyW * 16;
                D3D12_BOX box{ 0, 0, 0, kTexVerifyW, kTexVerifyH, 1 };
                cl->CopyTextureRegion(&dst, 0, 0, 0, &src, &box);
                std::swap(xb.Transition.StateBefore, xb.Transition.StateAfter);
                cl->ResourceBarrier(1, &xb);
            }
            HR(cl->Close());
            ID3D12CommandList* L[] = { cl }; q->ExecuteCommandLists(1, L);
            if (flush(20000)) {
                void* mp = nullptr; D3D12_RANGE vr{ 0, (SIZE_T)kVerify };
                HR(vrb->Map(0, &vr, &mp));
                std::string of = dumpDir + "\\out_" + v.name + ".bin";
                FILE* fo = fopen(of.c_str(), "wb");
                if (fo) {
                    fwrite(mp, 1, (size_t)kVerify, fo);
                    if (dumpTex) {
                        void* tp = nullptr; D3D12_RANGE tr{ 0, (SIZE_T)kTexVerify };
                        HR(trb->Map(0, &tr, &tp));
                        fwrite(tp, 1, (size_t)kTexVerify, fo);
                        D3D12_RANGE tnw{ 0, 0 }; trb->Unmap(0, &tnw);
                    }
                    fclose(fo);
                }
                D3D12_RANGE nw{ 0, 0 }; vrb->Unmap(0, &nw);
            }
        }
        pso->Release();
    }
    fclose(out);
    return 0;
}
