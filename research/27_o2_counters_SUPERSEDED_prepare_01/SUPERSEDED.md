# O2 `prepare`, attempt 1 — succeeded, SUPERSEDED before any build

No build and no application run: **0 experimental cycles, no GPU work.**

Superseded because reading `CommandContext::Flush` afterwards showed it does
`ExecuteCommandList` followed by `m_CommandList->Reset(...)`, which would invalidate a GPA
command-list registration made earlier in the frame — the hazard the handoff audit flagged
and left unquantified. In this configuration the flush before `Render Color`
(`SponzaRenderer.cpp:371`) sits inside `if (SSAO::AsyncCompute)` and the frozen O1/O2 config
sets `SSAO::AsyncCompute = false`, so it does not run. That is luck, not a guarantee.

`tools/o2_gpa.h` was hardened before any measurement:

- `O2Gpa::Scope` now takes the command context and **requires** the live
  `ID3D12GraphicsCommandList*` to equal the one registered at context begin, so a reset or a
  replacement is detected instead of silently producing counters for a list GPA no longer
  tracks.
- A measuring frame that ends without a `Render Color` sample is now rejected. Previously it
  would have left the pass permanently incomplete and the session would have hung in
  `GpaIsSessionComplete`.

The instrumentation patch text changed accordingly (`O2Gpa::Scope _o2gpa(gfxContext);`), so
the workspace and its recorded source hashes had to be regenerated. Nothing deleted.
