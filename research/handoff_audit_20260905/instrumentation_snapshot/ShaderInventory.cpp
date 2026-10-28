//
// Phase 2M - inventario degli shader realmente eseguiti. Vedi ShaderInventory.h.
//
#include "pch.h"
#include "ShaderInventory.h"
#include "PipelineState.h"
#include <map>
#include <vector>
#include <mutex>
#include <string>
#include <cstdio>

namespace ShaderInventory
{
    bool Enabled = false;

    namespace
    {
        struct Key
        {
            std::wstring scope;
            const PSO* pso;
            bool operator<(const Key& o) const
            {
                if (scope != o.scope) return scope < o.scope;
                return pso < o.pso;
            }
        };

        struct Rec
        {
            uint64_t calls = 0;
            uint64_t indirect = 0;
            uint64_t groups = 0;        // somma dei gruppi dispatchati
            uint64_t verts = 0;         // somma vertici * istanze
            uint64_t instances = 0;
            uint32_t lastX = 0, lastY = 0, lastZ = 0;
            bool isDraw = false;
        };

        // Le stringhe sono copiate per valore: i nodi del profiler possono essere
        // distrutti da EngineProfiling::Update(). Il mutex serve perche' MiniEngine
        // puo' registrare comandi da piu' thread.
        std::map<Key, Rec> g_Recs;
        std::vector<std::wstring> g_Stack;
        std::wstring g_Scope = L"(root)";
        const PSO* g_PSO = nullptr;
        uint64_t g_Frames = 0;
        std::mutex g_Mtx;

        Rec& Cur()
        {
            return g_Recs[Key{ g_Scope, g_PSO }];
        }
    }

    void PushScope(const wchar_t* name)
    {
        if (!Enabled) return;
        std::lock_guard<std::mutex> lk(g_Mtx);
        g_Stack.push_back(g_Scope);
        g_Scope = name ? name : L"(senza nome)";
    }

    void PopScope()
    {
        if (!Enabled) return;
        std::lock_guard<std::mutex> lk(g_Mtx);
        if (g_Stack.empty()) return;
        g_Scope = g_Stack.back(); g_Stack.pop_back();
    }

    void SetPSO(const PSO* pso)
    {
        if (!Enabled) return;
        std::lock_guard<std::mutex> lk(g_Mtx);
        g_PSO = pso;
    }

    void RecordDispatch(uint32_t x, uint32_t y, uint32_t z)
    {
        if (!Enabled) return;
        std::lock_guard<std::mutex> lk(g_Mtx);
        Rec& r = Cur();
        ++r.calls;
        r.groups += (uint64_t)x * y * z;
        r.lastX = x; r.lastY = y; r.lastZ = z;
    }

    void RecordDispatchIndirect()
    {
        if (!Enabled) return;
        std::lock_guard<std::mutex> lk(g_Mtx);
        Rec& r = Cur();
        ++r.calls; ++r.indirect;      // dimensioni note solo alla GPU
    }

    void RecordDraw(uint32_t verts, uint32_t instances, bool)
    {
        if (!Enabled) return;
        std::lock_guard<std::mutex> lk(g_Mtx);
        Rec& r = Cur();
        ++r.calls; r.isDraw = true;
        r.verts += (uint64_t)verts * (instances ? instances : 1);
        r.instances += instances ? instances : 1;
    }

    void NextFrame()
    {
        if (!Enabled) return;
        std::lock_guard<std::mutex> lk(g_Mtx);
        ++g_Frames;
    }

    void Reset()
    {
        std::lock_guard<std::mutex> lk(g_Mtx);
        g_Recs.clear();
        g_Frames = 0;
        g_Stack.clear();
    }

    void Dump(const char* path)
    {
        std::lock_guard<std::mutex> lk(g_Mtx);
        FILE* f = nullptr;
        if (fopen_s(&f, path, "w") != 0 || !f) return;
        fprintf(f, "scope,pso,kind,calls_per_frame,indirect_per_frame,groups_per_frame,"
                   "verts_per_frame,instances_per_frame,last_dispatch,vs_hash,ps_hash,cs_hash,"
                   "vs_bytes,ps_bytes,cs_bytes,frames\n");
        const double inv = g_Frames ? 1.0 / (double)g_Frames : 0.0;
        for (auto& kv : g_Recs)
        {
            const PSO* p = kv.first.pso;
            char scope[192] = {}, name[192] = {};
            size_t n = 0;
            wcstombs_s(&n, scope, sizeof(scope), kv.first.scope.c_str(), sizeof(scope) - 1);
            for (char* c = scope; *c; ++c) if (*c == ',') *c = ';';
            const wchar_t* pn = p ? p->GetName() : L"(nessun PSO)";
            wcstombs_s(&n, name, sizeof(name), pn ? pn : L"(senza nome)", sizeof(name) - 1);
            for (char* c = name; *c; ++c) if (*c == ',') *c = ';';
            const Rec& r = kv.second;
            fprintf(f, "%s,%s,%s,%.4f,%.4f,%.2f,%.2f,%.2f,%ux%ux%u,%016llX,%016llX,%016llX,"
                       "%zu,%zu,%zu,%llu\n",
                    scope, name, r.isDraw ? "draw" : "dispatch",
                    r.calls * inv, r.indirect * inv, r.groups * inv, r.verts * inv,
                    r.instances * inv, r.lastX, r.lastY, r.lastZ,
                    (unsigned long long)(p ? p->GetShaderHash(0) : 0),
                    (unsigned long long)(p ? p->GetShaderHash(1) : 0),
                    (unsigned long long)(p ? p->GetShaderHash(2) : 0),
                    p ? p->GetShaderSize(0) : 0, p ? p->GetShaderSize(1) : 0,
                    p ? p->GetShaderSize(2) : 0,
                    (unsigned long long)g_Frames);
        }
        fclose(f);
    }
}
