<#
.SYNOPSIS
Create a local deploy SSH key and install it on the documentation server.

.DESCRIPTION
Run this once before using deploy_docs.ps1. It creates a passwordless
Ed25519 key for documentation deployment and appends the public key to the
remote user's ~/.ssh/authorized_keys. The SSH password may be requested once
during setup. After setup, deploy_docs.ps1 uses the key and does not prompt
for a password.

.EXAMPLE
.\setup_docs_ssh_key.ps1

.EXAMPLE
.\setup_docs_ssh_key.ps1 -ServerHost 43.139.106.150 -ServerUser root -Port 22
#>

[CmdletBinding()]
param(
    [string]$ServerHost = "43.139.106.150",
    [string]$ServerUser = "root",
    [int]$Port = 22,
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\elys_doc_deploy_ed25519"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $OutputEncoding

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

function ConvertTo-ShellSingleQuoted {
    param([string]$Value)
    return "'" + $Value.Replace("'", "'\''") + "'"
}

function New-DeployKeyIfMissing {
    $keyDir = Split-Path -Parent $SshKeyPath
    if (-not (Test-Path -LiteralPath $keyDir)) {
        New-Item -ItemType Directory -Path $keyDir -Force | Out-Null
    }

    if (Test-Path -LiteralPath $SshKeyPath) {
        Write-Host "Use existing SSH key: $SshKeyPath"
        return
    }

    Write-Step "Create deploy SSH key"
    Write-Host "Key path: $SshKeyPath"
    $escapedKeyPath = $SshKeyPath.Replace('"', '\"')
    & cmd.exe /d /c "ssh-keygen -t ed25519 -f ""$escapedKeyPath"" -N """" -C ""elys-doc-deploy"""
    Assert-LastExitCode "Failed to create SSH key. Check whether ssh-keygen is available in PATH."
}

function Install-PublicKey {
    $publicKeyPath = "$SshKeyPath.pub"
    if (-not (Test-Path -LiteralPath $publicKeyPath)) {
        throw "Public key not found: $publicKeyPath"
    }

    $remote = "${ServerUser}@${ServerHost}"
    $publicKey = ([System.IO.File]::ReadAllText($publicKeyPath, [System.Text.UTF8Encoding]::new($false))).Trim()
    if (-not $publicKey) {
        throw "Public key is empty: $publicKeyPath"
    }

    $sshArgs = @(
        "-p", $Port.ToString(),
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3"
    )

    $remoteCommandTemplate = @'
umask 077
mkdir -p ~/.ssh
touch ~/.ssh/authorized_keys
tmp="$(mktemp)"
cat ~/.ssh/authorized_keys > "$tmp"
printf '%s\n' __PUBLIC_KEY__ >> "$tmp"
awk '!seen[$0]++' "$tmp" > ~/.ssh/authorized_keys
rm -f "$tmp"
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
'@
    $remoteCommand = $remoteCommandTemplate.Replace("__PUBLIC_KEY__", (ConvertTo-ShellSingleQuoted $publicKey))

    Write-Step "Install public key on server"
    Write-Host "Server: $remote"
    Write-Host "Port:   $Port"
    Write-Host "Public: $publicKeyPath"
    Write-Host "You may need to enter the SSH password once."

    & ssh @sshArgs $remote $remoteCommand
    Assert-LastExitCode "Failed to install public key on server."

    Write-Step "Confirm public key on server"
    $checkCommand = "grep -F " + (ConvertTo-ShellSingleQuoted $publicKey) + " ~/.ssh/authorized_keys >/dev/null && echo 'Public key is present in authorized_keys.'"
    & ssh @sshArgs $remote $checkCommand
    Assert-LastExitCode "Public key was not found in ~/.ssh/authorized_keys after installation."
}

function Test-KeyLogin {
    $remote = "${ServerUser}@${ServerHost}"
    $sshArgs = @(
        "-p", $Port.ToString(),
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        "-i", $SshKeyPath,
        "-o", "IdentitiesOnly=yes"
    )

    Write-Step "Verify passwordless SSH login"
    & ssh @sshArgs $remote "true"
    Assert-LastExitCode "SSH key login still failed. Check /root/.ssh/authorized_keys, sshd settings, or whether root login is allowed."
    Write-Host "SSH key login OK. Future deploy_docs runs should not ask for a password."
}

Write-Host "SSH deploy key path: $SshKeyPath"

New-DeployKeyIfMissing
Install-PublicKey
Test-KeyLogin
