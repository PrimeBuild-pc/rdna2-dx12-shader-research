"""Phase 1B - map the extracted AMD driver package. Read-only: nothing is written into the package."""
import os, sys, json, hashlib, re, io
import pandas as pd
import pefile

PKG = "whql-amd-software-adrenalin-edition-26.9.1-win11-a"
OUT = "research/01_driver_map"
os.makedirs(OUT, exist_ok=True)

# ---------- 1. walk + hash ----------
def sha256(p, buf=1 << 22):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(buf)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


MACHINE = {0x8664: "x64", 0x14c: "x86", 0xaa64: "arm64", 0x1c0: "arm", 0x1c4: "armnt"}
SUBSYS = {1: "native", 2: "gui", 3: "console"}


def pe_info(path):
    """PE metadata via pefile. Returns {} for non-PE."""
    try:
        pe = pefile.PE(path, fast_load=True)
    except Exception:
        return {}
    d = {}
    try:
        d["pe_machine"] = MACHINE.get(pe.FILE_HEADER.Machine, hex(pe.FILE_HEADER.Machine))
        d["pe_timestamp"] = int(pe.FILE_HEADER.TimeDateStamp)
        d["pe_subsystem"] = SUBSYS.get(pe.OPTIONAL_HEADER.Subsystem, pe.OPTIONAL_HEADER.Subsystem)
        d["pe_dll"] = bool(pe.FILE_HEADER.Characteristics & 0x2000)
        dc = pe.OPTIONAL_HEADER.DllCharacteristics
        d["pe_aslr"] = bool(dc & 0x40)
        d["pe_nx"] = bool(dc & 0x100)
        d["pe_cfg"] = bool(dc & 0x4000)
        d["pe_size_of_image"] = pe.OPTIONAL_HEADER.SizeOfImage
        pe.parse_data_directories(directories=[
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"],
            pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"],
        ])
        imps = []
        for e in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) or []:
            imps.append(e.dll.decode("ascii", "replace").lower())
        d["imports"] = sorted(set(imps))
        d["n_imports"] = len(d["imports"])
        exps = []
        de = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
        if de:
            for s in de.symbols:
                if s.name:
                    exps.append(s.name.decode("ascii", "replace"))
        d["exports"] = exps
        d["n_exports"] = len(exps)
        vi = {}
        for fi in getattr(pe, "FileInfo", []) or []:
            for entry in fi:
                if entry.Key == b"StringFileInfo":
                    for st in entry.StringTable:
                        for k, v in st.entries.items():
                            vi[k.decode("ascii", "replace")] = v.decode("ascii", "replace").strip()
        d["version_info"] = vi
        d["has_manifest"] = any(
            getattr(r, "id", None) == 24 for r in
            getattr(getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None), "entries", []) or [])
    except Exception as e:
        d["pe_error"] = str(e)
    finally:
        pe.close()
    return d


rows, pedb = [], {}
for root, _, files in os.walk(PKG):
    for fn in files:
        p = os.path.join(root, fn)
        rel = os.path.relpath(p, PKG).replace("\\", "/")
        st = os.stat(p)
        with open(p, "rb") as f:
            magic = f.read(2)
        r = dict(rel_path=rel, filename=fn, ext=os.path.splitext(fn)[1].lower().lstrip("."),
                 size=st.st_size, sha256=sha256(p), is_pe=(magic == b"MZ"))
        if r["is_pe"]:
            info = pe_info(p)
            pedb[rel] = info
            vi = info.get("version_info", {})
            r.update(pe_machine=info.get("pe_machine"), pe_subsystem=info.get("pe_subsystem"),
                     pe_is_dll=info.get("pe_dll"), pe_timestamp=info.get("pe_timestamp"),
                     n_imports=info.get("n_imports"), n_exports=info.get("n_exports"),
                     imports=";".join(info.get("imports", [])),
                     file_version=vi.get("FileVersion"), product_name=vi.get("ProductName"),
                     product_version=vi.get("ProductVersion"), company=vi.get("CompanyName"),
                     file_description=vi.get("FileDescription"),
                     internal_name=vi.get("InternalName"),
                     original_filename=vi.get("OriginalFilename"),
                     has_manifest=info.get("has_manifest"))
        rows.append(r)
