<#
  Phase 1.5-A - ETW capture harness (read-only, no injection, no hooking).

  Registra WPR (CPU sampling + stack, GPU/DxgKrnl) e PresentMon insieme, attorno a una run
  di un workload avviato manualmente. Cattura di attribuzione, non braccio A/B prestazionale.

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
  [ValidateRange(1, 600)][int]$Seconds = 75,
  [ValidateRange(0, 120)][int]$PreRoll = 10,
  [string]$OutDir = "research\08_etw_fortnite\raw",
  [string]$Process = "FortniteClient-Win64-Shipping.exe",
  [string]$Tag = "fortnite",
  # Zero preserves the current interval. An explicit nonzero value is opt-in (100 ns units).
  [ValidateRange(0, 100000)][int]$ProfInt = 0,
  # Passive profiling: leave the current CPU sampling interval untouched.
  [switch]$PreserveSamplingInterval,
  [switch]$SkipPresentMon,
  [string]$PresentMonSession = "fnetw",
  # Esegue SOLO il pre-flight di PresentMon: niente WPR, niente ETL, niente countdown.
  [switch]$ValidateOnly,
  # Processo usato dal pre-flight quando il target non e' in esecuzione (dwm.exe presenta sempre).
  [string]$ValidateProcess = "dwm.exe",
  [ValidateRange(1, 60)][int]$ValidateSeconds = 8
)

$ErrorActionPreference = "Stop"
$WPT   = "C:\Program Files (x86)\Windows Kits\10\Windows Performance Toolkit"
$XPERF = Join-Path $WPT "xperf.exe"
$PM    = "C:\Program Files\Intel\PresentMon\PresentMonConsoleApplication\PresentMon-2.5.1-x64.exe"

# --- stato per il cleanup ---
$script:WprStarted   = $false
$script:ProfIntSet   = $false
$script:OriginalProfInt = $null
$script:PmProc       = $null

function Quote-Arg([string]$s) {
  # Start-Process non quota nulla: lo facciamo noi, altrimenti gli spazi spezzano gli argomenti.
  if ($s -match '[\s"]') { '"' + ($s -replace '"', '\"') + '"' } else { $s }
}

function Build-PmArgs([string]$targetProcess, [string]$csvPath, [int]$timedSeconds) {
  @("--process_name",        $targetProcess,
    "--output_file",         $csvPath,
    "--session_name",        $PresentMonSession,
    "--timed",               "$timedSeconds",
    "--terminate_after_timed",
    "--terminate_on_proc_exit",
    "--v2_metrics",
    "--qpc_time_ms",
    "--no_console_stats")
}

