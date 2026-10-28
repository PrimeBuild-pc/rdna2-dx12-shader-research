"""Non-invasive frame capture for a game this project does not control.

PresentMon is an ETW consumer: it attaches to a process that is already running and reads events
Windows already emits. Nothing is injected, hooked, or written into the target. This tool never
launches the game - the operator does that by hand, through the game's own launcher - and it
refuses to start a process it was pointed at.

It records, around every capture, the state the project's rules require before any performance
claim: driver version, GPU and OS identity, the AMD shader cache inventory, the display mode, the
power plan, and every process using measurable CPU. Two snapshots, before and after, so a run
that happened during a background storm can be recognised as one rather than averaged in.

    python -B tools/capture_game.py --process Cyberpunk2077.exe --seconds 120 --label bench_run1
    python -B tools/capture_game.py --list                      # what is running that presents

Output: research/<session>/<label>/ with presentmon.csv, metadata.json and the two snapshots.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import buildv as G

ROOT = Path(__file__).resolve().parents[1]
PRESENTMON = Path(r"C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication"
                  r"\PresentMon-2.5.1-x64.exe")
CACHE = Path(os.environ["LOCALAPPDATA"]) / "AMD"


def ps(script):
    """One PowerShell call, JSON out. Read-only queries only."""
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not r.stdout.strip():
        return {"error": (r.stderr or "no output").strip()[:400]}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"raw": r.stdout.strip()[:2000]}


def cache_state():
    """Inventory of the AMD shader caches: counts, bytes and the newest mtime per directory.

    Read-only. The project never deletes or replaces these files.
    """
    out = {}
    for name in ("DxCache", "DxcCache", "DX9Cache"):
        d = CACHE / name
        if not d.is_dir():
            out[name] = None
            continue
        files = [f for f in d.rglob("*") if f.is_file()]
        out[name] = dict(files=len(files), bytes=sum(f.stat().st_size for f in files),
                         newest_mtime=(max((f.stat().st_mtime for f in files), default=None)))
    return out


def snapshot(when):
    return dict(
        when=when,
        timestamp=datetime.now().astimezone().isoformat(),
        gpu=ps("Get-CimInstance Win32_VideoController | "
               "Select-Object Name,DriverVersion,DriverDate,VideoModeDescription,"
               "CurrentRefreshRate,AdapterRAM | ConvertTo-Json -Compress"),
        os=ps("$o = Get-CimInstance Win32_OperatingSystem; "
              "[pscustomobject]@{Caption=$o.Caption;Version=$o.Version;"
              "BuildNumber=$o.BuildNumber;FreePhysicalMemoryKB=$o.FreePhysicalMemory} | "
              "ConvertTo-Json -Compress"),
        power_plan=ps("$p = powercfg /getactivescheme; "
                      "[pscustomobject]@{scheme=\"$p\"} | ConvertTo-Json -Compress"),
        # Every process above a tenth of a core-second of CPU, so a background storm during a run
        # is visible afterwards instead of being averaged into the result.
        busy_processes=ps("Get-Process | Where-Object { $_.CPU -gt 0.1 } | "
                          "Sort-Object CPU -Descending | Select-Object -First 25 "
                          "Name,Id,CPU,WorkingSet64 | ConvertTo-Json -Compress"),
        amd_cache=cache_state(),
    )


def list_targets():
    out = ps("Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | "
             "Select-Object Name,Id,MainWindowTitle | ConvertTo-Json -Compress")
    print(json.dumps(out, indent=2))


def capture(process, seconds, label, session, delay):
    G.require(PRESENTMON.is_file(), f"PresentMon not found at {PRESENTMON}")
    G.require(not process.lower().endswith((".bat", ".cmd")), "target must be an exe name")

    out = ROOT / "research" / session / label
    G.require(not out.exists(), f"{out} already exists; pick another label")
    out.mkdir(parents=True)

    before = snapshot("before")
    running = ps(f"@(Get-Process -Name '{Path(process).stem}' -ErrorAction SilentlyContinue).Count")
    G.require(isinstance(running, int) and running > 0,
              f"{process} is not running. This tool never launches the target: start the game "
              f"by hand, get it to the scene you want to measure, then run this again.")

    cmd = [str(PRESENTMON), "--process_name", process, "--timed", str(seconds),
           # v1 metrics, not v2: the project's existing Fortnite and Steel Nomad baselines are
           # in that schema (MsBetweenPresents, MsGPUBusy, ...) and tools/pmparse.py was
           # validated against them on 14 of 14 files. A new capture has to be comparable with
           # what is already on disk.
           "--output_file", str(out / "presentmon.csv"), "--v1_metrics",
           "--no_console_stats", "--qpc_time_ms", "--terminate_on_proc_exit",
           # Without --terminate_after_timed, --timed only stops the recording and PresentMon
           # keeps running; --stop_existing_session recovers from a previous run left behind.
           "--terminate_after_timed", "--stop_existing_session"]
    if delay:
        cmd += ["--delay", str(delay)]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=seconds + delay + 300)
    elapsed = time.time() - t0
    (out / "presentmon.log").write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
    after = snapshot("after")

    csv = out / "presentmon.csv"
    frames = max(0, sum(1 for _ in csv.open(encoding="utf-8", errors="replace")) - 1) if csv.is_file() else 0
    G.save_json(out / "metadata.json", dict(
        label=label, session=session, target_process=process,
        requested_seconds=seconds, delay_seconds=delay, elapsed_seconds=round(elapsed, 2),
        presentmon=str(PRESENTMON), presentmon_returncode=proc.returncode,
        rows_in_csv=frames, command=cmd,
        launched_by_this_tool=False,
        invasiveness="ETW consumer only: no injection, no hooking, no file or registry change, "
                     "no modification of the target process",
        before=before, after=after))
    print(f"{label}: {frames} rows, {elapsed:.1f} s, exit {proc.returncode} -> "
          f"{csv.relative_to(ROOT) if csv.is_file() else 'NO CSV'}", flush=True)
    if frames == 0:
        print("  no frames captured: check that the target is presenting and that this shell "
              "is elevated enough for ETW", flush=True)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--process")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--label")
    ap.add_argument("--session", default="60_c2077")
    ap.add_argument("--delay", type=int, default=0)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        list_targets()
    else:
        G.require(a.process and a.label, "--process and --label are required")
        capture(a.process, a.seconds, a.label, a.session, a.delay)
