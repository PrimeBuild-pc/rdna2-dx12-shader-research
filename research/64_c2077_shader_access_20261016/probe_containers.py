"""Read project-local copies only; inventory structurally valid DXBC shader containers."""
import collections
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent
EXPECTED = {
    'shader_final.cache': '339145371a3b5aaa08eb4ef82d558f445b632e28603ee0f3b4860270dfc3ccfa',
    'staticshader_final.cache': 'bff160947aba8df144200247adc39b44c26322360628d875f7c7218ad26c59ff',
}


def container(data, offset):
    if offset+32 > len(data) or data[offset:offset+4] != b'DXBC':
        return None
    version, size, count = struct.unpack_from('<III', data, offset+20)
    if version != 1 or not 0 < count <= 128 or size < 32+4*count or offset+size > len(data):
        return None
    chunks = []
    ranges = []
    for i in range(count):
        pos = struct.unpack_from('<I', data, offset+32+4*i)[0]
        if pos < 32+4*count or pos+8 > size:
            return None
        tag = data[offset+pos:offset+pos+4]
        length = struct.unpack_from('<I', data, offset+pos+4)[0]
        end = pos+8+length
        if end > size or any(pos < b and end > a for a,b in ranges):
            return None
        ranges.append((pos,end)); chunks.append(tag.decode('ascii',errors='replace'))
    if not any(tag in chunks for tag in ('SHDR','SHEX','DXIL')):
        return None
    return dict(offset=offset, bytes=size, chunks=chunks)


def selfcheck():
    # Minimal synthetic container tests framing, not shader validity or DXBC checksum.
    good = b'DXBC'+bytes(16)+struct.pack('<IIII',1,52,1,36)+b'SHDR'+struct.pack('<III',8,0x50,2)
    assert len(good)==52 and container(good,0)['chunks']==['SHDR']
    assert container(good[:-1],0) is None
    bad=bytearray(good);struct.pack_into('<I',bad,32,4)
    assert container(bad,0) is None
    assert container(b'prefix'+good,6)['offset']==6


if __name__ == '__main__':
    selfcheck()
    output=ROOT/'probe_results.json'
    if output.exists():
        raise FileExistsError(output)
    results=[]
    for name,expected in EXPECTED.items():
        p=ROOT/'copies'/name
        data=p.read_bytes()
        digest=hashlib.sha256(data).hexdigest()
        assert digest==expected, 'Copy differs from hashed original'
        matches=[]; raw=0; pos=0
        while True:
            pos=data.find(b'DXBC',pos)
            if pos<0:break
            raw+=1
            item=container(data,pos)
            if item:
                blob=data[pos:pos+item['bytes']]
                item['sha256']=hashlib.sha256(blob).hexdigest()
                matches.append(item)
            pos+=4
        counts=collections.Counter(tag for item in matches for tag in item['chunks'])
        results.append(dict(copy=name,bytes=len(data),sha256=digest,first_64_bytes_hex=data[:64].hex(),
                            raw_dxbc_magic_hits=raw,valid_shader_container_frames=len(matches),chunk_counts=dict(counts),containers=matches,
                            limitation='Framing only: checksum, bytecode validation, shader identity, runtime use and reinsertion not established. Zero hits does not exclude compressed shader data.'))
        print(name, 'bytes',len(data),'DXBC magic',raw,'valid frames',len(matches),'chunks',dict(counts))
    output.write_text(json.dumps(dict(selfcheck='PASS',files=results),indent=2),encoding='utf-8')
