// Phase 2F - microbenchmark D3D12 per RX 6950 XT.
// Misura il tempo GPU dei dispatch con timestamp query. Nessun rendering, nessun VSync.
//
//   bench.exe <out.csv> <reps> <dispatchPerMeasure> <dataset> <dumpdir|-> name:file:threads:hasSRV:tg ...
//
// Per ogni variante: warm-up, poi `reps` misure indipendenti; ogni misura racchiude
// `dispatchPerMeasure` dispatch fra due timestamp. Output: ns per singolo dispatch.
// `dataset` = indice del set di input deterministico (0..N-1, vedi fillDataset).
// `dumpdir` = cartella dove scrivere out_<name>.bin per la verifica; "-" = non dumpare.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <algorithm>
#include <cmath>

#pragma comment(lib, "d3d12.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "dxguid.lib")

#define HR(x) do { HRESULT _hr = (x); if (FAILED(_hr)) { \
    fprintf(stderr, "FAIL %s -> 0x%08lX (riga %d)\n", #x, (unsigned long)_hr, __LINE__); exit(2);} } while(0)

static const UINT64 kElems = 4u * 1024u * 1024u;      // float4 per buffer
static const UINT64 kBufBytes = kElems * 16u;

struct Variant { std::string name, file; UINT threads, tg, groups; bool hasSRV; };

// LCG deterministico: stessa sequenza a ogni esecuzione, su qualunque macchina.
static inline UINT lcg(UINT& s) { s = s * 1664525u + 1013904223u; return s; }
static inline float u01(UINT& s) { return float(lcg(s) >> 8) * (1.0f / 16777216.0f); }

static const int kNumDatasets = 20;
static const char* kDatasetName[kNumDatasets] = {
    "orig_0.25_1.25", "zeros", "ones", "small_1e-6", "large_1e6",
    "negatives", "alternating_pm1", "mixed_mag_1e-8_1e8", "rand_pm1", "rand_pm100",
    "near_pi_mult", "tiny_1e-30", "pow2_exact", "big_int", "const_0.5",
    "ramp_full", "half_pi_mult", "huge_1e30", "rand_sparse_zero", "rand_pm10000"
};

// Riempie 4 float per elemento. Deterministica: dipende solo da (ds, i).
static void fillDataset(int ds, UINT64 i, float* o) {
    UINT s = (UINT)(i * 2654435761u) ^ (UINT)(ds * 97u + 1u);
    lcg(s); lcg(s);
    float t = float(i % 1024) * (1.0f / 1024.0f);
    switch (ds) {
    case 0: { float a = t + 0.25f; o[0]=a; o[1]=1.0f-a; o[2]=a*0.5f-0.25f; o[3]=1.0f; } break;
    case 1: o[0]=o[1]=o[2]=o[3]=0.0f; break;
    case 2: o[0]=o[1]=o[2]=o[3]=1.0f; break;
    case 3: for (int k=0;k<4;++k) o[k] = (t + 0.1f + 0.01f*k) * 1e-6f; break;
    case 4: for (int k=0;k<4;++k) o[k] = (t + 0.1f + 0.01f*k) * 1e6f; break;
    case 5: for (int k=0;k<4;++k) o[k] = -(t + 0.25f + 0.05f*k); break;
    case 6: for (int k=0;k<4;++k) o[k] = ((i + k) & 1) ? -1.0f : 1.0f; break;
    case 7: for (int k=0;k<4;++k) o[k] = powf(10.0f, -8.0f + 4.0f*float((i + k) % 5)) * (t + 0.5f); break;
    case 8: for (int k=0;k<4;++k) o[k] = u01(s) * 2.0f - 1.0f; break;
    case 9: for (int k=0;k<4;++k) o[k] = (u01(s) * 2.0f - 1.0f) * 100.0f; break;
    case 10: for (int k=0;k<4;++k) o[k] = 3.14159265f * float((i + k) % 17); break;
    case 11: for (int k=0;k<4;++k) o[k] = (t + 0.1f) * 1e-30f; break;
    case 12: for (int k=0;k<4;++k) o[k] = ldexpf(1.0f, int((i + k) % 25) - 12); break;
    case 13: for (int k=0;k<4;++k) o[k] = float((i * 4 + k) % 1000000); break;
    case 14: o[0]=o[1]=o[2]=o[3]=0.5f; break;
    case 15: for (int k=0;k<4;++k) o[k] = float(i * 4 + k) * (1.0f / float(kElems * 4)); break;
    case 16: for (int k=0;k<4;++k) o[k] = 1.57079633f * float((i + k) % 9); break;
    case 17: for (int k=0;k<4;++k) o[k] = (t + 0.1f) * 1e30f; break;
    case 18: for (int k=0;k<4;++k) o[k] = ((i + k) % 7 == 0) ? 0.0f : (u01(s) * 2.0f - 1.0f); break;
    default: for (int k=0;k<4;++k) o[k] = (u01(s) * 2.0f - 1.0f) * 10000.0f; break;
    }
}

static std::vector<char> readFile(const std::string& p) {
    FILE* f = fopen(p.c_str(), "rb");
    if (!f) { fprintf(stderr, "non trovo %s\n", p.c_str()); exit(2); }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    std::vector<char> b(n);
    if (fread(b.data(), 1, n, f) != (size_t)n) { fclose(f); exit(2); }
    fclose(f); return b;
}

static ID3D12Resource* makeBuffer(ID3D12Device* dev, UINT64 bytes, D3D12_HEAP_TYPE heap,
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

static double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    size_t n = v.size();
    return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}
static double pct(std::vector<double> v, double p) {
    std::sort(v.begin(), v.end());
    double idx = p * (v.size() - 1);
    size_t lo = (size_t)idx; double fr = idx - lo;
    return lo + 1 < v.size() ? v[lo] * (1 - fr) + v[lo + 1] * fr : v[lo];
}

int main(int argc, char** argv) {
    if (argc < 7) {
        fprintf(stderr, "uso: bench.exe <out.csv> <reps> <dpm> <dataset> <dumpdir|-> name:file:threads:hasSRV:tg ...\n");
        return 1;
    }
    const char* outCsv = argv[1];
    const int reps = atoi(argv[2]);
    const int dpm = atoi(argv[3]);
    const int dataset = atoi(argv[4]);
    const std::string dumpDir = argv[5];
    if (dataset < 0 || dataset >= kNumDatasets) { fprintf(stderr, "dataset %d fuori range\n", dataset); return 1; }
    std::vector<Variant> vars;
    for (int i = 6; i < argc; ++i) {
        std::string s = argv[i]; std::vector<std::string> f; size_t p = 0, q;
        while ((q = s.find(':', p)) != std::string::npos) { f.push_back(s.substr(p, q - p)); p = q + 1; }
        f.push_back(s.substr(p));
        if (f.size() < 5) { fprintf(stderr, "argomento malformato (name:file:threads:hasSRV:tg): %s\n", argv[i]); return 1; }
        UINT th = (UINT)atoi(f[2].c_str()), tg = (UINT)atoi(f[4].c_str());
        if (tg == 0 || th % tg) { fprintf(stderr, "threads %u non divisibile per tg %u\n", th, tg); return 1; }
        vars.push_back({f[0], f[1], th, tg, th / tg, atoi(f[3].c_str()) != 0});
    }

    // --- adapter AMD ---
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
    wprintf(L"GPU: %s (vendor 0x%04X, VRAM %llu MB)\n", ades.Description, ades.VendorId,
            (unsigned long long)(ades.DedicatedVideoMemory >> 20));

    D3D12_COMMAND_QUEUE_DESC qd{}; qd.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    ID3D12CommandQueue* q = nullptr; HR(dev->CreateCommandQueue(&qd, IID_PPV_ARGS(&q)));
    UINT64 tsFreq = 0; HR(q->GetTimestampFrequency(&tsFreq));
    printf("timestamp frequency: %llu Hz\n", (unsigned long long)tsFreq);

    ID3D12CommandAllocator* alloc = nullptr;
    HR(dev->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&alloc)));
    ID3D12GraphicsCommandList* cl = nullptr;
    HR(dev->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, alloc, nullptr, IID_PPV_ARGS(&cl)));
    HR(cl->Close());
    ID3D12Fence* fence = nullptr; HR(dev->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)));
    HANDLE ev = CreateEventW(nullptr, FALSE, FALSE, nullptr); UINT64 fv = 0;

    // Una coppia di timestamp per ogni misura: tutte le `reps` misure stanno in UNA
    // sola command list, quindi la GPU lavora senza pause fra una e l'altra. Con una
    // submission+fence per misura il duty cycle scende, il governor abbassa i clock e
    // gli shader corti si misurano fino a 2x piu' lenti del reale.
    D3D12_QUERY_HEAP_DESC qhd{}; qhd.Type = D3D12_QUERY_HEAP_TYPE_TIMESTAMP; qhd.Count = 2 * reps;
    ID3D12QueryHeap* qh = nullptr; HR(dev->CreateQueryHeap(&qhd, IID_PPV_ARGS(&qh)));
    ID3D12Resource* rb = makeBuffer(dev, 2 * reps * sizeof(UINT64), D3D12_HEAP_TYPE_READBACK,
                                    D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_FLAG_NONE);
    // verifica sull'INTERA regione scritta dal dispatch, non su un prefisso
    UINT64 kVerifyBytes = 0;
    for (auto& v : vars) kVerifyBytes = std::max<UINT64>(kVerifyBytes, UINT64(v.threads) * 16u);
    kVerifyBytes = std::min<UINT64>(kVerifyBytes, kBufBytes);
    ID3D12Resource* vrb = makeBuffer(dev, kVerifyBytes, D3D12_HEAP_TYPE_READBACK,
                                     D3D12_RESOURCE_STATE_COPY_DEST, D3D12_RESOURCE_FLAG_NONE);
    ID3D12Resource* uav = makeBuffer(dev, kBufBytes, D3D12_HEAP_TYPE_DEFAULT,
                                     D3D12_RESOURCE_STATE_UNORDERED_ACCESS,
                                     D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS);
    ID3D12Resource* srv = makeBuffer(dev, kBufBytes, D3D12_HEAP_TYPE_DEFAULT,
                                     D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE,
                                     D3D12_RESOURCE_FLAG_NONE);

    // Inizializza il buffer SRV con dati noti: senza questo gli shader leggono bit
    // indeterminati (denormali/NaN hanno costi diversi) e la misura diventa rumorosa.
    {
        ID3D12Resource* up = makeBuffer(dev, kBufBytes, D3D12_HEAP_TYPE_UPLOAD,
                                        D3D12_RESOURCE_STATE_GENERIC_READ, D3D12_RESOURCE_FLAG_NONE);
        float* m = nullptr; D3D12_RANGE nr{ 0, 0 };
        HR(up->Map(0, &nr, (void**)&m));
        for (UINT64 i = 0; i < kElems; ++i) fillDataset(dataset, i, m + i * 4);
        // dump dei primi 65536 float4 dell'input: e' l'unica regione che gli shader leggono
        // (indice mascherato & 65535). Serve alla reference CPU per usare gli stessi bit.
        if (dumpDir != "-") {
            std::string ip = dumpDir + "\\in_ds" + std::to_string(dataset) + ".bin";
            FILE* fi = fopen(ip.c_str(), "wb");
            if (fi) { fwrite(m, 1, 65536u * 16u, fi); fclose(fi); }
        }
        up->Unmap(0, nullptr);
        HR(alloc->Reset()); HR(cl->Reset(alloc, nullptr));
        D3D12_RESOURCE_BARRIER b{}; b.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
        b.Transition.pResource = srv; b.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
        b.Transition.StateBefore = D3D12_RESOURCE_STATE_NON_PIXEL_SHADER_RESOURCE;
        b.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_DEST;
        cl->ResourceBarrier(1, &b);
        cl->CopyResource(srv, up);
        std::swap(b.Transition.StateBefore, b.Transition.StateAfter);
        cl->ResourceBarrier(1, &b);
        HR(cl->Close());
        ID3D12CommandList* L[] = { cl }; q->ExecuteCommandLists(1, L);
        HR(q->Signal(fence, ++fv));
        if (fence->GetCompletedValue() < fv) { HR(fence->SetEventOnCompletion(fv, ev)); WaitForSingleObject(ev, 60000); }
        up->Release();
        printf("buffer SRV inizializzato: dataset %d (%s)\n", dataset, kDatasetName[dataset]);
    }

    FILE* out = fopen(outCsv, "w");
    fprintf(out, "variant,dataset,threads,tg,groups,dispatch_per_measure,reps,ns_median,ns_mean,ns_p95,"
                 "ns_sd,cv_pct,ns_min,ns_max,pso_create_ms,ns_cold,ns_warm_median,warm_iters\n");

    for (auto& v : vars) {
        auto blob = readFile(v.file);
        ID3D12RootSignature* rs = nullptr;
        if (FAILED(dev->CreateRootSignature(0, blob.data(), blob.size(), IID_PPV_ARGS(&rs)))) {
            fprintf(stderr, "  %s: root signature non estraibile dal DXIL\n", v.name.c_str());
            continue;
        }
        D3D12_COMPUTE_PIPELINE_STATE_DESC pd{};
        pd.pRootSignature = rs; pd.CS.pShaderBytecode = blob.data(); pd.CS.BytecodeLength = blob.size();
        ID3D12PipelineState* pso = nullptr;
        LARGE_INTEGER qf, q0, q1; QueryPerformanceFrequency(&qf); QueryPerformanceCounter(&q0);
        HRESULT psoHr = dev->CreateComputePipelineState(&pd, IID_PPV_ARGS(&pso));
        QueryPerformanceCounter(&q1);
        double psoMs = 1000.0 * double(q1.QuadPart - q0.QuadPart) / double(qf.QuadPart);
        if (FAILED(psoHr)) {
            fprintf(stderr, "  %s: PSO non creabile\n", v.name.c_str()); rs->Release(); continue;
        }

        std::vector<double> ns, warmNs;
        // Warm-up A TEMPO. Una submission contiene tutte le `reps` misure di fila, quindi
        // la GPU non ha buchi fra una e l'altra: con un fence per misura il duty cycle
        // scende, il governor abbassa i clock e gli shader corti si misurano fino a 2x
        // piu' lenti del reale (verificato su poly_horner: 26.6 us a freddo vs 5.1 us).
        const char* wenv = getenv("BENCH_WARM_MS");
        const double warmMs = wenv ? atof(wenv) : 500.0;
        LARGE_INTEGER wf, w0, w1; QueryPerformanceFrequency(&wf); QueryPerformanceCounter(&w0);

        auto submitBurst = [&](std::vector<double>& into) {
            HR(alloc->Reset()); HR(cl->Reset(alloc, nullptr));
            cl->SetPipelineState(pso);
            cl->SetComputeRootSignature(rs);
            cl->SetComputeRootUnorderedAccessView(0, uav->GetGPUVirtualAddress());
            if (v.hasSRV) cl->SetComputeRootShaderResourceView(1, srv->GetGPUVirtualAddress());
            for (int b = 0; b < reps; ++b) {
                cl->EndQuery(qh, D3D12_QUERY_TYPE_TIMESTAMP, 2 * b);
                for (int d = 0; d < dpm; ++d) cl->Dispatch(v.groups, 1, 1);
                cl->EndQuery(qh, D3D12_QUERY_TYPE_TIMESTAMP, 2 * b + 1);
            }
            cl->ResolveQueryData(qh, D3D12_QUERY_TYPE_TIMESTAMP, 0, 2 * reps, rb, 0);
            HR(cl->Close());
            ID3D12CommandList* lists[] = { cl };
            q->ExecuteCommandLists(1, lists);
            HR(q->Signal(fence, ++fv));
            if (fence->GetCompletedValue() < fv) { HR(fence->SetEventOnCompletion(fv, ev)); WaitForSingleObject(ev, 60000); }
            UINT64* t = nullptr; D3D12_RANGE rr{ 0, (SIZE_T)(2 * reps * sizeof(UINT64)) };
            HR(rb->Map(0, &rr, (void**)&t));
            into.clear();
            for (int b = 0; b < reps; ++b)
                into.push_back(double(t[2 * b + 1] - t[2 * b]) / double(tsFreq) * 1e9 / dpm);
            D3D12_RANGE nw{ 0, 0 }; rb->Unmap(0, &nw);
        };

        int warm = 0;
        for (;;) {
            std::vector<double> cur;
            submitBurst(cur);
            QueryPerformanceCounter(&w1);
            double el = 1000.0 * double(w1.QuadPart - w0.QuadPart) / double(wf.QuadPart);
            if (el >= warmMs) { ns = cur; break; }     // l'ultima raffica e' la misura
            if (warmNs.empty()) warmNs = cur;          // la prima serve per il tempo "a freddo"
            ++warm;
        }

        double mean = 0; for (double x : ns) mean += x; mean /= ns.size();
        double sd = 0; for (double x : ns) sd += (x - mean) * (x - mean);
        sd = std::sqrt(sd / (ns.size() - 1));
        double med = median(ns), p95 = pct(ns, 0.95);
        double mn = *std::min_element(ns.begin(), ns.end());
        double mx = *std::max_element(ns.begin(), ns.end());
        // BENCH_RAW=dir -> scrive tutti i campioni in ordine, per ispezionare la convergenza
        if (const char* rawd = getenv("BENCH_RAW")) {
            std::string rp = std::string(rawd) + "\\raw_" + v.name + ".csv";
            if (FILE* rf = fopen(rp.c_str(), "w")) {
                fprintf(rf, "idx,phase,ns\n");
                for (size_t i = 0; i < warmNs.size(); ++i) fprintf(rf, "%zu,warm,%.1f\n", i, warmNs[i]);
                for (size_t i = 0; i < ns.size(); ++i) fprintf(rf, "%zu,measure,%.1f\n", warmNs.size() + i, ns[i]);
                fclose(rf);
            }
        }
        double cold = warmNs.empty() ? -1.0 : warmNs[0];
        double warmMed = warmNs.empty() ? -1.0 : median(warmNs);
        printf("  %-28s med %10.1f ns  CV %6.3f%%  pso %.2f ms  cold %9.0f  warm %d\n",
               v.name.c_str(), med, 100.0 * sd / mean, psoMs, cold, warm);
        fprintf(out, "%s,%d,%u,%u,%u,%d,%d,%.1f,%.1f,%.1f,%.1f,%.4f,%.1f,%.1f,%.3f,%.1f,%.1f,%d\n",
                v.name.c_str(), dataset, v.threads, v.tg, v.groups, dpm, (int)ns.size(),
                med, mean, p95, sd, 100.0 * sd / mean, mn, mx, psoMs, cold, warmMed, warm);
        fflush(out);
        // --- verifica di correttezza: un dispatch pulito, poi copia dell'output su file ---
        if (dumpDir != "-") {
            const UINT64 nbytes = std::min<UINT64>(UINT64(v.threads) * 16u, kVerifyBytes);
            HR(alloc->Reset()); HR(cl->Reset(alloc, nullptr));
            cl->SetPipelineState(pso); cl->SetComputeRootSignature(rs);
            cl->SetComputeRootUnorderedAccessView(0, uav->GetGPUVirtualAddress());
            if (v.hasSRV) cl->SetComputeRootShaderResourceView(1, srv->GetGPUVirtualAddress());
            cl->Dispatch(v.groups, 1, 1);
            D3D12_RESOURCE_BARRIER ub{}; ub.Type = D3D12_RESOURCE_BARRIER_TYPE_UAV; ub.UAV.pResource = uav;
            cl->ResourceBarrier(1, &ub);
            D3D12_RESOURCE_BARRIER tb{}; tb.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
            tb.Transition.pResource = uav; tb.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
            tb.Transition.StateBefore = D3D12_RESOURCE_STATE_UNORDERED_ACCESS;
            tb.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
            cl->ResourceBarrier(1, &tb);
            cl->CopyBufferRegion(vrb, 0, uav, 0, nbytes);
            std::swap(tb.Transition.StateBefore, tb.Transition.StateAfter);
            cl->ResourceBarrier(1, &tb);
            HR(cl->Close());
            ID3D12CommandList* L2[] = { cl }; q->ExecuteCommandLists(1, L2);
            HR(q->Signal(fence, ++fv));
            if (fence->GetCompletedValue() < fv) { HR(fence->SetEventOnCompletion(fv, ev)); WaitForSingleObject(ev, 60000); }
            void* mp = nullptr; D3D12_RANGE vr{ 0, (SIZE_T)nbytes };
            HR(vrb->Map(0, &vr, &mp));
            std::string of = dumpDir + "\\out_" + v.name + ".bin";
            FILE* fo = fopen(of.c_str(), "wb");
            if (!fo) { fprintf(stderr, "  %s: non posso scrivere %s\n", v.name.c_str(), of.c_str()); }
            else { fwrite(mp, 1, (size_t)nbytes, fo); fclose(fo); }
            D3D12_RANGE nw2{ 0, 0 }; vrb->Unmap(0, &nw2);
        }
        pso->Release(); rs->Release();
    }
    fclose(out);
    printf("scritto %s\n", outCsv);
    return 0;
}
