#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
groupshared float4 sh[2048];
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;

  uint base = gid.x * 2048u;
  for (uint q = gtid.x; q < 2048u; q += 64u) sh[q] = In[(base + q) & 65535];
  GroupMemoryBarrierWithGroupSync();
  float4 acc = 0;
  for (int i = 0; i < 32; ++i) { float4 a = sh[gtid.x*32u + i]; acc += a * a; }
  s = acc;
  Out[t] = s;
}
