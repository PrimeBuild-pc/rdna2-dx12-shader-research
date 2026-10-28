#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
   for (int i = 0; i < 32; i += 4) {
    float4 a0 = In[(t*32+(i + 0)) & 65535];
    float4 a1 = In[(t*32+(i + 1)) & 65535];
    float4 a2 = In[(t*32+(i + 2)) & 65535];
    float4 a3 = In[(t*32+(i + 3)) & 65535];
    if (((gid.x + i + 0) & 1u)) s += a0*a0; else s += sin(a0)*cos(a0);
    if (((gid.x + i + 1) & 1u)) s += a1*a1; else s += sin(a1)*cos(a1);
    if (((gid.x + i + 2) & 1u)) s += a2*a2; else s += sin(a2)*cos(a2);
    if (((gid.x + i + 3) & 1u)) s += a3*a3; else s += sin(a3)*cos(a3);
    }

  Out[t] = s;
}
