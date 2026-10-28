"""Fail-closed O1 build gate. No legacy/incremental/Rebuild fallback.

Used by run_o1.py only; historical runners are deliberately not migrated.
Each invocation requires a new stage directory and an instrumented source copy.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from map2m import fnv1a

MSBUILD = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe")


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def save_json(path, value):
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2)


def save_json_over(path, value):
    """For derived reports that are regenerated from artefacts, never for provenance records."""
    Path(path).write_text(json.dumps(value, indent=2), encoding="utf-8")


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run_checked(args, cwd, log, env=None, timeout=600):
    """Record actual Windows child image, command, PID, exit status, stdout/stderr."""
    args = [str(a) for a in args]
    log = Path(log)
    require(not log.exists() and not log.with_suffix(".json").exists(), "log already exists")
    exe = Path(args[0]).resolve(strict=True)
    before = sha(exe)
    record = dict(args=args, command_line=subprocess.list2cmdline(args), cwd=str(cwd),
                  requested_executable=str(exe), executable_sha256=before)
    with log.open("xb") as f:
        p = subprocess.Popen(args, executable=str(exe), cwd=cwd, env=env,
                             stdout=f, stderr=subprocess.STDOUT)
        record["pid"] = p.pid
        try:
            buf = ctypes.create_unicode_buffer(32768)
            n = ctypes.c_ulong(len(buf))
            query = ctypes.windll.kernel32.QueryFullProcessImageNameW
            query.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p,
                              ctypes.POINTER(ctypes.c_ulong)]
            require(query(int(p._handle), 0, buf, ctypes.byref(n)), "cannot identify child image")
            actual = Path(buf.value).resolve(strict=True)
            record["actual_executable"] = str(actual)
            require(actual == exe, "unexpected child executable")
            record["returncode"] = p.wait(timeout=timeout)
        except BaseException as e:
            if p.poll() is None:
                p.kill()  # only this owned validation/build process, never personal apps
                p.wait()
            record.update(returncode=p.returncode, failure=str(e))
            raise
        finally:
            save_json(log.with_suffix(".json"), record)
    require(record["returncode"] == 0, f"process failed ({record['returncode']}): {log}")
    require(sha(exe) == before, "executable changed while running")
    return record


def bytecode(header):
    text = Path(header).read_text(encoding="utf-8-sig")
    arrays = re.findall(r"g_pModelViewerPS\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;", text, re.S)
    require(len(arrays) == 1, "missing/ambiguous shader initializer")
    tokens = arrays[0].strip().rstrip(",").split(",")
    require(all(re.fullmatch(r"\s*0x[0-9a-fA-F]{2}\s*", t) for t in tokens),
            "unextractable shader bytecode")
    data = bytes(int(t, 16) for t in tokens)
    require(len(data) >= 32 and data[:4] == b"DXBC", "not a DXBC/DXIL container")
    size, count = struct.unpack_from("<II", data, 24)
    require(size == len(data) and 0 < count <= (len(data)-32)//4, "invalid container size")
    chunks = []
    for i in range(count):
        pos = struct.unpack_from("<I", data, 32+4*i)[0]
        require(pos >= 32+4*count and pos+8 <= len(data), "invalid chunk offset")
        length = struct.unpack_from("<I", data, pos+4)[0]
        require(pos+8+length <= len(data), "invalid chunk length")
        chunks.append(data[pos:pos+4])
    require(b"DXIL" in chunks, "DXIL chunk missing")
    return data


def effective_inputs(deps, inputs):
    """Every file DXC actually read must be one we hashed. O1 paths contain no spaces."""
    # hlsli? and not (hlsl|hlsli): that alternation matches "hlsl" first and truncates ".hlsli".
    names = re.findall(r"[A-Za-z]:[/\\]\S+\.hlsli?(?=\s|$)",
                       Path(deps).read_text(encoding="utf-8-sig"))
    require(names, "DXC dependency list unextractable")
    effective = {}
    for name in names:
        p = str(Path(name).resolve(strict=True))
        require(p in inputs, f"unregistered include: {p}")
        effective[p] = inputs[p]
    return effective


def shader_artifact(stage, expected=None, different=None):
    headers = list(Path(stage).rglob("ModelViewerPS.h"))
    require(len(headers) == 1, "shader header missing or ambiguous")
    header = headers[0]
    data = bytecode(header)
    digest = hashlib.sha256(data).hexdigest()
    require(expected is None or digest == expected, "unexpected bytecode SHA-256")
    require(different is None or digest != different, "canary bytecode unchanged")
    return dict(header=str(header), header_sha256=sha(header), bytecode_sha256=digest,
                custom_hash=f"{fnv1a(data):016X}", bytecode_bytes=len(data))


def verify_runtime(path, artifact):
    import csv
    with Path(path).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    require(rows and all(r["scope"] == "Render Color" for r in rows), "missing/wrong live pass")
    require(all(r["ps_hash"] == artifact["custom_hash"] and
                int(r["ps_bytes"]) == artifact["bytecode_bytes"] and
                int(r["indices"]) > 0 and int(r["native_matches"]) == 1 for r in rows),
            "runtime PSO hash/size/native binding mismatch")
    return rows


def build(me, stage, logs, dxc, expected=None, different=None):
    me, stage, logs, dxc = map(Path, (me, stage, logs, dxc))
    stage.mkdir(parents=True, exist_ok=False)  # freshness boundary; never reuse a stage
    logs.mkdir(parents=True, exist_ok=False)
    source = me / "Model/Shaders/ModelViewerPS.hlsl"
    inputs = {str(p): sha(p) for p in [source, *sorted(source.parent.glob("*.hlsli"))]}
    shader_out = stage / "Output/Model/CompiledShaders"
    shader_out.mkdir(parents=True)
    header, cso, deps = (shader_out/"ModelViewerPS.h", stage/"ModelViewerPS.cso", stage/"deps.d")
    base = [dxc, "-nologo", "-E", "main", "-T", "ps_6_2", "-D", "_GAMING_DESKTOP=1", "-HV", "2021"]
    # Measured: -MD puts DXC in dependency-only mode — it writes the depfile, emits NO -Fh/-Fo
    # output and still exits 0. Compile and dependency scan must be separate invocations.
    record = run_checked([*base, "-Fh", header, "-Vn", "g_pModelViewerPS", "-Fo", cso, source],
                         source.parent, logs/"dxc.log", timeout=120)
    run_checked([*base, "-Vi", "-MD", "-MF", deps, source], source.parent,
                logs/"dxc_deps.log", timeout=120)
    require(cso.is_file() and deps.is_file(), "DXC output/dependencies missing")
    artifact = shader_artifact(stage, expected, different)
    require(bytecode(header) == cso.read_bytes(), "header and DXC object differ")
    effective = effective_inputs(deps, inputs)
    require(str(source.resolve()) in effective, "source absent from DXC dependencies")
    for p, h in inputs.items():
        require(sha(p) == h, "source/include changed during compile")
    record.update(entry="main", shader_model="ps_6_2", defines=["_GAMING_DESKTOP=1"],
                  source_sha256=inputs[str(source)], effective_inputs=effective)
    version = run_checked([dxc, "--version"], me, logs/"dxc_version.log", timeout=15)
    record["version_output"] = (logs/"dxc_version.log").read_text(encoding="utf-8-sig")
    save_json(stage/"compiler_provenance.json", record)
    args = [MSBUILD, me/"ModelViewer/ModelViewer.vcxproj", "-t:Build",
            "-p:Configuration=Profile", "-p:Platform=x64", "-p:PlatformToolset=v145",
            f"-p:O1BuildRoot={stage}", "-p:VcpkgManifestInstall=false", "-m:4", "-v:normal",
            f"-flp:logfile={logs/'msbuild_diagnostic.log'};verbosity=diagnostic"]
    run_checked(args, me, logs/"msbuild.log", timeout=900)
    after = shader_artifact(stage, artifact["bytecode_sha256"])
    require(after == artifact, "MSBuild replaced the verified shader header")
    exes = list(stage.rglob("ModelViewer.exe"))
    require(len(exes) == 1, "executable missing or ambiguous")
    # MSBuild's file tracker excludes the build output tree, so CL.read.*.tlog can never name
    # a generated header (measured: 0 output-tree paths in a real Model CL.read.1.tlog; same
    # root cause as the empty dxc.write tlog). Prove propagation directly instead — the
    # verified bytes must be linked, exactly once, into the library and the executable.
    for name in ["Model.lib", "ModelViewer.exe"]:
        found = list(stage.rglob(name))
        require(len(found) == 1, f"{name} missing or ambiguous")
        require(found[0].read_bytes().count(bytecode(header)) == 1,
                f"verified shader bytecode not linked exactly once into {name}")
    for p, h in inputs.items():
        require(sha(p) == h, "source/include changed during build")
    artifact.update(executable=str(exes[0]), executable_sha256=sha(exes[0]),
                    source_sha256=inputs[str(source)])
    save_json(stage/"verified_build.json", artifact)
    return artifact
