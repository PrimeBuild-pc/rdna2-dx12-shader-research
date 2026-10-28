# Notes for AI coding agents

Read [HANDOFF.md](HANDOFF.md) first, then [docs/ROADMAP.md](docs/ROADMAP.md). To set up a machine
(tools, versions, sources, data to recapture) follow [docs/REBUILD.md](docs/REBUILD.md) /
[data/manifests/environment.json](data/manifests/environment.json). Results live in
`research/NN_*/` (index: [docs/PHASES.md](docs/PHASES.md)); tools in `tools/`.

Hard rules (inherited from the original project, see CONTRIBUTING.md):

- Never modify signed driver files, shader caches, game files, the Registry, boot or security
  settings. Analyse copies only, hash them first.
- Never inject, hook or load ReShade into games with anti-cheat. The loader in `tools/c2077_*` is
  for single-player Cyberpunk 2077 only, installed and removed with the game closed.
- No performance claim without measured A/A noise, a preregistered threshold, bytecode provenance
  and a correctness oracle. Keep negative results; do not move thresholds after the fact.
- Do not commit binaries or game-derived data; record SHA-256 in `data/manifests/` instead.
- Most phase reports are in Italian; keep new docs in English.
- Keep `HANDOFF.md` and `PLAN.md` up to date at every milestone.

The original agent instructions (Italian) are in [docs/history/CLAUDE.md](docs/history/CLAUDE.md).
