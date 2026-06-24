<#
.SYNOPSIS
  Fast code-only push for an already configured ELYS remote deployment.

.DESCRIPTION
  Uploads the current backend/frontend code bundle to the active entry + compute
  servers, preserves remote venv/node_modules/.env, restarts the backend
  services, and rebuilds the frontend. It intentionally does not upload or
  rewrite database/deploy/storage files, install packages, reset data, rewrite
  Nginx, recreate .env, or run DB bootstrap.

.EXAMPLE
  .\s2_push_code.cmd

.EXAMPLE
  .\s2_push_code.cmd -SkipCheck
#>
param(
    [ValidateSet("aliyun-test", "prod-hybrid")]
    [string]$Profile = "aliyun-test",

    [string]$ProfilePath = "",

    [string]$EntryServerIP = "",

    [string]$ComputeServerIP = "",

    [string]$EntryDomain = "elysbrain.site",

    [string]$DataDomain = "data.elysbrain.site",

    [ValidateSet("ip", "domain")]
    [string]$AccessMode = "ip",

    [ValidateSet("http", "https")]
    [string]$PublicScheme = "http",

    [string]$ServerUser = "root",

    [int]$Port = 22,

    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\elys_deploy_ed25519",

    [switch]$SkipCheck
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProfileDir = Join-Path $PSScriptRoot "profiles"
$RemoteArchive = "/tmp/elys_code_push.tar.gz"
$RemoteTmp = "/tmp/elys_code_push"
$TarName = Join-Path $env:TEMP ("elys-code-push-{0}.tar.gz" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

function Read-EnvProfile {
    param([Parameter(Mandatory = $true)][string]$Path)
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Profile file not found: $Path"
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) { continue }
        $eq = $trimmed.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $trimmed.Substring(0, $eq).Trim()
        $value = $trimmed.Substring($eq + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$key] = $value
    }
    return $values
}

function Apply-ProfileValue {
    param(
        [hashtable]$Values,
        [string]$Key,
        [string]$ParameterName,
        [scriptblock]$Setter
    )
    if ($Values.ContainsKey($Key) -and -not $PSBoundParameters.ContainsKey($ParameterName)) {
        & $Setter $Values[$Key]
    }
}

function Assert-LastExitCode {
    param([string]$Message)
    if ($LASTEXITCODE -ne 0) { throw $Message }
}

function Write-Step {
    param([int]$Number, [int]$Total, [string]$Title)
    Write-Host ""
    Write-Host (" CODE {0}/{1} " -f $Number, $Total) -BackgroundColor DarkMagenta -ForegroundColor White -NoNewline
    Write-Host ("  {0}" -f $Title) -ForegroundColor White
}

function Write-Info { param([string]$Message) Write-Host "  [INFO] $Message" -ForegroundColor DarkGray }
function Write-Ok   { param([string]$Message) Write-Host "  [OK]   $Message" -ForegroundColor Green }

function Get-RemoteTarget {
    param([Parameter(Mandatory = $true)][string]$ServerIP)
    return "${ServerUser}@${ServerIP}"
}

function Get-SshArgs {
    param([Parameter(Mandatory = $true)][string]$ServerIP)
    return @(
        "-p", $Port,
        "-o", "StrictHostKeyChecking=no",
        "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout=15",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=4",
        "-i", $SshKeyPath,
        (Get-RemoteTarget $ServerIP)
    )
}

function Invoke-Remote {
    param(
        [Parameter(Mandatory = $true)][string]$ServerIP,
        [Parameter(Mandatory = $true)][string]$Command
    )
    $args = Get-SshArgs -ServerIP $ServerIP
    & ssh @args $Command
    Assert-LastExitCode "Remote command failed on ${ServerIP}."
}

