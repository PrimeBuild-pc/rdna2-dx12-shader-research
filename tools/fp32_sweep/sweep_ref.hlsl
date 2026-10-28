// Phase 2Q, second probe: which of the two forms is CLOSER TO THE TRUE VALUE of x^5.
//
// The reference is computed in double precision from the same float32 input. x is exactly
// representable as a double, and four double multiplies carry a relative error near 2^-50,
// which is seven orders of magnitude below float32's spacing - so rounding the double result to
// float32 gives the correctly-rounded x^5 for all practical purposes.
//
// Reduction slots, all uint:
//   [0] pow strictly closer   [1] multiplication strictly closer   [2] equally close
//   [3] max ULP error of pow  [4] max ULP error of the multiplication form
//   [5] max relative error of pow, as a float bit pattern
//   [6] max relative error of the multiplication form, same encoding
//   [9] values visited

RWStructuredBuffer<uint> Reduce : register(u0);

cbuffer Args : register(b0)
{
    uint FirstPattern;
    uint Count;
    uint Pad0, Pad1;
};

[numthreads(256, 1, 1)]
void main(uint3 tid : SV_DispatchThreadID)
{
    if (tid.x >= Count)
        return;

    float x = asfloat(FirstPattern + tid.x);

    float a = pow(x, 5.0);              // the original form
    float f2 = x * x;
    float b = f2 * f2 * x;              // the transformed form

    double xd = (double)x;
    double refd = xd * xd * xd * xd * xd;
    float  ref  = (float)refd;

    uint ua = asuint(a), ub = asuint(b), ur = asuint(ref);
    uint ea = ua > ur ? ua - ur : ur - ua;      // all three are non-negative here
    uint eb = ub > ur ? ub - ur : ur - ub;

    if (ea < eb)      InterlockedAdd(Reduce[0], 1);
    else if (eb < ea) InterlockedAdd(Reduce[1], 1);
    else              InterlockedAdd(Reduce[2], 1);

    InterlockedMax(Reduce[3], ea);
    InterlockedMax(Reduce[4], eb);
    if (ref != 0.0)
    {
        InterlockedMax(Reduce[5], asuint(abs(a - ref) / abs(ref)));
        InterlockedMax(Reduce[6], asuint(abs(b - ref) / abs(ref)));
    }
    InterlockedAdd(Reduce[9], 1);
}
