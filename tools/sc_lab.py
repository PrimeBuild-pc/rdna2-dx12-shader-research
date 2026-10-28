"""Phase 2E - Controlled Compiler Optimization Lab (RGA + driver AMD installato).

Compila ogni shader in un processo RGA separato con timeout, estrae le metriche di codegen
dall'ISA e dal CSV di analisi, e confronta baseline vs variante (una sola opzione per volta).

    python tools/sc_lab.py baseline
    python tools/sc_lab.py sweep

Non modifica driver, Registry, cache o file di sistema. Le env var sono process-local.
ATTENZIONE: AMD_SC_OPTIONS splitta sugli spazi -> nessun path con spazi al suo interno.
"""
import csv, os, re, shutil, subprocess, sys, tempfile, hashlib, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RGA = os.path.join(ROOT, "RadeonDeveloperToolSuite-2026-05-28-1806",
                   "RadeonDeveloperToolSuite-2026-05-28-1806", "rga.exe")
LAB = os.path.join(ROOT, "research", "11_compiler_experiments")
SH = os.path.join(LAB, "shaders")
ASIC = "gfx1030"          # Navi 21 = RX 6950 XT

# stage, entry, shader model per ogni file
SHADERS = [
    ("s1_simple",    "cs", "cs_6_0"),
    ("s2_alu",       "cs", "cs_6_0"),
    ("s3_mem",       "cs", "cs_6_0"),
    ("s4_pressure",  "cs", "cs_6_0"),
    ("s5_divergent", "cs", "cs_6_0"),
    ("s6_texture",   "cs", "cs_6_0"),
]

ISA_RE = {
    "vgpr": re.compile(r"vgpr_count\((\d+)\)"),
    "sgpr": re.compile(r"sgpr_count\((\d+)\)"),
    "wave_size": re.compile(r"wave_size\((\d+)\)"),
    "asic": re.compile(r"asic\((\w+)\)"),
    "type": re.compile(r"type\((\w+)\)"),
}
HASH_RE = {
    "d3d12_hash": re.compile(r"D3D12 Shader Hash (0x[0-9a-f]+)"),
    "pso_hash": re.compile(r"API PSO Hash (0x[0-9a-f]+)"),
    "pipeline_hash": re.compile(r"Driver Internal Pipeline Hash (0x[0-9a-f]+)"),
}


