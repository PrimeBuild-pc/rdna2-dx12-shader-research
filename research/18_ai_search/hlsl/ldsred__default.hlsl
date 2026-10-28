#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
groupshared float4 g[64];
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 a = In[t & 65535];
  for (int i = 0; i < 8; ++i) a += In[(t*8+i) & 65535] * (i+1);
  g[gtid.x] = a;
  GroupMemoryBarrierWithGroupSync();
  for (int q = 0; q < 64; ++q) s += g[q] * 0.015625;
  Out[t] = s;
}
