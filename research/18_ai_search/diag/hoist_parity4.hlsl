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
    for (int i = 0; i < 32; i += 4) {
      float4 a0=In[(t*32+i)&65535], a1=In[(t*32+i+1)&65535];
      float4 a2=In[(t*32+i+2)&65535], a3=In[(t*32+i+3)&65535];
      s += a0*a0; s += sin(a1)*cos(a1); s += a2*a2; s += sin(a3)*cos(a3); }
  } else {
    for (int j = 0; j < 32; j += 4) {
      float4 b0=In[(t*32+j)&65535], b1=In[(t*32+j+1)&65535];
      float4 b2=In[(t*32+j+2)&65535], b3=In[(t*32+j+3)&65535];
      s += sin(b0)*cos(b0); s += b1*b1; s += sin(b2)*cos(b2); s += b3*b3; }
  }
  Out[t] = s;
}
