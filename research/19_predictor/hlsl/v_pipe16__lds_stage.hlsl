#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
groupshared float4 shm[1024];
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  uint base = gid.x * 1024u;
  for (uint q0 = gtid.x; q0 < 1024u; q0 += 64u) shm[q0] = In[(base + q0) & 65535];
  GroupMemoryBarrierWithGroupSync();
  float4 v[16];
   for (int i = 0; i < 16; ++i) v[i] = shm[gtid.x*16u + i] * (i+1);
   for (int k = 0; k < 16; ++k) v[k] = sin(v[k]) + v[(k*7)%16]*cos(v[(k*11)%16]);
   for (int j = 0; j < 16; ++j) s += v[j]*v[(j*5)%16];

  Out[t] = s;
}
