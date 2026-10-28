#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);

[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID)
{
  uint t = tid.x;
  float4 s = 0;

  float4 a = In[t & 65535] + 0.5;
  [loop] for (int i = 0; i < 48; ++i) a = sin(a) * 0.5 + a * 0.25 + 0.125;
  s = a;
  Out[t] = s;
}
