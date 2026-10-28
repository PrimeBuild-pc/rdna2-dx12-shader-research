#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 v[24];
   for (int i = 0; i < 24; ++i) { float f = float(((t*24+i) & 65535) & 1023) * 0.0009765625 + 0.25;
        v[i] = float4(f, 1.0-f, f*0.5-0.25, 1.0) * (i+1); }
   for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  [loop] for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];
  Out[t] = s;
}
