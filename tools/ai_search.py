"""Phase 2I - AI-guided shader search.

Il riferimento e' SEMPRE il default reale di DXC/AMD: nessun attributo, nessun hint.
Le trasformazioni sono proposte a mano (dall'LLM); a decidere e' solo il tempo GPU misurato.

Statistica: confronto APPAIATO dentro lo stesso processo. In ogni processo il default e'
misurato due volte, in prima e ultima posizione, e il riferimento e' la media delle due:
cancella la deriva di clock lungo il processo (misurata in 2I: +0.35% sulla seconda
posizione di pressure24). Le varianti sono mescolate a ogni run.

    python tools/ai_search.py compile
    python tools/ai_search.py correct
    python tools/ai_search.py screen   --runs 5
    python tools/ai_search.py confirm  --runs 10

Nessun driver / Registry / cache / gioco toccato.
"""
import argparse, csv, hashlib, json, os, random, re, shutil, statistics, subprocess, sys, tempfile
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.join(ROOT, "research", "12_d3d12_microbench")
BENCH = os.path.join(BENCH_DIR, "bench.exe")
OUT = os.path.join(ROOT, "research", "18_ai_search")
DXC = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\dxc.exe"
RGA = os.path.join(ROOT, "RadeonDeveloperToolSuite-2026-05-28-1806",
                   "RadeonDeveloperToolSuite-2026-05-28-1806", "rga.exe")
TMP = os.path.join(os.environ.get("TEMP", "."), "claude", "aisearch")

REPS, DPM = 25, 8
SCREEN_TH, SCREEN_DS = 262144, 0
CONFIRM = [(262144, 0), (65536, 8), (1048576, 12)]   # (thread, dataset) indipendenti
CORRECT_DS = [0, 5, 8, 12, 17]

# --- criteri, fissati prima di guardare i risultati -------------------------
CAND_PCT = -0.5      # soglia di screening: candidato se media appaiata < -0.5%
ACCEPT_PCT = -1.0    # soglia di accettazione: media appaiata < -1.0%
ACCEPT_SIGMA = 2.0   # e media + 2*SE < 0
TOL_STRICT = 1e-6    # livello "strict": sostituto sicuro
TOL_RMS = 1e-5       # livello "riassociazione": stesso calcolo a meno di riordino FP

SRV_STRUCT = "StructuredBuffer<float4> In : register(t0);"
SRV_RAW = "ByteAddressBuffer In : register(t0);"

WRAP = """#define RS "RootFlags(0), UAV(u0), SRV(t0)"
%(DECLS)s
RWStructuredBuffer<float4> Out : register(u0);
[RootSignature(RS)]
[numthreads(%(TG)d,1,1)]
void main(uint3 tid : SV_DispatchThreadID, uint3 gtid : SV_GroupThreadID, uint3 gid : SV_GroupID)
{
  uint t = tid.x;
  float4 s = 0;
%(BODY)s
  Out[t] = s;
}
"""

# =========================================================================
# Corpus. Per ogni shader: 'default' e' il codice senza alcun hint.
# Ogni variante e' semanticamente equivalente (al piu' riassociazione FP).
# =========================================================================
S = {}

