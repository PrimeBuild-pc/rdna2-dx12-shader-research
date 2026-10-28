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
  g[gtid.x] = a * 0.015625;
  GroupMemoryBarrierWithGroupSync();
  [unroll] for (uint st = 32u; st > 0u; st >>= 1) {
    if (gtid.x < st) g[gtid.x] += g[gtid.x + st];
    GroupMemoryBarrierWithGroupSync(); }
  s = g[0];
  Out[t] = s;
}
