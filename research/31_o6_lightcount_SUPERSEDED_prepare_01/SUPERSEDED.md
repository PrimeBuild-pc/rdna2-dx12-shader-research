# Superseded — O6 prepare attempt 1

`prepare` completed the workspace copy, the input hashing and the instrumentation, then failed
writing the manifest: `buildv.save_json` opens with mode `"x"`, so the O6 preregistration could
not overwrite the one the inherited O4 runner had already written. That is the gate working as
designed — an artifact is never silently rewritten.

**No build ran and no counter was read from this attempt.** Kept for provenance; the manifest
here carries the O4 runner's criteria text, which is *not* O6's preregistration. The valid cycle
is in `31_o6_lightcount/`, prepared from scratch with the O6 criteria written in one shot.