def compile_one(name, stage, model, env_extra=None, timeout=240):
    """Un processo RGA separato. Ritorna dict con metriche, o {'ok': False}."""
    out = tempfile.mkdtemp(prefix="sclab_")
    isa = os.path.join(out, "isa.txt")
    ana = os.path.join(out, "an.csv")
    cmd = [RGA, "-s", "dx12", "-c", ASIC,
           f"--{stage}", os.path.join(SH, name + ".hlsl"),
           f"--{stage}-entry", "main", f"--{stage}-model", model,
           "--rs-macro", "RS", "--isa", isa, "-a", ana]
    env = dict(os.environ)
    for k in ("AMD_SC_OPTIONS", "AMD_SC_CFG_FILE", "AMD_DXCP_TEST_OPTIONS"):
        env.pop(k, None)
    if env_extra:
        env.update(env_extra)
    r = dict(shader=name, ok=False, error="")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=out)
        log = (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        r["error"] = "timeout"
        shutil.rmtree(out, ignore_errors=True)
        return r
    if "succeeded" not in log:
        m = re.search(r"Error:.*", log)
        r["error"] = (m.group(0)[:90] if m else "failed")
        shutil.rmtree(out, ignore_errors=True)
        return r

    # l'ISA finisce in <dir>/<asic>_isa_<stage>.txt
    isa_file = None
    for f in os.listdir(out):
        if "isa" in f and f.endswith(".txt"):
            isa_file = os.path.join(out, f)
    if not isa_file:
        r["error"] = "nessun ISA prodotto"
        shutil.rmtree(out, ignore_errors=True)
        return r
    text = open(isa_file, encoding="utf-8", errors="replace").read()
    r["ok"] = True
    for k, rx in {**ISA_RE, **HASH_RE}.items():
        m = rx.search(text)
        r[k] = m.group(1) if m else ""
    body = text[text.find("Disassembly"):]
    instrs = [l for l in body.splitlines()
              if re.match(r"\s{2}[a-z][a-z0-9_]+\s", l) and "//" in l]
    r["num_inst"] = len(instrs)
    r["num_valu"] = sum(1 for l in instrs if re.match(r"\s+v_", l))
    r["num_salu"] = sum(1 for l in instrs if re.match(r"\s+s_", l))
    r["num_mem"] = sum(1 for l in instrs if re.search(r"\s(buffer_|global_|flat_|image_|ds_)", l))
    r["num_branch"] = sum(1 for l in instrs if re.search(r"\ss_(branch|cbranch)", l))
    # code size dai commenti di encoding: ultimo offset esadecimale
    offs = re.findall(r"//\s*([0-9A-F]{12})", body)
    r["code_bytes"] = int(offs[-1], 16) if offs else ""
    r["isa_sha256"] = hashlib.sha256(
        re.sub(r"//.*", "", body).encode()).hexdigest()[:16]
    # statistiche RGA
    for f in os.listdir(out):
        if f.endswith(".csv"):
            try:
                rows = list(csv.DictReader(open(os.path.join(out, f), encoding="utf-8-sig")))
                if rows:
                    for key in ("USED_VGPRs", "USED_SGPRs", "ISA_SIZE", "SCRATCH_MEM",
                                "LDS_USAGE", "VGPR_SPILL", "SGPR_SPILL"):
                        for col in rows[0]:
                            if key.lower().replace("_", "") in col.lower().replace(" ", "").replace("_", ""):
                                r["rga_" + key.lower()] = rows[0][col]
            except Exception:
                pass
    shutil.rmtree(out, ignore_errors=True)
    return r


FIELDS = ["shader", "variant", "ok", "error", "type", "asic", "wave_size", "vgpr", "sgpr",
          "num_inst", "num_valu", "num_salu", "num_mem", "num_branch", "code_bytes",
          "isa_sha256", "d3d12_hash", "pso_hash", "pipeline_hash"]


def write(rows, path):
    keys = list(FIELDS)
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def baseline():
    rows = []
    for name, stage, model in SHADERS:
        r = compile_one(name, stage, model)
        r["variant"] = "baseline"
        rows.append(r)
        print(f"  {'OK ' if r['ok'] else 'KO '} {name:14s} "
              + (f"vgpr={r.get('vgpr'):>3} sgpr={r.get('sgpr'):>3} inst={r.get('num_inst'):>4} "
                 f"wave={r.get('wave_size')} isa={r.get('isa_sha256')}" if r["ok"] else r["error"]))
    write(rows, os.path.join(LAB, "baseline.csv"))
    return rows


# Le uniche opzioni che il parser SC accetta (verificato: gli altri gruppi non esistono).
VARIANTS = [
    ("dump-all",        {"AMD_SC_OPTIONS": "--dump-all=1"}),
    ("dump-il-text",    {"AMD_SC_OPTIONS": "--dump-il-text=1"}),
    ("dump-input-xml",  {"AMD_SC_OPTIONS": "--dump-input-xml=1"}),
    ("dump-separate",   {"AMD_SC_OPTIONS": "--dump-separate=1"}),
]


def sweep():
    base = {r["shader"]: r for r in baseline() if r["ok"]}
    rows, diffs = [], []
    for vname, env in VARIANTS:
        for name, stage, model in SHADERS:
            r = compile_one(name, stage, model, env_extra=env)
            r["variant"] = vname
            rows.append(r)
            b = base.get(name)
            if r["ok"] and b:
                changed = r["isa_sha256"] != b["isa_sha256"]
                diffs.append(dict(
                    shader=name, option=vname, value="1",
                    isa_changed="YES" if changed else "no",
                    d_inst=int(r["num_inst"]) - int(b["num_inst"]),
                    d_vgpr=int(r["vgpr"] or 0) - int(b["vgpr"] or 0),
                    d_sgpr=int(r["sgpr"] or 0) - int(b["sgpr"] or 0),
                    d_code=(int(r["code_bytes"] or 0) - int(b["code_bytes"] or 0)),
                    wave=f"{b['wave_size']}->{r['wave_size']}",
                    notes="" if changed else "codegen identico"))
                print(f"  {vname:16s} {name:14s} ISA {'CAMBIATO' if changed else 'identico'}")
            else:
                diffs.append(dict(shader=name, option=vname, value="1", isa_changed="ERR",
                                  d_inst="", d_vgpr="", d_sgpr="", d_code="", wave="",
                                  notes=r["error"]))
                print(f"  {vname:16s} {name:14s} ERRORE: {r['error']}")
    write(rows, os.path.join(LAB, "variants_raw.csv"))
    with open(os.path.join(LAB, "compiler_option_results.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["shader", "option", "value", "isa_changed",
                                          "d_inst", "d_vgpr", "d_sgpr", "d_code", "wave", "notes"])
        w.writeheader()
        w.writerows(diffs)
    n = sum(1 for d in diffs if d["isa_changed"] == "YES")
    print(f"\nvarianti che cambiano l'ISA: {n} su {len(diffs)}")


if __name__ == "__main__":
    os.makedirs(LAB, exist_ok=True)
    (sweep if len(sys.argv) > 1 and sys.argv[1] == "sweep" else baseline)()
