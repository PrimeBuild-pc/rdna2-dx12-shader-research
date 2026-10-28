#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;

  [unroll] for (int i = 0; i < 24; ++i) { float4 a = In[(t*24+i) & 65535];
    s += sin(a) * cos(a * 1.25) + a * 0.5; }
  Out[t] = s;
}
