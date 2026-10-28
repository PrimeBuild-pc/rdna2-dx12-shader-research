"""Independent crosschecks: raw ETW/QPC vs xperf and online PresentMon.

Run after c2077_etw_offline.py; no live tracing. Assertions fail closed.
"""
import argparse
import bisect
import collections as C
import csv
import json
from html.parser import HTMLParser
from pathlib import Path
from c2077_etw_offline import save, table


class StackReport(HTMLParser):
    def __init__(self):
        super().__init__();self.section='';self.tables=C.defaultdict(list);self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and a.get('id','').startswith('Tbl'):self.section=a['id']
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
    def handle_data(self,data):
        if self.cell is not None:self.cell+=data
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.row is not None and self.cell is not None:
            self.row.append(self.cell.strip());self.cell=None
        if tag=='tr' and self.row is not None:
            self.tables[self.section].append(self.row);self.row=None


def native_summaries(root):
    analysis=root/'analysis'; summaries={}
    for name,file in [('broad_profile_not_validated_cpu_sampling','stacks_retry_profile.html'),('switch','stacks_CSwitch.txt'),('ready','stacks_ReadyThread.txt')]:
        parser=StackReport();parser.feed((root/file).read_text(encoding='utf-8'))
        for section,rows in parser.tables.items():
            if rows:table(analysis/f'{name}_{section}.csv',rows[0],rows[1:])
        summaries[name]=dict(source=file,process_rows=parser.tables['TblP'][1:],
                             function_rows=len(parser.tables['TblSI'])-1)
    weighted=C.Counter(); process=C.Counter(); functions=C.Counter()
    with (root/'cpu_profile.txt').open() as f:
        for row in csv.reader(f,skipinitialspace=True):
            if len(row)<4 or not row[1].strip().isdigit():continue
            pid=int(row[0].rsplit('(',1)[1].rstrip(') '));weight=int(row[1]);fn=row[3].strip()
            process[pid]+=weight;weighted[pid,fn.split('!',1)[0]]+=weight
            if pid==16316:functions[fn]+=weight
    table(analysis/'xperf_weighted_cpu_modules.csv',['pid','module','weight_us','pct_of_process'],
          ((pid,mod,n,100*n/process[pid]) for (pid,mod),n in sorted(weighted.items(),key=lambda x:(x[0][0],-x[1]))))
    table(analysis/'xperf_target_functions.csv',['function','weight_us','pct_of_process'],
          ((fn,n,100*n/process[16316]) for fn,n in functions.most_common()))
    precise={}
    with (root/'cpu_cswitch.txt').open() as f:
        for row in csv.reader(f,skipinitialspace=True):
            if len(row)==3 and 'Cyberpunk2077.exe (16316)' in row[1] and row[0].strip().isdigit():precise[int(row[2])]=int(row[0])
    errors=[]
    with (analysis/'threads.csv').open() as f:
        for row in csv.DictReader(f):
            if row['pid']=='16316' and int(row['tid']) in precise:
                errors.append(abs(float(row['running_ms'])*1000-precise[int(row['tid'])]))
    assert errors and max(errors)<=1.1,('Scheduler differs from native xperf',max(errors))
    summaries['scheduler_crosscheck']=dict(target_threads=len(errors),max_running_time_error_us=max(errors))
    summaries['target_weighted_cpu_us']=process[16316]
    etw_functions={fn:n for fn,n in functions.items() if fn.startswith('ntoskrnl.exe!Etw')}
    stack_functions={fn:n for fn,n in functions.items() if fn in ('ntoskrnl.exe!RtlpLookupFunctionEntryForStackWalks','ntoskrnl.exe!RtlpWalkFrameChain')}
    summaries['explicit_etw_symbol_samples']=dict(weight_us=sum(etw_functions.values()),pct_of_game_cpu=100*sum(etw_functions.values())/process[16316],functions=etw_functions)
    summaries['explicit_stackwalk_helper_samples']=dict(weight_us=sum(stack_functions.values()),pct_of_game_cpu=100*sum(stack_functions.values())/process[16316],functions=stack_functions,limit='Caller stacks are not validated for CPU sampling; not every generic unwind routine is assigned to ETW.')
    summaries['sampled_caller_stacks_validated']=False
    summaries['broad_profile_filter_limit']='Profile matches an ambiguous family with more hits than CPU samples and different exclusive distribution; excluded from CPU cost/caller attribution. SampledProfile and SampleProf filters returned empty tables.'
    gpu=json.loads((analysis/'gpu/summary.json').read_text())
    assert {(x['id'],x['layout']) for x in gpu['queue_start_layouts']}=={(178,'dma'),(244,'wait'),(245,'signal')}
    lo,hi=gpu['window_qpc']
    for n in gpu['node_diagnostics']:
        assert not n['counts'].get('out_of_order_completion',0)
        assert all(not lo<=e[0]<hi for e in n['anomaly_events'])
    assert all(x['event_pid']==x['context_owner_pid']==16316 for x in gpu['ownership_checks'])
    node_totals=C.Counter()
    with (analysis/'gpu/node_timeline_totals.csv').open() as f:
        for r in csv.DictReader(f):node_totals[r['adapter'],r['node']]+=float(r['ms'])
    assert all(abs(t-gpu['duration_ms'])<1e-6 for t in node_totals.values())
    unmapped=json.loads((analysis/'gpu/unmapped_context_events.json').read_text())
    assert len(unmapped)==18 and all(e['fields']['PacketType']==6 for e in unmapped)
    waits=json.loads((analysis/'gpu/wait_packets.json').read_text())
    assert all(w['unwait'] is None or w['start']<=w['unwait']<=w['stop'] for w in waits)
    with (root.parent/'presentmon.csv').open(encoding='utf-8-sig') as f:pm=list(csv.DictReader(f))[7745:13049]
    pm_busy=sum(float(r['GPUBusy']) for r in pm)
    summaries['gpu_crosscheck']=dict(status='PASS',fifo_union_ms=gpu['target_dma_fifo_union_ms'],online_frame_gpu_busy_sum_ms=pm_busy,
       delta_ms=gpu['target_dma_fifo_union_ms']-pm_busy,
       limitation='Window-clipped union and per-frame busy attribution have different boundaries; agreement is a decoder check, not independent hardware occupancy.')
    save(analysis/'native_summary_validation.json',summaries)
    print('Native CPU/stack exports and scheduler crosscheck PASS',summaries['scheduler_crosscheck'])


