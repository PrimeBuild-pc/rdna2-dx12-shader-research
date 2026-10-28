$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
  (Join-Path $PSScriptRoot 'capture_etw.ps1'), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
# Load only pure functions; this check never starts WPR, changes sampling, or launches a process.
$ast.FindAll({param($n)
  $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
  $n.Name -in @('Quote-Arg', 'Build-PmArgs')
}, $true) | ForEach-Object { Invoke-Expression $_.Extent.Text }
$PresentMonSession = 'c2077_test'
$a = Build-PmArgs 'Cyberpunk2077.exe' 'C:\path with spaces\test.csv' 150
foreach ($required in @('--v2_metrics', '--qpc_time_ms', '--terminate_on_proc_exit', '--terminate_after_timed')) {
  if ($required -notin $a) { throw "Missing $required" }
}
if ('--stop_existing_session' -in $a -or '--qpc_time' -in $a) { throw 'Unsafe/incompatible PM args' }
if ((Quote-Arg 'a b') -ne '"a b"') { throw 'Space quoting failed' }
if ((Quote-Arg 'abc') -ne 'abc') { throw 'Plain argument quoting failed' }
if ($a[$a.IndexOf('--output_file')+1] -ne 'C:\path with spaces\test.csv') { throw 'Output path changed' }
if ($ast.Extent.Text -match '& wpr -cancel') { throw 'Cleanup must preserve recorded data' }
Write-Host 'capture harness syntax/arguments/cleanup selfcheck PASS'
