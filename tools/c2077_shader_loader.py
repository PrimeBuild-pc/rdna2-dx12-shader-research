"""Install/remove only new, manifest-owned Cyberpunk loader files. Never launch a game."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PHASE=ROOT/'research/66_c2077_shader_loader_20261016'
GAME=Path(r'E:\GOG\Cyberpunk 2077\bin\x64')
GAME_SHA='a7de82945c03e041fc7339fcf9066224d98db2f5d80fea50f7947bb350a60991'
STATE=PHASE/'deployment.json'
LAB='C2077ShaderLab'
MODES=('observe','control','canary')


def check(ok,message):
    if not ok:raise RuntimeError(message)


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path,value):
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                     prefix=path.name+'.',suffix='.pending',delete=False) as f:
        temp=Path(f.name)
        json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def game_processes():
    script="@(Get-Process Cyberpunk2077 -ErrorAction SilentlyContinue) | Select-Object Id,Path | ConvertTo-Json -Compress"
    r=subprocess.run(['pwsh','-NoProfile','-Command',script],capture_output=True,text=True,timeout=30)
    r.check_returncode()
    if not r.stdout.strip():return []
    value=json.loads(r.stdout)
    return value if isinstance(value,list) else [value]


def stopped():check(not game_processes(),'Close Cyberpunk normally before changing the loader; no process is stopped by this tool')


def child(base,relative):
    p=Path(relative)
    check(not p.is_absolute() and '..' not in p.parts,'Invalid manifest path')
    resolved=(base/p).resolve()
    check(resolved.is_relative_to(base.resolve()),'Path escapes target')
    return resolved


def baseline(game):
    # No overwrite of pre-existing files is permitted; originals need hashes, not replacement backups.
    return [dict(path=str(f.relative_to(game)),sha256=sha(f),bytes=f.stat().st_size)
            for f in sorted(game.rglob('*')) if f.is_file()]


def install_files(stage,game,state_path):
    check(not state_path.exists(),'Deployment state already exists')
    check(not (game/LAB).exists(),'Lab directory already exists')
    for name in ('dxgi.dll','d3d12.dll','version.dll','winmm.dll','ReShade.ini','ReShade.log','ReShadePreset.ini'):
        check(not (game/name).exists(),f'Conflicting loader/config/log: {name}')
    items=[]
    files=sorted(f for f in stage.rglob('*') if f.is_file())
    check(any(f.relative_to(stage).as_posix()=='dxgi.dll' for f in files),'Loader payload missing')
    for source in files:
        relative=source.relative_to(stage)
        check(not child(game,str(relative)).exists(),f'Would overwrite: {relative}')
        items.append(dict(path=str(relative),sha256=sha(source),bytes=source.stat().st_size,
                          mutable=source.suffix=='.ini' or source.name=='mode.txt',created=False,verified=False))
    state=dict(schema=1,experiment='C2077-SHADER-LOADER-001',target=str(game.resolve()),
               created_utc=now(),state='installing',mode='control',files=items,
               preexisting=baseline(game),history=[])
    save(state_path,state)
    (game/LAB).mkdir()
    (game/LAB/'empty').mkdir();(game/LAB/'effect-cache').mkdir()
    # The proxy is published last, via a same-volume rename, after every support file is ready.
    ordered=sorted(items,key=lambda e:e['path']=='dxgi.dll')
    for entry in ordered:
        target=child(game,entry['path']);source=child(stage,entry['path'])
        if entry['path']=='dxgi.dll':
            pending=game/LAB/'.loader.pending'
            with source.open('rb') as src,pending.open('xb') as dst:
                shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
            check(sha(pending)==entry['sha256'],'Proxy staging hash mismatch')
            check(not target.exists(),'Proxy appeared during installation')
            entry['created']=True;entry['verified']=True;save(state_path,state)
            pending.rename(target)  # Windows refuses to replace an existing destination.
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            with source.open('rb') as src,target.open('xb') as dst:
                entry['created']=True;save(state_path,state)
                shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
        check(sha(target)==entry['sha256'],'Installed payload hash mismatch')
        entry['verified']=True;save(state_path,state)
    for entry in state['preexisting']:
        check(sha(child(game,entry['path']))==entry['sha256'],'Pre-existing file changed during install')
    state['state']='installed';state['history'].append(dict(action='install',utc=now(),mode='control'))
    save(state_path,state)
    return state


def remove_files(game,state_path,archive):
    state=json.loads(state_path.read_text())
    check(state['target']==str(game.resolve()),'Manifest target differs')
    check(state['state'] in ('installed','installing'),'No active deployment to remove')
    # Fail before deleting anything if an immutable payload now belongs to another mod/version.
    for entry in state['files']:
        p=child(game,entry['path'])
        if entry['created'] and p.exists() and not entry['mutable'] and entry['verified']:
            check(sha(p)==entry['sha256'],f'Changed immutable payload; refusing deletion: {p}')
    archive.mkdir(exist_ok=False)
    owned=[child(game,e['path']) for e in state['files'] if e['created'] and child(game,e['path']).exists()]
    pending=game/LAB/'.loader.pending'
    if pending.exists():owned.append(pending)
    for prefix,experiment in [('runtime','C2077-SHADER-LOADER-001'),('probe','C2077-SHADER-PROBE-001'),('backbuffer','C2077-BACKBUFFER-PROBE-001')]:
        for p in (game/LAB).glob(prefix+'-*.jsonl'):
            if re.fullmatch(prefix+r'-\d+-\d+\.jsonl',p.name):
                with p.open('rb') as f:first=f.readline(4096)
                try:header=json.loads(first)
                except (ValueError,UnicodeError):continue
                if header.get('experiment')==experiment:owned.append(p)
    host_log=game/'ReShade.log'
    if host_log.exists():
        with host_log.open('rb') as f:prefix=f.read(4096)
        if b"Initializing crosire's ReShade version" in prefix:owned.append(host_log)
    for p in owned:
        dest=archive/p.relative_to(game);dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dest);check(sha(p)==sha(dest),'Rollback archive hash mismatch')
    # Disable the proxy before removing its config/add-on. Unknown new files are left untouched.
    for p in sorted(owned,key=lambda p:p.name!='dxgi.dll'):p.unlink()
    for p in sorted((game/LAB).rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if p.is_dir():
            try:p.rmdir()
            except OSError:pass
    try:(game/LAB).rmdir()
    except OSError:pass
    changed=[e['path'] for e in state['preexisting'] if not child(game,e['path']).exists() or sha(child(game,e['path']))!=e['sha256']]
    state['state']='removed';state['history'].append(dict(action='remove',utc=now(),archive=str(archive),changed_preexisting=changed))
    save(state_path,state)
    return dict(state='removed',changed_preexisting=changed,lab_directory_remaining=(game/LAB).exists())


def set_mode(game,state_path,mode):
    check(mode in MODES,'Unknown mode')
    state=json.loads(state_path.read_text());check(state['state']=='installed','Loader not installed')
    check(state['target']==str(game.resolve()),'Wrong target')
    p=game/LAB/'mode.txt';temp=p.with_suffix('.pending')
    with temp.open('x',encoding='ascii') as f:f.write(mode+'\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,p)
    state['mode']=mode;state['history'].append(dict(action='mode',mode=mode,utc=now()))
    save(state_path,state)


def log_status(game,prefix):
    expected={'runtime':'C2077-SHADER-LOADER-001','probe':'C2077-SHADER-PROBE-001','backbuffer':'C2077-BACKBUFFER-PROBE-001'}[prefix]
    result=[]
    for p in sorted((game/LAB).glob(prefix+'-*.jsonl'),key=lambda p:p.stat().st_mtime_ns)[-5:]:
        with p.open('rb') as f:
            f.seek(max(0,p.stat().st_size-32768));lines=f.read().splitlines()
        records=[]
        for line in lines:
            try:
                record=json.loads(line)
                if isinstance(record,dict) and record.get('experiment')==expected:records.append(record)
            except (ValueError,UnicodeError):pass
        if records:result.append(dict(file=str(p),latest=records[-1]))
    return result


def status():
    state=json.loads(STATE.read_text()) if STATE.exists() else dict(state='not_installed')
    result=dict(state=state.get('state'),mode=state.get('mode'),processes=game_processes(),
                runtime=log_status(GAME,'runtime'),probe=log_status(GAME,'probe'),backbuffer=log_status(GAME,'backbuffer'))
    print(json.dumps(result,indent=2))


def selfcheck():
    with tempfile.TemporaryDirectory(prefix='c2077-loader-test-') as temp:
        root=Path(temp);stage=root/'stage';game=root/'game';stage.mkdir();game.mkdir()
        (stage/LAB).mkdir();(stage/'dxgi.dll').write_bytes(b'test proxy, never executed')
        (stage/'ReShade.ini').write_text('test config');(stage/LAB/'mode.txt').write_text('control\n')
        (stage/LAB/'test.addon64').write_bytes(b'test addon, never executed');(game/'keep.bin').write_bytes(b'untouched')
        state=root/'state.json';stale=root/'state.json.pending';stale.write_text('preserve interrupted journal')
        install_files(stage,game,state);assert (game/'keep.bin').read_bytes()==b'untouched'
        assert stale.read_text()=='preserve interrupted journal'
        set_mode(game,state,'canary');assert (game/LAB/'mode.txt').read_text()=='canary\n'
        (game/'ReShade.ini').write_text('runtime changed config')
        (game/LAB/'user-note.txt').write_text('do not delete')
        (game/LAB/'probe-123-456.jsonl').write_text(json.dumps(dict(experiment='C2077-SHADER-PROBE-001'))+'\n')
        (game/LAB/'probe-123-999.jsonl').write_text(json.dumps(dict(experiment='OTHER'))+'\n')
        assert len(log_status(game,'probe'))==1
        (game/LAB/'backbuffer-123-456.jsonl').write_text(json.dumps(dict(experiment='C2077-BACKBUFFER-PROBE-001'))+'\n')
        (game/LAB/'backbuffer-123-999.jsonl').write_text(json.dumps(dict(experiment='OTHER'))+'\n')
        assert len(log_status(game,'backbuffer'))==1
        for i in range(6):
            log=game/LAB/f'runtime-{900-i}-100.jsonl';log.write_text(json.dumps(dict(experiment='C2077-SHADER-LOADER-001',sequence=i))+'\n')
            os.utime(log,ns=(1700000000000000000+i*1000000000,)*2)
        assert log_status(game,'runtime')[-1]['latest']['sequence']==5
        result=remove_files(game,state,root/'archive');assert not result['changed_preexisting']
        assert (root/'archive'/LAB/'probe-123-456.jsonl').exists()
        assert (game/LAB/'probe-123-999.jsonl').exists()
        assert (root/'archive'/LAB/'backbuffer-123-456.jsonl').exists()
        assert (game/LAB/'backbuffer-123-999.jsonl').exists()
        assert not (game/'dxgi.dll').exists() and (game/LAB/'user-note.txt').exists()
        assert (root/'archive/ReShade.ini').read_text()=='runtime changed config'
        collision=root/'collision';collision.mkdir();(collision/'dxgi.dll').write_bytes(b'other mod')
        try:install_files(stage,collision,root/'collision.json')
        except RuntimeError:pass
        else:raise AssertionError('Existing loader overwritten')
        game2=root/'game2';game2.mkdir();state2=root/'state2.json';install_files(stage,game2,state2)
        (game2/'dxgi.dll').write_bytes(b'changed by another tool')
        try:remove_files(game2,state2,root/'refused-archive')
        except RuntimeError:pass
        else:raise AssertionError('Changed payload deleted')
        assert (game2/'ReShade.ini').exists()
    print('Loader install/mode/rollback/collision/changed-file selfcheck PASS')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=('install','status','mode','uninstall','selfcheck'));ap.add_argument('value',nargs='?',choices=MODES);a=ap.parse_args()
    if a.action=='selfcheck':selfcheck()
    elif a.action=='status':status()
    else:
        stopped()
        if a.action=='install':
            check(sha(GAME/'Cyberpunk2077.exe')==GAME_SHA,'Unexpected game executable')
            package=json.loads((PHASE/'package.json').read_text())
            actual={str(p.relative_to(PHASE/'stage')) for p in (PHASE/'stage').rglob('*') if p.is_file()}
            check(actual=={e['path'] for e in package['files']},'Staged package file set changed')
            for e in package['files']:check(sha(child(PHASE/'stage',e['path']))==e['sha256'],'Staged package changed')
            install_files(PHASE/'stage',GAME,STATE);print('Installed in control mode; game not started')
        elif a.action=='mode':
            check(a.value in MODES,'Mode required');check(sha(GAME/'Cyberpunk2077.exe')==GAME_SHA,'Unexpected game executable');set_mode(GAME,STATE,a.value);print('Mode set; applies only on next manual game start')
        else:print(json.dumps(remove_files(GAME,STATE,PHASE/('rollback-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))),indent=2))
