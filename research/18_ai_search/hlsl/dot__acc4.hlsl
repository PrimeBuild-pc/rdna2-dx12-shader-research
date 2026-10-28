#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 a0 = 0, a1 = 0, a2 = 0, a3 = 0;
  for (int i = 0; i < 32; i += 4) {
    float4 b0 = In[(t*32+i) & 65535], b1 = In[(t*32+i+1) & 65535];
    float4 b2 = In[(t*32+i+2) & 65535], b3 = In[(t*32+i+3) & 65535];
    a0 += b0*b0; a1 += b1*b1; a2 += b2*b2; a3 += b3*b3; }
  s = (a0 + a1) + (a2 + a3);
  Out[t] = s;
}