def check(root):
    analysis=root/'analysis'
    raw=json.loads((analysis/'probe_raw.json').read_text())
    clock=json.loads((analysis/'clock_inputs.json').read_text())
    origin=324166830818
    def stamp(qpc):return (qpc-origin+5)//10
    states={'Initialized':0,'Ready':1,'Running':2,'Standby':3,'Terminated':4,
            'Waiting':5,'Transition':6,'DeferredReady':7,'GateWaitObsolete':8,
            'WaitingForProcessInSwap':9}
    native_samples=C.Counter((stamp(t),tid,pc,w) for t,tid,pc,w in raw['samples'] if stamp(t)<200000)
    native_switch=C.Counter((stamp(t),cpu,new,old) for t,cpu,new,old,state,reason in raw['switches'] if stamp(t)<200000)
    raw_states={(stamp(t),cpu,new,old):state for t,cpu,new,old,state,reason in raw['switches']}
    native_ready=C.Counter((stamp(t),cpu,tid) for t,cpu,tid,flags in raw['ready'] if stamp(t)<200000)
    raw_reason={(stamp(t),cpu,new,old):reason for t,cpu,new,old,state,reason in raw['switches']}
    raw_flags={(stamp(t),cpu,tid):flags for t,cpu,tid,flags in raw['ready']}
    xp_samples=C.Counter();xp_switch=C.Counter();xp_ready=C.Counter();xp_dxgi=[]
    reason_labels=C.defaultdict(set);state_labels=C.defaultdict(set);flag_labels=C.defaultdict(C.Counter)
    with (root/'schema_probe.txt').open(encoding='utf-8',errors='replace') as f:
        for line in f:
            s=line.lstrip()
            if not s.startswith(('SampledProfile,','CSwitch,','ReadyThread,','Microsoft-Windows-DXGI/Present/')):continue
            c=[v.strip() for v in next(csv.reader([s],skipinitialspace=True))]
            if not c[1].isdigit():continue
            ts=int(c[1])
            if ts>=200000:continue
            if c[0]=='SampledProfile':xp_samples[ts,int(c[3]),int(c[4],16),int(c[8])]+=1
            elif c[0]=='CSwitch':
                key=(ts,int(c[16]),int(c[3]),int(c[9]))
                xp_switch[key]+=1
                if key in raw_states:
                    state_labels[raw_states[key]].add(c[12])
                    if c[12] in states:assert raw_states[key]==states[c[12]],(key,raw_states[key],c[12])
                if key in raw_reason:reason_labels[raw_reason[key]].add(c[13])
            elif c[0]=='ReadyThread':
                key=(ts,int(c[8]),int(c[5]));xp_ready[key]+=1
                if key in raw_flags:flag_labels[raw_flags[key]][c[9] if len(c)>9 else '']+=1
            elif 'Cyberpunk2077.exe (16316)' in c[2]:xp_dxgi.append((ts,int(c[3]),c[0].rsplit(':',1)[1]))
    diagnostics={}
    for name,a,b in [('sample',native_samples,xp_samples),('cswitch',native_switch,xp_switch),('ready',native_ready,xp_ready)]:
        diagnostics[name]=dict(native=sum(a.values()),xperf=sum(b.values()),native_only=sum((a-b).values()),xperf_only=sum((b-a).values()))
        assert a==b, (name,diagnostics[name],(a-b).most_common(3),(b-a).most_common(3))
    native_dxgi=[(stamp(e['qpc']),e['tid'],e['opcode']) for e in clock['dxgi_first'] if stamp(e['qpc'])<200000]
    assert native_dxgi and native_dxgi==xp_dxgi,(native_dxgi,xp_dxgi)
    # Raw QPC frequency is 10 MHz in the recorded trace header, not today's QPC.
    native=json.loads((root.parent/'native_analysis_v2/analysis.json').read_text())
    with (root.parent/'presentmon.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    stops=clock['target_present_stop_qpc']
    a=native['alignment'];window=rows[a['first_row']:a['last_row']+1]
    online_qpc=[round(float(r['CPUStartQPCTime'])*10000) for r in window]
    matched=[];indices=[];residuals=[];second_nearest=[]
    for q in online_qpc:
        index=bisect.bisect_left(stops,q)
        candidates=sorted(range(max(0,index-1),min(len(stops),index+2)),key=lambda i:abs(stops[i]-q))
        chosen=candidates[0];indices.append(chosen);matched.append(stops[chosen]);residuals.append(stops[chosen]-q)
        second_nearest.append(abs(stops[candidates[1]]-q))
    assert len(window)==5304 and len(matched)==len(window)
    # Separate real-time sessions can timestamp the same provider emission a few us apart.
    # Require a contiguous one-to-one sequence and a wide margin to any alternative.
    assert all(b-a==1 for a,b in zip(indices,indices[1:])), 'Noncontiguous native Present sequence'
    assert max(map(abs,residuals))<=1000 and min(second_nearest)>10000, 'Ambiguous cross-session match'
    interval_errors=[(b-a)-round(float(r['FrameTime'])*10000) for a,b,r in zip(matched,matched[1:],window)]
    assert max(map(abs,interval_errors))<=2000, 'Present sequence intervals disagree' 
    lo=online_qpc[0]
    hi=online_qpc[-1]+round(float(window[-1]['FrameTime'])*10000)
    assert [lo,hi]==json.loads((analysis/'cpu_summary.json').read_text())['window_qpc']
    report=dict(status='PASS',raw_qpc_frequency_hz=10000000,origin_qpc=origin,
                qpc_to_etl_us='(raw_qpc - 324166830818) / 10; xperf display rounds to whole us',
                probe_crosschecks=diagnostics,dxgi_anchor_events=len(native_dxgi),
                native_window_presentmon_rows=len(window),contiguous_qpc_matches_to_dxgi_present_stop=len(matched),
                exact_timestamp_matches=sum(r==0 for r in residuals),
                cross_session_stop_minus_online_ticks=dict(min=min(residuals),median=sorted(residuals)[len(residuals)//2],max=max(residuals)),
                nearest_alternative_min_us=min(second_nearest)/10,
                interval_error_max_us=max(map(abs,interval_errors))/10,
                window_qpc=[lo,hi],window_etl_us=[(lo-origin)/10,(hi-origin)/10],
                wait_reason_labels={str(k):sorted(v) for k,v in reason_labels.items()},
                old_state_labels={str(k):sorted(v) for k,v in state_labels.items()},
                ready_flags_vs_xperf={str(k):dict(v) for k,v in flag_labels.items()},
                limitation='PresentMon CPUStart corresponds to the previous Present stop. Online and WPR timestamps are not bit-identical; this verifies clocks/window with reported cross-session residuals, not exact event identity or hardware GPU timestamp precision.')
    save(analysis/'clock_and_layout_validation.json',report)
    native_summaries(root)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);check(ap.parse_args().root)