function Invoke-RemoteScript {
    param(
        [Parameter(Mandatory = $true)][string]$ServerIP,
        [Parameter(Mandatory = $true)][string]$Script
    )
    $tempScript = Join-Path $env:TEMP ("elys-remote-script-{0}.sh" -f ([guid]::NewGuid().ToString("N")))
    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tempScript, $Script, $utf8NoBom)
        $args = (Get-SshArgs -ServerIP $ServerIP) + @("bash", "-s")
        $process = Start-Process -FilePath "ssh" -ArgumentList $args -RedirectStandardInput $tempScript -NoNewWindow -Wait -PassThru
        if ($process.ExitCode -ne 0) {
            throw "Remote script failed on ${ServerIP}."
        }
    }
    finally {
        Remove-Item -LiteralPath $tempScript -Force -ErrorAction SilentlyContinue
    }
}

function Copy-RemoteFile {
    param(
        [Parameter(Mandatory = $true)][string]$ServerIP,
        [Parameter(Mandatory = $true)][string]$LocalPath,
        [Parameter(Mandatory = $true)][string]$RemotePath
    )
    $target = "$(Get-RemoteTarget $ServerIP):$RemotePath"
    $args = @(
        "-P", $Port,
        "-o", "StrictHostKeyChecking=no",
        "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout=15",
        "-i", $SshKeyPath,
        $LocalPath,
        $target
    )
    & scp @args
    Assert-LastExitCode "SCP upload failed on ${ServerIP}."
}

function Shell-SingleQuote {
    param([AllowNull()][string]$Value)
    if ($null -eq $Value) { $Value = "" }
    return "'" + $Value.Replace("'", "'\''") + "'"
}

$ResolvedProfilePath = if (-not [string]::IsNullOrWhiteSpace($ProfilePath)) {
    $ProfilePath
} else {
    Join-Path $ProfileDir "${Profile}.env"
}
$ProfileValues = Read-EnvProfile -Path $ResolvedProfilePath

$ActiveSet = ""
if ($ProfileValues.ContainsKey("ACTIVE_SET")) { $ActiveSet = "$($ProfileValues['ACTIVE_SET'])".Trim() }
if ($ActiveSet) {
    $setPrefix = $ActiveSet.ToUpper() + "_"
    foreach ($k in @("ENTRY_SERVER_IP", "COMPUTE_SERVER_IP")) {
        if ($ProfileValues.ContainsKey($setPrefix + $k) -and $ProfileValues[$setPrefix + $k]) {
            $ProfileValues[$k] = $ProfileValues[$setPrefix + $k]
        }
    }
}

Apply-ProfileValue $ProfileValues "ENTRY_SERVER_IP" "EntryServerIP" { param($v) $script:EntryServerIP = $v }
Apply-ProfileValue $ProfileValues "COMPUTE_SERVER_IP" "ComputeServerIP" { param($v) $script:ComputeServerIP = $v }
Apply-ProfileValue $ProfileValues "ENTRY_DOMAIN" "EntryDomain" { param($v) $script:EntryDomain = $v }
Apply-ProfileValue $ProfileValues "DATA_DOMAIN" "DataDomain" { param($v) $script:DataDomain = $v }
Apply-ProfileValue $ProfileValues "ACCESS_MODE" "AccessMode" { param($v) $script:AccessMode = $v }
Apply-ProfileValue $ProfileValues "PUBLIC_SCHEME" "PublicScheme" { param($v) $script:PublicScheme = $v }
Apply-ProfileValue $ProfileValues "SERVER_USER" "ServerUser" { param($v) $script:ServerUser = $v }
Apply-ProfileValue $ProfileValues "SSH_PORT" "Port" { param($v) $script:Port = [int]$v }
Apply-ProfileValue $ProfileValues "SSH_KEY_PATH" "SshKeyPath" { param($v) $script:SshKeyPath = $v }

if ([string]::IsNullOrWhiteSpace($EntryServerIP) -or [string]::IsNullOrWhiteSpace($ComputeServerIP)) {
    throw "EntryServerIP/ComputeServerIP is missing. Check $ResolvedProfilePath."
}
if (-not (Test-Path -LiteralPath $SshKeyPath)) {
    throw "SSH key not found: $SshKeyPath. Run s2_deploy.cmd once to install the deploy key."
}

