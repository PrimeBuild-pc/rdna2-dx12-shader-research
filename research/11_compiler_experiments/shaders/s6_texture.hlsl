#define RS "RootFlags(0), UAV(u0), DescriptorTable(SRV(t0)), StaticSampler(s0)"
Texture2D<float4> Tex : register(t0);
SamplerState Smp : register(s0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)][numthreads(64,1,1)]
void main(uint3 t : SV_DispatchThreadID){
  float2 uv = float2(t.x, t.y) * (1.0/512.0);
  float4 c = 0;
  [unroll] for (int k=0;k<8;++k){
    float2 o = float2(k*0.013, k*0.017);
    c += Tex.SampleLevel(Smp, uv+o, 0) * Tex.SampleLevel(Smp, uv-o, 1.0);
  }
  Out[t.x] = c / 8.0;
}
