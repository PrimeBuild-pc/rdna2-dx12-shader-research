"""Analyze etl_extract output, retaining raw QPC and explicit ownership/coverage.

No live capture, configuration change, injection, or game access. See the phase report
for the build/extraction commands. New output directories only.
"""
import argparse
import bisect
import collections as C
import csv
import gzip
import json
import ntpath
from pathlib import Path
import struct
import sys


def schemas(path):
    result = {}
    for line in path.open(encoding='utf-8'):
        c = line.rstrip('\n').split('\t')
        props = {}
        for p in c[7:]:
            if ':' in p:
                name, flags, typ, count, length = p.rsplit(':', 4)
                props[name] = tuple(map(int, (flags, typ, count, length)))
        result[int(c[0])] = dict(provider=c[1], task=c[2], opcode=c[3].strip(),
                                 id=int(c[4]), version=int(c[5]), op=int(c[6]), props=props)
    return result


def fields(columns, schema):
    out = {}
    for col in columns:
        name, value = col.split('=', 1)
        b = bytes.fromhex(value)
        flags, typ, count, length = schema['props'][name]
        if typ == 1:
            out[name] = b.decode('utf-16-le').rstrip('\0')
        elif typ == 2:
            out[name] = b.decode('utf-8', errors='replace').rstrip('\0')
        else:
            width = {3: 1, 4: 1, 5: 2, 6: 2, 7: 4, 8: 4, 9: 8, 10: 8,
                     13: 4, 16: length, 20: 4, 21: 8}.get(typ)
            if width not in (1, 2, 4, 8) or len(b) % width:
                raise ValueError(f'Unsupported property {name}: type={typ}, bytes={len(b)}')
            values = [int.from_bytes(b[i:i+width], 'little', signed=typ in (3, 5, 7, 9))
                      for i in range(0, len(b), width)]
            array = bool(flags & 4) or count > 1
            if not array and len(values) != 1:
                raise ValueError(f'Scalar size mismatch: {name}')
            out[name] = values if array else values[0]
    return out


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def table(path, header, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


class Scheduler:
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi
        self.current = {}
        self.state = {}
        self.times = C.Counter()
        self.waits = C.Counter()
        self.switches = C.Counter()
        self.anomalies = C.Counter()
        self.wakes = C.Counter()
        self.ready_wait = C.Counter()

    def clipped(self, a, b):
        return max(0, min(b, self.hi) - max(a, self.lo))

    def change(self, tid, t, state, reason=None):
        if tid == 0:
            return
        prev = self.state.get(tid)
        if prev:
            old, start, old_reason = prev
            if t < start:
                raise ValueError('Scheduler time inversion')
            dt = self.clipped(start, t)
            self.times[tid, old] += dt
            if old == 'waiting':
                self.waits[tid, old_reason] += dt
        self.state[tid] = (state, t, reason)

    def switch(self, t, cpu, new, old, old_state, reason):
        previous = self.current.get(cpu)
        if previous is not None and previous != old:
            self.anomalies['cpu_old_tid_mismatch'] += 1
        if old != new:
            self.change(old, t, 'waiting' if old_state == 5 else
                        'ready' if old_state in (1, 7) else 'other_offcpu', reason)
            prev = self.state.get(new)
            if prev and prev[0] == 'waiting':
                self.anomalies['switchin_without_ready'] += 1
            self.change(new, t, 'running')
        self.current[cpu] = new
        if self.lo <= t < self.hi:
            self.switches[new] += 1

    def ready(self, t, cpu, target, flags, owners):
        actor = self.current.get(cpu, -1)
        if self.lo <= t < self.hi:
            self.wakes[target, owners.get(actor, -1), actor, flags] += 1
        prev = self.state.get(target)
        if prev and prev[0] == 'running':
            self.anomalies['ready_while_current'] += 1
            return
        if prev and prev[0] == 'ready':
            self.anomalies['duplicate_ready'] += 1
            return
        self.change(target, t, 'ready')

    def finish(self):
        for tid in list(self.state):
            if self.state[tid][1] <= self.hi:
                self.change(tid, self.hi, 'end')


class Images:
    def __init__(self):
        self.maps = C.defaultdict(dict)
        self.sorted = {}

    def update(self, pid, base, size, name, unload=False):
        if unload:
            self.maps[pid].pop(base, None)
        else:
            self.maps[pid][base] = (base + size, ntpath.basename(name), name)
        self.sorted.pop(pid, None)

    def lookup(self, pid, address):
        owner = 0 if address >= 0xffff000000000000 else pid
        if owner not in self.sorted:
            bases = sorted(self.maps[owner])
            self.sorted[owner] = (bases, [self.maps[owner][b] for b in bases])
        bases, vals = self.sorted[owner]
        i = bisect.bisect_right(bases, address) - 1
        return vals[i][1] if i >= 0 and address < vals[i][0] else '[unmapped]'


def cpu_bucket(module):
    m = module.lower()
    if m == 'cyberpunk2077.exe':
        return 'game'
    if m.startswith(('amd', 'ati')) and m.endswith('.dll'):
        return 'amd_usermode'
    if m.startswith(('amd', 'ati')) and m.endswith('.sys'):
        return 'amd_kernel_interrupted_context_not_owner'
    if m in ('d3d12.dll', 'd3d12core.dll', 'dxgi.dll', 'dxcore.dll'):
        return 'd3d_runtime'
    if m in ('dxgkrnl.sys', 'dxgmms2.sys'):
        return 'graphics_kernel'
    if m.endswith('.sys') or m in ('ntoskrnl.exe', 'ntkrnlmp.exe', 'hal.dll'):
        return 'other_kernel_interrupted_context_not_owner'
    if m == '[unmapped]':
        return 'unmapped'
    return 'other_usermode'


def cpu(args):
    sch = schemas(args.prefix.with_suffix('.schemas.tsv'))
    out = args.out
    out.mkdir(exist_ok=False)
    lo, hi = args.lo, args.hi
    images = Images()
    # shortcut: TID-keyed scheduler state assumes no target TID reuse; track lifetimes for other captures.
    owners = {0: 0}
    names = {}
    sched = Scheduler(lo, hi)
    counts = C.Counter()
    samples = C.Counter()
    process_samples = C.Counter()
    target_pcs = C.Counter()
    unknown = C.Counter()
    probe_samples, probe_switches, probe_ready = [], [], []
    main_started = False
    dxgi_stops = []
    dxgi_probe = []
    metadata = []
    first_qpc = args.origin
    with args.prefix.with_suffix('.tsv').open(encoding='utf-8') as f, gzip.open(out/'gpu_events.jsonl.gz', 'wt', encoding='utf-8', compresslevel=1) as gpu:
        for i, line in enumerate(f):
            c = line.rstrip('\n').split('\t')
            t, hp, ht, cp, sid = map(int, c[:5])
            kind = c[5]
            s = sch[sid]
            if kind in ('sample', 'cswitch', 'ready'):
                if t >= lo - 5000000 and not main_started:
                    sched = Scheduler(lo, hi)
                    main_started = True
                b = bytes.fromhex(c[7])
                counts[kind, len(b), s['version']] += 1
                if kind == 'sample':
                    if s['version'] != 2 or len(b) != 16:
                        raise ValueError('Unvalidated SampleProf layout')
                    pc, tid, weight, reserved = struct.unpack('<QIHH', b)
                    pid = owners.get(tid, -1)
                    if t < first_qpc + 2000000:
                        probe_samples.append((t, tid, pc, weight))
                    if lo <= t < hi:
                        mod = images.lookup(pid, pc)
                        samples[pid, tid, mod] += weight
                        process_samples[pid] += weight
                        if pid == 16316:
                            target_pcs[mod, pc] += weight
                        if pid == -1:
                            unknown[tid] += weight
                elif kind == 'cswitch':
                    if s['version'] != 5 or len(b) != 28:
                        raise ValueError('Unvalidated CSwitch layout')
                    new, old = struct.unpack_from('<II', b)
                    old_reason, old_state = b[12], b[14]
                    if t < first_qpc + 2000000:
                        probe_switches.append((t, cp, new, old, old_state, old_reason))
                    sched.switch(t, cp, new, old, old_state, old_reason)
                else:
                    if s['version'] != 2 or len(b) != 8:
                        raise ValueError('Unvalidated ReadyThread layout')
                    target, reason, increment, flags, _ = struct.unpack('<IbbBB', b)
                    if t < first_qpc + 2000000:
                        probe_ready.append((t, cp, target, flags))
                    sched.ready(t, cp, target, flags, owners)
                continue
            d = fields(c[7:], s)
            task, op = s['task'], s['opcode']
            if s['provider'] == 'MSNT_SystemTrace' and task == 'Thread':
                tid = d.get('TThreadId', d.get('ThreadId'))
                if tid is not None and 'ProcessId' in d:
                    owners[tid] = d['ProcessId']
                if 'ThreadName' in d:
                    names[tid] = d['ThreadName']
            elif s['provider'] == 'MSNT_SystemTrace' and task == 'Image' and s['op'] in (2, 3, 4, 10):
                images.update(d['ProcessId'], d['ImageBase'], d['ImageSize'], d['FileName'], s['op'] == 2)
            elif s['provider'] == 'Microsoft-Windows-DXGI':
                if task == 'Present' and hp == 16316:
                    if op == 'Stop':
                        dxgi_stops.append(t)
                    if t < first_qpc + 2000000:
                        dxgi_probe.append(dict(qpc=t, tid=ht, opcode=op, fields=d))
            elif s['provider'] == 'Microsoft-Windows-DxgKrnl':
                event = dict(qpc=t, pid=hp, tid=ht, cpu=cp, task=task, opcode=op, id=s['id'], version=s['version'], fields=d)
                gpu.write(json.dumps(event, separators=(',', ':'))+'\n')
                if task in ('Device', 'Context', 'HwQueue', 'NodeMetadata'):
                    metadata.append(event)
            if i and i % 5000000 == 0:
                print(f'{i:,} input rows', flush=True)
    sched.finish()
    mods = C.Counter()
    threads = C.Counter()
    for (pid, tid, mod), n in samples.items():
        mods[pid, mod] += n
        threads[pid, tid] += n
    table(out/'cpu_modules.csv', ['pid', 'module', 'samples', 'pct_of_process', 'bucket'],
          ((pid, mod, n, 100*n/process_samples[pid], cpu_bucket(mod))
           for (pid, mod), n in sorted(mods.items(), key=lambda x: (x[0][0], -x[1]))))
    duration = (hi-lo)/10000
    table(out/'threads.csv', ['pid', 'tid', 'name', 'samples', 'running_ms', 'ready_ms', 'waiting_ms', 'other_offcpu_ms', 'uncovered_ms', 'switches_in'],
          ((pid, tid, names.get(tid, ''), n, *(sched.times[tid, state]/10000 for state in ('running', 'ready', 'waiting', 'other_offcpu')),
            max(0, duration-sum(sched.times[tid, st]/10000 for st in ('running', 'ready', 'waiting', 'other_offcpu'))), sched.switches[tid])
           for (pid, tid), n in threads.most_common()))
    table(out/'target_thread_modules.csv', ['tid', 'module', 'samples'],
          ((tid, mod, n) for (pid, tid, mod), n in sorted(samples.items(), key=lambda x: -x[1]) if pid == 16316))
    table(out/'wait_reasons.csv', ['tid', 'wait_reason_raw', 'waiting_ms'],
          ((tid, reason, n/10000) for (tid, reason), n in sched.waits.most_common() if owners.get(tid) == 16316))
    table(out/'wake_edges.csv', ['target_tid', 'actor_pid_current_cpu', 'actor_tid_current_cpu', 'flags_raw', 'count'],
          ((*key, n) for key, n in sched.wakes.most_common() if owners.get(key[0]) == 16316))
    table(out/'target_hot_pcs.csv', ['module', 'absolute_pc', 'samples'],
          ((mod, hex(pc), n) for (mod, pc), n in target_pcs.most_common(2000)))
    save(out/'cpu_summary.json', dict(window_qpc=[lo, hi], duration_ms=duration,
         process_samples=dict(process_samples), owner_unknown_samples=dict(unknown),
         scheduler_anomalies=dict(sched.anomalies), layouts=[dict(kind=k, bytes=b, version=v, rows=n) for (k,b,v),n in counts.items()],
         limitations='Scheduled CPU residency includes DPC/ISR. Ready actor is the current CPU thread, not proof it caused the signal; flags retained. Exclusive sampling is not a critical-path proof.'))
    save(out/'clock_inputs.json', dict(dxgi_first=dxgi_probe, target_present_stop_qpc=dxgi_stops))
    save(out/'probe_raw.json', dict(samples=probe_samples, switches=probe_switches, ready=probe_ready))
    save(out/'gpu_metadata.json', metadata)
    print('CPU/scheduler extraction complete', dict(process_samples), flush=True)


def selfcheck():
    s = {'props': {'hContext': (0,16,1,8), 'ObjectArray': (4,16,1,8), 'Name': (0,1,1,0)}}
    d = fields(['hContext=0100000000000000', 'ObjectArray=02000000000000000300000000000000', 'Name=41000000'], s)
    assert d == {'hContext': 1, 'ObjectArray': [2,3], 'Name': 'A'}
    im = Images(); im.update(7, 100, 20, r'C:\test.dll')
    assert im.lookup(7,100)=='test.dll' and im.lookup(7,119)=='test.dll' and im.lookup(7,120)=='[unmapped]'
    im.update(7,100,20,'test.dll',True); assert im.lookup(7,100)=='[unmapped]'
    sc = Scheduler(10,110)
    sc.switch(0,0,1,0,2,0); sc.switch(30,0,2,1,5,6)
    sc.ready(70,0,1,0,{1:7,2:8}); sc.switch(90,0,1,2,1,0); sc.finish()
    assert sc.times[1,'running']==40 and sc.times[1,'waiting']==40 and sc.times[1,'ready']==20
    assert sc.times[2,'running']==60 and sc.times[2,'ready']==20
    assert sc.waits[1,6]==40 and sc.wakes[1,8,2,0]==1
    assert sum(sc.times[1,x] for x in ('running','waiting','ready'))==100
    print('Offline ETW parser selfcheck PASS')


if __name__ == '__main__':
    if sys.argv[1:] == ['--selfcheck']:
        selfcheck()
    else:
        ap=argparse.ArgumentParser()
        ap.add_argument('prefix', type=Path)
        ap.add_argument('out', type=Path)
        ap.add_argument('--lo', type=int, required=True)
        ap.add_argument('--hi', type=int, required=True)
        ap.add_argument('--origin', type=int, required=True)
        args=ap.parse_args()
        if not (args.origin < args.lo < args.hi):
            ap.error('Invalid raw-QPC bounds')
        cpu(args)
