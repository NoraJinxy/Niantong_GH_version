$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python venv not found: $Python"
}

& $Python (Join-Path $PSScriptRoot "create_and_download_sub009_bandpass.py")
& $Python (Join-Path $PSScriptRoot "compare_sub009_bandpass_mne.py")
