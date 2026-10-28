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
   for (int i = 0; i < 16; i += 2) {
    float4 a0 = In[(t*16+(i + 0)) & 65535];
    float4 a1 = In[(t*16+(i + 1)) & 65535];
    r0 += a0*0.5;
    r1 += a1*0.5;
    }
  s = (r0) + (r1);

  Out[t] = s;
}
