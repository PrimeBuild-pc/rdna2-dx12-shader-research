#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  float4 v[8];
   for (int i = 0; i < 8; ++i) v[i] = In[(t*8+i) & 65535] * (i+1);
   for (int k = 0; k < 8; ++k) v[k] = sin(v[k]) + v[(k*3)%8]*cos(v[(k*5)%8]);
   for (int j = 0; j < 8; ++j) s += v[j]*v[(j*3)%8];

  Out[t] = s;
}
