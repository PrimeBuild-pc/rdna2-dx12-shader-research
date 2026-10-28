#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  float4 a = float4(t & 255, (t >> 3) & 255, (t >> 6) & 255, 3) * 0.00390625 + 0.5;
   for (int i = 0; i < 40; ++i) { a = exp2(log2(a + 1.0) * 0.5) + rsqrt(a + 2.0); }
  s = a;

  Out[t] = s;
}
