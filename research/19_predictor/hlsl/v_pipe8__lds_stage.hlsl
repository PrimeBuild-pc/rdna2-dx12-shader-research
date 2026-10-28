#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
groupshared float4 shm[512];
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  uint base = gid.x * 512u;
  for (uint q0 = gtid.x; q0 < 512u; q0 += 64u) shm[q0] = In[(base + q0) & 65535];
  GroupMemoryBarrierWithGroupSync();
  float4 v[8];
   for (int i = 0; i < 8; ++i) v[i] = shm[gtid.x*8u + i] * (i+1);
   for (int k = 0; k < 8; ++k) v[k] = sin(v[k]) + v[(k*3)%8]*cos(v[(k*5)%8]);
   for (int j = 0; j < 8; ++j) s += v[j]*v[(j*3)%8];

  Out[t] = s;
}
