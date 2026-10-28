#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 p[24];
  [unroll] for (int i = 0; i < 24; ++i) p[i] = In[(t*24+i) & 65535];
  float4 s0 = 0, s1 = 0;
  for (int j = 0; j < 24; j += 2) {
    float4 a = p[j], b = p[j+1];
    s0 += sin(a) * cos(a * 1.25) + a * 0.5;
    s1 += sin(b) * cos(b * 1.25) + b * 0.5; }
  s = s0 + s1;
  Out[t] = s;
}
