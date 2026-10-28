#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  float4 r0 = 0, r1 = 0;
   for (int i = 0; i < 32; i += 2) {
    float4 a0 = In[(t*32+(i + 0)) & 65535];
    float4 a1 = In[(t*32+(i + 1)) & 65535];
    if (((gid.x + i + 0) & 1u)) r0 += a0*a0; else r0 += sin(a0)*cos(a0);
    if (((gid.x + i + 1) & 1u)) r1 += a1*a1; else r1 += sin(a1)*cos(a1);
    }
  s = (r0) + (r1);

  Out[t] = s;
}
