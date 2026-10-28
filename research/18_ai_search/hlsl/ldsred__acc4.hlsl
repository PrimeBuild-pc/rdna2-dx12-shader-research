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
  float4 s0=0, s1=0, s2=0, s3=0;
  for (int q = 0; q < 64; q += 4) { s0 += g[q]*0.015625; s1 += g[q+1]*0.015625;
    s2 += g[q+2]*0.015625; s3 += g[q+3]*0.015625; }
  s = ((s0+s1)+(s2+s3));
  Out[t] = s;
}
