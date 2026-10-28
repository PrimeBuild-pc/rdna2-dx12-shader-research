#define RS "RootFlags(0), UAV(u0), SRV(t0)"
StructuredBuffer<float4> In : register(t0);
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)][numthreads(64,1,1)]
void main(uint3 t : SV_DispatchThreadID){
  float4 a = In[t.x & 65535]; float4 r = 0;
  [loop] for (uint i=0;i<8;++i){
    if (a.x > 0.5f)      { r += sin(a*i); if (a.y > 0.25f) r *= 1.5f; else r -= cos(a); }
    else if (a.z < -0.1f){ r -= exp2(a);  [loop] for(uint j=0;j<4;++j) r += rsqrt(abs(r)+1); }
    else                 { r = mad(r, a, frac(a*3.1)); }
    a = frac(a*1.37 + r*0.11);
  }
  Out[t.x] = r;
}
