// Phase 2Q: exhaustive comparison of pow(x, 5.0) against the multiplication form used by the
// accepted `fresnel5` transformation, over EVERY float32 value the expression can be given.
//
// FSchlick computes `1.0 - saturate(dot(lightDir, halfVec))`. saturate clamps into [0,1] and
// maps NaN to zero, so the input domain is exactly the float32 values with bit patterns
// 0x00000000 .. 0x3F800000 - all 1 065 353 217 of them, swept here with no sampling.
//
// The reduction buffer, all as uint:
//   [0] count of inputs where the two forms differ
//   [1] max ULP distance between the two results
//   [2] max relative error, as the bit pattern of a positive float (monotonic, so InterlockedMax
//       on the pattern is InterlockedMax on the value)
//   [3] count where either result is NaN        [4] count where either is +Inf
//   [5] count where either is -Inf              [6] count where either is negative zero
//   [7] max absolute error, same bit-pattern trick
//   [8] count where pow gives 0 and the product does not, or vice versa

RWStructuredBuffer<uint> Reduce : register(u0);

cbuffer Args : register(b0)
{
    uint FirstPattern;      // first float32 bit pattern this dispatch covers
    uint Count;             // how many patterns
    uint Pad0, Pad1;
};

[numthreads(256, 1, 1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    if (tid.x >= Count)
        return;

    uint pattern = FirstPattern + tid.x;
    float x = asfloat(pattern);

    // The two forms, written exactly as they appear in Lighting.hlsli.
    float a = pow(x, 5.0);
    float f2 = x * x;
    float b = f2 * f2 * x;

    uint ua = asuint(a), ub = asuint(b);
    if (ua != ub)
    {
        InterlockedAdd(Reduce[0], 1);
        // Both results are non-negative here, so the unsigned patterns are already ordered.
        uint ulp = ua > ub ? ua - ub : ub - ua;
        InterlockedMax(Reduce[1], ulp);
        float diff = abs(b - a);
        InterlockedMax(Reduce[7], asuint(diff));
        float rel = a != 0.0 ? diff / abs(a) : (diff != 0.0 ? 1.0 : 0.0);
        InterlockedMax(Reduce[2], asuint(rel));
        if ((a == 0.0) != (b == 0.0))
            InterlockedAdd(Reduce[8], 1);
    }
    if (isnan(a) || isnan(b))                       InterlockedAdd(Reduce[3], 1);
    if (isinf(a) && a > 0.0 || isinf(b) && b > 0.0) InterlockedAdd(Reduce[4], 1);
    if (isinf(a) && a < 0.0 || isinf(b) && b < 0.0) InterlockedAdd(Reduce[5], 1);
    if ((a == 0.0 && (asuint(a) >> 31)) || (b == 0.0 && (asuint(b) >> 31)))
        InterlockedAdd(Reduce[6], 1);
}
