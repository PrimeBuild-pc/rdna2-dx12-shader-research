"""Phase 1.5-A - module-level CPU attribution from an ETW/WPR trace.

Streams `xperf -a dumper` output and aggregates in memory: never writes the multi-GB
text dump. Module attribution needs no symbols; function names are only emitted when
xperf itself resolved them (never invented).

    python tools/etw_analyze.py <trace.etl> <outdir> [--process FortniteClient-Win64-Shipping.exe]
"""
import argparse, collections, csv, os, re, subprocess, sys

XPERF = r"C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit\xperf.exe"
AMD_MODULES = ("amdxc64.dll", "amdxc32.dll", "amdxx64.dll", "amdxn64.dll", "amdkmdag.sys",
               "amdxcffx64.dll", "amdxcstub64.dll", "atiadlxx.dll", "amdihk64.dll",
               "amdvlk64.dll", "atio6axx.dll")
D3D_MODULES = ("d3d12.dll", "d3d12core.dll", "dxgi.dll", "d3d11.dll", "dxcore.dll",
               "d3d10warp.dll", "dxilconv.dll")


def split(line):
    return [c.strip().strip('"') for c in line.split(",")]


def proc_name(field):
    """'Fortnite.exe ( 1234)' -> ('Fortnite.exe', 1234)"""
    m = re.match(r"^(.*?)\s*\(\s*(\d+)\s*\)$", field)
    return (m.group(1), int(m.group(2))) if m else (field, -1)


