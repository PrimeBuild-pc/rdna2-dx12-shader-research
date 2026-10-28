#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 a0 = float4(t & 255, 1, 2, 3) * 0.00390625 + 0.25, a1 = a0 + 0.125, a2 = a0 + 0.25, a3 = a0 + 0.5;
   for (int i = 0; i < 64; ++i) { a0 = a0*1.0009765625 + 0.001; a1 = a1*1.0009765625 + 0.002;
        a2 = a2*1.0009765625 + 0.003; a3 = a3*1.0009765625 + 0.004; }
  s = (a0 + a1) + (a2 + a3);
  Out[t] = s;
}
