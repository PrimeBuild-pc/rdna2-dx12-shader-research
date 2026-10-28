// Root signature reconstructed from MiniEngine Renderer::m_RootSig (Model/Renderer.cpp),
// parameter order from Renderer.h. Offline ISA generation only.
#define MVRS \
    "RootFlags(ALLOW_INPUT_ASSEMBLER_INPUT_LAYOUT)," \
    "CBV(b0, space=0, visibility=SHADER_VISIBILITY_VERTEX)," \
    "CBV(b0, space=0, visibility=SHADER_VISIBILITY_PIXEL)," \
    "DescriptorTable(SRV(t0, numDescriptors=10), visibility=SHADER_VISIBILITY_PIXEL)," \
    "DescriptorTable(Sampler(s0, numDescriptors=10), visibility=SHADER_VISIBILITY_PIXEL)," \
    "DescriptorTable(SRV(t10, numDescriptors=10), visibility=SHADER_VISIBILITY_PIXEL)," \
    "CBV(b1)," \
    "SRV(t20, visibility=SHADER_VISIBILITY_VERTEX)," \
    "StaticSampler(s10, filter=FILTER_ANISOTROPIC, maxAnisotropy=8, visibility=SHADER_VISIBILITY_PIXEL)," \
    "StaticSampler(s11, filter=FILTER_COMPARISON_MIN_MAG_LINEAR_MIP_POINT, comparisonFunc=COMPARISON_GREATER_EQUAL, addressU=TEXTURE_ADDRESS_CLAMP, addressV=TEXTURE_ADDRESS_CLAMP, addressW=TEXTURE_ADDRESS_CLAMP, visibility=SHADER_VISIBILITY_PIXEL)," \
    "StaticSampler(s12, filter=FILTER_ANISOTROPIC, maxAnisotropy=8, visibility=SHADER_VISIBILITY_PIXEL)"
