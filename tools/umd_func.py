"""Trova la funzione che contiene un RVA usando la .pdata (exception directory) x64,
e la disassembla. Serve a capire com'e' raggiunto il sito di lettura di AMD_SC_CFG_FILE.
Read-only su una copia del binario.
"""
import struct, sys
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM
from capstone.x86 import X86_REG_RIP

PATH = sys.argv[1]
md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
pe = pefile.PE(PATH)
IB = pe.OPTIONAL_HEADER.ImageBase
data = pe.__data__
secs = [(s.Name.rstrip(b"\0").decode(), s.VirtualAddress, s.Misc_VirtualSize,
         s.PointerToRawData, s.SizeOfRawData) for s in pe.sections]


def rva2off(r):
    for n, va, vs, po, rs in secs:
        if va <= r < va + max(vs, rs):
            return po + (r - va)


# --- .pdata: array di RUNTIME_FUNCTION {BeginAddress, EndAddress, UnwindInfo} ---
pd = next(s for s in secs if s[0] == ".pdata")
raw = data[pd[3]:pd[3] + pd[4]]
funcs = []
for i in range(0, len(raw) - 11, 12):
    b, e, u = struct.unpack_from("<III", raw, i)
    if b == 0 and e == 0:
        break
    funcs.append((b, e))
funcs.sort()


def func_of(rva):
    lo, hi = 0, len(funcs) - 1
    while lo <= hi:
        m = (lo + hi) // 2
        b, e = funcs[m]
        if rva < b:
            hi = m - 1
        elif rva >= e:
            lo = m + 1
        else:
            return b, e
    return None


def disasm_range(b, e, limit=400):
    off = rva2off(b)
    out = []
    for ins in md.disasm(data[off:off + min(e - b, limit * 15)], IB + b):
        if ins.address - IB >= e:
            break
        line = f"{ins.address - IB:#010x}  {ins.mnemonic:<9} {ins.op_str}"
        for op in ins.operands:
            if op.type == CS_OP_MEM and op.mem.base == X86_REG_RIP:
                t = ins.address + ins.size + op.mem.disp - IB
                o = rva2off(t)
                if o:
                    s = data[o:o + 48].split(b"\0")[0]
                    if 2 < len(s) < 48 and all(32 <= c < 127 for c in s):
                        line += f'   ; "{s.decode()}"'
        out.append(line)
        if len(out) >= limit:
            break
    return out


def callers_of(target_rva, cap=20):
    """Trova CALL rel32 verso target_rva scandendo le sezioni eseguibili."""
    hits = []
    for n, va, vs, po, rs in secs:
        if n not in (".text",):
            continue
        blob = data[po:po + rs]
        for i in range(len(blob) - 5):
            if blob[i] != 0xE8:
                continue
            disp = struct.unpack_from("<i", blob, i + 1)[0]
            if va + i + 5 + disp == target_rva:
                hits.append(va + i)
                if len(hits) >= cap:
                    return hits
    return hits


if __name__ == "__main__":
    for a in sys.argv[2:]:
        rva = int(a, 16)
        f = func_of(rva)
        print(f"\n{'='*70}\nRVA {rva:#x} -> funzione {f[0]:#x}-{f[1]:#x} ({f[1]-f[0]} byte)" if f
              else f"\nRVA {rva:#x} -> nessuna RUNTIME_FUNCTION")
        if not f:
            continue
        print(f"{'='*70}")
        for l in disasm_range(f[0], f[1]):
            print(l)
        print(f"\n--- chiamanti di {f[0]:#x} ---")
        for c in callers_of(f[0]):
            cf = func_of(c)
            print(f"   call da {c:#x}" + (f"  (dentro funzione {cf[0]:#x})" if cf else ""))
