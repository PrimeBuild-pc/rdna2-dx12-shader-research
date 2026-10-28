#define RS "RootFlags(0), UAV(u0)"
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    float4 v = 0;
    for (uint i = 0; i < 8; ++i)
        v += sin((float)(tid.x + i)) * cos((float)(tid.y + i));
    Out[tid.x] = v;
}
