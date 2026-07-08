$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"

& $Python (Join-Path $PSScriptRoot "download_test_ica_outputs.py")
& $Python (Join-Path $PSScriptRoot "compare_test_ica_mne.py")
