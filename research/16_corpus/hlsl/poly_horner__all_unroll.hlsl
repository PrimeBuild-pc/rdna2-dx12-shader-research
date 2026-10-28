#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 x = float4(t & 255, (t >> 3) & 255, (t >> 6) & 255, 1) * 0.00390625;
  float4 a = 0;
  [unroll] for (int i = 0; i < 40; ++i) a = a * x + float(40 - i) * 0.03125;
  s = a;
  Out[t] = s;
}