df = pd.DataFrame(rows)

# ---------- 2. sigcheck join ----------
sc = pd.read_csv(os.path.join(OUT, "_sigcheck.csv"))
sc["rel_path"] = sc.Path.str.replace("\\", "/", regex=False).str.lower().str.split(
    PKG.lower() + "/").str[-1]
sc = sc.rename(columns={"Verified": "sig_verified", "Publisher": "sig_publisher",
                        "Date": "sig_date", "Machine Type": "sig_machine"})
df["_k"] = df.rel_path.str.lower()
df = df.merge(sc[["rel_path", "sig_verified", "sig_publisher", "sig_date", "sig_machine"]],
              left_on="_k", right_on="rel_path", how="left", suffixes=("", "_sc")).drop(
    columns=["_k", "rel_path_sc"])

# ---------- 3. INF parsing ----------
inf_files = sorted(df[df.ext == "inf"].rel_path)
inf_db = {}
KEYRE = re.compile(r"^HKR,([^,]*),([^,]+),([^,]*),(.*)$", re.I)
for rel in inf_files:
    p = os.path.join(PKG, rel)
    try:
        txt = open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    if "\x00" in txt[:200]:
        txt = open(p, encoding="utf-16", errors="replace").read()
    sections, cur = {}, None
    for line in txt.splitlines():
        s = line.split(";")[0].strip()
        if not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]
            sections.setdefault(cur, [])
        elif cur:
            sections[cur].append(s)
    # every filename mentioned anywhere in the INF
    mentioned = set(m.group(0).lower() for m in
                    re.finditer(r"[A-Za-z0-9_\-\.]+\.(dll|sys|exe|so|cab|dat|json|bin|inf|msi|xclbin|elf)", txt))
    # HKR AddReg keys that name a binary
    keys = {}
    for sec, lines in sections.items():
        for s in lines:
            m = KEYRE.match(s)
            if m:
                sub, val, typ, data = (x.strip() for x in m.groups())
                if re.search(r"\.(dll|so|json|cab|dat|sys)\b", data, re.I):
                    keys.setdefault(val, []).append(dict(section=sec, subkey=sub, data=data))
    inf_db[rel] = dict(sections=sorted(sections), n_sections=len(sections),
                       mentioned_files=sorted(mentioned), binary_keys=keys,
                       catalog=[s.split("=")[-1].strip() for s in sections.get("Version", [])
                                if s.lower().startswith("catalogfile")],
                       provider=[s.split("=")[-1].strip() for s in sections.get("Version", [])
                                 if s.lower().startswith("provider")],
                       driverver=[s.split("=")[-1].strip() for s in sections.get("Version", [])
                                  if s.lower().startswith("driverver")],
                       classguid=[s.split("=")[-1].strip() for s in sections.get("Version", [])
                                  if s.lower().startswith("class")])

# which INF references each file (by basename)
byname = {}
for rel, d in inf_db.items():
    for f in d["mentioned_files"]:
        byname.setdefault(f, set()).add(rel)
df["referenced_by_inf"] = df.filename.str.lower().map(lambda n: ";".join(sorted(byname.get(n, []))))
df["inf_referenced"] = df.referenced_by_inf.astype(bool)

df.to_csv(os.path.join(OUT, "driver_files.csv"), index=False)
json.dump({"inf": inf_db}, open(os.path.join(OUT, "inf_map.json"), "w"), indent=1)
json.dump({k: {kk: vv for kk, vv in v.items() if kk != "exports"} | {
    "exports_sample": v.get("exports", [])[:80], "n_exports": v.get("n_exports", 0)}
    for k, v in pedb.items()}, open(os.path.join(OUT, "pe_metadata.json"), "w"), indent=1)

print("files:", len(df), "PE:", df.is_pe.sum(), "signed:", (df.sig_verified == "Signed").sum(),
      "INF:", len(inf_files))
print(df.groupby("ext").size().sort_values(ascending=False).head(12).to_string())
