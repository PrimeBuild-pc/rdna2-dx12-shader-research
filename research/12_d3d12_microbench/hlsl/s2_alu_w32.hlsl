#define RS "RootFlags(0), UAV(u0)"
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)][WaveSize(32)][numthreads(64,1,1)]
void main(uint3 t : SV_DispatchThreadID){
  float4 a = float4(t.x,t.y,t.z,1); float4 b = 0;
  [unroll] for (int i=0;i<32;++i){
    a = sin(a)*cos(a.yzwx) + rsqrt(abs(a)+1.0);
    b += a*a - exp2(a.wxyz) + log2(abs(a)+2.0);
    a = mad(a, b.zwxy, frac(b*1.7));
  }
  Out[t.x] = a+b;
}
