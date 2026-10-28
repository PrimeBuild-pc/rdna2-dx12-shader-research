"""Fast RIP-relative xref finder: scan .text for any int32 displacement landing on a target RVA.

Catches every RIP-relative reference regardless of opcode, at the cost of some false
positives (a random dword that happens to encode the right displacement). Candidates are
confirmed by disassembling backwards a few bytes and checking the instruction really
references the target.
"""
import struct, sys, json
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM
from capstone.x86 import X86_REG_RIP

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True


class Img:
    def __init__(self, path):
        self.pe = pefile.PE(path)
        self.d = self.pe.__data__
        self.IB = self.pe.OPTIONAL_HEADER.ImageBase
        self.secs = [(s.Name.rstrip(b"\0").decode(), s.VirtualAddress, s.Misc_VirtualSize,
                      s.PointerToRawData, s.SizeOfRawData,
                      bool(s.Characteristics & 0x20000000)) for s in self.pe.sections]

    def off2rva(self, o):
        for n, va, vs, po, rs, x in self.secs:
            if po <= o < po + rs:
                return va + (o - po)

    def rva2off(self, r):
        for n, va, vs, po, rs, x in self.secs:
            if va <= r < va + max(vs, rs):
                return po + (r - va)

    def find_string(self, s, enc="ascii"):
        b = s.encode() if enc == "ascii" else s.encode("utf-16-le")
        out, i = [], 0
        while True:
            i = self.d.find(b, i)
            if i < 0:
                return out
            out.append(self.off2rva(i))
            i += 1

    def xrefs(self, target_rva, max_hits=40):
        """Scan executable sections for int32 displacements that resolve to target_rva."""
        hits = []
        for n, va, vs, po, rs, ex in self.secs:
            if not ex:
                continue
            blob = self.d[po:po + rs]
            for i in range(0, len(blob) - 4):
                disp = struct.unpack_from("<i", blob, i)[0]
                # instruction end is somewhere in [i+4, i+4+8] (imm bytes may follow)
                if not (0 <= target_rva - (va + i + 4) <= 8):
                    continue
                if target_rva - disp != va + i + 4 + (target_rva - (va + i + 4) - (target_rva - disp - (va + i + 4))):
                    pass
                for endslack in range(0, 9):
                    if va + i + 4 + endslack + disp == target_rva:
                        ins = self._decode_around(po, i, va)
                        if ins:
                            hits.append(ins)
                        break
                if len(hits) >= max_hits:
                    return hits
        return hits

    def _decode_around(self, po, i, va):
        for back in range(3, 12):
            start = i - back
            if start < 0:
                continue
            for ins in md.disasm(self.d[po + start:po + start + 20], va + start):
                if ins.address + ins.size <= va + i + 4:
                    break
                for op in ins.operands:
                    if op.type == CS_OP_MEM and op.mem.base == X86_REG_RIP:
                        return dict(rva=ins.address, mnemonic=ins.mnemonic, op_str=ins.op_str,
                                    target=ins.address + ins.size + op.mem.disp)
                break
        return None


def scan(path, strings):
    im = Img(path)
    out = {}
    for s in strings:
        rvas = im.find_string(s) + im.find_string(s, "utf16")
        out[s] = dict(string_rvas=[hex(r) for r in rvas if r], xrefs=[])
        for r in rvas:
            if r is None:
                continue
            for h in im.xrefs(r, 12):
                out[s]["xrefs"].append(dict(rva=hex(h["rva"]), ins=f"{h['mnemonic']} {h['op_str']}",
                                            target=hex(h["target"])))
    return out


if __name__ == "__main__":
    print(json.dumps(scan(sys.argv[1], sys.argv[2:]), indent=1))
