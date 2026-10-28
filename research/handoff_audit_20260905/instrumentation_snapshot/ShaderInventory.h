//
// Phase 2M - inventario degli shader REALMENTE eseguiti.
//
// Regola della fase: profile first, optimize second. Uno shader entra nel corpus solo se
// il workload lo esegue davvero. Questo modulo registra, per ogni frame:
//
//   scope del profiler -> PSO -> hash del bytecode VS/PS/CS -> numero di invocazioni
//                              -> dimensioni reali di dispatch / draw
//
// I contatori vengono azzerati alla fine del warm-up e mediati sui frame misurati.
//
#pragma once

#include <cstdint>

class PSO;

namespace ShaderInventory
{
    // attivo solo in modalita' benchmark: costo zero quando spento
    extern bool Enabled;

    void PushScope(const wchar_t* name);         // scope del profiler (annidato)
    void PopScope();
    void SetPSO(const PSO* pso);                 // PSO legato al contesto corrente
    void RecordDispatch(uint32_t x, uint32_t y, uint32_t z);
    void RecordDispatchIndirect();
    void RecordDraw(uint32_t verts, uint32_t instances, bool indexed);
    void NextFrame();                            // fine frame: conta i frame osservati
    void Reset();                                // azzera dopo il warm-up
    void Dump(const char* path);
}
