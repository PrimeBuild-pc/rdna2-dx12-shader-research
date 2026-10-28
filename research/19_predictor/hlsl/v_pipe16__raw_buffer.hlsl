#define RS "RootFlags(0), UAV(u0), SRV(t0)"
ByteAddressBuffer In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
  float4 v[16];
   for (int i = 0; i < 16; ++i) v[i] = In.Load<float4>(((t*16+i) & 65535) << 4) * (i+1);
   for (int k = 0; k < 16; ++k) v[k] = sin(v[k]) + v[(k*7)%16]*cos(v[(k*11)%16]);
   for (int j = 0; j < 16; ++j) s += v[j]*v[(j*5)%16];

  Out[t] = s;
}
