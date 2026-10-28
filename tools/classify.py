"""Phase 1B - classify package components from evidence (INF keys, PE exports, version info).

Every classification carries the evidence that produced it. Filenames are never
evidence on their own; `filename_only` marks the cases where nothing else was available.
"""
import json, os, re
import pandas as pd

OUT = "research/01_driver_map"
df = pd.read_csv(os.path.join(OUT, "driver_files.csv"))
pe = json.load(open(os.path.join(OUT, "pe_metadata.json")))
inf = json.load(open(os.path.join(OUT, "inf_map.json")))["inf"]

DISPLAY_INF = "Packages/Drivers/Display/WT6A_INF/u0203729.inf"

# --- evidence source 1: WDDM registry keys in the display INF -------------------
# UserModeDriverName is REG_MULTI_SZ indexed by D3D runtime version: [D3D9, D3D10, D3D11, D3D12]
UMD_INDEX = {0: "d3d9", 1: "d3d10", 2: "d3d11", 3: "d3d12"}
reg_roles = {}          # basename -> list of {key, index, role, inf}


def note(name, **kw):
    reg_roles.setdefault(name.lower(), []).append(kw)


for rel, d in inf.items():
    for key, entries in d["binary_keys"].items():
        for e in entries:
            parts = [p.strip() for p in e["data"].split(",") if p.strip()]
            for i, p in enumerate(parts):
                base = os.path.basename(p.replace("%13%\\", "").replace("\\", "/")).lower()
                if not re.search(r"\.(dll|so|json|cab|dat|sys)$", base):
                    continue
                role = None
                if key.lower() in ("usermodedrivername", "usermodedrivernamewow"):
                    role = "UMD " + UMD_INDEX.get(i, f"idx{i}")
                elif key.lower().startswith("usermodedrivernamewsl"):
                    role = "UMD d3d12 (WSL)"
                elif key.lower().startswith("opengldrivername"):
                    role = "OpenGL ICD"
                elif key.lower().startswith("vulkandrivername"):
                    role = "Vulkan ICD manifest"
                elif key.lower() == "d3dvendorname":
                    role = "D3DVendorName idx%d" % i
                elif key.lower() == "installeddisplaydrivers":
                    role = "InstalledDisplayDrivers"
                else:
                    role = key
                note(base, key=key, index=i, role=role, inf=rel, raw=e["data"][:160])

# InstalledDisplayDrivers is a bare-name list, catch it separately
for rel, d in inf.items():
    for key, entries in d["binary_keys"].items():
        if key.lower() != "installeddisplaydrivers":
            continue
        for e in entries:
            for nm in [x.strip() for x in e["data"].split(",")]:
                if nm and not nm.startswith("%"):
                    note(nm.lower() + ".dll", key=key, index=-1,
                         role="InstalledDisplayDrivers", inf=rel, raw=e["data"][:160])

# --- evidence source 2: exported entry points -----------------------------------
EXPORT_SIGNATURES = [
    (r"^OpenAdapter12$", "d3d12_umd", "esporta OpenAdapter12 (entry point WDDM per D3D12)"),
    (r"^D3D12OpenCompilerDDI$", "d3d12_compiler", "esporta D3D12OpenCompilerDDI (DDI compilatore D3D12)"),
    (r"^OpenAdapter10(_2)?$", "d3d10_11_umd", "esporta OpenAdapter10/OpenAdapter10_2"),
    (r"^AmdDxGsaCompileShader$", "shader_compiler_api", "esporta AmdDxGsaCompileShader (GSA: compilazione shader)"),
    (r"^GetSettingsBlobsAll", "driver_settings", "esporta GetSettingsBlobsAll* (blob impostazioni driver)"),
    (r"^vk_icdGetInstanceProcAddr$", "vulkan_icd", "esporta vk_icdGetInstanceProcAddr (ICD Vulkan)"),
    (r"^Drv(Present|Swap)Buffers$", "opengl_icd", "esporta DrvPresentBuffers/DrvSwapBuffers (ICD OpenGL)"),
    (r"^AmdExtD3DCreateInterface$", "amd_d3d_ext", "esporta AmdExtD3DCreateInterface (estensioni AMD per D3D)"),
    (r"^UpdateFfxApiProvider$", "ffx_provider", "esporta UpdateFfxApiProvider (provider FidelityFX API)"),
    (r"^ALVRInit$", "liquidvr", "esporta ALVRInit (LiquidVR)"),
    (r"^clGetPlatformIDs$|^clIcdGetPlatformIDsKHR$", "opencl_icd", "esporta entry point OpenCL ICD"),
]