$EntryAccessHost = if ($AccessMode -eq "domain") { $EntryDomain } else { $EntryServerIP }
$DataAccessHost = if ($AccessMode -eq "domain") { $DataDomain } else { $ComputeServerIP }
$EntryOrigin = "${PublicScheme}://${EntryAccessHost}"
$DataOrigin = "${PublicScheme}://${DataAccessHost}"

$computeScript = @'
set -euo pipefail
APP_DIR=/var/www/elys
BACKEND_DIR="${APP_DIR}/backend"
SRC=__REMOTE_TMP__
ARCHIVE=__REMOTE_ARCHIVE__

rm -rf "${SRC}"
mkdir -p "${SRC}"
tar -xzf "${ARCHIVE}" -C "${SRC}"
rm -f "${ARCHIVE}"

if [ ! -d "${BACKEND_DIR}/venv" ] || [ ! -x "${BACKEND_DIR}/venv/bin/python" ]; then
  echo "[FAIL] Existing backend venv not found. Run full s2_deploy.cmd first."
  exit 1
fi
if [ ! -f "${BACKEND_DIR}/.env" ]; then
  echo "[FAIL] Existing backend .env not found. Run full s2_deploy.cmd first."
  exit 1
fi

systemctl stop elys-worker 2>/dev/null || true
systemctl stop elys-backend 2>/dev/null || true
for i in 1 2 3 4 5; do
  if ! pgrep -f "${BACKEND_DIR}/venv/bin" >/dev/null 2>&1; then break; fi
  sleep 1
done
pkill -9 -f "${BACKEND_DIR}/venv/bin" 2>/dev/null || true

old_req="$(cat "${BACKEND_DIR}/.requirements.installed.sha256" 2>/dev/null || true)"
new_req="$(sha256sum "${SRC}/backend/requirements.txt" 2>/dev/null | awk '{print $1}')"
if [ -n "${old_req}" ] && [ -n "${new_req}" ] && [ "${old_req}" != "${new_req}" ]; then
  echo "[FAIL] requirements.txt changed; code-only push will not install packages."
  echo "[FAIL] Run full s2_deploy.cmd when dependency changes are needed."
  exit 1
fi

rm -rf "${BACKEND_DIR}/app" "${BACKEND_DIR}/scripts" "${BACKEND_DIR}/tests" "${BACKEND_DIR}/__pycache__" 2>/dev/null || true
find "${BACKEND_DIR}" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

mkdir -p "${BACKEND_DIR}" "${APP_DIR}"
cp -a "${SRC}/backend/app" "${BACKEND_DIR}/"
if [ -d "${SRC}/backend/scripts" ]; then cp -a "${SRC}/backend/scripts" "${BACKEND_DIR}/"; fi
chown -R www-data:www-data "${BACKEND_DIR}/app" "${BACKEND_DIR}/scripts" 2>/dev/null || true

systemctl start elys-backend
systemctl start elys-worker
sleep 2
systemctl is-active --quiet elys-backend
systemctl is-active --quiet elys-worker
echo "[OK] compute code pushed and services restarted"
'@

$entryScript = @'
set -euo pipefail
APP_DIR=/var/www/elys
FRONTEND_DIR="${APP_DIR}/frontend/elys-web"
SRC=__REMOTE_TMP__
ARCHIVE=__REMOTE_ARCHIVE__
ENTRY_ORIGIN=__ENTRY_ORIGIN__
DATA_ORIGIN=__DATA_ORIGIN__

rm -rf "${SRC}"
mkdir -p "${SRC}"
tar -xzf "${ARCHIVE}" -C "${SRC}"
rm -f "${ARCHIVE}"

if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
  echo "[FAIL] Existing frontend node_modules not found. Run full s2_deploy.cmd first."
  exit 1
fi

KEEP_MODULES="$(dirname "${APP_DIR}")/.elys_code_push_node_modules_keep"
rm -rf "${KEEP_MODULES}" 2>/dev/null || true
mv "${FRONTEND_DIR}/node_modules" "${KEEP_MODULES}"
rm -rf "${APP_DIR}/frontend" 2>/dev/null || true
mkdir -p "${APP_DIR}/frontend"
cp -a "${SRC}/frontend/elys-web" "${APP_DIR}/frontend/"
rm -rf "${FRONTEND_DIR}/node_modules" 2>/dev/null || true
mv "${KEEP_MODULES}" "${FRONTEND_DIR}/node_modules"

