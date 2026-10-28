#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 p[32];
  [unroll] for (int i = 0; i < 32; ++i) p[i] = In[(t*32+i) & 65535];
  if ((t & 1) != 0) {
    for (int j = 0; j < 32; j += 2) { s += p[j]*p[j]; s += sin(p[j+1])*cos(p[j+1]); }
  } else {
    for (int j2 = 0; j2 < 32; j2 += 2) { s += sin(p[j2])*cos(p[j2]); s += p[j2+1]*p[j2+1]; }
  }
  Out[t] = s;
}
