"""Phase 1.5-B: targeted static analysis of the LIVE amdxc64.dll (read-only, on a copy).

No patching, no execution of driver code. Only PE parsing, string search, RIP-relative
xref scanning and capstone disassembly of specific functions.
"""
import os, re, sys, json, struct
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_IMM, CS_OP_REG
from capstone.x86 import X86_REG_RIP

PATH = sys.argv[1] if len(sys.argv) > 1 else "umd/amdxc64.dll"
OUT = sys.argv[2] if len(sys.argv) > 2 else "."

pe = pefile.PE(PATH)
IB = pe.OPTIONAL_HEADER.ImageBase
data = pe.__data__
secs = [(s.Name.rstrip(b"\0").decode(), s.VirtualAddress, s.Misc_VirtualSize,
         s.PointerToRawData, s.SizeOfRawData,
         bool(s.Characteristics & 0x20000000)) for s in pe.sections]


def rva2off(rva):
    for _, va, vs, po, rs, _x in secs:
        if va <= rva < va + max(vs, rs):
            return po + (rva - va)
    return None


def off2rva(off):
    for _, va, vs, po, rs, _x in secs:
        if po <= off < po + rs:
            return va + (off - po)
    return None


# ---------- 1. exports ----------
exports = []
for s in pe.DIRECTORY_ENTRY_EXPORT.symbols:
    if s.name:
        exports.append((s.name.decode("ascii", "replace"), s.address, s.ordinal))
undec = [e for e in exports if not e[0].startswith("?")]

# ---------- 2. strings of interest ----------
TARGETS = [b"DXCTuningsFileName", b"ABCDTuningsFileName", b"amdxc64z", b"amdxc32z",
           b"amdxc64d.dat", b"amdxc64b.dat", b"SettingsBlob", b"settings_blob",
           b"_SC_COMPILE_FLAGS", b"SC_COMPILE_FLAGS", b"MINIMIZE_VGPRS",
           b"_SC_CACHE_POLICY", b"CACHE_POLICY", b"Tunings", b"amdxc64z.dll",
           b"ShaderCache", b"DxcCache", b"PipelineCache", b"DXCTunings"]

hits = {}
for t in TARGETS:
    for enc, tag in ((t, "ascii"), (t.decode().encode("utf-16-le"), "utf16")):
        start = 0
        while True:
            i = data.find(enc, start)
            if i < 0:
                break
            hits.setdefault(t.decode(), []).append(dict(offset=i, rva=off2rva(i), enc=tag))
            start = i + 1
            if len(hits.get(t.decode(), [])) > 40:
                break


def cstring(off, maxlen=160):
    e = data.find(b"\0", off, off + maxlen)
    return data[off:e if e > 0 else off + maxlen].decode("ascii", "replace")


# ---------- 3. RIP-relative xrefs to a target RVA ----------
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True
text = [s for s in secs if s[5]]  # executable sections


def find_xrefs(target_rvas, window=None):
    """Scan executable sections for `lea/mov reg,[rip+disp]` landing on a target RVA."""
    want = set(target_rvas)
    found = []
    for name, va, vs, po, rs, _x in text:
        blob = data[po:po + rs]
        base = va
        # Fast pre-filter: encode the possible 4-byte displacements is not practical over
        # 60 MB, so disassemble linearly in chunks. This is slow but bounded to .text.
        off = 0
        size = len(blob)
        while off < size:
            chunk = blob[off:off + (1 << 20)]
            for ins in md.disasm(chunk, base + off):
                for op in ins.operands:
                    if op.type == CS_OP_MEM and op.mem.base == X86_REG_RIP:
                        t = ins.address + ins.size + op.mem.disp
                        if t in want:
                            found.append(dict(ins_rva=ins.address, mnemonic=ins.mnemonic,
                                              op_str=ins.op_str, target_rva=t,
                                              section=name))
            off += (1 << 20)
    return found


# ---------- 4. disassemble a function from an RVA ----------
def disasm(rva, n=90):
    off = rva2off(rva)
    if off is None:
        return []
    out = []
    for ins in md.disasm(data[off:off + n * 15], IB + rva):
        out.append(f"{ins.address - IB:#010x}  {ins.mnemonic:<9} {ins.op_str}")
        if len(out) >= n:
            break
        if ins.mnemonic in ("ret", "jmp") and len(out) > 3:
            out.append("   ; --- flow end ---")
            break
    return out


if __name__ == "__main__":
    r = dict(path=os.path.abspath(PATH), image_base=hex(IB),
             sections=[dict(name=n, rva=hex(v), vsize=vs, raw=rs, exec=x)
                       for n, v, vs, po, rs, x in secs],
             undecorated_exports=[dict(name=n, rva=hex(a), ordinal=o) for n, a, o in undec],
             n_exports=len(exports), string_hits={})
    for k, v in hits.items():
        for h in v[:8]:
            h["context"] = cstring(h["offset"] - 0 if h["enc"] == "ascii" else h["offset"])
        r["string_hits"][k] = v[:8]
    print(json.dumps(r, indent=1))
