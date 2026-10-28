# Environment verification before the clean-room replication

Checked immediately before the first measurement, 2026-09-06.

| check | result |
|---|---|
| Chrome / Edge / Firefox / Brave / Opera | **absent** |
| Discord | **absent** |
| Steam / Epic / Fortnite / Call of Duty | **absent** |
| OBS / ffmpeg / HandBrake / VLC / Spotify / Teams / Zoom | **absent** |
| Blender / Unity / Unreal / 3DMark / DaVinci | **absent** |
| live CPU over a 4 s window | only `claude` at **0.44 %**, everything else below 0.3 % |
| GPU engine utilisation, all engines summed | **1.69 %** — `csrss` 1.43 % + `dwm` 0.38 %, i.e. the desktop compositor only |

Present and left running, as instructed (no personal application was closed): Windows Defender
(`MsMpEng`), the Herdr session manager, this Claude session, four idle Codex CLI processes and a
Hyper-V/WSL `vmmem` (0 % live CPU during the window).

Note: `Get-Process -match 'cod'` matches the **Codex CLI**, not Call of Duty. Verified by name.

The historical Phase 2O measurements were taken with the user's ordinary desktop session
running. This is the difference the replication tests.