rows = []
for _, r in df.iterrows():
    rel = r.rel_path
    base = r.filename.lower()
    ev, tags = [], set()

    for e in reg_roles.get(base, []):
        ev.append(f"INF {os.path.basename(e['inf'])}: {e['key']} -> {e['role']}")
        k = e["role"].lower()
        if "d3d12" in k:
            tags.add("d3d12_umd")
        elif "d3d11" in k or "d3d10" in k:
            tags.add("d3d10_11_umd")
        elif "d3d9" in k:
            tags.add("d3d9_umd")
        elif "opengl" in k:
            tags.add("opengl_icd")
        elif "vulkan" in k:
            tags.add("vulkan_icd")

    info = pe.get(rel, {})
    exports = info.get("exports_sample", [])
    for pat, tag, why in EXPORT_SIGNATURES:
        if any(re.match(pat, e) for e in exports):
            tags.add(tag)
            ev.append("PE: " + why)

    vi = info.get("version_info", {}) or {}
    desc = (vi.get("FileDescription") or "") + " | " + (vi.get("ProductName") or "")
    if desc.strip(" |"):
        ev.append(f"PE version-info: {desc.strip(' |')}")

    if str(r.get("ext", "")).lower() == "sys":
        tags.add("kernel_mode")
        ev.append("estensione .sys + SERVICE_ nel INF" if r.get("inf_referenced") else "estensione .sys")

    if r.get("sig_verified") == "Signed":
        ev.append(f"Authenticode: Signed by {r.get('sig_publisher')}")

    # final component label, most specific first
    if "d3d12_umd" in tags or "d3d12_compiler" in tags:
        comp = "dx12_user_mode_driver"
    elif "ffx_provider" in tags:
        comp = "dx12_fidelityfx"
    elif "d3d10_11_umd" in tags:
        comp = "dx10_11_user_mode_driver"
    elif "d3d9_umd" in tags:
        comp = "dx9_user_mode_driver"
    elif "vulkan_icd" in tags:
        comp = "vulkan_user_mode_driver"
    elif "opengl_icd" in tags:
        comp = "opengl_user_mode_driver"
    elif "opencl_icd" in tags:
        comp = "opencl_runtime"
    elif "kernel_mode" in tags:
        comp = "kernel_mode_driver"
    elif "shader_compiler_api" in tags:
        comp = "shader_compiler_helper"
    elif "amd_d3d_ext" in tags:
        comp = "d3d_extension_stub"
    elif "liquidvr" in tags:
        comp = "liquidvr"
    else:
        comp = None

    conf = "confirmed" if any(e.startswith("INF ") for e in ev) and comp else (
        "strong" if comp else "unclassified")
    if comp is None and r.is_pe:
        # fall back to declared description only, and say so
        d2 = (vi.get("FileDescription") or vi.get("ProductName") or "")
        if d2:
            comp = "declared:" + d2[:60]
            conf = "probable (solo metadata dichiarati dal file)"
    rows.append(dict(rel_path=rel, filename=r.filename, size=r["size"],
                     sha256=r.sha256, component=comp, confidence=conf,
                     tags="|".join(sorted(tags)), evidence=" ;; ".join(ev)))

cl = pd.DataFrame(rows)
cl.to_csv(os.path.join(OUT, "component_classification.csv"), index=False)

dx = cl[cl.component.astype(str).str.startswith(("dx12", "dx10", "dx9", "vulkan", "opengl",
                                                 "kernel", "shader", "d3d_ext", "opencl"))]
json.dump(dict(
    package=dict(root="whql-amd-software-adrenalin-edition-26.9.1-win11-a",
                 files=len(df), pe_files=int(df.is_pe.sum()),
                 signed=int((df.sig_verified == "Signed").sum()), infs=len(inf)),
    display_inf=dict(path=DISPLAY_INF, driverver=inf[DISPLAY_INF]["driverver"],
                     catalog=inf[DISPLAY_INF]["catalog"],
                     registry_binary_keys=inf[DISPLAY_INF]["binary_keys"]),
    classified={r.rel_path: dict(component=r.component, confidence=r.confidence,
                                 tags=r.tags, sha256=r.sha256, size=int(r.size),
                                 evidence=r.evidence.split(" ;; "))
                for r in dx.itertuples()},
), open(os.path.join(OUT, "driver_map.json"), "w"), indent=1)

print(cl.component.value_counts(dropna=False).head(20).to_string())
print("\n--- classified core components ---")
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 45)
print(dx[["filename", "size", "component", "confidence"]].sort_values(
    "size", ascending=False).head(30).to_string(index=False))
