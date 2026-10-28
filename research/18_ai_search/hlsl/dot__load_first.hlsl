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
  float4 acc = 0;
  for (int j = 0; j < 32; ++j) acc += p[j]*p[j];
  s = acc;
  Out[t] = s;
}
