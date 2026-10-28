#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
groupshared float4 sh[1536];
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;

  uint base = gid.x * 1536u;
  for (uint q = gtid.x; q < 1536u; q += 64u) sh[q] = In[(base + q) & 65535];
  GroupMemoryBarrierWithGroupSync();
  float4 v[24];
  for (int i = 0; i < 24; ++i) v[i] = sh[gtid.x*24u + i] * (i+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];
  Out[t] = s;
}
