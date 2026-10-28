"""Replay classic DxgKrnl DMA queues from the offline, schema-validated event subset.

DMA start is node enqueue, not a hardware start timestamp. FIFO execution bounds are
only reported alongside ordering/preemption diagnostics; no shader-cost attribution.
"""
import argparse
import bisect
import collections as C
import gzip
import json
from pathlib import Path
import statistics
import sys
from c2077_etw_offline import save, table


def clip(a, b, lo, hi):
    return max(0, min(b, hi)-max(a, lo))


def stats(values):
    if not values:
        return dict(n=0)
    values=sorted(values)
    def percentile(p):
        pos=(len(values)-1)*p
        i=int(pos)
        return values[i]+(values[min(i+1,len(values)-1)]-values[i])*(pos-i)
    return dict(n=len(values), mean_ms=statistics.fmean(values)/10000,
                p50_ms=percentile(.5)/10000, p95_ms=percentile(.95)/10000,
                p99_ms=percentile(.99)/10000, max_ms=values[-1]/10000)


def packet_type(d):
    # PresentMon's pinned DxgKrnl enum: scalar fence WAIT=4, array SIGNAL=5.
    if 'PacketType' in d:return d['PacketType'],'dma'
    if 'hSyncObject' in d and 'FenceValue' in d:return 4,'wait'
    if 'ObjectArray' in d and 'FenceValue' in d:return 5,'signal'
    raise ValueError('Unvalidated QueuePacket Start layout')


class Node:
    def __init__(self, lo, hi):
        self.lo, self.hi=lo,hi
        self.last=lo
        self.queue=[]
        self.pending=set()
        self.waits=set()
        self.time=C.Counter()
        self.diagnostics=C.Counter()
        self.anomaly_events=[]
        self.spans=[]
        self.empty=[]
        self.max_depth=0

    def tick(self,t):
        dt=clip(self.last,t,self.lo,self.hi)
        if self.queue:
            state='target_dma' if self.queue[0]['pid']==16316 else 'other_dma'
        elif self.pending:
            state='empty_pending_dma_with_wait' if self.waits else 'empty_pending_dma_no_wait'
        else:
            state='empty_no_pending_dma_with_wait' if self.waits else 'empty_no_pending_dma_no_wait'
        self.time[state]+=dt
        if dt and not self.queue:
            self.empty.append((max(self.last,self.lo), min(t,self.hi),state))
        self.last=t

    def start(self,t,key,pid,submitted=None):
        self.tick(t)
        if any(x['key']==key for x in self.queue):
            self.diagnostics['duplicate_dma_start']+=1
            return
        self.queue.append(dict(key=key,pid=pid,enqueued=t,running=t if not self.queue else None,submitted=submitted))
        self.pending.discard(key[:2])
        self.max_depth=max(self.max_depth,len(self.queue))

    def complete(self,t,key):
        self.tick(t)
        index=next((i for i,x in enumerate(self.queue) if x['key']==key),None)
        if index is None:
            self.diagnostics['completion_without_start']+=1
            self.anomaly_events.append((t,'completion_without_start',key))
            return
        if index:
            # Do not invent completion times for packets that violated FIFO order.
            self.diagnostics['out_of_order_completion']+=1
            self.anomaly_events.append((t,'out_of_order_completion',key))
            self.queue.pop(index)
            return
        x=self.queue.pop(0)
        self.spans.append((x['running'],t,x))
        if self.queue:
            self.queue[0]['running']=t


