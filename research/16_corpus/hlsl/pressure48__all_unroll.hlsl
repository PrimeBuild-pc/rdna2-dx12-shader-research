#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 v[48];
  [unroll] for (int i = 0; i < 48; ++i) v[i] = In[(t*48+i) & 65535] * (i+1);
  [unroll] for (int k = 0; k < 48; ++k) v[k] = sin(v[k]) + v[(k*7)%48]*cos(v[(k*13)%48]);
  [unroll] for (int j = 0; j < 48; ++j) s += v[j]*v[(j*5)%48];
  Out[t] = s;
}
