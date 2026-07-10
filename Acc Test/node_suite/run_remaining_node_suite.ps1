param(
  [switch]$SkipServerRun,
  [string[]]$Case
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $Root "..\..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
Set-Location $Root

if (-not $SkipServerRun) {
  & $Python .\create_and_download_remaining_nodes.py
}

$argsList = @()
if ($Case) {
  foreach ($name in $Case) {
    $argsList += "--case"
    $argsList += $name
  }
}

& $Python .\compare_remaining_nodes_mne.py @argsList
