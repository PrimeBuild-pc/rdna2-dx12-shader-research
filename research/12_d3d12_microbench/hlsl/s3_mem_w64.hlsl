#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
groupshared float4 lds[256];
[RootSignature(RS)][WaveSize(64)][numthreads(256,1,1)]
void main(uint3 t : SV_DispatchThreadID, uint gi : SV_GroupIndex){
  float4 s = 0;
  [loop] for (uint i=0;i<16;++i) s += In[(t.x*16+i) & 65535];
  lds[gi] = s; GroupMemoryBarrierWithGroupSync();
  [loop] for (uint j=0;j<16;++j) s += lds[(gi+j*7) & 255];
  Out[t.x] = s;
}
