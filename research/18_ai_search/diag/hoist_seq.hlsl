#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;

  if ((t & 1) != 0) {
    for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535];
      if ((i & 1) == 0) s += a * a; else s += sin(a) * cos(a); }
  } else {
    for (int j = 0; j < 32; ++j) { float4 a = In[(t*32+j) & 65535];
      if ((j & 1) == 0) s += sin(a) * cos(a); else s += a * a; }
  }
  Out[t] = s;
}
