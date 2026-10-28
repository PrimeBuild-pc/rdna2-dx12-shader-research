"""Phase 1A - project + system inventory. Read-only."""
import json, os, subprocess, hashlib, sys

OUT = "research/00_inventory"
os.makedirs(OUT, exist_ok=True)
PS = ["powershell", "-NoProfile", "-Command"]


def ps(cmd):
    r = subprocess.run(PS + [cmd], capture_output=True, text=True)
    return r.stdout.strip()


def psjson(cmd):
    t = ps(cmd + " | ConvertTo-Json -Depth 4 -Compress")
    try:
        return json.loads(t) if t else None
    except Exception:
        return {"_raw": t}


# --- project tree ---
lines = []
for root, dirs, files in os.walk("."):
    if any(p in root for p in (".git", "__pycache__")):
        continue
    depth = root.count(os.sep)
    if depth > 4:
        dirs[:] = []
        continue
    lines.append(f"{'  ' * depth}{os.path.basename(root) or '.'}/")
    if depth >= 4:
        continue
    for f in sorted(files)[:60]:
        try:
            sz = os.path.getsize(os.path.join(root, f))
        except OSError:
            sz = -1
        lines.append(f"{'  ' * (depth + 1)}{f}  ({sz:,} B)")
    if len(files) > 60:
        lines.append(f"{'  ' * (depth + 1)}... +{len(files) - 60} altri file")
open(os.path.join(OUT, "project_tree.txt"), "w", encoding="utf-8").write("\n".join(lines))

# --- hardware ---
hw = dict(
    cpu=psjson("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,"
               "NumberOfLogicalProcessors,MaxClockSpeed,L3CacheSize,ProcessorId"),
    baseboard=psjson("Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version"),
    bios=psjson("Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate"),
    memory_modules=psjson("Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,"
                          "ConfiguredClockSpeed,Manufacturer,PartNumber"),
    total_ram_bytes=psjson("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"),
    disks=psjson("Get-CimInstance Win32_DiskDrive | Select-Object Model,Size,InterfaceType"),
)
json.dump(hw, open(os.path.join(OUT, "hardware_info.json"), "w"), indent=1)

# --- windows ---
win = dict(
    os=psjson("Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,"
              "OSArchitecture,InstallDate,LastBootUpTime"),
    ubr=ps(r"(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR"),
    display_version=ps(r"(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion"),
    hags=ps(r"(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name HwSchMode -EA SilentlyContinue).HwSchMode"),
    game_dvr=ps(r"(Get-ItemProperty 'HKCU:\System\GameConfigStore' -Name GameDVR_Enabled -EA SilentlyContinue).GameDVR_Enabled"),
    power_plan=ps("(Get-CimInstance -Namespace root\\cimv2\\power -ClassName Win32_PowerPlan -Filter \"IsActive=True\").ElementName"),
    defender_rtp=ps("(Get-MpPreference).DisableRealtimeMonitoring"),
)
json.dump(win, open(os.path.join(OUT, "windows_info.json"), "w"), indent=1)

# --- gpu ---
gpu = dict(
    video_controllers=psjson("Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,"
                             "DriverDate,VideoProcessor,AdapterRAM,VideoModeDescription,PNPDeviceID,Status"),
    driverstore=psjson("Get-ChildItem 'C:\\Windows\\System32\\DriverStore\\FileRepository' -Directory "
                       "-Filter 'u0*.inf_amd64_*' | Select-Object Name,FullName,LastWriteTime"),
    monitors=psjson("Get-CimInstance -Namespace root\\wmi WmiMonitorBasicDisplayParams -EA SilentlyContinue "
                    "| Select-Object InstanceName,MaxHorizontalImageSize,MaxVerticalImageSize"),
)
# hash the live D3D12 UMD in the driver store, for comparison with the package copy
live = []
for root, _, files in os.walk("C:/Windows/System32/DriverStore/FileRepository"):
    if "u0" not in root.lower():
        continue
    for f in files:
        if f.lower() in ("amdxc64.dll", "amdxcstub64.dll", "amdkmdag.sys", "amdxcffx64.dll",
                         "amdxx64.dll", "amdvlk64.dll", "atio6axx.dll"):
            p = os.path.join(root, f)
            try:
                h = hashlib.sha256(open(p, "rb").read()).hexdigest()
                live.append(dict(path=p.replace("\\", "/"), size=os.path.getsize(p), sha256=h))
            except Exception as e:
                live.append(dict(path=p.replace("\\", "/"), error=str(e)))
gpu["installed_binaries"] = live
json.dump(gpu, open(os.path.join(OUT, "gpu_info.json"), "w"), indent=1)

print("wrote", os.listdir(OUT))
for k in ("cpu", "baseboard"):
    print(k, hw[k])
print("gpu", gpu["video_controllers"])
print("installed binaries:", len(live))
