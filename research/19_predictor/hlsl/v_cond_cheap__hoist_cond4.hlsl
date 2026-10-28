#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  uint hp = t & 1u;
  if (hp == 0u) {
   for (int i = 0; i < 32; i += 4) {
    float4 a0 = In[(t*32+(i + 0)) & 65535];
    float4 a1 = In[(t*32+(i + 1)) & 65535];
    float4 a2 = In[(t*32+(i + 2)) & 65535];
    float4 a3 = In[(t*32+(i + 3)) & 65535];
    s += a0*0.5;
    s += a1*a1;
    s += a2*0.5;
    s += a3*a3;
    }
  }
  else if (hp == 1u) {
   for (int i = 0; i < 32; i += 4) {
    float4 a0 = In[(t*32+(i + 0)) & 65535];
    float4 a1 = In[(t*32+(i + 1)) & 65535];
    float4 a2 = In[(t*32+(i + 2)) & 65535];
    float4 a3 = In[(t*32+(i + 3)) & 65535];
    s += a0*a0;
    s += a1*0.5;
    s += a2*a2;
    s += a3*0.5;
    }
  }

  Out[t] = s;
}