def run(args):
    inp=args.analysis
    out=inp/'gpu'
    out.mkdir(exist_ok=False)
    summary=json.loads((inp/'cpu_summary.json').read_text())
    lo,hi=summary['window_qpc']
    devices={};contexts={};nodes={};node_metadata={};all_contexts={}
    queues={};dma_starts={};wait_packets={};signals=C.defaultdict(list)
    diagnostics=C.Counter();counts=C.Counter();target_counts=C.Counter();unmapped=[]
    preemptions=C.Counter();timeouts=C.Counter();ownership=C.Counter()
    queue_latency=[];dispatch_latency=[];enqueue_latency=[];stop_interrupt=[]
    wait_duration=[];unwait_duration=[];wait_details=[]
    queue_schemas=C.Counter();completion_interrupts=C.Counter();cpu_signals=0
    target_adapters=set();first_qpc=None;last_qpc=None

    def get_context(h):
        c=contexts.get(h)
        if c:
            d=devices.get(c['device'])
            if d:
                return c,d
        return None,None

    def get_node(c,d):
        key=(d['adapter'],c['node'])
        if key not in nodes:
            nodes[key]=Node(lo,hi)
        return nodes[key]

    with gzip.open(inp/'gpu_events.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            e=json.loads(line)
            t=e['qpc'];task=e['task'];op=e['opcode'];d=e['fields']
            counts[task,op]+=int(lo<=t<hi)
            if task=='Device':
                if op in ('Start','DCStart'):
                    value=dict(pid=d['hProcessId'],adapter=d['pDxgAdapter'])
                    if d['hDevice'] in devices and devices[d['hDevice']]!=value:
                        diagnostics['device_handle_reuse']+=1
                    devices[d['hDevice']]=value
                    if value['pid']==16316:target_adapters.add(value['adapter'])
                continue
            if task=='Context':
                if op in ('Start','DCStart'):
                    value=dict(device=d['hDevice'],node=d['NodeOrdinal'])
                    contexts[d['hContext']]=value
                    all_contexts[d['hContext']]=value.copy()
                continue
            if task=='HwQueue':
                diagnostics['hardware_queue_metadata_not_supported']+=1
                continue
            if task=='NodeMetadata':
                node_metadata[d['pDxgAdapter'],d['NodeOrdinal']]=d
                continue
            if not (lo-5000000<=t<hi+5000000):
                continue
            first_qpc=t if first_qpc is None else first_qpc
            last_qpc=t
            h=d.get('hContext')
            c,dev=get_context(h if isinstance(h,int) else None)
            if task in ('QueuePacket','DmaPacket') and c is None:
                diagnostics['unmapped_packet_context']+=int(lo<=t<hi)
                if lo<=t<hi:unmapped.append(dict(qpc=t,event_pid=e['pid'],context=hex(h),task=task,opcode=op,fields=d))
                continue
            if c is None:
                if task=='SignalSynchronizationObjectFromCpu':
                    dv=devices.get(d.get('hDevice'))
                    if dv and dv['pid']==16316:
                        cpu_signals+=int(lo<=t<hi)
                        for obj,val in zip(d['ObjectArray'],d['MonitoredFenceValue']):
                            signals[obj].append((val,t,'CPU',e['tid']))
                continue
            n=get_node(c,dev)
            target=dev['pid']==16316
            if target and lo<=t<hi:
                target_counts[task,op]+=1
                if task=='QueuePacket' and op=='Start':
                    ownership[e['pid'],dev['pid']]+=1
            if task=='QueuePacket':
                seq=d['SubmitSequence'];key=(h,seq)
                n.tick(t)
                if op=='Start':
                    typ,layout=packet_type(d)
                    if lo<=t<hi:queue_schemas[e['id'],e['version'],layout]+=1
                    q=dict(t=t,pid=dev['pid'],typ=typ,fields=d,tid=e['tid'])
                    queues[key]=q
                    if target and typ in (0,1):n.pending.add(key)
                    if target and typ==4:
                        n.waits.add(key)
                        wait_packets[d['pQueuePacket']]=(key,t,d)
                    if target and typ==5:
                        for obj,val in zip(d['ObjectArray'],d['FenceValue']):
                            signals[obj].append((val,t,'GPU-signal-enqueued',e['tid']))
                elif op=='Info':
                    if key in queues:queues[key]['info']=t
                elif op=='Stop':
                    n.pending.discard(key);n.waits.discard(key)
                    q=queues.pop(key,None)
                    if q and q['typ']==4:
                        pointer=q['fields']['pQueuePacket']
                        if wait_packets.get(pointer,(None,))[0]==key:wait_packets.pop(pointer)
                    if target and q and q['typ']==5:
                        sd=q['fields']
                        for obj,val in zip(sd['ObjectArray'],sd['FenceValue']):
                            signals[obj].append((val,t,'GPU-signal-completed',q['tid']))
                    if target and lo<=t<hi:
                        preemptions['queue']+=bool(d.get('bPreempted'))
                        timeouts['queue']+=bool(d.get('bTimeouted'))
                        if q:
                            queue_latency.append(t-q['t'])
                            if q['typ']==4:
                                wait_duration.append(t-q['t'])
                                wait_details.append(dict(start=q['t'],stop=t,unwait=q.get('unwait'),context=h,sequence=seq,tid=q['tid'],fields=q['fields']))
            elif task=='DmaPacket':
                seq=d['ulQueueSubmitSequence']
                if seq==0:
                    diagnostics['zero_sequence_nonwork_dma']+=int(lo<=t<hi)
                    continue
                submission=d.get('uliSubmissionId',d.get('uliCompletionId'))
                key=(h,seq,submission)
                if op=='Start':
                    q=queues.get((h,seq))
                    if target and lo<=t<hi:
                        if q:
                            enqueue_latency.append(t-q['t'])
                        else:diagnostics['target_dma_without_queue_start']+=1
                    n.start(t,key,dev['pid'],q['t'] if q else None)
                    dma_starts[key]=dict(enqueued=t,pid=dev['pid'])
                elif op=='Info':
                    if lo<=t<hi:completion_interrupts[d['InterruptType']]+=1
                    n.complete(t,key)
                    if target and d['InterruptType']==2:n.pending.add((h,seq))
                    item=dma_starts.get(key)
                    if item is not None:item['interrupt']=t
                elif op=='Stop':
                    if target and lo<=t<hi:preemptions['dma']+=bool(d.get('bPreempted'))
                    item=dma_starts.pop(key,None)
                    if target and item and 'interrupt' in item and lo<=t<hi:
                        stop_interrupt.append(t-item['interrupt'])
            elif task=='UnwaitQueuePacket' and target:
                n.tick(t)
                item=wait_packets.pop(d['QueuePacket'],None)
                if item:
                    key,start,wd=item
                    if lo<=t<hi:unwait_duration.append(t-start)
                    if key in queues:queues[key]['unwait']=t
                elif lo<=t<hi:diagnostics['unwait_without_active_wait_packet']+=1
            elif task.startswith('WaitForSynchronizationObject') and target:
                pass
    for n in nodes.values():
        n.tick(hi)
    rows=[];span_rows=[];empty_rows=[]
    global_spans=[]
    for (adapter,node),n in nodes.items():
        if adapter not in target_adapters:continue
        meta=node_metadata.get((adapter,node),{})
        for state,ticks in n.time.items():rows.append([hex(adapter),node,meta.get('EngineType'),meta.get('FriendlyName',''),state,ticks/10000,100*ticks/(hi-lo)])
        for a,b,x in n.spans:
            if x['pid']!=16316 or not clip(a,b,lo,hi):continue
            span_rows.append([hex(adapter),node,hex(x['key'][0]),x['key'][1],x['key'][2],max(a,lo),min(b,hi),(b-a)/10000])
            global_spans.append((max(a,lo),min(b,hi)))
            if x['submitted'] is not None:dispatch_latency.append(a-x['submitted'])
        for a,b,state in n.empty:empty_rows.append([hex(adapter),node,a,b,state,(b-a)/10000])
    table(out/'node_timeline_totals.csv',['adapter','node','engine_type','friendly_name','state','ms','pct_of_window'],rows)
    table(out/'dma_fifo_spans.csv',['adapter','node','context','submit_sequence','submission_id','start_qpc','end_qpc','full_span_ms'],span_rows)
    table(out/'empty_intervals.csv',['adapter','node','start_qpc','end_qpc','state','ms'],empty_rows)
    table(out/'contexts.csv',['context','device','owner_pid','adapter','node'],
          ((hex(h),hex(c['device']),devices.get(c['device'],{}).get('pid'),hex(devices[c['device']]['adapter']) if c['device'] in devices else '',c['node']) for h,c in all_contexts.items()))
    merged=[]
    for a,b in sorted(global_spans):
        if merged and a<=merged[-1][1]:merged[-1][1]=max(b,merged[-1][1])
        else:merged.append([a,b])
    union=sum(b-a for a,b in merged)
    exact_signals=C.defaultdict(list)
    for obj,observations in signals.items():
        for value,t,source,tid in observations:exact_signals[obj,value].append((t,source,tid))
    for observations in exact_signals.values():observations.sort()
    for rec in wait_details:
        d=rec['fields']; endpoint=rec['unwait'] or rec['stop']; matches=[]
        assert rec['unwait'] is None or rec['start']<=rec['unwait']<=rec['stop'], 'Stale/reused wait packet pointer'
        for obj,value in [(d['hSyncObject'],d['FenceValue'])]:
            observations=exact_signals.get((obj,value),[])
            index=bisect.bisect_right(observations,(endpoint,chr(0x10ffff),sys.maxsize))-1
            last=observations[index] if index>=0 else None
            matches.append(dict(object=hex(obj),required_value=value,last_observed_exact_value_signal=last))
        rec['signal_observations_not_proof_of_satisfaction']=matches
    save(out/'wait_packets.json',wait_details)
    save(out/'unmapped_context_events.json',unmapped)
    save(out/'summary.json',dict(window_qpc=[lo,hi],duration_ms=(hi-lo)/10000,
         target_adapters=[hex(x) for x in target_adapters],
         diagnostic_counts=dict(diagnostics),node_diagnostics=[dict(adapter=hex(a),node=k,counts=dict(n.diagnostics),anomaly_events=n.anomaly_events,max_dma_depth=n.max_depth,unfinished_dma=len(n.queue)) for (a,k),n in nodes.items() if a in target_adapters],
         all_event_counts=[dict(task=t,opcode=o,n=n) for (t,o),n in counts.most_common()],
         target_event_counts=[dict(task=t,opcode=o,n=n) for (t,o),n in target_counts.most_common()],
         queue_start_layouts=[dict(id=i,version=v,layout=l,n=n) for (i,v,l),n in queue_schemas.items()],
         ownership_checks=[dict(event_pid=e,context_owner_pid=p,n=n) for (e,p),n in ownership.items()],
         target_preemptions=dict(preemptions),target_timeouts=dict(timeouts),interrupt_types=dict(completion_interrupts),
         target_dma_fifo_union_ms=union/10000,target_dma_fifo_union_pct=100*union/(hi-lo),
         queue_start_to_stop=stats(queue_latency),queue_start_to_dma_enqueue=stats(enqueue_latency),
         queue_start_to_inferred_running=stats(dispatch_latency),dma_interrupt_to_stop=stats(stop_interrupt),
         wait_queue_start_to_stop=stats(wait_duration),wait_queue_start_to_unwait=stats(unwait_duration),target_cpu_signal_events=cpu_signals,
         limits='DMA FIFO bounds are scheduler evidence, not hardware occupancy or shader execution timestamps. Empty-with-pending includes fence dependencies and scheduling; empty-without-pending does not prove a game CPU bottleneck. CPU/GPU fence signals are preserved, not equated to wait satisfaction.'))
    print('GPU queue replay complete; target FIFO union',100*union/(hi-lo),'percent')


def selfcheck():
    assert packet_type({'PacketType':0})==(0,'dma')
    assert packet_type({'hSyncObject':7,'FenceValue':8})==(4,'wait')
    assert packet_type({'ObjectArray':[7],'FenceValue':[8]})==(5,'signal')
    try:packet_type({'hContext':1})
    except ValueError:pass
    else:raise AssertionError('Unknown packet layout accepted')
    n=Node(10,110)
    n.pending.add((1,1)); n.start(20,(1,1,1),16316,10)
    n.start(30,(2,2,2),4,15);n.complete(50,(1,1,1));n.complete(80,(2,2,2));n.tick(110)
    assert n.time['target_dma']==30 and n.time['other_dma']==30
    assert sum(n.time.values())==100 and n.max_depth==2
    assert [(a,b) for a,b,_ in n.spans]==[(20,50),(50,80)]
    n=Node(0,100);n.start(0,(1,1,1),16316);n.start(1,(2,2,2),16316);n.complete(2,(2,2,2))
    assert n.diagnostics['out_of_order_completion']==1 and len(n.queue)==1
    assert clip(0,100,10,80)==70 and stats([])=={'n':0}
    print('GPU queue replay selfcheck PASS')


if __name__=='__main__':
    if sys.argv[1:]==['--selfcheck']:selfcheck()
    else:
        ap=argparse.ArgumentParser();ap.add_argument('analysis',type=Path);run(ap.parse_args())
