#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
groupshared float4 shm[2048];
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  uint base = gid.x * 2048u;
  for (uint q0 = gtid.x; q0 < 2048u; q0 += 64u) shm[q0] = In[(base + q0) & 65535];
  GroupMemoryBarrierWithGroupSync();
   for (int i = 0; i < 32; i += 1) {
    float4 a0 = shm[gtid.x*32u + (i + 0)];
    if (((t + i + 0) & 1u)) s += a0*a0; else s += a0*0.5;
    }

  Out[t] = s;
}
