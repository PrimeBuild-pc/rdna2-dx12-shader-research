"""C2077-DXIL-CANARY-001: offline only; never installs a cache or runs the game."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from buildv import run_checked, sha, save_json
import c2077_shader_cache as cache

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT/'research/64_c2077_shader_access_20261016'
PHASE = ROOT/'research/65_c2077_dxil_roundtrip_20261016'
SDK = Path(r'C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64')
EXPECTED = {
    'dxc.exe':'854d5f29dbbe25b584942855e65d673db3164f7f68e20fb784be9cd747d14814',
    'dxcompiler.dll':'97abd3b3083607dc29cc3f8eae56c39c349b76ee3c20deeb2f66258708e55bd8',
    'dxil.dll':'fda4dde92222ddb8564c3173ce48faa56f7e1c7b46b0b67dada1182ee07a4123',
}
CACHE_SHA = '339145371a3b5aaa08eb4ef82d558f445b632e28603ee0f3b4860270dfc3ccfa'
GLASS_SHA = 'c8755b8ac5d61f208d02e0fda1c3bbed2c7e0a15f59c9edbb0f8c559925828b9'
TARGET = 15973390170752892218


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def module_ir(text):
    lines = text.splitlines()
    starts = [i for i,line in enumerate(lines) if line.startswith('target datalayout')]
    check(len(starts)==1, 'Missing/ambiguous LLVM module')
    return lines[starts[0]:]


def magenta(text):
    for component,value in enumerate(('1.000000e+00','0.000000e+00','1.000000e+00','1.000000e+00')):
        pattern = (r'(^  call void @dx\.op\.storeOutput\.f32\(i32 5, i32 0, i32 0, i8 '
                   + str(component) + r', float )%[0-9]+(\).*$)')
        text,n = re.subn(pattern,r'\g<1>'+value+r'\g<2>',text,flags=re.MULTILINE)
        check(n==1, f'Output component {component} not unique')
    return text


def parts(blob):
    import struct
    size,count = struct.unpack_from('<II',blob,24)
    check(blob[:4]==b'DXBC' and size==len(blob) and 0<count<128,'Bad container')
    result = {}
    for i in range(count):
        offset = struct.unpack_from('<I',blob,32+4*i)[0]
        check(32+4*count<=offset and offset+8<=len(blob),'Part offset out of bounds')
        tag = blob[offset:offset+4].decode('ascii')
        length = struct.unpack_from('<I',blob,offset+4)[0]
        check(offset+8+length<=len(blob) and tag not in result,'Bad part extent')
        result[tag] = blob[offset+8:offset+8+length]
    return result


def selfcheck():
    cache.selfcheck()
    lines = '\n'.join(f'  call void @dx.op.storeOutput.f32(i32 5, i32 0, i32 0, i8 {i}, float %{10+i})  ; marker' for i in range(4))
    other = '\n  call void @dx.op.storeOutput.f32(i32 5, i32 1, i32 0, i8 0, float %99)'
    changed = magenta(lines+other)
    assert changed.endswith(other) and sum(a!=b for a,b in zip((lines+other).splitlines(),changed.splitlines()))==4
    try:magenta(lines+'\n'+lines)
    except RuntimeError:pass
    else:raise AssertionError('Ambiguous canary accepted')
    assert module_ir('header\ntarget datalayout = "x"\r\nbody\r\n')==['target datalayout = "x"','body']
    print('Shader experiment pure selfcheck PASS')


def run(out):
    out=out.resolve()
    check(out.is_relative_to(PHASE.resolve()),'Outputs must stay in this research phase')
    for name,digest in EXPECTED.items():check(sha(SDK/name)==digest,f'SDK changed: {name}')
    executable=PHASE/'dxil_roundtrip.exe'
    check(executable.exists(),'Build the offline utility first')
    check((PHASE/'PREREGISTRATION.md').exists(),'Preregistration missing')
    selfcheck()
    out.mkdir(exist_ok=False)
    command_count=0
    def positive(args,label):
        nonlocal command_count
        command_count+=1
        return run_checked(args,ROOT,out/label,timeout=45)
    def negative(args,label,absent=None):
        nonlocal command_count
        command_count+=1
        before=sha(args[0])
        r=subprocess.run([str(x) for x in args],cwd=ROOT,capture_output=True,timeout=45)
        (out/label).write_bytes(r.stdout+r.stderr)
        save_json((out/label).with_suffix('.json'),dict(command=list(map(str,args)),exit=r.returncode,executable_sha256=before))
        check(r.returncode!=0,'Negative control was accepted')
        check(sha(args[0])==before,'Executable changed')
        if absent is not None:check(not absent.exists(),'Rejected shader left an output')
        return r.stdout+r.stderr
    comparisons=[]
    originals={
        'pixel':next((INPUT/'extracted').glob('pixel_*.dxil')),
        'compute':next((INPUT/'extracted').glob('compute_*.dxil')),
        'glass':PHASE/'glass_original.dxil',
    }
    check(sha(originals['glass'])==GLASS_SHA,'Glass original changed')
    extraction=json.loads((INPUT/'extraction.json').read_text())
    for kind in ('pixel','compute'):
        expected=next(s['sha256'] for s in extraction['extracted'] if s['stage']==kind)
        check(sha(originals[kind])==expected,'Extracted input changed')
    canonical={}
    for kind,source in originals.items():
        positive([executable,'validate',SDK,source],kind+'_validate_original.log')
        positive([SDK/'dxc.exe','-dumpbin',source],kind+'_original.ll')
        ir=(out/(kind+'_original.ll')).read_text(encoding='utf-8-sig')
        control=out/(kind+'_control.dxil')
        positive([executable,'assemble',SDK,out/(kind+'_original.ll'),control],kind+'_assemble.log')
        positive([executable,'validate',SDK,control],kind+'_revalidate.log')
        positive([SDK/'dxc.exe','-dumpbin',control],kind+'_control.ll')
        rebuilt=(out/(kind+'_control.ll')).read_text(encoding='utf-8-sig')
        check(module_ir(ir)==module_ir(rebuilt),f'IR changed in {kind} roundtrip')
        a,b=parts(source.read_bytes()),parts(control.read_bytes())
        check(set(a)==set(b),'Container part set changed')
        for tag in ('SFI0','ISG1','OSG1','PSV0'):check(a[tag]==b[tag],f'Interface changed: {tag}')
        check(control.read_bytes()[4:20]!=bytes(16),'No final DXIL digest')
        canonical[kind]=ir
        comparisons.append(dict(shader=kind,original_sha256=sha(source),control_sha256=sha(control),
            original_bytes=source.stat().st_size,control_bytes=control.stat().st_size,module_ir_equal=True,
            interface_parts_equal=True,external_validator='PASS'))
    canary_ir=magenta(canonical['glass'])
    (out/'glass_canary_input.ll').write_text(canary_ir,encoding='utf-8')
    canary=out/'glass_canary.dxil'
    positive([executable,'assemble',SDK,out/'glass_canary_input.ll',canary],'glass_canary_assemble.log')
    positive([executable,'validate',SDK,canary],'glass_canary_revalidate.log')
    positive([SDK/'dxc.exe','-dumpbin',canary],'glass_canary.ll')
    check(module_ir((out/'glass_canary.ll').read_text())==module_ir(canary_ir),'Canary differs from requested IR')
    before,after=module_ir(canonical['glass']),module_ir(canary_ir)
    changes=[dict(line=i+1,before=a,after=b) for i,(a,b) in enumerate(zip(before,after)) if a!=b]
    check(len(before)==len(after) and len(changes)==4,'Canary changed more than four calls')
    a,b=parts(originals['glass'].read_bytes()),parts(canary.read_bytes())
    for tag in ('SFI0','ISG1','OSG1','PSV0'):check(a[tag]==b[tag],f'Canary interface changed: {tag}')
    (out/'bad_syntax.ll').write_text('This is not LLVM IR.\n')
    negative([executable,'assemble',SDK,out/'bad_syntax.ll',out/'bad_syntax.dxil'],'bad_syntax.log',out/'bad_syntax.dxil')
    check('@dx.op.unary.f32(i32 23,' in canonical['pixel'],'Negative opcode fixture not found')
    invalid=canonical['pixel'].replace('@dx.op.unary.f32(i32 23,','@dx.op.unary.f32(i32 999,',1)
    (out/'bad_opcode.ll').write_text(invalid,encoding='utf-8')
    rejected=negative([executable,'assemble',SDK,out/'bad_opcode.ll',out/'bad_opcode.dxil'],'bad_opcode.log',out/'bad_opcode.dxil')
    check(b'validation_status_hresult=' in rejected and b'validation_status_hresult=0x00000000' not in rejected,'Opcode was not rejected by external validation')
    digest=sha(canary)
    negative([executable,'assemble',SDK,out/'glass_canary_input.ll',canary],'overwrite_rejected.log')
    check(sha(canary)==digest,'Overwrite guard failed')
    original_cache=(INPUT/'copies/shader_final.cache').read_bytes()
    check(hashlib.sha256(original_cache).hexdigest()==CACHE_SHA,'Input cache changed')
    footer,records=cache.index(original_cache)
    metadata=cache.compilation_info(original_cache,footer)
    record=next(r for r in records if r['guid']==TARGET)
    old_blob=original_cache[record['blob_offset']:record['blob_offset']+record['bytes']]
    check(hashlib.sha256(old_blob).hexdigest()==GLASS_SHA,'Cache mapping differs from candidate')
    check(cache.replace(original_cache,TARGET,old_blob)==original_cache,'No-op cache roundtrip differs')
    repacks=[]
    for kind,payload in [('control',out/'glass_control.dxil'),('canary',canary)]:
        replacement=payload.read_bytes()
        packed=cache.replace(original_cache,TARGET,replacement)
        f,rr=cache.index(packed)
        check(cache.compilation_info(packed,f)==metadata,'Compilation metadata changed')
        for old,new in zip(records,rr):
            check((old['guid'],old['params_guid'])==(new['guid'],new['params_guid']),'Shader identity changed')
            old_data=original_cache[old['blob_offset']:old['blob_offset']+old['bytes']]
            new_data=packed[new['blob_offset']:new['blob_offset']+new['bytes']]
            check(new_data==(replacement if old['guid']==TARGET else old_data),'Unexpected shader changed')
        dest=out/f'shader_final.{kind}.offline.cache'
        with dest.open('xb') as stream:stream.write(packed)
        repacks.append(dict(kind=kind,path=str(dest),bytes=len(packed),sha256=sha(dest),shader_records=len(rr),
                            compilation_records=len(metadata),changed_shader_guid=TARGET,other_shader_payloads_identical=len(rr)-1))
    installed=Path(r'E:\GOG\Cyberpunk 2077\engine\shader_final.cache')
    check(sha(installed)==CACHE_SHA,'Installed original changed')
    save_json(out/'result.json',dict(experiment='C2077-DXIL-CANARY-001',status='PASS_OFFLINE',comparisons=comparisons,
       canary_sha256=sha(canary),canary_changes=changes,negative_controls=3,command_count=command_count,
       cache_noop_byte_identical=True,offline_repacks=repacks,installed_cache_unchanged=True,
       game_started=False,benchmarks_started=0,game_writes=[],runtime_acceptance='NOT TESTED',performance='NOT MEASURED'))
    print('C2077-DXIL-CANARY-001 PASS_OFFLINE; game/runtime not tested')


if __name__=='__main__':
    if sys.argv[1:]==['--selfcheck']:selfcheck()
    else:
        ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);run(ap.parse_args().out)
