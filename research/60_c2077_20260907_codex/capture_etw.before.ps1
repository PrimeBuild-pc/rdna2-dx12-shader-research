<#
  Phase 1.5-A - ETW capture harness (read-only, no injection, no hooking).

  Registra WPR (CPU sampling + stack, GPU/DxgKrnl) e PresentMon insieme, attorno a una run
  del solito percorso Creative.

  RICHIEDE PowerShell ELEVATA. Non scrive nulla nel gioco, nel package driver o nel
  DriverStore: solo dentro -OutDir.

  Uso:
      .\tools\capture_etw.ps1 -ValidateOnly          # <-- fai SEMPRE questo per primo
      .\tools\capture_etw.ps1 -Run 4 -Seconds 60 -ProfInt 2441

  Sequenza:
    1. pre-flight: avvia PresentMon e verifica che resti vivo e produca righe. Se fallisce,
       stampa stdout/stderr completi e ESCE con errore, senza avviare WPR e senza countdown.
    2. avvia WPR, poi PresentMon per la cattura vera
    3. countdown -PreRoll secondi -> ALT-TAB nel gioco e parti col percorso
    4. si ferma da solo dopo -Seconds

  STORICO BUG (2026-09-04): Start-Process -ArgumentList NON quota gli argomenti contenenti
  spazi. Con il progetto in "...\driver mod\..." PresentMon riceveva
  `--output_file C:\Users\Lorenzo\Downloads\driver` e poi `mod\research\...` come opzione
  ignota, uscendo con exit 1:
      error: unrecognized option 'mod\research\08_etw_fortnite\raw\...-presentmon.csv'.
  Ha fatto fallire silenziosamente le run 1-3 e la run 4. NON era PresentMonService, NON era
  una collisione di sessione ETW, NON era WPR: tutti e tre verificati innocenti.
  Fix: quoting esplicito in Quote-Arg + pre-flight che fallisce forte.
#>
[CmdletBinding()]
param(
  [int]$Run = 1,
  [int]$Seconds = 75,
  [int]$PreRoll = 10,
  [string]$OutDir = "research\08_etw_fortnite\raw",
  [string]$Process = "FortniteClient-Win64-Shipping.exe",
  [string]$Tag = "fortnite",
  # Sampling a 8 kHz (unita' = 100 ns). Default 10000 = 1 kHz, troppo grezzo a 600 FPS.
  # 2441 = ~4 kHz, dimezza la dimensione dell'ETL restando abbondante.
  [int]$ProfInt = 1221,
  [switch]$SkipPresentMon,
  [string]$PresentMonSession = "fnetw",
  # Esegue SOLO il pre-flight di PresentMon: niente WPR, niente ETL, niente countdown.
  [switch]$ValidateOnly,
  # Processo usato dal pre-flight quando il target non e' in esecuzione (dwm.exe presenta sempre).
  [string]$ValidateProcess = "dwm.exe",
  [int]$ValidateSeconds = 8
)

$ErrorActionPreference = "Stop"
$WPT   = "C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit"
$XPERF = Join-Path $WPT "xperf.exe"
$PM    = "C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication\PresentMon-2.5.1-x64.exe"

# --- stato per il cleanup ---
$script:WprStarted   = $false
$script:ProfIntSet   = $false
$script:PmProc       = $null

function Quote-Arg([string]$s) {
  # Start-Process non quota nulla: lo facciamo noi, altrimenti gli spazi spezzano gli argomenti.
  if ($s -match '[\s"]') { '"' + ($s -replace '"', '\"') + '"' } else { $s }
}

function Build-PmArgs([string]$targetProcess, [string]$csvPath, [int]$timedSeconds) {
  @("--process_name",        $targetProcess,
    "--output_file",         $csvPath,
    "--session_name",        $PresentMonSession,
    "--stop_existing_session",
    "--timed",               "$timedSeconds",
    "--terminate_after_timed",
    "--qpc_time",
    "--no_console_stats")
}

