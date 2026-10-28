#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  float4 pbuf[24];
  [unroll] for (int q = 0; q < 24; ++q) pbuf[q] = In[(t*24+(q)) & 65535];
   for (int i = 0; i < 24; i += 1) {
    float4 a0 = pbuf[i + 0];
    s += sin(a0)*cos(a0*1.25) + a0*0.5;
    }

  Out[t] = s;
}
