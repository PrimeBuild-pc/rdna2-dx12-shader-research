#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  float4 r0 = 0, r1 = 0, r2 = 0, r3 = 0;
   for (int i = 0; i < 32; i += 4) {
    float4 a0 = In[(t*32+(i + 0)) & 65535];
    float4 a1 = In[(t*32+(i + 1)) & 65535];
    float4 a2 = In[(t*32+(i + 2)) & 65535];
    float4 a3 = In[(t*32+(i + 3)) & 65535];
    r0 += a0*a0;
    r1 += a1*a1;
    r2 += a2*a2;
    r3 += a3*a3;
    }
  s = (r0) + (r1) + (r2) + (r3);

  Out[t] = s;
}