function Start-Pm([string[]]$pmArgs, [string]$outLog, [string]$errLog) {
  $cmdline = ($pmArgs | ForEach-Object { Quote-Arg $_ }) -join ' '
  Write-Host "COMANDO PRESENTMON:" -ForegroundColor Cyan
  Write-Host ("  `"{0}`" {1}" -f $PM, $cmdline) -ForegroundColor Gray
  $p = Start-Process -FilePath $PM -ArgumentList $cmdline -PassThru -WindowStyle Minimized `
                     -RedirectStandardOutput $outLog -RedirectStandardError $errLog
  # Senza toccare .Handle subito, PowerShell non cachea l'handle e .ExitCode resta $null
  # dopo l'uscita del processo. Questo e' il motivo per cui il primo pre-flight riportava
  # "exit code ." invece di 0.
  $null = $p.Handle
  $p
}

function Show-PmLogs([string]$outLog, [string]$errLog) {
  Write-Host "--- PresentMon STDOUT ---" -ForegroundColor Yellow
  if (Test-Path $outLog) { Get-Content $outLog | Write-Host } else { Write-Host "(vuoto)" }
  Write-Host "--- PresentMon STDERR ---" -ForegroundColor Yellow
  if (Test-Path $errLog) { Get-Content $errLog | Write-Host } else { Write-Host "(vuoto)" }
}

function Invoke-Cleanup {
  if ($script:PmProc -and -not $script:PmProc.HasExited) {
    Write-Host "cleanup: chiudo PresentMon (PID $($script:PmProc.Id))" -ForegroundColor DarkGray
    try { $script:PmProc.Kill(); $script:PmProc.WaitForExit(5000) } catch {}
  }
  if ($script:WprStarted) {
    Write-Host "cleanup: wpr -cancel" -ForegroundColor DarkGray
    try { & wpr -cancel 2>&1 | Out-Null } catch {}
    $script:WprStarted = $false
  }
  if ($script:ProfIntSet) {
    Write-Host "cleanup: ripristino sampling interval a 10000 (1 kHz)" -ForegroundColor DarkGray
    try { & $XPERF -setprofint 10000 2>&1 | Out-Null } catch {}
    $script:ProfIntSet = $false
  }
}

# ============================ MAIN ============================
try {
  if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Serve una PowerShell ELEVATA (WPR richiede admin)."
  }
  New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
  $OutDir = (Resolve-Path $OutDir).Path
  $stamp  = Get-Date -Format "yyyyMMdd-HHmmss"
  $base   = Join-Path $OutDir ("{0}-run{1}-{2}" -f $Tag, $Run, $stamp)

  # ---------- 1. PRE-FLIGHT PRESENTMON (nessun WPR, nessun ETL) ----------
  if (-not $SkipPresentMon) {
    $running   = Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($Process)) -EA SilentlyContinue
    $pfTarget  = if ($running) { $Process } else { $ValidateProcess }
    $pfCsv     = Join-Path $OutDir "_preflight-presentmon.csv"
    $pfOut     = Join-Path $OutDir "_preflight-pm-stdout.txt"
    $pfErr     = Join-Path $OutDir "_preflight-pm-stderr.txt"
    Remove-Item $pfCsv, $pfOut, $pfErr -EA SilentlyContinue

    Write-Host "=== PRE-FLIGHT PresentMon (target: $pfTarget, ${ValidateSeconds}s) ===" -ForegroundColor Cyan
    $pf = Start-Pm (Build-PmArgs $pfTarget $pfCsv $ValidateSeconds) $pfOut $pfErr
    $script:PmProc = $pf

    Start-Sleep -Seconds 3
    if ($pf.HasExited -and $pf.ExitCode -ne 0) {
      Show-PmLogs $pfOut $pfErr
      throw "PRE-FLIGHT FALLITO: PresentMon e' uscito entro 3s con exit code $($pf.ExitCode). Nessun WPR avviato, nessun countdown."
    }
    if (-not $pf.HasExited) { $pf.WaitForExit(($ValidateSeconds + 15) * 1000) | Out-Null }
    $script:PmProc = $null

    if ($pf.ExitCode -ne 0) {
      Show-PmLogs $pfOut $pfErr
      throw "PRE-FLIGHT FALLITO: PresentMon exit code $($pf.ExitCode)."
    }
    $pfRows = if (Test-Path $pfCsv) { (Get-Content $pfCsv | Measure-Object -Line).Lines } else { 0 }
    if ($pfRows -lt 2) {
      Show-PmLogs $pfOut $pfErr
      throw "PRE-FLIGHT FALLITO: nessun CSV utile ($pfRows righe in '$pfCsv'). Nessun WPR avviato."
    }
    Write-Host "PRE-FLIGHT OK: $pfRows righe in $pfCsv" -ForegroundColor Green
    Show-PmLogs $pfOut $pfErr
  }

  if ($ValidateOnly) {
    Write-Host "`n-ValidateOnly: mi fermo qui. Nessun WPR avviato, nessun ETL scritto." -ForegroundColor Green
    return
  }

  # ---------- 2. snapshot processi in background ----------
  Get-Process | Where-Object { $_.CPU -gt 1 } |
    Sort-Object CPU -Descending |
    Select-Object -First 40 Name, Id, CPU, WorkingSet64, Path |
    Export-Csv -NoTypeInformation -Path "$base-background.csv"

  $target = Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($Process)) -EA SilentlyContinue
  if (-not $target) { throw "$Process non e' in esecuzione: avvialo e mettiti in partita prima di catturare." }
  Write-Host ("Target PID: {0}" -f ($target.Id -join ",")) -ForegroundColor Green

  # ---------- 3. WPR ----------
  & $XPERF -setprofint $ProfInt | Out-Null
  $script:ProfIntSet = $true
  Write-Host "wpr -start CPU -start GPU -filemode ..." -ForegroundColor Cyan
  & wpr -start CPU -start GPU -filemode -recordtempto $OutDir
  if ($LASTEXITCODE -ne 0) { throw "wpr -start ha fallito (exit $LASTEXITCODE)." }
  $script:WprStarted = $true

  # ---------- 4. PresentMon per la cattura vera ----------
  if (-not $SkipPresentMon) {
    $pmOut = "$base-pm-stdout.txt"; $pmErr = "$base-pm-stderr.txt"
    $script:PmProc = Start-Pm (Build-PmArgs $Process "$base-presentmon.csv" ($Seconds + $PreRoll + 5)) $pmOut $pmErr
    Start-Sleep -Seconds 3
    if ($script:PmProc.HasExited -and $script:PmProc.ExitCode -ne 0) {
      Show-PmLogs $pmOut $pmErr
      throw "PresentMon e' uscito subito (exit $($script:PmProc.ExitCode)). Cattura annullata."
    }
    Write-Host "PresentMon attivo (PID $($script:PmProc.Id)), sessione '$PresentMonSession'" -ForegroundColor Green
  }

  # ---------- 5. countdown + cattura ----------
  $t0 = Get-Date
  for ($i = $PreRoll; $i -gt 0; $i--) { Write-Host "  inizia il percorso fra $i s..."; Start-Sleep 1 }
  Write-Host (">>> VAI - percorso Creative, {0} s <<<" -f $Seconds) -ForegroundColor Yellow
  for ($i = 0; $i -lt $Seconds; $i++) { Start-Sleep 1 }   # loop di 1s: Ctrl+C reagisce subito

  # ---------- 6. stop ----------
  Write-Host "wpr -stop ..." -ForegroundColor Cyan
  & wpr -stop "$base.etl"
  $script:WprStarted = $false
  if ($script:PmProc -and -not $script:PmProc.HasExited) { $script:PmProc.WaitForExit(15000) | Out-Null }
  $script:PmProc = $null

  $pmRows = if (Test-Path "$base-presentmon.csv") { (Get-Content "$base-presentmon.csv" | Measure-Object -Line).Lines } else { 0 }
  if (-not $SkipPresentMon -and $pmRows -lt 2) {
    Show-PmLogs "$base-pm-stdout.txt" "$base-pm-stderr.txt"
    Write-Warning "ATTENZIONE: il CSV PresentMon ha $pmRows righe. L'ETL c'e' ma la correlazione frametime NON sara' possibile."
  }

  [pscustomobject]@{
    run = $Run; tag = $Tag; process = $Process
    started_utc = $t0.ToUniversalTime().ToString("o")
    preroll_s = $PreRoll; capture_s = $Seconds; profint_100ns = $ProfInt
    etl = "$base.etl"; presentmon = "$base-presentmon.csv"; presentmon_rows = $pmRows
    background = "$base-background.csv"; presentmon_session = $PresentMonSession
    wpr_profiles = "CPU,GPU (filemode)"
    driver_version = (Get-CimInstance Win32_VideoController | Where-Object Name -like "*Radeon*").DriverVersion
    os_build = (Get-CimInstance Win32_OperatingSystem).Version
    hags = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name HwSchMode -EA SilentlyContinue).HwSchMode
  } | ConvertTo-Json | Set-Content "$base-meta.json"

  Write-Host "OK -> $base.etl  (PresentMon: $pmRows righe)" -ForegroundColor Green
  Get-Item "$base.etl" | Select-Object Name, Length
}
finally {
  # Eseguito anche su Ctrl+C e su eccezione. Se il processo PowerShell viene ucciso
  # brutalmente questo non gira: in quel caso  wpr -cancel  e  xperf -setprofint 10000  a mano.
  Invoke-Cleanup
}
