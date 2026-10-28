#define RS "RootFlags(0), UAV(u0)"
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)][numthreads(64,1,1)]
void main(uint3 t : SV_DispatchThreadID){ Out[t.x] = float4(t.x, t.y, t.z, 1); }