# --- p24: pressione registri + 24 load per thread -------------------------
S["p24"] = {
 "default": ("", 64, """
  float4 v[24];
  for (int i = 0; i < 24; ++i) v[i] = In[(t*24+i) & 65535] * (i+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),
 # load raggruppate esplicitamente: srotolo SOLO il ciclo di load
 "batch_loads": ("", 64, """
  float4 v[24];
  [unroll] for (int i = 0; i < 24; ++i) v[i] = In[(t*24+i) & 65535] * (i+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),
 # array di appoggio: load grezze, scala applicata dopo -> live range piu' corto
 "load_then_scale": ("", 64, """
  float4 v[24];
  for (int i = 0; i < 24; ++i) v[i] = In[(t*24+i) & 65535];
  for (int i2 = 0; i2 < 24; ++i2) v[i2] = v[i2] * (i2+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),
 # riduzione finale spezzata in due catene indipendenti (riassociazione)
 "split_reduce": ("", 64, """
  float4 v[24];
  for (int i = 0; i < 24; ++i) v[i] = In[(t*24+i) & 65535] * (i+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  float4 s0 = 0, s1 = 0;
  for (int j = 0; j < 12; ++j) s0 += v[j]*v[(j*5)%24];
  for (int j2 = 12; j2 < 24; ++j2) s1 += v[j2]*v[(j2*5)%24];
  s = s0 + s1;"""),
 # ByteAddressBuffer: indirizzamento raw invece che structured
 "raw_buffer": (SRV_RAW, 64, """
  float4 v[24];
  for (int i = 0; i < 24; ++i) v[i] = In.Load<float4>((((t*24+i) & 65535) << 4)) * (i+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),
 # staging LDS: il gruppo carica il proprio blocco in modo coalescente
 "lds_stage": ("groupshared float4 sh[1536];", 64, """
  uint base = gid.x * 1536u;
  for (uint q = gtid.x; q < 1536u; q += 64u) sh[q] = In[(base + q) & 65535];
  GroupMemoryBarrierWithGroupSync();
  float4 v[24];
  for (int i = 0; i < 24; ++i) v[i] = sh[gtid.x*24u + i] * (i+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),
 "tg128": ("", 128, """
  float4 v[24];
  for (int i = 0; i < 24; ++i) v[i] = In[(t*24+i) & 65535] * (i+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),
 "tg32": ("", 32, """
  float4 v[24];
  for (int i = 0; i < 24; ++i) v[i] = In[(t*24+i) & 65535] * (i+1);
  for (int k = 0; k < 24; ++k) v[k] = sin(v[k]) + v[(k*7)%24]*cos(v[(k*13)%24]);
  for (int j = 0; j < 24; ++j) s += v[j]*v[(j*5)%24];"""),
}

# --- dot: riduzione memory-bound, 32 load per thread ----------------------
_DOT = "for (int i = 0; i < 32; ++i) { float4 a = %s; acc += a * a; }"
S["dot"] = {
 "default": ("", 64, """
  float4 acc = 0;
  """ + (_DOT % "In[(t*32+i) & 65535]") + """
  s = acc;"""),
 "unroll": ("", 64, """
  float4 acc = 0;
  [unroll] """ + (_DOT % "In[(t*32+i) & 65535]") + """
  s = acc;"""),
 "acc4": ("", 64, """
  float4 a0 = 0, a1 = 0, a2 = 0, a3 = 0;
  for (int i = 0; i < 32; i += 4) {
    float4 b0 = In[(t*32+i) & 65535], b1 = In[(t*32+i+1) & 65535];
    float4 b2 = In[(t*32+i+2) & 65535], b3 = In[(t*32+i+3) & 65535];
    a0 += b0*b0; a1 += b1*b1; a2 += b2*b2; a3 += b3*b3; }
  s = (a0 + a1) + (a2 + a3);"""),
 "acc4_unroll": ("", 64, """
  float4 a0 = 0, a1 = 0, a2 = 0, a3 = 0;
  [unroll] for (int i = 0; i < 32; i += 4) {
    float4 b0 = In[(t*32+i) & 65535], b1 = In[(t*32+i+1) & 65535];
    float4 b2 = In[(t*32+i+2) & 65535], b3 = In[(t*32+i+3) & 65535];
    a0 += b0*b0; a1 += b1*b1; a2 += b2*b2; a3 += b3*b3; }
  s = (a0 + a1) + (a2 + a3);"""),
 # carico tutto prima, poi riduco: separa la fase di memoria da quella di calcolo
 "load_first": ("", 64, """
  float4 p[32];
  [unroll] for (int i = 0; i < 32; ++i) p[i] = In[(t*32+i) & 65535];
  float4 acc = 0;
  for (int j = 0; j < 32; ++j) acc += p[j]*p[j];
  s = acc;"""),
 # staging LDS coalescente: 64 thread x 32 float4 = blocco contiguo e allineato
 "lds_stage": ("groupshared float4 sh[2048];", 64, """
  uint base = gid.x * 2048u;
  for (uint q = gtid.x; q < 2048u; q += 64u) sh[q] = In[(base + q) & 65535];
  GroupMemoryBarrierWithGroupSync();
  float4 acc = 0;
  for (int i = 0; i < 32; ++i) { float4 a = sh[gtid.x*32u + i]; acc += a * a; }
  s = acc;"""),
 "raw_buffer": (SRV_RAW, 64, """
  float4 acc = 0;
  """ + (_DOT % "In.Load<float4>((((t*32+i) & 65535) << 4))") + """
  s = acc;"""),
}

# --- ldsred: riduzione sequenziale in LDS ---------------------------------
_LDSPRE = """
  float4 a = In[t & 65535];
  for (int i = 0; i < 8; ++i) a += In[(t*8+i) & 65535] * (i+1);"""
S["ldsred"] = {
 "default": ("groupshared float4 g[64];", 64, _LDSPRE + """
  g[gtid.x] = a;
  GroupMemoryBarrierWithGroupSync();
  for (int q = 0; q < 64; ++q) s += g[q] * 0.015625;"""),
 # tree reduction: log2(64) passi invece di 64 letture per lane
 "tree": ("groupshared float4 g[64];", 64, _LDSPRE + """
  g[gtid.x] = a * 0.015625;
  GroupMemoryBarrierWithGroupSync();
  [unroll] for (uint st = 32u; st > 0u; st >>= 1) {
    if (gtid.x < st) g[gtid.x] += g[gtid.x + st];
    GroupMemoryBarrierWithGroupSync(); }
  s = g[0];"""),
 # riduzione a livello di wave, poi combinazione fra wave via LDS
 "wave": ("groupshared float4 g[8];", 64, _LDSPRE + """
  float4 w = WaveActiveSum(a * 0.015625);
  uint lanes = WaveGetLaneCount(), wi = gtid.x / lanes;
  if (WaveGetLaneIndex() == 0) g[wi] = w;
  GroupMemoryBarrierWithGroupSync();
  uint nw = 64u / lanes;
  for (uint q = 0; q < nw; ++q) s += g[q];"""),
 "acc4": ("groupshared float4 g[64];", 64, _LDSPRE + """
  g[gtid.x] = a;
  GroupMemoryBarrierWithGroupSync();
  float4 s0=0, s1=0, s2=0, s3=0;
  for (int q = 0; q < 64; q += 4) { s0 += g[q]*0.015625; s1 += g[q+1]*0.015625;
    s2 += g[q+2]*0.015625; s3 += g[q+3]*0.015625; }
  s = ((s0+s1)+(s2+s3));"""),
}

# --- bdiv: branch divergente, lo shader piu' lento del corpus -------------
S["bdiv"] = {
 "default": ("", 64, """
  for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535];
    if ((t + i) & 1) s += a * a; else s += sin(a) * cos(a); }"""),
 # branchless: stessa semantica, il ramo diventa una select
 "select": ("", 64, """
  for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535];
    s += ((t + i) & 1) ? (a * a) : (sin(a) * cos(a)); }"""),
 # la parita' dipende solo da t: la sollevo fuori dal ciclo (ordine di somma identico)
 "hoist_parity": ("", 64, """
  if ((t & 1) != 0) {
    for (int i = 0; i < 32; i += 2) {
      float4 a0 = In[(t*32+i) & 65535], a1 = In[(t*32+i+1) & 65535];
      s += a0 * a0; s += sin(a1) * cos(a1); }
  } else {
    for (int i = 0; i < 32; i += 2) {
      float4 a0 = In[(t*32+i) & 65535], a1 = In[(t*32+i+1) & 65535];
      s += sin(a0) * cos(a0); s += a1 * a1; }
  }"""),
 "hoist_parity_batch": ("", 64, """
  float4 p[32];
  [unroll] for (int i = 0; i < 32; ++i) p[i] = In[(t*32+i) & 65535];
  if ((t & 1) != 0) {
    for (int j = 0; j < 32; j += 2) { s += p[j]*p[j]; s += sin(p[j+1])*cos(p[j+1]); }
  } else {
    for (int j2 = 0; j2 < 32; j2 += 2) { s += sin(p[j2])*cos(p[j2]); s += p[j2+1]*p[j2+1]; }
  }"""),
 "unroll": ("", 64, """
  [unroll] for (int i = 0; i < 32; ++i) { float4 a = In[(t*32+i) & 65535];
    if ((t + i) & 1) s += a * a; else s += sin(a) * cos(a); }"""),
}

# --- mix: memoria + trascendenti -----------------------------------------
S["mix"] = {
 "default": ("", 64, """
  for (int i = 0; i < 24; ++i) { float4 a = In[(t*24+i) & 65535];
    s += sin(a) * cos(a * 1.25) + a * 0.5; }"""),
 "unroll": ("", 64, """
  [unroll] for (int i = 0; i < 24; ++i) { float4 a = In[(t*24+i) & 65535];
    s += sin(a) * cos(a * 1.25) + a * 0.5; }"""),
 # separo la fase di load da quella di calcolo, ordine di somma invariato
 "load_first": ("", 64, """
  float4 p[24];
  [unroll] for (int i = 0; i < 24; ++i) p[i] = In[(t*24+i) & 65535];
  for (int j = 0; j < 24; ++j) { float4 a = p[j]; s += sin(a) * cos(a * 1.25) + a * 0.5; }"""),
 "load_first_acc2": ("", 64, """
  float4 p[24];
  [unroll] for (int i = 0; i < 24; ++i) p[i] = In[(t*24+i) & 65535];
  float4 s0 = 0, s1 = 0;
  for (int j = 0; j < 24; j += 2) {
    float4 a = p[j], b = p[j+1];
    s0 += sin(a) * cos(a * 1.25) + a * 0.5;
    s1 += sin(b) * cos(b * 1.25) + b * 0.5; }
  s = s0 + s1;"""),
 "lds_stage": ("groupshared float4 sh[1536];", 64, """
  uint base = gid.x * 1536u;
  for (uint q = gtid.x; q < 1536u; q += 64u) sh[q] = In[(base + q) & 65535];
  GroupMemoryBarrierWithGroupSync();
  for (int i = 0; i < 24; ++i) { float4 a = sh[gtid.x*24u + i];
    s += sin(a) * cos(a * 1.25) + a * 0.5; }"""),
}

# --- trig: catena ALU seriale, nessuna memoria (controllo) ----------------
S["trig"] = {
 "default": ("", 64, """
  float4 a = float4(t & 511, (t >> 2) & 511, (t >> 4) & 511, 1) * 0.001953125;
  for (int i = 0; i < 32; ++i) a = sin(a) + cos(a * 1.5) * 0.5;
  s = a;"""),
 "unroll": ("", 64, """
  float4 a = float4(t & 511, (t >> 2) & 511, (t >> 4) & 511, 1) * 0.001953125;
  [unroll] for (int i = 0; i < 32; ++i) a = sin(a) + cos(a * 1.5) * 0.5;
  s = a;"""),
 "unroll4": ("", 64, """
  float4 a = float4(t & 511, (t >> 2) & 511, (t >> 4) & 511, 1) * 0.001953125;
  [unroll(4)] for (int i = 0; i < 32; ++i) a = sin(a) + cos(a * 1.5) * 0.5;
  s = a;"""),
}


# =========================================================================
def norm_hlsl(src):
    """Hash del sorgente normalizzato: whitespace e commenti non contano."""
    x = re.sub(r"//.*", "", src)
    x = re.sub(r"\s+", " ", x).strip()
    return hashlib.sha256(x.encode()).hexdigest()[:16]


def sh(cmd, cwd=None, timeout=900):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def isa_of(hlsl):
    d = tempfile.mkdtemp(prefix="ai_")
    rc, log = sh([RGA, "-s", "dx12", "-c", "gfx1030", "--cs", os.path.abspath(hlsl),
                  "--cs-entry", "main", "--cs-model", "cs_6_6", "--rs-macro", "RS",
                  "--isa", os.path.join(d, "isa.txt"), "-a", os.path.join(d, "st.txt")], cwd=d)
    r = {}
    fi = [x for x in os.listdir(d) if "isa" in x and x.endswith(".txt")]
    fs = [x for x in os.listdir(d) if x.startswith("gfx") and "st" in x and x.endswith(".txt")]
    if fi:
        t = open(os.path.join(d, fi[0]), encoding="utf-8", errors="replace").read()
        b = t[t.find("Disassembly"):]
        ops = re.findall(r"^\s{2,}([a-z][a-z0-9_]+)", b, re.M)
        cat = lambda *p: sum(1 for o in ops if o.startswith(p))
        loads = [i for i, o in enumerate(ops) if o.startswith(("buffer_load", "global_load"))]
        waits = [i for i, o in enumerate(ops) if o == "s_waitcnt"]
        dist = [min((w for w in waits if w > i), default=i) - i for i in loads]
        r = dict(inst=len(ops) - cat("s_code_end"), valu=cat("v_"),
                 salu=sum(1 for o in ops if o.startswith("s_") and not o.startswith(
                     ("s_waitcnt", "s_clause", "s_branch", "s_cbranch", "s_code_end"))),
                 vmem=cat("buffer_", "global_", "image_", "tbuffer_"), lds=cat("ds_"),
                 waitcnt=len(waits), clause=cat("s_clause"), branch=cat("s_cbranch", "s_branch"),
                 trans=cat("v_sin", "v_cos", "v_exp", "v_log", "v_rcp", "v_rsq", "v_sqrt"),
                 load_use_med=(sorted(dist)[len(dist) // 2] if dist else 0),
                 isa_sha=hashlib.sha256(re.sub(r"//.*", "", b).encode()).hexdigest()[:16])
    if fs:
        st = open(os.path.join(d, fs[0]), encoding="utf-8", errors="replace").read()
        g = lambda p: (re.search(p, st).group(1) if re.search(p, st) else "")
        r["vgpr"] = g(r"numUsedVgprs\s*=\s*(\d+)")
        r["sgpr"] = g(r"numUsedSgprs\s*=\s*(\d+)")
        r["lds_bytes"] = g(r"ldsUsageSizeInBytes\s*=\s*(\d+)")
        r["scratch"] = g(r"scratchMemUsageInBytes\s*=\s*(\d+)")
    shutil.rmtree(d, ignore_errors=True)
    return r


def stage_compile():
    hd, cd = os.path.join(OUT, "hlsl"), os.path.join(OUT, "cso")
    for p in (OUT, hd, cd, TMP):
        os.makedirs(p, exist_ok=True)
    meta, dedup = {}, []
    seen_src, seen_dxil, seen_isa = {}, {}, {}
    for sn, variants in S.items():
        for vn, (decls, tg, body) in variants.items():
            name = f"{sn}__{vn}"
            src = WRAP % dict(DECLS=(decls if decls.startswith(("Structured", "ByteAddress"))
                                     else SRV_STRUCT + ("\n" + decls if decls else "")),
                              TG=tg, BODY=body)
            hsha = norm_hlsl(src)
            rec = dict(name=name, shader=sn, variant=vn, tg=tg, hlsl_sha=hsha)
            if hsha in seen_src:
                rec.update(status="dup_hlsl", dup_of=seen_src[hsha]); dedup.append(rec)
                meta[name] = rec; continue
            seen_src[hsha] = name
            hp = os.path.join(hd, name + ".hlsl"); open(hp, "w").write(src)
            cp = os.path.join(cd, name + ".cso")
            rc, log = sh([DXC, "-T", "cs_6_6", "-E", "main", "-Fo", cp, hp])
            if not os.path.exists(cp):
                rec.update(status="dxc_fail", log=log[-300:]); meta[name] = rec
                print(f"  KO {name}: DXC\n{log[-300:]}"); continue
            dsha = hashlib.sha256(open(cp, "rb").read()).hexdigest()[:16]
            rec["dxil_sha"] = dsha
            if dsha in seen_dxil:
                rec.update(status="dup_dxil", dup_of=seen_dxil[dsha]); dedup.append(rec)
                meta[name] = rec; print(f"  = {name}: DXIL identico a {seen_dxil[dsha]}"); continue
            seen_dxil[dsha] = name
            im = isa_of(hp)
            if not im:
                rec.update(status="rga_fail"); meta[name] = rec; print(f"  KO {name}: RGA"); continue
            rec.update(im)
            if im["isa_sha"] in seen_isa:
                rec.update(status="dup_isa", dup_of=seen_isa[im["isa_sha"]]); dedup.append(rec)
                meta[name] = rec; print(f"  = {name}: ISA identica a {seen_isa[im['isa_sha']]}")
                continue
            seen_isa[im["isa_sha"]] = name
            rec["status"] = "ok"
            meta[name] = rec
            print(f"  ok {name:26s} vgpr={im.get('vgpr',''):>4} inst={im.get('inst',0):>5} "
                  f"vmem={im.get('vmem',0):>3} wait={im.get('waitcnt',0):>3} "
                  f"clau={im.get('clause',0):>3} br={im.get('branch',0):>3} "
                  f"lds={im.get('lds_bytes','0'):>6} scr={im.get('scratch','0'):>4} "
                  f"d_lu={im.get('load_use_med',0):>3}")
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=1)
    with open(os.path.join(OUT, "isa_dedup.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["name", "shader", "variant", "status", "dup_of",
                                       "hlsl_sha", "dxil_sha", "isa_sha"])
        for r in meta.values():
            w.writerow([r["name"], r["shader"], r["variant"], r.get("status", ""),
                        r.get("dup_of", ""), r.get("hlsl_sha", ""), r.get("dxil_sha", ""),
                        r.get("isa_sha", "")])
    n = sum(1 for r in meta.values() if r.get("status") == "ok")
    print(f"\n{n} varianti uniche da misurare, {len(dedup)} deduplicate, "
          f"{len(meta)-n-len(dedup)} fallite")


def bench(specs, dataset, threads, dumpdir, tag):
    """specs = [(nome, cso_path, tg)]. Restituisce {nome: ns_median}."""
    out_csv = os.path.join(TMP, tag + ".csv")
    args = [BENCH, out_csv, str(REPS), str(DPM), str(dataset), dumpdir]
    args += [f"{n}:{os.path.relpath(p, BENCH_DIR)}:{threads}:1:{tg}" for n, p, tg in specs]
    rc, log = sh(args, cwd=BENCH_DIR, timeout=3600)
    r = {}
    if os.path.exists(out_csv):
        for row in csv.DictReader(open(out_csv)):
            r[row["variant"]] = float(row["ns_median"])
        os.remove(out_csv)
    if not r:
        print(log[-500:])
    return r


def err_metrics(ref, var):
    a = np.fromfile(ref, dtype=np.float32); b = np.fromfile(var, dtype=np.float32)
    if a.shape != b.shape:
        return dict(bad=True, lvl="size_mismatch", max_rel=float("inf"), rms_rel=float("inf"), div=-1)
    div = int(np.count_nonzero(np.isnan(a) != np.isnan(b))) + \
          int(np.count_nonzero(np.isinf(a) != np.isinf(b)))
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return dict(bad=div > 0, lvl="degenere", max_rel=0.0, rms_rel=0.0, div=div)
    x = a[m].astype(np.float64); y = b[m].astype(np.float64)
    d = np.abs(x - y); den = np.maximum(np.abs(x), np.abs(y)); sig = den > 1e-30
    mr = float(np.max(d[sig] / den[sig])) if sig.any() else 0.0
    rms = float(np.sqrt(np.mean(d * d))); rx = float(np.sqrt(np.mean(x * x)))
    rr = rms / rx if rx else 0.0
    if div:
        lvl, bad = "nan_inf_div", True
    elif mr <= TOL_STRICT:
        lvl, bad = "strict", False
    elif rr <= TOL_RMS:
        lvl, bad = "riassociazione", False
    else:
        lvl, bad = "fuori_tolleranza", True
    return dict(bad=bad, lvl=lvl, max_rel=mr, rms_rel=rr, div=div)


def live(meta):
    cd = os.path.join(OUT, "cso")
    return {sn: [(n, os.path.join(cd, n + ".cso"), r["tg"])
                 for n, r in meta.items() if r["shader"] == sn and r.get("status") == "ok"]
            for sn in S}


def stage_correct():
    meta = json.load(open(os.path.join(OUT, "meta.json")))
    L = live(meta)
    rows = []
    for sn, specs in L.items():
        ref_name = f"{sn}__default"
        for ds in CORRECT_DS:
            d = os.path.join(TMP, f"c_{sn}_{ds}")
            shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
            bench(specs, ds, 262144, d, f"c{sn}{ds}")
            ref = os.path.join(d, f"out_{ref_name}.bin")
            for n, p, tg in specs:
                if n == ref_name:
                    continue
                vb = os.path.join(d, f"out_{n}.bin")
                if not (os.path.exists(ref) and os.path.exists(vb)):
                    rows.append(dict(name=n, shader=sn, dataset=ds, lvl="dump_mancante", bad=1))
                    continue
                e = err_metrics(ref, vb)
                rows.append(dict(name=n, shader=sn, dataset=ds, lvl=e["lvl"],
                                 max_rel=f"{e['max_rel']:.3e}", rms_rel=f"{e['rms_rel']:.3e}",
                                 div=e["div"], bad=int(e["bad"])))
            shutil.rmtree(d, ignore_errors=True)
        print(f"  correttezza {sn}: {len(CORRECT_DS)} dataset")
    # una variante e' valida solo se supera TUTTI i dataset
    verdict = {}
    for r in rows:
        v = verdict.setdefault(r["name"], dict(name=r["name"], shader=r["shader"],
                                               bad=0, lvls=set()))
        v["bad"] += r["bad"]; v["lvls"].add(r["lvl"])
    with open(os.path.join(OUT, "rejected_correctness.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "shader", "dataset", "lvl", "max_rel",
                                          "rms_rel", "div", "bad"])
        w.writeheader()
        for r in rows:
            if r["bad"]:
                w.writerow({k: r.get(k, "") for k in w.fieldnames})
    ok = {n: ("strict" if v["lvls"] == {"strict"} else "riassociazione")
          for n, v in verdict.items() if v["bad"] == 0}
    json.dump(ok, open(os.path.join(OUT, "correct.json"), "w"), indent=1)
    print(f"\ncorrette su tutti i {len(CORRECT_DS)} dataset: {len(ok)} / {len(verdict)}")
    for n, v in sorted(verdict.items()):
        if v["bad"]:
            print(f"  SCARTATA {n}: {sorted(v['lvls'])}")


def paired(meta, ok, threads, dataset, runs, tag, seed0=0):
    """Confronto appaiato con doppio riferimento e ordine mescolato.
    Restituisce {name: [d_i%]} e {name: [ns_i]}."""
    L = live(meta)
    diffs, abso = {}, {}
    for sn, specs in L.items():
        ref_name = f"{sn}__default"
        ref = next((x for x in specs if x[0] == ref_name), None)
        cand = [x for x in specs if x[0] != ref_name and (x[0] in ok)]
        if not ref or not cand:
            continue
        for r in range(runs):
            rnd = random.Random(seed0 * 1000 + r)
            order = cand[:]; rnd.shuffle(order)
            lst = [("REF_A", ref[1], ref[2])] + order + [("REF_B", ref[1], ref[2])]
            m = bench(lst, dataset, threads, "-", f"{tag}{sn}{r}")
            if "REF_A" not in m or "REF_B" not in m:
                continue
            base = 0.5 * (m["REF_A"] + m["REF_B"])
            abso.setdefault(ref_name, []).append(base)
            for n, _, _ in order:
                if n in m:
                    diffs.setdefault(n, []).append(100.0 * (m[n] - base) / base)
                    abso.setdefault(n, []).append(m[n])
        print(f"  {tag} {sn}: {runs} processi")
    return diffs, abso


def summarize(diffs):
    out = {}
    for n, v in diffs.items():
        if len(v) < 2:
            continue
        m, sd = statistics.mean(v), statistics.stdev(v)
        se = sd / len(v) ** 0.5
        out[n] = dict(n=len(v), mean=m, sd=sd, se=se, hi=m + ACCEPT_SIGMA * se,
                      worst=max(v), best=min(v))
    return out


def stage_screen(runs):
    meta = json.load(open(os.path.join(OUT, "meta.json")))
    ok = json.load(open(os.path.join(OUT, "correct.json")))
    diffs, abso = paired(meta, ok, SCREEN_TH, SCREEN_DS, runs, "scr")
    st = summarize(diffs)
    json.dump(dict(diffs=diffs, abso=abso), open(os.path.join(OUT, "screen_raw.json"), "w"))
    rows = []
    for n, v in sorted(st.items(), key=lambda x: x[1]["mean"]):
        rows.append(dict(name=n, shader=n.split("__")[0], variant=n.split("__")[1],
                         corr=ok.get(n, ""), runs=v["n"], mean_pct=round(v["mean"], 3),
                         sd_pct=round(v["sd"], 3), se_pct=round(v["se"], 3),
                         mean_plus_2se=round(v["hi"], 3),
                         candidate="SI" if v["mean"] < CAND_PCT else "no",
                         ns_median=round(statistics.median(abso[n]), 1)))
    with open(os.path.join(OUT, "search_history.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"\n{'variante':28s} {'corr':15s} {'media%':>8} {'SE%':>6} {'+2SE':>8} {'ns':>9} cand")
    for r in rows:
        print(f"{r['name']:28s} {r['corr']:15s} {r['mean_pct']:+8.3f} {r['se_pct']:6.3f} "
              f"{r['mean_plus_2se']:+8.3f} {r['ns_median']:9.0f} {r['candidate']}")
    cands = [r["name"] for r in rows if r["candidate"] == "SI"]
    json.dump(cands, open(os.path.join(OUT, "candidates.json"), "w"), indent=1)
    print(f"\ncandidati (media < {CAND_PCT}%): {len(cands)}")


def stage_confirm(runs):
    meta = json.load(open(os.path.join(OUT, "meta.json")))
    ok = json.load(open(os.path.join(OUT, "correct.json")))
    cands = json.load(open(os.path.join(OUT, "candidates.json")))
    if not cands:
        print("nessun candidato da confermare"); return
    okc = {n: ok[n] for n in cands if n in ok}
    allrows = []
    per = {}
    for i, (th, ds) in enumerate(CONFIRM):
        diffs, abso = paired(meta, okc, th, ds, runs, f"cf{i}_", seed0=i + 1)
        st = summarize(diffs)
        for n, v in st.items():
            per.setdefault(n, []).append((th, ds, v))
            allrows.append(dict(name=n, threads=th, dataset=ds, runs=v["n"],
                                mean_pct=round(v["mean"], 3), se_pct=round(v["se"], 3),
                                mean_plus_2se=round(v["hi"], 3),
                                best=round(v["best"], 3), worst=round(v["worst"], 3),
                                ns_median=round(statistics.median(abso[n]), 1)))
    with open(os.path.join(OUT, "confirm_detail.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(allrows[0].keys())); w.writeheader(); w.writerows(allrows)

    acc = []
    for n, lst in per.items():
        means = [v["mean"] for _, _, v in lst]
        his = [v["hi"] for _, _, v in lst]
        n_neg = sum(1 for m in means if m < 0)
        passed = (all(m < ACCEPT_PCT for m in means) and all(h < 0 for h in his)
                  and n_neg == len(lst))
        acc.append(dict(name=n, shader=n.split("__")[0], variant=n.split("__")[1],
                        corr=okc.get(n, ""), combos=len(lst), combos_neg=n_neg,
                        mean_worst=round(max(means), 3), mean_best=round(min(means), 3),
                        max_mean_plus_2se=round(max(his), 3),
                        accepted="SI" if passed else "no"))
    acc.sort(key=lambda r: r["mean_worst"])
    with open(os.path.join(OUT, "accepted_variants.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(acc[0].keys())); w.writeheader(); w.writerows(acc)
    print(f"\n{'variante':28s} {'corr':15s} {'peggiore%':>10} {'migliore%':>10} "
          f"{'max+2SE':>9} {'combo<0':>8} acc")
    for r in acc:
        print(f"{r['name']:28s} {r['corr']:15s} {r['mean_worst']:+10.3f} {r['mean_best']:+10.3f} "
              f"{r['max_mean_plus_2se']:+9.3f} {r['combos_neg']}/{r['combos']:<6} {r['accepted']}")
    n = sum(1 for r in acc if r["accepted"] == "SI")
    print(f"\nACCETTATE (media < {ACCEPT_PCT}% su tutte le combo, +2SE < 0): {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["compile", "correct", "screen", "confirm"])
    ap.add_argument("--runs", type=int, default=5)
    a = ap.parse_args()
    os.makedirs(TMP, exist_ok=True)
    if a.stage == "compile":
        stage_compile()
    elif a.stage == "correct":
        stage_correct()
    elif a.stage == "screen":
        stage_screen(a.runs)
    else:
        stage_confirm(a.runs)


if __name__ == "__main__":
    main()
