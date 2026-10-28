//
// Phase 2N - raccolta di performance counter hardware AMD (GPUPerfAPI) attorno a uno
// scope del profiler, dentro l'applicazione reale.
//
// Uso: ME_GPA_SCOPE="Render Color" ME_GPA_CSV=out.csv ModelViewer.exe
// GPA puo' richiedere piu' passate: l'applicazione ripete lo stesso frame una volta per
// passata, il che e' lecito perche' il carico e' deterministico a passo fisso.
//
#pragma once

#include <cstdint>

class CommandContext;

namespace GpaProfiler
{
    extern bool Enabled;

    void Initialize(void* commandQueue);     // ID3D12CommandQueue*
    void Shutdown();

    // chiamate dagli scope del profiler
    void BeginScope(const wchar_t* name, CommandContext* ctx);
    void EndScope(const wchar_t* name, CommandContext* ctx);

    void BeginFrame();
    void OnContextBegin(CommandContext* ctx);
    void OnContextFinish(CommandContext* ctx);
    void EndFrame();                         // avanza la passata; true quando ha finito
    bool Done();
    void Dump(const char* path);
}
