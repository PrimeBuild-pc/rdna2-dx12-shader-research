"""Offline parser/repacker for the RDHS v10 layout documented in pinned WolvenKit.

Pure byte operations only. This does not install a cache or prove game acceptance.
Unknown footer fields and all metadata bytes are preserved, not interpreted as hashes.
"""
import struct

FOOTER = struct.Struct('<8I9Q2I')
FIELDS = ('shaderCount extraCount notherCount uk1 uk2 uk3 onemorePostfix struct2Count '
          'shadersSize extrasSize notherSize struct2Size onemoreSize '
          'extraOffset notherOffset onemoreOffset struct2Offset rdhs ten').split()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def index(data):
    require(len(data) >= FOOTER.size, 'Truncated footer')
    footer = dict(zip(FIELDS, FOOTER.unpack_from(data, len(data)-FOOTER.size)))
    require(footer['rdhs'] == int.from_bytes(b'RDHS','little') and footer['ten'] == 10,
            'Unsupported cache layout')
    pos = footer['shadersSize']
    for offset, size in [('extraOffset','extrasSize'), ('notherOffset','notherSize'),
                         ('onemoreOffset','onemoreSize'), ('struct2Offset','struct2Size')]:
        require(footer[offset] == pos, f'Noncontiguous section: {offset}')
        pos += footer[size]
    require(pos == len(data)-FOOTER.size, 'Section sizes do not cover cache')
    require(0 < footer['shaderCount'] <= footer['shadersSize']//20, 'Invalid shader count')
    records = []
    guids = set()
    pos = 0
    for _ in range(footer['shaderCount']):
        require(pos+20 <= footer['shadersSize'], 'Truncated shader header')
        guid, params, size = struct.unpack_from('<QQI', data, pos)
        require(size >= 32 and pos+20+size <= footer['shadersSize'], 'Invalid shader size')
        require(data[pos+20:pos+24] == b'DXBC', 'Shader is not a DXBC container')
        require(struct.unpack_from('<I', data, pos+44)[0] == size, 'Container/header size mismatch')
        require(guid not in guids, 'Duplicate shader GUID')
        guids.add(guid)
        records.append(dict(guid=guid, params_guid=params, record_offset=pos,
                            blob_offset=pos+20, bytes=size))
        pos += 20+size
    require(pos == footer['shadersSize'], 'Shader records do not cover shader section')
    return footer, records


def compilation_info(data, footer):
    """Decode the exact WolvenKit extra layout; fail if this cache differs."""
    pos = footer['extraOffset']
    end = pos+footer['extrasSize']
    result = []
    for _ in range(footer['extraCount']):
        require(pos+10 <= end, 'Truncated compilation info')
        start_tag, end_tag = struct.unpack_from('<II', data, pos)
        first, second = data[pos+8:pos+10]
        length = (first & 0xbf) | ((second & 1) << 6)
        pos += 10
        require(pos+length+48 <= end, 'Compilation string out of bounds')
        text = data[pos:pos+length].decode('utf-8', errors='strict')
        pos += length
        start2, shader_a, shader_b, material, material2, unknown, end2 = struct.unpack_from('<IQQQQQI', data, pos)
        pos += 48
        require(start_tag == start2 and end_tag == end2 and material == material2,
                'Compilation metadata sentinel mismatch')
        flags = []
        for _ in range(2):
            require(pos+4 <= end, 'Missing flag count')
            count = struct.unpack_from('<I', data, pos)[0]
            pos += 4
            require(count <= (end-pos)//8, 'Flag array out of bounds')
            flags.append(list(struct.unpack_from('<'+'Q'*count, data, pos)))
            pos += count*8
        # WolvenKit's slot names disagree with this cache's DXIL stage tokens; keep neutral names.
        result.append(dict(info=text, shader_a_guid=shader_a, shader_b_guid=shader_b,
                           material_guid=material, flags=flags))
    require(pos == end, 'Compilation records do not cover extra section')
    return result


def replace(data, guid, blob):
    footer, records = index(data)
    match = [r for r in records if r['guid'] == guid]
    require(len(match) == 1, 'Target shader GUID not unique')
    require(32 <= len(blob) <= 0xffffffff and blob[:4] == b'DXBC', 'Invalid replacement container')
    require(struct.unpack_from('<I', blob, 24)[0] == len(blob), 'Replacement size mismatch')
    record = match[0]
    delta = len(blob)-record['bytes']
    pos = record['blob_offset']
    result = bytearray(data[:pos]+blob+data[pos+record['bytes']:])
    struct.pack_into('<I', result, record['record_offset']+16, len(blob))
    for field in ('shadersSize','extraOffset','notherOffset','onemoreOffset','struct2Offset'):
        footer[field] += delta
    result[-FOOTER.size:] = FOOTER.pack(*(footer[k] for k in FIELDS))
    result = bytes(result)
    new_footer, new_records = index(result)
    require(data[pos+record['bytes']:-FOOTER.size] == result[pos+len(blob):-FOOTER.size],
            'Bytes outside shader/footer changed')
    require(len(new_records) == len(records), 'Record count changed')
    return result


def selfcheck():
    blob = b'DXBC'+bytes(20)+struct.pack('<II',32,0)
    head = struct.pack('<QQI',1,2,len(blob))+blob
    f = dict.fromkeys(FIELDS,0)
    f.update(shaderCount=1,shadersSize=len(head),rdhs=int.from_bytes(b'RDHS','little'),ten=10)
    for k in ('extraOffset','notherOffset','onemoreOffset','struct2Offset'):f[k]=len(head)
    cache = head+FOOTER.pack(*(f[k] for k in FIELDS))
    assert replace(cache,1,blob) == cache
    bigger = bytearray(blob+bytes(4));struct.pack_into('<I',bigger,24,len(bigger))
    changed = replace(cache,1,bytes(bigger))
    assert index(changed)[0]['shadersSize'] == len(head)+4
    assert compilation_info(cache,index(cache)[0]) == []
    for bad in (cache[:-1],cache[:20],cache[:-8]+b'BAD!'+cache[-4:]):
        try:index(bad)
        except ValueError:pass
        else:raise AssertionError('Malformed cache accepted')
    try:replace(cache,9,blob)
    except ValueError:pass
    else:raise AssertionError('Unknown shader GUID accepted')
    print('RDHS cache parser/repacker selfcheck PASS')


if __name__ == '__main__':
    selfcheck()
