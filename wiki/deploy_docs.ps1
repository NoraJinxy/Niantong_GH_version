<#
.SYNOPSIS
Build MkDocs documentation, upload one archive by SSH/SCP, and unpack it on the server.

.DESCRIPTION
This is faster than FTP for static documentation with many small files:
1. Run mkdocs build --clean in the wiki directory.
2. Create one tar.gz archive from the generated site directory.
3. Upload the archive by scp.
4. Unpack it on the server and replace the target directory.

.EXAMPLE
.\deploy_docs.ps1

.EXAMPLE
.\deploy_docs.ps1 -ServerUser root -ServerHost 43.139.106.150 -Port 22

.EXAMPLE
.\deploy_docs.ps1 -SshKeyPath "$env:USERPROFILE\.ssh\elys_doc_deploy_ed25519"

.EXAMPLE
.\setup_docs_ssh_key.ps1
Run once to install the deploy SSH key on the server. After that, deploy_docs.ps1 does not prompt for an SSH password.
#>

[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [string]$WikiDir,
    [string]$SiteDir,

    [string]$ConfigFile = "mkdocs.yml",

    [string]$ServerHost = "43.139.106.150",
    [string]$ServerUser = "root",
    [int]$Port = 22,
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\elys_doc_deploy_ed25519",

    [string]$RemoteWebRoot = "/www/wwwroot/huanggan.site",
    [string]$RemoteDirName = "elys_doc",
    [string]$RemoteOwner = "hughherald:hughherald",

    [switch]$BuildOnly,
    [switch]$DryRun,
    [switch]$SkipBuild,
    [switch]$NoCleanup,
    [switch]$AllowPasswordPrompt
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding

$RunId = Get-Date -Format "yyyyMMdd_HHmmss"
$ArchivePath = Join-Path $env:TEMP "elys_doc_site_$RunId.tar.gz"
$RemoteTmp = "/tmp/elys_doc_deploy_$RunId"
$RemoteScriptName = "publish_docs.sh"
$LocalRemoteScript = Join-Path $env:TEMP "elys_doc_publish_$RunId.sh"

function Resolve-DefaultPaths {
    if (-not $ProjectRoot) {
        $script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    }
    if (-not $WikiDir) {
        $script:WikiDir = $PSScriptRoot
    }
    if (-not $SiteDir) {
        $script:SiteDir = Join-Path $WikiDir "site"
    }
}

function Assert-LastExitCode {
    param([string]$Message)
    if ($LASTEXITCODE -ne 0) {
        throw $Message
    }
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Join-RemotePath {
    param(
        [string]$Base,
        [string]$Child
    )
    $baseClean = "/" + $Base.Trim("/")
    $childClean = $Child.Trim("/")
    if (-not $childClean) {
        return $baseClean
    }
    if ($baseClean -eq "/") {
        return "/$childClean"
    }
    return "$baseClean/$childClean"
}

function Assert-SafeRemoteTarget {
    param([string]$RemoteTarget)

    if (-not $RemoteTarget -or $RemoteTarget.Trim() -eq "/" -or $RemoteTarget.Trim() -eq "") {
        throw "Refuse to deploy to unsafe remote target: '$RemoteTarget'"
    }
    if ($RemoteTarget -notmatch "^/") {
        throw "Remote target must be an absolute Linux path: '$RemoteTarget'"
    }
    if ($RemoteTarget -match "(^|/)\.\.($|/)") {
        throw "Remote target must not contain '..': '$RemoteTarget'"
    }
}

function Test-SshTcpPort {
    if ($DryRun) {
        Write-Host "Dry run: skip SSH TCP port check"
        return
    }

    Write-Step "Check SSH port"
    Write-Host "Server: ${ServerHost}:${Port}"

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect($ServerHost, $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(5000, $false)
        if (-not $connected) {
            throw "SSH port check failed: ${ServerHost}:${Port} timed out. If BaoTa changed the SSH port, run .\deploy_docs.cmd -Port <ssh-port>. Also check the Tencent Cloud security group and server firewall."
        }
        $client.EndConnect($async)
        Write-Host "SSH TCP port is reachable."
    }
    catch [System.Net.Sockets.SocketException] {
        if ($_.Exception.SocketErrorCode -eq [System.Net.Sockets.SocketError]::ConnectionRefused) {
            throw "SSH port check failed: ${ServerHost}:${Port} refused the connection. This usually means sshd is not listening on this port, or the server firewall rejects it. On the server, run: ss -lntp | grep sshd. If SSH uses another port, run: .\deploy_docs.cmd -Port <ssh-port>."
        }
        throw "SSH port check failed: ${ServerHost}:${Port} socket error $($_.Exception.SocketErrorCode). Check the SSH port, Tencent Cloud security group, BaoTa firewall, and server firewall."
    }
    catch {
        if ($_.Exception.Message -like "*timed out*") {
            throw $_.Exception.Message
        }
        throw "SSH port check failed: ${ServerHost}:${Port} is not reachable. If BaoTa changed the SSH port, run .\deploy_docs.cmd -Port <ssh-port>. On the server, check: ss -lntp | grep sshd"
    }
    finally {
        $client.Close()
    }
}

function Invoke-MkDocsBuild {
    if (-not (Test-Path -LiteralPath $WikiDir)) {
        throw "Wiki directory not found: $WikiDir"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $WikiDir $ConfigFile))) {
        throw "$ConfigFile not found in $WikiDir"
    }

    Write-Step "Build MkDocs site"
    Write-Host "Wiki dir: $WikiDir"
    Write-Host "Config:   $ConfigFile"
    if ($DryRun) {
        Write-Host "Dry run: skip mkdocs build"
        return
    }

    Push-Location $WikiDir
    try {
        $previousMkDocs2Warning = $env:NO_MKDOCS_2_WARNING
        $env:NO_MKDOCS_2_WARNING = "1"

        $mkdocs = Get-Command mkdocs -ErrorAction SilentlyContinue
        if ($mkdocs) {
            & mkdocs build --clean --config-file $ConfigFile
        }
        else {
            & python -m mkdocs build --clean --config-file $ConfigFile
        }
        Assert-LastExitCode "mkdocs build failed."
    }
    finally {
        if ($null -eq $previousMkDocs2Warning) {
            Remove-Item Env:NO_MKDOCS_2_WARNING -ErrorAction SilentlyContinue
        }
        else {
            $env:NO_MKDOCS_2_WARNING = $previousMkDocs2Warning
        }
        Pop-Location
    }
}