cd "${FRONTEND_DIR}"
cat > .env.production <<EOF
VITE_API_BASE_URL=/api/v1
VITE_DATA_API_BASE_URL=${DATA_ORIGIN}/api/v1
VITE_APP_ORIGIN=${ENTRY_ORIGIN}
VITE_DATA_ORIGIN=${DATA_ORIGIN}
EOF
npm run build
test -d "${FRONTEND_DIR}/dist"
echo "[OK] entry code pushed and frontend rebuilt"
'@

$computeScript = $computeScript.Replace("__REMOTE_TMP__", (Shell-SingleQuote $RemoteTmp)).
    Replace("__REMOTE_ARCHIVE__", (Shell-SingleQuote $RemoteArchive))
$entryScript = $entryScript.Replace("__REMOTE_TMP__", (Shell-SingleQuote $RemoteTmp)).
    Replace("__REMOTE_ARCHIVE__", (Shell-SingleQuote $RemoteArchive)).
    Replace("__ENTRY_ORIGIN__", (Shell-SingleQuote $EntryOrigin)).
    Replace("__DATA_ORIGIN__", (Shell-SingleQuote $DataOrigin))

try {
    Write-Host ""
    Write-Host "ELYS code-only push" -ForegroundColor White
    Write-Info "profile=$Profile entry=$EntryServerIP compute=$ComputeServerIP"
    Write-Info "entry_origin=$EntryOrigin data_origin=$DataOrigin"

    if (-not $SkipCheck) {
        Write-Step 1 6 "Run local static checks"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "check.ps1")
        if ($LASTEXITCODE -ne 0) {
            throw "Local checks failed. Fix them, or rerun s2_push_code.cmd -SkipCheck."
        }
        Write-Ok "Local checks passed"
    } else {
        Write-Step 1 6 "Skip local static checks"
        Write-Info "Skipped by -SkipCheck"
    }

    Write-Step 2 6 "Package code"
    Push-Location $ProjectRoot
    try {
        & tar -czf $TarName `
            --exclude='node_modules' `
            --exclude='venv' `
            --exclude='.venv' `
            --exclude='dist' `
            --exclude='__pycache__' `
            --exclude='*.pyc' `
            --exclude='.DS_Store' `
            --exclude='.git' `
            --exclude='.pytest_cache' `
            --exclude='.codex-pytest-tmp' `
            --exclude='.codex-*' `
            backend/app `
            backend/requirements.txt `
            backend/scripts `
            frontend `
            README.md
    }
    finally {
        Pop-Location
    }
    Assert-LastExitCode "Local package creation failed."
    $sizeKB = [math]::Round((Get-Item $TarName).Length / 1KB, 1)
    Write-Ok "Archive created: $TarName ($sizeKB KB)"

    Write-Step 3 6 "Upload to compute"
    Copy-RemoteFile -ServerIP $ComputeServerIP -LocalPath $TarName -RemotePath $RemoteArchive
    Write-Ok "Uploaded to compute"

    Write-Step 4 6 "Upload to entry"
    Copy-RemoteFile -ServerIP $EntryServerIP -LocalPath $TarName -RemotePath $RemoteArchive
    Write-Ok "Uploaded to entry"

    Write-Step 5 6 "Apply compute backend code"
    Invoke-RemoteScript -ServerIP $ComputeServerIP -Script $computeScript
    Write-Ok "Compute updated"

    Write-Step 6 6 "Apply entry frontend code"
    Invoke-RemoteScript -ServerIP $EntryServerIP -Script $entryScript
    Write-Ok "Entry updated"

    Write-Host ""
    Write-Host " DONE " -BackgroundColor DarkGreen -ForegroundColor White -NoNewline
    Write-Host "  code-only push finished. Open: $EntryOrigin" -ForegroundColor Green
}
finally {
    Remove-Item -LiteralPath $TarName -Force -ErrorAction SilentlyContinue
}
