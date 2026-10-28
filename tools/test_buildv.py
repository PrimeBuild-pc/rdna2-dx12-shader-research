"""No-GPU gate test required by CODEX_HANDOFF_AUDIT section 7 step 1.

Proves buildv rejects all four failure modes named there: process error, missing header,
unchanged hash, unexpected hash. Plus the runtime-inventory checks. No build, no GPU.

    python -B tools/test_buildv.py
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G

DXC = Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe")
SOURCE = Path(os.environ["TEMP"]) / "claude/src/dxs/MiniEngine/Model/Shaders/ModelViewerPS.hlsl"
PY = Path(sys.executable)


def rejects(fn, fragment):
    """fn must raise, and the message must name the reason we expect."""
    try:
        fn()
    except Exception as e:
        assert fragment in str(e), f"wrong rejection reason: {e!r} (wanted {fragment!r})"
        return
    raise AssertionError(f"NOT REJECTED: expected failure containing {fragment!r}")


def write_runtime_csv(path, artifact, **override):
    row = dict(scope="Render Color", ps_hash=artifact["custom_hash"],
               ps_bytes=artifact["bytecode_bytes"], indices="1234", native_matches="1")
    row.update(override)
    path.write_text("scope,ps_hash,ps_bytes,indices,native_matches\n"
                    + ",".join(str(row[k]) for k in
                              ["scope", "ps_hash", "ps_bytes", "indices", "native_matches"])
                    + "\n", encoding="utf-8")


def main(tmp):
    tmp = Path(tmp)
    # --- reference artifact: compile the real PS once (compiler only, no GPU) -------------
    stage = tmp / "good/Output/Model/CompiledShaders"
    stage.mkdir(parents=True)
    header = stage / "ModelViewerPS.h"
    assert subprocess.run([DXC, "-nologo", "-E", "main", "-T", "ps_6_2", "-D", "_GAMING_DESKTOP=1",
                           "-Fh", header, "-Vn", "g_pModelViewerPS", "-HV", "2021", SOURCE],
                          cwd=SOURCE.parent).returncode == 0, "reference compile failed"
    good = G.shader_artifact(tmp / "good")
    assert good["bytecode_bytes"] > 1000 and len(good["custom_hash"]) == 16
    print(f"reference ModelViewerPS: {good['bytecode_bytes']} bytes, hash {good['custom_hash']}")

    # --- 1. process error must be rejected (audit A01: returncode was ignored) ------------
    rejects(lambda: G.run_checked([PY, "-c", "raise SystemExit(3)"], tmp, tmp / "l1.log"),
            "process failed (3)")
    rejects(lambda: G.run_checked([PY, "-c", "pass"], tmp, tmp / "l1.log"), "log already exists")

    # --- 2. missing / ambiguous header must be rejected -----------------------------------
    (tmp / "empty").mkdir()
    rejects(lambda: G.shader_artifact(tmp / "empty"), "shader header missing or ambiguous")
    two = tmp / "two"
    (two / "a").mkdir(parents=True); (two / "b").mkdir()
    shutil.copy2(header, two / "a/ModelViewerPS.h"); shutil.copy2(header, two / "b/ModelViewerPS.h")
    rejects(lambda: G.shader_artifact(two), "shader header missing or ambiguous")

    # --- 3. unexpected hash must be rejected ----------------------------------------------
    rejects(lambda: G.shader_artifact(tmp / "good", expected="00" * 32),
            "unexpected bytecode SHA-256")

    # --- 4. unchanged hash must be rejected when a canary was expected --------------------
    rejects(lambda: G.shader_artifact(tmp / "good", different=good["bytecode_sha256"]),
            "canary bytecode unchanged")

    # --- 5. corrupt / non-shader headers must be rejected, not silently accepted ----------
    text = header.read_text(encoding="utf-8-sig")
    hexdump = lambda b: ", ".join(f"0x{x:02x}" for x in b)  # DXC also emits braces in comments
    for name, content, why in [
        ("no_array", "// nothing here\n", "missing/ambiguous shader initializer"),
        ("dup_array", text + text, "missing/ambiguous shader initializer"),
        ("not_hex", "const BYTE g_pModelViewerPS[] = { 0x44, oops };", "unextractable shader bytecode"),
        ("not_dxbc", "const BYTE g_pModelViewerPS[] = {" + ", ".join(["0x00"] * 64) + "};",
         "not a DXBC/DXIL container"),
        ("truncated", "const BYTE g_pModelViewerPS[] = {"
         + hexdump(G.bytecode(header)[:512]) + "};", "invalid container size"),
    ]:
        d = tmp / name
        d.mkdir()
        (d / "ModelViewerPS.h").write_text(content, encoding="utf-8")
        rejects(lambda d=d: G.shader_artifact(d), why)

    # --- 6. runtime inventory: only the exact live PSO passes -----------------------------
    csv = tmp / "runtime.csv"
    write_runtime_csv(csv, good)
    assert len(G.verify_runtime(csv, good)) == 1, "valid runtime inventory must pass"
    for why, override in [
        ("missing/wrong live pass", dict(scope="Z PrePass")),
        ("runtime PSO hash/size/native binding mismatch", dict(ps_hash="0" * 16)),
        ("runtime PSO hash/size/native binding mismatch", dict(ps_bytes=good["bytecode_bytes"] - 4)),
        ("runtime PSO hash/size/native binding mismatch", dict(indices="0")),
        ("runtime PSO hash/size/native binding mismatch", dict(native_matches="0")),
    ]:
        write_runtime_csv(csv, good, **override)
        rejects(lambda: G.verify_runtime(csv, good), why)
    csv.write_text("scope,ps_hash,ps_bytes,indices,native_matches\n", encoding="utf-8")
    rejects(lambda: G.verify_runtime(csv, good), "missing/wrong live pass")

    print("\nALL GATE CHECKS REJECTED AS REQUIRED — buildv is fail-closed on: "
          "process error, missing/ambiguous header, unchanged hash, unexpected hash, "
          "corrupt bytecode, wrong runtime PSO.")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        main(d)
