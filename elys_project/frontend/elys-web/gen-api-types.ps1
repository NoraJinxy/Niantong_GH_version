#requires -Version 5
# Pull openapi.json from the LIVE cloud backend and regenerate frontend TS types (src/types/api.ts).
# Server address follows the deploy profile (same single-source idea as elys_scripts/common/config.py):
# it reads COMPUTE_SERVER_IP from elys_project/deploy/profiles/<profile>.env.
# Usage:
#   .\gen-api-types.ps1                       # use aliyun-test profile's compute IP
#   .\gen-api-types.ps1 -ComputeIP 1.2.3.4    # override IP directly
#   .\gen-api-types.ps1 -Profile prod-hybrid
param(
  [string]$Profile = "aliyun-test",
  [string]$ComputeIP = ""
)
$ErrorActionPreference = "Stop"
$webRoot = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $webRoot "..\..\..")).Path

if (-not $ComputeIP) {
  $profilePath = Join-Path $repo "elys_project\deploy\profiles\$Profile.env"
  if (-not (Test-Path $profilePath)) { throw "profile not found: $profilePath (pass -ComputeIP to override)" }
  foreach ($line in Get-Content $profilePath) {
    if ($line -match '^\s*COMPUTE_SERVER_IP\s*=\s*(.+?)\s*$') { $ComputeIP = $matches[1].Trim().Trim('"').Trim("'") }
  }
  if (-not $ComputeIP) { throw "COMPUTE_SERVER_IP not found in profile; pass -ComputeIP" }
}

$url = "http://$ComputeIP/openapi.json"
$specPath = Join-Path $webRoot "openapi.json"
Write-Host "-> fetching $url" -ForegroundColor Cyan
Invoke-WebRequest -Uri $url -OutFile $specPath -UseBasicParsing -TimeoutSec 30
Write-Host "   openapi.json $((Get-Item $specPath).Length) bytes" -ForegroundColor Green

Write-Host "-> generating src/types/api.ts" -ForegroundColor Cyan
Push-Location $webRoot
try {
  npx openapi-typescript openapi.json -o src/types/api.ts
  if ($LASTEXITCODE -ne 0) { throw "openapi-typescript failed" }
} finally { Pop-Location }
Write-Host "[OK] src/types/api.ts regenerated. Run check.cmd to verify types compile." -ForegroundColor Green
