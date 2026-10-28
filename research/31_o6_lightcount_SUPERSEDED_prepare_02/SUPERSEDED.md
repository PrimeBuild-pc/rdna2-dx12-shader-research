# Superseded — O6 prepare attempt 2

The manifest was written correctly this time, but its `experiment_id` (`O6_20260906_185253`) no
longer matched the workspace directory the inherited O4 runner had already created
(`O4_20260906_185253`). `build()` requires `workspace.name == experiment_id` — a deliberate check
that the build is happening inside *this* experiment's own copy — so every build would have been
rejected. Caught by reading the gate, not by a failed build.

**No build ran and no counter was read from this attempt.** Fixed by parameterising the runner's
experiment-id prefix (`run_o4.PREFIX`) instead of renaming the id after the fact. The valid cycle
is in `31_o6_lightcount/`.
