# Full-precision equivalence probe (phase 2Q)

`sweep.exe <shader.dxil> <out.json> [firstPattern] [lastPattern]` runs a compute shader over a
range of float32 **bit patterns** and reads back a 16-slot uint reduction. The default range,
`0x00000000..0x3F800000`, is every float32 value in [0,1] — 1 065 353 217 of them, all visited,
none sampled.

Two shaders share the host, and **they use the reduction slots differently**. The named JSON
fields (`differing`, `max_ulp`, `nan`, …) are written for `sweep.hlsl`; for any other shader read
**`slots_raw`** and `slots_as_float`, which are the untouched reduction, and ignore the names.

| shader | slots |
|---|---|
| `sweep.hlsl` — do the two forms of x⁵ agree | [0] differing, [1] max ULP between them, [2] max rel (float bits), [3] NaN, [4] +Inf, [5] −Inf, [6] −0, [7] max abs (float bits), [8] zero mismatch |
| `sweep_ref.hlsl` — which form is closer to the true x⁵ | [0] `pow` closer, [1] multiplication closer, [2] equal, [3] max ULP error of `pow`, [4] max ULP error of the multiplication, [5] max rel error of `pow` (float bits), [6] max rel error of the multiplication (float bits), [9] values visited |

The reference in `sweep_ref.hlsl` is computed in **double precision** from the same float32 input:
four double multiplies carry ~2^-50 relative error, seven orders of magnitude below float32
spacing, so rounding it back to float32 gives the correctly-rounded x⁵.

Build: `build.cmd` (MSVC) for the host, `dxc -T cs_6_2 -E main -Fo <out>.dxil <shader>.hlsl` for
the shaders.
