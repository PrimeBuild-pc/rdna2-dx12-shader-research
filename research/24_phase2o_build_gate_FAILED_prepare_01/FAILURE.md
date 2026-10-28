# Attempt 1 of O1 `prepare` — FAILED, preserved as record

**Experiment ID:** `O1_20260906_003712` · 2026-09-06 00:37

**Failure:** `RuntimeError: patch not unique: .../Core/GameCore.cpp` on the
`GameInput::Update / EngineTuning::Update` anchor (`tools/run_o1.py:127`).

**Cause (confirmed, from source):** `replace_once()` decodes raw bytes
(`path.read_bytes().decode("utf-8-sig")`), which does **not** translate line endings, while
`GameCore.cpp` is CRLF. The anchor is the only one in the script that spans a line break, so
its embedded `\n` could never match `\r\n`. Count was 0, not 2 — the message wording
("not unique") covers both. The other 15 anchors are single-line and matched.

**Why the pre-flight dry-run missed it:** the dry-run read with `Path.read_text()`, which
applies universal-newline translation and turns CRLF into LF. It reported 16/16 anchors OK.
A pre-flight check must use the *same* decoding path as the code it is checking.

**Fix applied:** `replace_once()` now converts both anchor and replacement to the file's own
line ending when the file is CRLF. This also stops the inserted lines from writing bare LF
into CRLF files.

**State left behind:** partially patched workspace at `%TEMP%\claude\O1_20260906_003712`
(Build.props, Model.vcxproj, CommandContext.h, SponzaRenderer.cpp, ModelViewer.cpp patched;
GameCore.cpp patched up to line 125 only). **Do not reuse it.** Not deleted, per the audit's
no-deletion rule; superseded by the next attempt's workspace.

**Cost:** 0 builds, 0 GPU workloads, 0 measurements. Does not consume an experimental cycle.