function Start-Pm([string[]]$pmArgs, [string]$outLog, [string]$errLog) {
  $cmdline = ($pmArgs | ForEach-Object { Quote-Arg $_ }) -join ' '
  Write-Host "COMANDO PRESENTMON:" -ForegroundColor Cyan
  Write-Host ("  `"{0}`" {1}" -f $PM, $cmdline) -ForegroundColor Gray
  $p = Start-Process -FilePath $PM -ArgumentList $cmdline -PassThru -WindowStyle Hidden `
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
    # Preserve this capture on error/Ctrl+C; never cancel or stop somebody else's recording.
    Write-Host "cleanup: salvo WPR incompleto in $base-incomplete.etl" -ForegroundColor DarkGray
    try {
      & wpr -stop "$base-incomplete.etl"
      if ($LASTEXITCODE -ne 0) { Write-Warning "WPR resta attivo: recuperare la traccia, non cancellarla." }
    } catch { Write-Warning "WPR stop fallito: registrazione lasciata attiva per recupero." }
    $script:WprStarted = $false
  }
  if ($script:ProfIntSet) {
    Write-Host "cleanup: ripristino sampling interval a $script:OriginalProfInt" -ForegroundColor DarkGray
    & $XPERF -setprofint $script:OriginalProfInt
    if ($LASTEXITCODE -ne 0) { Write-Warning "Ripristino sampling interval FALLITO." }
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
  $stamp  = Get-Date -Format "yyyyMMdd-HHmmss-fff"
  $base   = Join-Path $OutDir ("{0}-run{1}-{2}" -f $Tag, $Run, $stamp)

  # ---------- 1. PRE-FLIGHT PRESENTMON (nessun WPR, nessun ETL) ----------
  if (-not $SkipPresentMon) {
    $running   = Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($Process)) -EA SilentlyContinue
    $pfTarget  = if ($running) { $Process } else { $ValidateProcess }
    $pfCsv     = "$base-preflight-presentmon.csv"
    $pfOut     = "$base-preflight-pm-stdout.txt"
    $pfErr     = "$base-preflight-pm-stderr.txt"
    if (Test-Path $pfCsv) { throw "Output gia' esistente: $pfCsv" }

    Write-Host "=== PRE-FLIGHT PresentMon (target: $pfTarget, ${ValidateSeconds}s) ===" -ForegroundColor Cyan
    $pf = Start-Pm (Build-PmArgs $pfTarget $pfCsv $ValidateSeconds) $pfOut $pfErr
    $script:PmProc = $pf

    Start-Sleep -Seconds 3
    if ($pf.HasExited -and $pf.ExitCode -ne 0) {
      Show-PmLogs $pfOut $pfErr
      throw "PRE-FLIGHT FALLITO: PresentMon e' uscito entro 3s con exit code $($pf.ExitCode). Nessun WPR avviato, nessun countdown."
    }
    if (-not $pf.HasExited -and -not $pf.WaitForExit(($ValidateSeconds + 15) * 1000)) {
      throw "PRE-FLIGHT timeout; cleanup termina solo il nostro PresentMon."
    }
    $pf.WaitForExit()
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

  # ---------- 2. target + stato iniziale, prima di avviare registrazioni ----------
  $target = @(Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($Process)) -EA SilentlyContinue)
  if ($target.Count -ne 1) { throw "Serve una sola istanza di $Process, trovate $($target.Count)." }
  Write-Host "Target PID: $($target.Id)" -ForegroundColor Green
  $wprStatus = (& wpr -status 2>&1 | Out-String)
  $wprStatus | Set-Content "$base-wpr-status-before.txt"
  if ($LASTEXITCODE -ne 0 -or $wprStatus -notmatch 'WPR is not recording') {
    throw "WPR gia' attivo o stato non riconosciuto: nessuna sessione esistente viene fermata."
  }
  $profStatus = (& $XPERF -ProfInt 2>&1 | Out-String)
  $profStatus | Set-Content "$base-sampling-before.txt"
  if ($LASTEXITCODE -ne 0 -or $profStatus -notmatch 'Current Profile Interval\s*=\s*(\d+)') {
    throw "Impossibile verificare il sampling interval corrente."
  }
  $script:OriginalProfInt = [int]$Matches[1]
  $freeBytes = (Get-Item $OutDir).PSDrive.Free
  if ($freeBytes -lt 20GB) { throw "Meno di 20 GB liberi sul volume output: cattura non avviata." }
  $captureStarted = Get-Date
  Get-Process | Where-Object { $_.CPU -gt 1 } |
    Sort-Object CPU -Descending |
    Select-Object -First 40 Name, Id, CPU, WorkingSet64, Path |
    Export-Csv -NoTypeInformation -Path "$base-background.csv"

  # ---------- 3. WPR ----------
  if ($ProfInt -gt 0 -and -not $PreserveSamplingInterval) {
    & $XPERF -setprofint $ProfInt | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Impossibile impostare il sampling interval." }
    $script:ProfIntSet = $true
  }
  Write-Host "wpr -start CPU -start GPU -filemode ..." -ForegroundColor Cyan
  & wpr -start CPU -start GPU -filemode -recordtempto $OutDir
  if ($LASTEXITCODE -ne 0) { throw "wpr -start ha fallito (exit $LASTEXITCODE)." }
  $script:WprStarted = $true

  # ---------- 4. PresentMon per la cattura vera ----------
  if (-not $SkipPresentMon) {
    $pmOut = "$base-pm-stdout.txt"; $pmErr = "$base-pm-stderr.txt"
    $pmArgs = Build-PmArgs $Process "$base-presentmon.csv" ($Seconds + $PreRoll + 5)
    $script:PmProc = Start-Pm $pmArgs $pmOut $pmErr
    Start-Sleep -Seconds 3
    if ($script:PmProc.HasExited) {
      Show-PmLogs $pmOut $pmErr
      throw "PresentMon e' uscito subito (exit $($script:PmProc.ExitCode)). Cattura annullata."
    }
    Write-Host "PresentMon attivo (PID $($script:PmProc.Id)), sessione '$PresentMonSession'" -ForegroundColor Green
  }

  # ---------- 5. countdown + cattura ----------
  $t0 = Get-Date
  for ($i = $PreRoll; $i -gt 0; $i--) { Write-Host "  inizia il percorso fra $i s..."; Start-Sleep 1 }
  & wpr -marker "$Tag-capture-ready"
  if ($LASTEXITCODE -ne 0) { throw "WPR marker fallito." }
  Write-Host (">>> VAI - {0}, cattura di {1} s <<<" -f $Tag, $Seconds) -ForegroundColor Yellow
  for ($i = 0; $i -lt $Seconds; $i++) { Start-Sleep 1 }   # loop di 1s: Ctrl+C reagisce subito
  & wpr -marker "$Tag-capture-end"
  if ($LASTEXITCODE -ne 0) { throw "WPR marker finale fallito." }

  # ---------- 6. stop ----------
  Write-Host "wpr -stop ..." -ForegroundColor Cyan
  & wpr -stop "$base.etl"
  if ($LASTEXITCODE -ne 0) {
    # Preserve the active recording for recovery instead of cancelling its data.
    $script:WprStarted = $false
    throw "wpr -stop fallito; registrazione lasciata attiva per il recupero."
  }
  $script:WprStarted = $false
  $pmExitCode = $null
  if ($script:PmProc) {
    if (-not $script:PmProc.HasExited -and -not $script:PmProc.WaitForExit(15000)) {
      throw "PresentMon timeout dopo WPR stop; ETL preservato."
    }
    $script:PmProc.WaitForExit()
    $pmExitCode = $script:PmProc.ExitCode
    $script:PmProc = $null
  }
  & $XPERF -ProfInt | Set-Content "$base-sampling-after.txt"

  $pmRows = if (Test-Path "$base-presentmon.csv") { (Get-Content "$base-presentmon.csv" | Measure-Object -Line).Lines } else { 0 }
  if (-not $SkipPresentMon -and $pmRows -lt 2) {
    Show-PmLogs "$base-pm-stdout.txt" "$base-pm-stderr.txt"
    Write-Warning "ATTENZIONE: il CSV PresentMon ha $pmRows righe. L'ETL c'e' ma la correlazione frametime NON sara' possibile."
  }

  [pscustomobject]@{
    run = $Run; tag = $Tag; process = $Process
    started_utc = $captureStarted.ToUniversalTime().ToString("o")
    countdown_started_utc = $t0.ToUniversalTime().ToString("o")
    ended_utc = (Get-Date).ToUniversalTime().ToString("o")
    target_pid = $target.Id; purpose = "attribution only; not a performance A/B arm"
    preroll_s = $PreRoll; capture_s = $Seconds
    original_profint_100ns = $script:OriginalProfInt
    profint_100ns = $(if ($script:ProfIntSet) { $ProfInt } else { $script:OriginalProfInt })
    sampling_interval_preserved = -not $script:ProfIntSet
    presentmon_returncode = $pmExitCode; command = $pmArgs
    rows_in_csv = [math]::Max(0, $pmRows - 1); free_bytes_before = $freeBytes
    etl = "$base.etl"; presentmon = "$base-presentmon.csv"; presentmon_rows = $pmRows
    background = "$base-background.csv"; presentmon_session = $PresentMonSession
    wpr_profiles = "CPU,GPU (filemode)"
    driver_version = (Get-CimInstance Win32_VideoController | Where-Object Name -like "*Radeon*").DriverVersion
    os_build = (Get-CimInstance Win32_OperatingSystem).Version
    hags = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\GraphicsDrivers' -Name HwSchMode -EA SilentlyContinue).HwSchMode
  } | ConvertTo-Json -Depth 5 | Set-Content "$base-meta.json"

  if (-not $SkipPresentMon -and ($pmExitCode -ne 0 -or $pmRows -lt 2)) {
    throw "PresentMon fallito (exit $pmExitCode, righe $pmRows). ETL e metadata preservati."
  }
  Write-Host "OK -> $base.etl  (PresentMon: $pmRows righe)" -ForegroundColor Green
  Get-Item "$base.etl" | Select-Object Name, Length
}
finally {
  # Eseguito anche su Ctrl+C e su eccezione. Se il processo PowerShell viene ucciso
  # brutalmente questo non gira: recuperare con wpr -stop, MAI cancellare l'ETL.
  # Se richiesto un intervallo diverso, quello originale e' nel file sampling-before.
  Invoke-Cleanup
}
