#requires -Version 5
# ELYS local static-check gate. Run before deploy_remote.
#   Default : backend Python compile (compileall) + frontend TypeScript typecheck (vue-tsc)
#   -Docs   : also run `mkdocs build` in wiki/
#   -Pytest : also run local pytest (NOTE: real pytest needs DB/services; cloud elys_debug is authoritative)
# Exit code 0 = all green; non-zero = something failed, do not deploy.
param(
  [switch]$Docs,
  [switch]$Pytest
)

$repo     = (Resolve-Path "$PSScriptRoot\..\..").Path
$backend  = Join-Path $repo 'elys_project\backend'
$frontend = Join-Path $repo 'elys_project\frontend\elys-web'
$wiki     = Join-Path $repo 'wiki'
$failures = @()
$localVenvPython = Join-Path $repo '.venv\Scripts\python.exe'
$pythonExe = $null
if(Test-Path $localVenvPython){
  $pythonExe = $localVenvPython
} else {
  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if($pythonCmd){ $pythonExe = $pythonCmd.Source }
}

function Section($name){ Write-Host ''; Write-Host ('  ' + ([string][char]0x2500) * 2 + " $name " + ([string][char]0x2500) * 2) -ForegroundColor DarkGray }

Section 'Backend: Python compile (compileall)'
if($pythonExe){
  Write-Host ("[INFO] python: {0}" -f $pythonExe) -ForegroundColor DarkGray
  & $pythonExe -m compileall -q (Join-Path $backend 'app')
  if($LASTEXITCODE -ne 0){ $failures += 'backend py_compile'; Write-Host '[FAIL] backend compile' -ForegroundColor Red }
  else { Write-Host '[OK] backend compile' -ForegroundColor Green }
} else {
  $failures += 'backend py_compile (python missing)'; Write-Host '[FAIL] python not found on PATH' -ForegroundColor Red
}

Section 'Frontend: TypeScript typecheck (vue-tsc)'
if(Test-Path (Join-Path $frontend 'node_modules')){
  Push-Location $frontend
  npm run typecheck
  if($LASTEXITCODE -ne 0){ $failures += 'frontend typecheck'; Write-Host '[FAIL] frontend typecheck' -ForegroundColor Red }
  else { Write-Host '[OK] frontend typecheck' -ForegroundColor Green }
  Pop-Location
} else {
  $failures += 'frontend typecheck (node_modules missing)'; Write-Host '[FAIL] node_modules missing -> run: npm install' -ForegroundColor Red
}

Section 'Frontend: unit tests (vitest)'
if(Test-Path (Join-Path $frontend 'node_modules')){
  Push-Location $frontend
  npx vitest run --passWithNoTests
  if($LASTEXITCODE -ne 0){ $failures += 'frontend unit tests'; Write-Host '[FAIL] frontend unit tests' -ForegroundColor Red }
  else { Write-Host '[OK] frontend unit tests' -ForegroundColor Green }
  Pop-Location
} else {
  $failures += 'frontend unit tests (node_modules missing)'; Write-Host '[FAIL] node_modules missing -> run: npm install' -ForegroundColor Red
}

if($Docs){
  Section 'Docs: mkdocs build'
  if(Get-Command mkdocs -ErrorAction SilentlyContinue){
    Push-Location $wiki
    mkdocs build --clean
    if($LASTEXITCODE -ne 0){ $failures += 'docs mkdocs'; Write-Host '[FAIL] mkdocs build' -ForegroundColor Red }
    else { Write-Host '[OK] mkdocs build (cross-dir link WARNINGs are expected)' -ForegroundColor Green }
    Pop-Location
  } else {
    $failures += 'docs mkdocs (mkdocs missing)'; Write-Host '[FAIL] mkdocs not found on PATH' -ForegroundColor Red
  }
}

if($Pytest){
  Section 'Backend: pytest (local; cloud elys_debug is authoritative)'
  if($pythonExe){
    Push-Location $backend
    & $pythonExe -m pytest -q
    if($LASTEXITCODE -ne 0){ Write-Host '[WARN] pytest failed locally (may lack DB/deps; cloud is source of truth)' -ForegroundColor Yellow }
    else { Write-Host '[OK] pytest' -ForegroundColor Green }
    Pop-Location
  } else {
    Write-Host '[WARN] pytest skipped because python is missing' -ForegroundColor Yellow
  }
}

Write-Host ''
if($failures.Count -gt 0){
  Write-Host ' FAIL ' -BackgroundColor DarkRed -ForegroundColor White -NoNewline
  Write-Host ('  static checks failed: {0}' -f ($failures -join ', ')) -ForegroundColor Red
  Write-Host '        fix the above before deploying.' -ForegroundColor Red
  exit 1
} else {
  Write-Host ' PASS ' -BackgroundColor DarkGreen -ForegroundColor White -NoNewline
  Write-Host '  all static checks passed - safe to deploy.' -ForegroundColor Green
  exit 0
}
