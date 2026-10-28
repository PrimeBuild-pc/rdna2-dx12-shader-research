#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 a = float4(t & 255, (t >> 3) & 255, (t >> 6) & 255, 1) * 0.00390625 + 0.25;
   for (int i = 0; i < 64; ++i) a = a * 1.0009765625 + 0.0009765625;
  s = a;
  Out[t] = s;
}