function Assert-ReadyForPackage {
    if (-not (Test-Path -LiteralPath $SiteDir)) {
        throw "Site directory not found: $SiteDir"
    }

    $files = @(Get-ChildItem -LiteralPath $SiteDir -Recurse -File)
    if ($files.Count -eq 0) {
        throw "Site directory is empty: $SiteDir"
    }
}

function New-SiteArchive {
    Write-Step "Create site archive"
    Write-Host "Archive: $ArchivePath"
    if ($DryRun) {
        Write-Host "Dry run: skip archive creation"
        return
    }

    if (Test-Path -LiteralPath $ArchivePath) {
        Remove-Item -LiteralPath $ArchivePath -Force
    }

    $siteRoot = (Resolve-Path -LiteralPath $SiteDir).Path
    & tar -czf $ArchivePath -C $siteRoot .
    Assert-LastExitCode "Failed to create archive with tar."
}

function Get-SshCommonArgs {
    # StrictHostKeyChecking=accept-new silently accepts new host keys on first
    # connection but rejects changed keys, balancing automation against MITM risk.
    $argList = @(
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3"
    )
    if (-not $AllowPasswordPrompt) {
        $argList += @("-o", "BatchMode=yes")
    }
    if ($SshKeyPath -and (Test-Path -LiteralPath $SshKeyPath)) {
        $argList += @("-i", $SshKeyPath, "-o", "IdentitiesOnly=yes")
    }
    return $argList
}

function Get-SshArgs {
    return @("-p", $Port.ToString()) + (Get-SshCommonArgs)
}

function Get-ScpArgs {
    return @("-P", $Port.ToString()) + (Get-SshCommonArgs)
}

function Assert-SshKeyAvailable {
    if ($DryRun -or $AllowPasswordPrompt) {
        return
    }

    if (-not $SshKeyPath -or -not (Test-Path -LiteralPath $SshKeyPath)) {
        throw "SSH deploy key not found: $SshKeyPath. Run .\setup_docs_ssh_key.cmd once, then run .\deploy_docs.cmd again. To use password manually, run .\deploy_docs.cmd -AllowPasswordPrompt."
    }
}

function Test-SshKeyLogin {
    if ($DryRun -or $AllowPasswordPrompt) {
        if ($AllowPasswordPrompt) {
            Write-Host "AllowPasswordPrompt set. SSH may ask for a password."
        }
        return
    }

    Write-Step "Check SSH key login"
    $remote = "${ServerUser}@${ServerHost}"
    $sshArgs = Get-SshArgs
    & ssh @sshArgs $remote "true"
    Assert-LastExitCode "SSH key login failed. Run .\setup_docs_ssh_key.cmd once to install the deploy key on the server, or run .\deploy_docs.cmd -AllowPasswordPrompt to use password manually."
    Write-Host "SSH key login OK."
}

