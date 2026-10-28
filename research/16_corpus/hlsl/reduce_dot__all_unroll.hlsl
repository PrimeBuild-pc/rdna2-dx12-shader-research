#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 acc = 0;
  [unroll] for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535]; acc += a * a; }
  s = acc;
  Out[t] = s;
}
