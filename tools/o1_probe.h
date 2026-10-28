// O1 only: observe native-bound PSO at real Sponza draws and copy SV_Target0
// immediately after Render Color, before particles/post-effects. Never used for timing.
#pragma once
#include "CommandContext.h"
#include "ReadbackBuffer.h"
#include "BufferManager.h"
#include "Display.h"
#include <cstdio>
#include <cstdlib>
#include <string>

namespace O1Probe
{
    // Sponza::RenderLightShadows copies exactly ONE of Lighting::MaxLights=128 shadow slices
    // per frame, so before frame 128 the shadow array is partly unrendered and its content
    // changes every frame. Capture after it is complete, with margin.
    // An enumerator, not `inline constexpr`: the project builds as C++14 (inline variables are
    // error C7525 there) and an enumerator has no linkage to worry about across translation units.
    enum : uint64_t { kCaptureFrame = 140 };
    inline bool Enabled() { return getenv("ME_O1_DIR") != nullptr; }
    inline bool TargetFrame() { return Enabled() && Graphics::GetFrameCount() == kCaptureFrame; }
    inline void Check(bool ok) { if (!ok) ExitProcess(81); }
    inline FILE* NewFile(const char* name, const char* mode)
    {
        std::string path = std::string(getenv("ME_O1_DIR")) + "/" + name;
        FILE* f = nullptr;
        Check(fopen_s(&f, path.c_str(), mode) == 0 && f != nullptr);
        return f;
    }
    inline FILE*& Log() { static FILE* f = nullptr; return f; }
    inline void Draw(GraphicsContext& ctx, uint32_t indices)
    {
        if (!TargetFrame()) return;
        const PSO* p = ctx.GetObservedPSO();
        Check(p != nullptr);
        if (!Log()) {
            Log() = NewFile("runtime.csv", "wx");
            Check(fprintf(Log(), "pid,frame,scope,pso_address,native_pso,ps_hash,ps_bytes,indices,native_matches\n") > 0);
        }
        Check(fprintf(Log(), "%lu,%llu,Render Color,%p,%p,%016llX,%zu,%u,1\n",
            GetCurrentProcessId(), (unsigned long long)Graphics::GetFrameCount(), p,
            p->GetPipelineStateObject(), (unsigned long long)p->GetShaderHash(1),
            p->GetShaderSize(1), indices) > 0);
    }
    struct Image
    {
        ReadbackBuffer buffer;
        UINT pitch = 0, width = 0, height = 0, format = 0, bpp = 4;
        bool captured = false;
    };
    inline Image& Shot() { static Image s; return s; }
    inline void Capture(GraphicsContext& ctx)
    {
        if (!TargetFrame()) return;
        Image& s = Shot();
        Check(!s.captured && Log() != nullptr);
        auto& color = Graphics::g_SceneColorBuffer;
        s.width = color.GetWidth(); s.height = color.GetHeight(); s.format = color.GetFormat();
        // Narrow, typed oracle; unsupported formats fail rather than being reinterpreted.
        // Two formats are accepted. R11G11B10 is the engine's real target and the oracle
        // phases 2O/2P used; R32G32B32A32 is the full-precision diagnostic target selected by
        // ME_Q_R32, which exists because a bit-identical quantised image does not prove that
        // two shaders computed the same float32 values.
        Check(s.format == DXGI_FORMAT_R11G11B10_FLOAT ||
              s.format == DXGI_FORMAT_R32G32B32A32_FLOAT);
        s.bpp = s.format == DXGI_FORMAT_R32G32B32A32_FLOAT ? 16u : 4u;
        s.pitch = ctx.ReadbackTexture(s.buffer, color);
        Check(s.pitch >= s.width * s.bpp);
        ctx.TransitionResource(color, D3D12_RESOURCE_STATE_RENDER_TARGET, true);
        s.captured = true;
    }
    inline void Save()
    {
        Image& s = Shot();
        Check(TargetFrame() && s.captured && Log() != nullptr);
        Graphics::g_CommandManager.IdleGPU();
        const unsigned char* bytes = (const unsigned char*)s.buffer.Map();
        Check(bytes != nullptr);
        FILE* f = NewFile("color.bin", "wbx");
        // Strip undefined row padding; preserve the GPU row pitch in metadata.
        for (UINT y = 0; y < s.height; ++y)
            Check(fwrite(bytes + (size_t)y * s.pitch, s.bpp, s.width, f) == s.width);
        Check(fclose(f) == 0);
        s.buffer.Unmap(); s.buffer.Destroy();
        f = NewFile("image.json", "wx");
        Check(fprintf(f, "{\"pid\":%lu,\"frame_index\":%llu,\"target\":\"g_SceneColorBuffer/SV_Target0\","
            "\"capture_point\":\"after Render Color, before particles/post-effects\","
            "\"dxgi_format\":%u,\"format_name\":\"%s\",\"bytes_per_pixel\":%u,"
            "\"width\":%u,\"height\":%u,"
            "\"row_pitch\":%u,\"stored_row_bytes\":%u,\"padding_stored\":false}",
            GetCurrentProcessId(), (unsigned long long)kCaptureFrame, s.format,
            s.bpp == 16 ? "R32G32B32A32_FLOAT" : "R11G11B10_FLOAT", s.bpp, s.width,
            s.height, s.pitch, s.width * s.bpp) > 0);
        Check(fclose(f) == 0); Check(fclose(Log()) == 0); Log() = nullptr;
        // The diagnostic target is not a format the post-processing chain was written for, so
        // when it is in use the process stops here rather than risking a failure downstream
        // that has nothing to do with what is being measured.
        if (getenv("ME_Q_R32") != nullptr)
            ExitProcess(0);
    }
}