function New-RemotePublishScript {
    param([string]$RemoteTarget)

    $script = @"
#!/usr/bin/env bash
set -euo pipefail

REMOTE_TMP="$RemoteTmp"
ARCHIVE="`$REMOTE_TMP/site.tar.gz"
TARGET="$RemoteTarget"
OWNER="$RemoteOwner"
NEW_DIR="`$REMOTE_TMP/site"
BACKUP="`$TARGET.bak_$RunId"

mkdir -p "`$(dirname "`$TARGET")" "`$NEW_DIR"
tar -xzf "`$ARCHIVE" -C "`$NEW_DIR"

if [ "`$(id -u)" = "0" ] && id "`${OWNER%%:*}" >/dev/null 2>&1; then
  chown -R "`$OWNER" "`$NEW_DIR"
fi
chmod -R u+rwX,go+rX "`$NEW_DIR"

if [ -e "`$BACKUP" ]; then
  rm -rf "`$BACKUP"
fi

RESTORE_NEEDED=0
if [ -e "`$TARGET" ]; then
  mv "`$TARGET" "`$BACKUP"
  RESTORE_NEEDED=1
fi

if mv "`$NEW_DIR" "`$TARGET"; then
  if [ "`$(id -u)" = "0" ] && id "`${OWNER%%:*}" >/dev/null 2>&1; then
    chown -R "`$OWNER" "`$TARGET"
  fi
  chmod -R u+rwX,go+rX "`$TARGET"
  rm -rf "`$BACKUP"
  rm -rf "`$REMOTE_TMP"
  echo "Published `$TARGET"
else
  echo "Publish failed, restoring previous directory" >&2
  if [ "`$RESTORE_NEEDED" = "1" ] && [ -e "`$BACKUP" ]; then
    mv "`$BACKUP" "`$TARGET"
  fi
  exit 1
fi
"@

    if ($DryRun) {
        Write-Host "Dry run: skip writing remote publish script"
        return
    }

    [System.IO.File]::WriteAllText($LocalRemoteScript, $script, [System.Text.UTF8Encoding]::new($false))
}

function Publish-ArchiveOverSsh {
    param([string]$RemoteTarget)

    $remote = "${ServerUser}@${ServerHost}"
    $remoteScriptPath = "$RemoteTmp/$RemoteScriptName"
    $sshArgs = Get-SshArgs
    $scpArgs = Get-ScpArgs

    Write-Step "Upload archive and publish on server"
    Write-Host "Server: $remote"
    Write-Host "Target: $RemoteTarget"
    Write-Host "Remote tmp: $RemoteTmp"

    if ($DryRun) {
        Write-Host "Dry run: ssh $($sshArgs -join ' ') $remote mkdir -p $RemoteTmp"
        Write-Host "Dry run: scp $ArchivePath ${remote}:$RemoteTmp/site.tar.gz"
        Write-Host "Dry run: scp $LocalRemoteScript ${remote}:$remoteScriptPath"
        Write-Host "Dry run: ssh $($sshArgs -join ' ') $remote bash $remoteScriptPath"
        return
    }

    & ssh @sshArgs $remote "mkdir -p '$RemoteTmp'"
    Assert-LastExitCode "Failed to create remote temp directory."

    & scp @scpArgs $ArchivePath "${remote}:$RemoteTmp/site.tar.gz"
    Assert-LastExitCode "Failed to upload site archive."

    & scp @scpArgs $LocalRemoteScript "${remote}:$remoteScriptPath"
    Assert-LastExitCode "Failed to upload publish script."

    & ssh @sshArgs $remote "bash '$remoteScriptPath'"
    Assert-LastExitCode "Remote publish failed."
}

Resolve-DefaultPaths
$RemoteTarget = Join-RemotePath $RemoteWebRoot $RemoteDirName
Assert-SafeRemoteTarget $RemoteTarget

Write-Host "Project root: $ProjectRoot"
Write-Host "Wiki dir:     $WikiDir"
Write-Host "Site dir:     $SiteDir"
Write-Host "SSH target:   ${ServerUser}@${ServerHost}:$RemoteTarget"

if (-not $BuildOnly) {
    Test-SshTcpPort
    Assert-SshKeyAvailable
    Test-SshKeyLogin
}

if (-not $SkipBuild) {
    Invoke-MkDocsBuild
}

Assert-ReadyForPackage

if ($BuildOnly) {
    Write-Host "BuildOnly set. Skip SSH upload."
    exit 0
}

$remoteReachable = $false
try {
    New-SiteArchive
    New-RemotePublishScript $RemoteTarget
    $remoteReachable = $true
    Publish-ArchiveOverSsh $RemoteTarget
}
catch {
    # Best-effort: clean up the remote tmp dir if we managed to create it.
    if ($remoteReachable -and -not $DryRun) {
        $sshArgs = Get-SshArgs
        & ssh @sshArgs "${ServerUser}@${ServerHost}" "rm -rf '$RemoteTmp'" 2>$null
    }
    throw
}
finally {
    if (-not $NoCleanup) {
        if (Test-Path -LiteralPath $ArchivePath -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path -LiteralPath $LocalRemoteScript -ErrorAction SilentlyContinue) {
            Remove-Item -LiteralPath $LocalRemoteScript -Force -ErrorAction SilentlyContinue
        }
    }
}
