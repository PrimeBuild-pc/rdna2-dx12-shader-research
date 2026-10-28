#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)][WaveSize(64)][numthreads(64,1,1)]
void main(uint3 t : SV_DispatchThreadID){
  float4 v[24];
  [unroll] for (int i=0;i<24;++i) v[i] = In[(t.x*24+i) & 65535] * (i+1);
  [unroll] for (int k=0;k<24;++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  float4 s = 0;
  [unroll] for (int j=0;j<24;++j) s += v[j]*v[(j*5)%24];
  Out[t.x] = s;
}
