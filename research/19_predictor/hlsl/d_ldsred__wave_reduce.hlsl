#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
groupshared float4 g[8];
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  float4 a = In[t & 65535];
   for (int i = 0; i < 8; ++i) a += In[(t*8+i) & 65535] * (i+1);
  float4 w = WaveActiveSum(a * (1.0/64.0));
  uint lanes = WaveGetLaneCount(), wi = gtid.x / lanes;
  if (WaveGetLaneIndex() == 0) g[wi] = w;
  GroupMemoryBarrierWithGroupSync();
  uint nw = 64u / lanes;
  for (uint q = 0; q < nw; ++q) s += g[q];

  Out[t] = s;
}