def module_of(imgfunc):
    """'amdxc64.dll!0x00007ff...' -> ('amdxc64.dll', '0x00007ff...')"""
    if "!" in imgfunc:
        mod, fn = imgfunc.split("!", 1)
        return mod.strip(), fn.strip()
    return imgfunc.strip(), ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("etl")
    ap.add_argument("outdir")
    ap.add_argument("--process", default=None, help="attribuisci solo questo processo")
    ap.add_argument("--xperf", default=XPERF)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    samples = collections.Counter()        # (proc, pid, tid, module) -> n
    thread_start = {}                      # (proc,pid,tid) -> ThreadStartImage!Function
    fn_hits = collections.Counter()        # (proc, module, resolved_function) -> n
    addr_hits = collections.Counter()      # (proc, module, absolute pc) -> n
    images = {}                            # (pid, module) -> (base, end, path)
    cswitch_in = collections.Counter()     # (proc,pid,tid) -> switches in
    waits = collections.Counter()          # (proc,pid,tid,reason) -> n
    timeline = collections.Counter()       # (second, proc, module) -> n
    t_min, t_max = None, None

    cmd = [a.xperf, "-i", a.etl, "-tle", "-tti", "-a", "dumper"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, errors="replace", bufsize=1 << 20)
    n_lines = 0
    for line in p.stdout:
        n_lines += 1
        s = line.lstrip()
        if s.startswith("SampledProfile,"):
            c = split(s)
            if len(c) < 8 or not c[1].isdigit():
                continue
            ts = int(c[1])
            pname, pid = proc_name(c[2])
            if a.process and pname.lower() != a.process.lower():
                continue
            t_min = ts if t_min is None else min(t_min, ts)
            t_max = ts if t_max is None else max(t_max, ts)
            tid = c[3]
            pc = c[4]
            mod, fn = module_of(c[7])
            samples[(pname, pid, tid, mod)] += 1
            thread_start.setdefault((pname, pid, tid), c[6])
            if fn and not fn.startswith("0x"):
                fn_hits[(pname, mod, fn)] += 1
            if mod.lower() in AMD_MODULES:
                addr_hits[(pname, pid, mod, pc)] += 1
            timeline[(ts // 1000000, pname, mod)] += 1
        elif s.startswith(("I-DCStart,", "I-DCEnd,", "Image,", "ImageId,")):
            c = split(s)
            if len(c) < 9 or not c[1].isdigit():
                continue
            _, pid = proc_name(c[2])
            try:
                base, end = int(c[3], 16), int(c[4], 16)
            except ValueError:
                continue
            path = c[8]
            images.setdefault((pid, os.path.basename(path).lower()), (base, end, path))
        elif s.startswith("CSwitch,"):
            c = split(s)
            if len(c) < 14 or not c[1].isdigit():
                continue
            npn, npid = proc_name(c[2])
            if not a.process or npn.lower() == a.process.lower():
                cswitch_in[(npn, npid, c[3])] += 1
            opn, opid = proc_name(c[8])
            if not a.process or opn.lower() == a.process.lower():
                waits[(opn, opid, c[9], c[13])] += 1
    p.wait()

    dur_s = (t_max - t_min) / 1e6 if t_min is not None and t_max is not None else 0.0
    total = sum(samples.values())

    # ---------- cpu_module_attribution.csv ----------
    per_proc = collections.Counter()
    per_proc_mod = collections.Counter()
    for (pn, pid, tid, mod), n in samples.items():
        per_proc[pn] += n
        per_proc_mod[(pn, mod)] += n
    with open(os.path.join(a.outdir, "cpu_module_attribution.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["process", "module", "samples", "pct_of_process", "pct_of_trace",
                    "bucket", "est_ms_per_s_of_one_core"])
        for (pn, mod), n in sorted(per_proc_mod.items(), key=lambda x: -x[1]):
            ml = mod.lower()
            bucket = ("amd_driver" if ml in AMD_MODULES else
                      "d3d_runtime" if ml in D3D_MODULES else
                      "os_kernel" if ml.endswith((".sys", "ntoskrnl.exe", "hal.dll")) else
                      "os_usermode" if ml in ("ntdll.dll", "kernelbase.dll", "kernel32.dll",
                                              "user32.dll", "win32u.dll", "gdi32.dll") else
                      "app_or_other")
            w.writerow([pn, mod, n, round(100 * n / per_proc[pn], 4),
                        round(100 * n / total, 4) if total else "",
                        bucket, round(1000 * n / dur_s / 1000, 4) if dur_s else ""])

    # ---------- hot_threads.csv ----------
    per_thread = collections.Counter()
    thread_mod = collections.defaultdict(collections.Counter)
    for (pn, pid, tid, mod), n in samples.items():
        per_thread[(pn, pid, tid)] += n
        thread_mod[(pn, pid, tid)][mod] += n
    with open(os.path.join(a.outdir, "hot_threads.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["process", "pid", "tid", "samples", "pct_of_process", "thread_start",
                    "context_switches_in", "top_modules"])
        for (pn, pid, tid), n in sorted(per_thread.items(), key=lambda x: -x[1])[:200]:
            top = "; ".join(f"{m}:{c}" for m, c in thread_mod[(pn, pid, tid)].most_common(6))
            w.writerow([pn, pid, tid, n, round(100 * n / per_proc[pn], 3),
                        thread_start.get((pn, pid, tid), ""),
                        cswitch_in.get((pn, pid, tid), 0), top])

    # ---------- amdxc64_hot_offsets.csv ----------
    with open(os.path.join(a.outdir, "amdxc64_hot_offsets.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["process", "module", "module_base", "abs_pc", "rva", "samples",
                    "pct_of_module", "module_path"])
        mod_tot = collections.Counter()
        for (pn, pid, mod, pc), n in addr_hits.items():
            mod_tot[(pn, mod)] += n
        rows = []
        for (pn, pid, mod, pc), n in addr_hits.items():
            base, end, path = images.get((pid, mod.lower()), (None, None, ""))
            if base is None:  # kernel modules load under pid 0 / Idle
                base, end, path = images.get((0, mod.lower()), (None, None, ""))
            try:
                rva = int(pc, 16) - base if base else None
            except (TypeError, ValueError):
                rva = None
            rows.append([pn, mod, hex(base) if base else "", pc,
                         hex(rva) if rva is not None and 0 <= rva < (1 << 32) else "", n,
                         round(100 * n / mod_tot[(pn, mod)], 3), path])
        rows.sort(key=lambda r: -r[5])
        w.writerows(rows[:5000])

    # ---------- waits ----------
    with open(os.path.join(a.outdir, "thread_waits.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["process", "pid", "tid", "wait_reason", "count"])
        for (pn, pid, tid, reason), n in sorted(waits.items(), key=lambda x: -x[1])[:500]:
            w.writerow([pn, pid, tid, reason, n])

    # ---------- per-second timeline (for gross correlation with PresentMon) ----------
    with open(os.path.join(a.outdir, "module_timeline_1s.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["second", "process", "module", "samples"])
        for (sec, pn, mod), n in sorted(timeline.items()):
            w.writerow([sec, pn, mod, n])

    # ---------- resolved function names, only where xperf resolved them ----------
    if fn_hits:
        with open(os.path.join(a.outdir, "resolved_functions.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["process", "module", "function", "samples"])
            for (pn, mod, fn), n in sorted(fn_hits.items(), key=lambda x: -x[1])[:2000]:
                w.writerow([pn, mod, fn, n])

    print(f"lines={n_lines:,} samples={total:,} duration={dur_s:.2f}s "
          f"processes={len(per_proc)} images={len(images)}")
    for pn, n in per_proc.most_common(8):
        print(f"  {pn:42s} {n:8,} samples")
    return 0


if __name__ == "__main__":
    sys.exit(main())
