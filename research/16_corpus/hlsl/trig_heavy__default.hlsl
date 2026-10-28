#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 a = float4(t & 511, (t >> 2) & 511, (t >> 4) & 511, 1) * 0.001953125;
   for (int i = 0; i < 32; ++i) a = sin(a) + cos(a * 1.5) * 0.5;
  s = a;
  Out[t] = s;
}
