"""Passata mirata: cosa fa il thread del percorso critico dentro ntoskrnl.
Conta gli offset (RVA) di ntoskrnl.exe sul TID indicato. Nessun simbolo inventato."""
import collections, csv, os, re, subprocess, sys
XPERF=r"C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\xperf.exe"
etl,outdir,tid=sys.argv[1],sys.argv[2],sys.argv[3]
os.makedirs(outdir,exist_ok=True)
def sp(l): return [c.strip().strip('"') for c in l.split(",")]
def pn(f):
    m=re.match(r"^(.*?)\s*\(\s*(\d+)\s*\)$",f); return (m.group(1),int(m.group(2))) if m else (f,-1)
images={}; hits=collections.Counter(); mods=collections.Counter(); tot=0
p=subprocess.Popen([XPERF,"-i",etl,"-tle","-tti","-a","dumper"],stdout=subprocess.PIPE,
                   stderr=subprocess.DEVNULL,text=True,errors="replace",bufsize=1<<20)
for line in p.stdout:
    s=line.lstrip()
    if s.startswith(("I-DCStart,","I-DCEnd,","Image,")):
        c=sp(s)
        if len(c)<9 or not c[1].isdigit(): continue
        _,pid=pn(c[2])
        try: base=int(c[3],16)
        except ValueError: continue
        images.setdefault((pid,os.path.basename(c[8]).lower()),base)
    elif s.startswith("SampledProfile,"):
        c=sp(s)
        if len(c)<8 or not c[1].isdigit() or c[3]!=tid: continue
        tot+=1
        mod=c[7].split("!",1)[0].strip(); mods[mod]+=1
        if mod.lower()=="ntoskrnl.exe":
            base=images.get((0,"ntoskrnl.exe")) or images.get((4,"ntoskrnl.exe"))
            try: rva=int(c[4],16)-base if base else None
            except (TypeError,ValueError): rva=None
            if rva is not None and 0<=rva<(1<<32): hits[rva//0x1000*0x1000]+=1
p.wait()
with open(os.path.join(outdir,f"tid{tid}_modules.csv"),"w",newline="") as f:
    w=csv.writer(f); w.writerow(["module","samples","pct"])
    for m,n in mods.most_common(): w.writerow([m,n,round(100*n/tot,3)])
with open(os.path.join(outdir,f"tid{tid}_ntoskrnl_pages.csv"),"w",newline="") as f:
    w=csv.writer(f); w.writerow(["rva_page","samples","pct_of_ntoskrnl"])
    nt=sum(hits.values())
    for r,n in hits.most_common(60): w.writerow([hex(r),n,round(100*n/nt,3)])
print(f"TID {tid}: {tot:,} campioni; ntoskrnl {mods['ntoskrnl.exe']:,}; pagine kernel distinte {len(hits)}")
for r,n in hits.most_common(12): print(f"   ntoskrnl+{r:#010x}  {n:7,}  {100*n/max(1,sum(hits.values())):5.2f}%")
