#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
groupshared float4 g[64];
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  g[gtid.x] = In[t & 65535];
  GroupMemoryBarrierWithGroupSync();
  [loop] for (int i = 0; i < 32; ++i) s += g[(gtid.x * 7 + i * 13) & 63] * sin(float(i) * 0.125);
  Out[t] = s;
}
