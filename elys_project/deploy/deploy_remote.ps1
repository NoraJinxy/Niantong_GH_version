<#
.SYNOPSIS
  ELYS hybrid-entry one-click deployment from Windows.

.DESCRIPTION
  Purpose: Windows-side orchestrator that copies code and triggers remote ELYS deployment over SSH/SCP.
  Related: deploy/deploy.sh, deploy/profiles/*.env, docs_v2/2-10 deployment architecture.

  混合入口架构:
    入口服务器  8.135.40.150  — Nginx + Vue 前端 + 轻 API 反代
    计算服务器  8.135.52.84   — Nginx + FastAPI + PostgreSQL + Redis + 项目数据目录

  备案完成前默认使用 IP 访问; 备案完成后可用 -AccessMode domain 切换到域名访问。

.EXAMPLE
  .\deploy_remote.ps1 -Profile aliyun-test

.EXAMPLE
  .\deploy_remote.ps1 -Profile prod-hybrid

.EXAMPLE
  .\deploy_remote.ps1

.EXAMPLE
  .\deploy_remote.ps1 -KeepExistingData

.EXAMPLE
  .\deploy_remote.ps1 -PublicScheme http

.EXAMPLE
  .\deploy_remote.ps1 -EntryServerIP 8.135.40.150 -ComputeServerIP 8.135.52.84 -ServerUser root -Port 22

.EXAMPLE
  .\deploy_remote.ps1 -DataUpstream http://172.16.0.12

.EXAMPLE
  .\deploy_remote.ps1 -AccessMode domain

.EXAMPLE
  .\deploy_remote.ps1 -ResetAll

.EXAMPLE
  .\deploy_remote.ps1 -ResetDb -ResetStorage

.EXAMPLE
  .\deploy_remote.ps1 -SshKeyPath "$env:USERPROFILE\.ssh\elys_deploy_ed25519"

.EXAMPLE
  .\deploy_remote.ps1 -StudiesDir /mnt/elys_data/studies
#>

param(
    [ValidateSet("aliyun-test", "prod-hybrid", "local")]
    [string]$Profile = "aliyun-test",

    [string]$ProfilePath = "",

    [string]$EntryServerIP = "8.135.40.150",

    [string]$ComputeServerIP = "8.135.52.84",

    [string]$EntryDomain = "elysbrain.site",

    [string]$DataDomain = "data.elysbrain.site",

    [ValidateSet("ip", "domain")]
    [string]$AccessMode = "ip",

    [ValidateSet("http", "https")]
    [string]$PublicScheme = "http",

    [string]$ServerUser = "root",

    [int]$Port = 22,

    [string]$StudiesDir = "/mnt/elys_data/studies",

    [string]$DataUpstream = "",

    [string]$ExtraAptPackages = "",

    [ValidateSet("true", "false")]
    [string]$UseCnMirrors = "true",

    [switch]$ResetDb,

    [switch]$ResetStorage,

    [switch]$ResetDataRoot,

    [switch]$ResetAll,

    [switch]$ResetVenv,

    [switch]$ResetNodeModules,

    [switch]$DeepReset,

    [switch]$KeepExistingData,

    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\elys_deploy_ed25519",

    [switch]$SkipSshKeySetup,

    [switch]$NoSshMultiplexing,

    [switch]$SkipCheck
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProfileDir = Join-Path $PSScriptRoot "profiles"
$TarName = "$env:TEMP\elys_project.tar.gz"
$RemoteTmp = "/tmp/elys_project"
$RemoteDeploy = "$RemoteTmp/deploy/deploy.sh"
$DeployRunId = Get-Date -Format "yyyyMMdd_HHmmss"
$script:CurrentPhase = "startup"

function ConvertTo-Bool {
    param(
        [string]$Value,
        [bool]$Default = $false
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Default
    }
    switch ($Value.Trim().ToLowerInvariant()) {
        "1" { return $true }
        "true" { return $true }
        "yes" { return $true }
        "y" { return $true }
        "on" { return $true }
        "0" { return $false }
        "false" { return $false }
        "no" { return $false }
        "n" { return $false }
        "off" { return $false }
        default { return $Default }
    }
}

function Read-EnvProfile {
    param([Parameter(Mandatory = $true)][string]$Path)
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Profile file not found: $Path"
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }
        $eq = $trimmed.IndexOf("=")
        if ($eq -lt 1) {
            continue
        }
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

$ResolvedProfilePath = if (-not [string]::IsNullOrWhiteSpace($ProfilePath)) {
    $ProfilePath
} else {
    Join-Path $ProfileDir "${Profile}.env"
}

if ($Profile -eq "local") {
    throw "Profile 'local' is for one-machine development. Use start_local.cmd + docker-compose.local.yml instead of deploy_remote.ps1."
}

$ProfileValues = Read-EnvProfile -Path $ResolvedProfilePath
Apply-ProfileValue $ProfileValues "ENTRY_SERVER_IP" "EntryServerIP" { param($v) $script:EntryServerIP = $v }
Apply-ProfileValue $ProfileValues "COMPUTE_SERVER_IP" "ComputeServerIP" { param($v) $script:ComputeServerIP = $v }
Apply-ProfileValue $ProfileValues "ENTRY_DOMAIN" "EntryDomain" { param($v) $script:EntryDomain = $v }
Apply-ProfileValue $ProfileValues "DATA_DOMAIN" "DataDomain" { param($v) $script:DataDomain = $v }
Apply-ProfileValue $ProfileValues "ACCESS_MODE" "AccessMode" { param($v) $script:AccessMode = $v }
Apply-ProfileValue $ProfileValues "PUBLIC_SCHEME" "PublicScheme" { param($v) $script:PublicScheme = $v }
Apply-ProfileValue $ProfileValues "SERVER_USER" "ServerUser" { param($v) $script:ServerUser = $v }
Apply-ProfileValue $ProfileValues "SSH_PORT" "Port" { param($v) $script:Port = [int]$v }
Apply-ProfileValue $ProfileValues "STUDIES_DIR" "StudiesDir" { param($v) $script:StudiesDir = $v }
Apply-ProfileValue $ProfileValues "DATA_UPSTREAM" "DataUpstream" { param($v) $script:DataUpstream = $v }
Apply-ProfileValue $ProfileValues "EXTRA_APT_PACKAGES" "ExtraAptPackages" { param($v) $script:ExtraAptPackages = $v }
Apply-ProfileValue $ProfileValues "USE_CN_MIRRORS" "UseCnMirrors" { param($v) $script:UseCnMirrors = $v }
Apply-ProfileValue $ProfileValues "SSH_KEY_PATH" "SshKeyPath" { param($v) $script:SshKeyPath = $v }

if (-not $PSBoundParameters.ContainsKey("KeepExistingData") -and $ProfileValues.ContainsKey("KEEP_EXISTING_DATA")) {
    $KeepExistingData = ConvertTo-Bool $ProfileValues["KEEP_EXISTING_DATA"]
}
if (-not $PSBoundParameters.ContainsKey("ResetDb") -and $ProfileValues.ContainsKey("RESET_DB")) {
    $ResetDb = ConvertTo-Bool $ProfileValues["RESET_DB"]
}
if (-not $PSBoundParameters.ContainsKey("ResetStorage") -and $ProfileValues.ContainsKey("RESET_STORAGE")) {
    $ResetStorage = ConvertTo-Bool $ProfileValues["RESET_STORAGE"]
}
if (-not $PSBoundParameters.ContainsKey("ResetDataRoot") -and $ProfileValues.ContainsKey("RESET_DATA_ROOT")) {
    $ResetDataRoot = ConvertTo-Bool $ProfileValues["RESET_DATA_ROOT"]
}
if ($DeepReset) {
    # 深度重置:数据(DB/存储/数据根) + 构建产物(venv/node_modules)全部从零重建。
    $ResetAll = $true
    $ResetVenv = $true
    $ResetNodeModules = $true
}
if ($ResetAll) {
    $ResetDb = $true
    $ResetStorage = $true
    $ResetDataRoot = $true
}
if ($KeepExistingData -and -not $ResetAll) {
    if (-not $PSBoundParameters.ContainsKey("ResetDb")) {
        $ResetDb = $false
    }
    if (-not $PSBoundParameters.ContainsKey("ResetStorage")) {
        $ResetStorage = $false
    }
    if (-not $PSBoundParameters.ContainsKey("ResetDataRoot")) {
        $ResetDataRoot = $false
    }
}
if (-not $KeepExistingData) {
    $ResetDb = $true
    $ResetStorage = $true
    $ResetDataRoot = $true
}
$EntryAccessHost = if ($AccessMode -eq "domain") { $EntryDomain } else { $EntryServerIP }
$DataAccessHost = if ($AccessMode -eq "domain") { $DataDomain } else { $ComputeServerIP }
$EntryOrigin = "${PublicScheme}://${EntryAccessHost}"
$DataOrigin = "${PublicScheme}://${DataAccessHost}"
if ([string]::IsNullOrWhiteSpace($DataUpstream)) {
    $DataUpstream = "http://${ComputeServerIP}"
}
foreach ($requiredValue in @($EntryServerIP, $ComputeServerIP, $DataUpstream, $EntryDomain, $DataDomain)) {
    if ($requiredValue -like "*CHANGE_ME*") {
        throw "Profile '$Profile' still contains placeholder value: $requiredValue"
    }
}

$script:UseSshMultiplexing = -not $NoSshMultiplexing
$SshControlDir = Join-Path $env:TEMP "elys-ssh-control"
$SshControlPaths = @{}
$StartedSshMasters = New-Object System.Collections.Generic.List[string]

function Assert-LastExitCode {
    param(
        [string]$Message
    )
    if ($LASTEXITCODE -ne 0) {
        throw $Message
    }
}

# ── 统一视觉语法(与 step_banner.ps1 同族):细线 + 反色徽标 + 灰键彩值 ──
$script:Accent = [ConsoleColor]::DarkMagenta   # step2 主色:部署=紫

function Write-DeployRule {
    param([ConsoleColor]$Color = "DarkGray")
    Write-Host ('  ' + (([string][char]0x2500) * 68)) -ForegroundColor $Color
}

function Write-ConfigRow {
    param(
        [string]$Name,
        [string]$Value,
        [ConsoleColor]$Color = "Gray"
    )
    Write-Host ("  {0,-16}" -f $Name) -ForegroundColor DarkGray -NoNewline
    Write-Host $Value -ForegroundColor $Color
}

function Write-LocalStep {
    param(
        [int]$Number,
        [int]$Total,
        [string]$Title,
        [string]$Detail = ""
    )
    $script:CurrentPhase = "LOCAL ${Number}/${Total} - ${Title}"
    # 每个本地步骤一行:反色徽标 + 标题。Detail 仍存入 CurrentPhase 供失败定位。
    Write-Host ""
    Write-Host (" 本地 {0}/{1} " -f $Number, $Total) -BackgroundColor $script:Accent -ForegroundColor White -NoNewline
    Write-Host ("  {0}" -f $Title) -ForegroundColor White
}

function Write-LocalInfo {
    param([string]$Message)
    Write-Host "  [INFO] $Message" -ForegroundColor DarkGray
}

function Write-LocalOk {
    param([string]$Message)
    Write-Host "  [OK]   $Message" -ForegroundColor Green
}

function Write-LocalWarn {
    param([string]$Message)
    Write-Host "  [WARN] $Message" -ForegroundColor Yellow
}

function Write-LocalFail {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

function Write-DeploySection {
    param(
        [string]$Title,
        [ConsoleColor]$Color = [ConsoleColor]::DarkMagenta
    )
    Write-Host ""
    Write-Host "── $Title ──" -ForegroundColor $Color
}

function Write-DeployHeader {
    # 开放式版式(无右边框) —— 中文宽度无需补齐,右边框对不齐的问题根治。
    # 大 logo 保留:它是"部署起点"路标,长滚动/截图里一眼定位每轮部署从哪开始。
    $resetSummary = @()
    if ($ResetDb)          { $resetSummary += "DB" }
    if ($ResetStorage)     { $resetSummary += "Storage" }
    if ($ResetDataRoot)    { $resetSummary += "DataRoot" }
    if ($ResetVenv)        { $resetSummary += "Venv" }
    if ($ResetNodeModules) { $resetSummary += "NodeModules" }
    $nowText = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $arrow = [string][char]0x2192

    Write-Host ""
    Write-Host "   ███████  ██      ██      ██   ██   ███████" -ForegroundColor White
    Write-Host "   ██       ██      ██       ██ ██    ██" -ForegroundColor White
    Write-Host "   █████    ██      ██        ███     ███████   " -ForegroundColor White -NoNewline
    Write-Host "ELYS · 念析" -ForegroundColor Gray
    Write-Host "   ██       ██      ██        ██           ██   " -ForegroundColor White -NoNewline
    Write-Host "EEG 分析平台 · 远程部署" -ForegroundColor DarkGray
    Write-Host "   ███████  ███████ ███████   ██      ███████" -ForegroundColor White
    Write-Host ""
    Write-DeployRule $script:Accent
    Write-ConfigRow "Run ID"      ("{0}   {1}" -f $DeployRunId, $nowText) Gray
    Write-ConfigRow "Profile"     ("{0}   (source: {1})" -f $Profile, (Split-Path -Leaf $ProjectRoot)) Gray
    Write-ConfigRow "入口服"      ("{0}@{1}:{2}  {3}  {4}" -f $ServerUser, $EntryServerIP, $Port, $arrow, $EntryOrigin) Yellow
    Write-ConfigRow "计算服"      ("{0}@{1}:{2}  {3}  {4}" -f $ServerUser, $ComputeServerIP, $Port, $arrow, $DataOrigin) Green
    Write-ConfigRow "流程"        ("本地打包 {0} 上传 {0} 计算服部署 {0} 入口服部署" -f $arrow) DarkGray
    Write-ConfigRow "Studies dir" $StudiesDir DarkGray
    if ($resetSummary.Count -gt 0) {
        Write-ConfigRow "重置 WIPE" ("[{0}]  远程数据会被清空" -f ($resetSummary -join ", ")) Red
    } else {
        Write-ConfigRow "重置 WIPE" "无 —— 保留所有现有数据 (KEEP)" Green
    }
    Write-DeployRule $script:Accent
}

function Write-FailureContext {
    param([string]$ErrorMessage)

    Write-Host ""
    Write-DeployRule Red
    Write-Host " FAIL " -BackgroundColor DarkRed -ForegroundColor White -NoNewline
    Write-Host "  部署失败 · ELYS DEPLOY FAILED" -ForegroundColor Red
    Write-Host ""
    Write-ConfigRow "Run ID" $DeployRunId Red
    Write-ConfigRow "Failed phase" $script:CurrentPhase Red
    Write-ConfigRow "Error" $ErrorMessage Red
    Write-Host ""
    Write-Host "AI_CONTEXT_BEGIN" -ForegroundColor Yellow
    Write-Host "run_id=$DeployRunId"
    Write-Host "failed_phase=$script:CurrentPhase"
    Write-Host "entry_server=${ServerUser}@${EntryServerIP}:${Port}"
    Write-Host "compute_server=${ServerUser}@${ComputeServerIP}:${Port}"
    Write-Host "entry_url=${EntryOrigin}"
    Write-Host "data_url=${DataOrigin}"
    Write-Host "studies_dir=${StudiesDir}"
    Write-Host "reset_db=${ResetDb}; reset_storage=${ResetStorage}; reset_data_root=${ResetDataRoot}"
    Write-Host "error=$ErrorMessage"
    Write-Host "compute_log_hint=/var/log/elys-deploy/compute_*.log"
    Write-Host "entry_log_hint=/var/log/elys-deploy/entry_*.log"
    Write-Host "AI_CONTEXT_END" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Copy the AI_CONTEXT block plus the last 80 terminal lines when asking for help." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Useful checks on compute server:" -ForegroundColor Yellow
    Write-Host "  ssh -i `"$SshKeyPath`" ${ServerUser}@${ComputeServerIP} `"tail -n 120 /var/log/elys-deploy/compute_*.log`""
    Write-Host "  ssh -i `"$SshKeyPath`" ${ServerUser}@${ComputeServerIP} `"systemctl status elys-backend elys-worker nginx postgresql redis-server --no-pager`""
    Write-Host "  ssh -i `"$SshKeyPath`" ${ServerUser}@${ComputeServerIP} `"journalctl -u elys-backend -n 100 --no-pager`""
    Write-Host "  ssh -i `"$SshKeyPath`" ${ServerUser}@${ComputeServerIP} `"journalctl -u elys-worker -n 100 --no-pager`""
    Write-Host "  ssh -i `"$SshKeyPath`" ${ServerUser}@${ComputeServerIP} `"sudo -u www-data test -w /var/www/elys/.matplotlib && echo MPLCONFIGDIR_OK`""
    Write-Host ""
    Write-Host "Useful checks on entry server:" -ForegroundColor Yellow
    Write-Host "  ssh -i `"$SshKeyPath`" ${ServerUser}@${EntryServerIP} `"tail -n 120 /var/log/elys-deploy/entry_*.log`""
    Write-Host "  ssh -i `"$SshKeyPath`" ${ServerUser}@${EntryServerIP} `"systemctl status nginx --no-pager`""
}

function Quote-RemoteValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )
    return "'" + $Value.Replace("'", "'`"'`"'") + "'"
}

function Get-RemoteTarget {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP
    )
    return "${ServerUser}@${ServerIP}"
}

function Get-ControlPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP
    )
    $safeName = "${ServerUser}_${ServerIP}_${Port}" -replace '[^A-Za-z0-9_.-]', '_'
    return (Join-Path $SshControlDir "${safeName}.sock")
}

function Get-SshOptions {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP,

        [switch]$BatchMode,

        [switch]$NoControlMaster
    )

    $options = @(
        "-o", "StrictHostKeyChecking=no",
        "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout=15",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=4",
        "-i", $SshKeyPath
    )

    if ($BatchMode) {
        $options += @("-o", "BatchMode=yes")
    }

    if (-not $NoControlMaster -and $UseSshMultiplexing -and $SshControlPaths.ContainsKey($ServerIP)) {
        $options += @(
            "-o", "ControlMaster=auto",
            "-o", "ControlPath=$($SshControlPaths[$ServerIP])",
            "-o", "ControlPersist=10m"
        )
    }

    return $options
}

function Ensure-DeployKey {
    if ($SkipSshKeySetup) {
        return
    }

    if (-not (Get-Command ssh-keygen -ErrorAction SilentlyContinue)) {
        throw "ssh-keygen not found. Install Windows OpenSSH Client, or run with -SkipSshKeySetup."
    }

    $sshDir = Split-Path -Parent $SshKeyPath
    if (-not (Test-Path -LiteralPath $sshDir)) {
        New-Item -ItemType Directory -Path $sshDir -Force | Out-Null
    }

    if (-not (Test-Path -LiteralPath $SshKeyPath)) {
        Write-LocalInfo "SSH key not found; creating deploy key: ${SshKeyPath}"
        # Windows OpenSSH may drop a literal empty string from -N ""; pass two quote
        # characters so ssh-keygen receives an empty passphrase reliably.
        & ssh-keygen -t ed25519 -q -N '""' -C "elys-deploy" -f $SshKeyPath
        Assert-LastExitCode "Failed to create SSH deploy key."
    }

    $publicKeyPath = "${SshKeyPath}.pub"
    if (-not (Test-Path -LiteralPath $publicKeyPath)) {
        & ssh-keygen -y -f $SshKeyPath | Set-Content -Encoding ascii -NoNewline -Path $publicKeyPath
        Assert-LastExitCode "Failed to derive SSH public key."
    }
}

function Test-KeyLogin {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP
    )

    $target = Get-RemoteTarget $ServerIP
    $options = Get-SshOptions -ServerIP $ServerIP -BatchMode -NoControlMaster
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & ssh -p $Port @options $target "true" 1>$null 2>$null
        return ($LASTEXITCODE -eq 0)
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
}

function Start-SshMaster {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not $UseSshMultiplexing) {
        return
    }

    New-Item -ItemType Directory -Path $SshControlDir -Force | Out-Null
    $controlPath = Get-ControlPath $ServerIP
    $target = Get-RemoteTarget $ServerIP

    if (Test-Path -LiteralPath $controlPath) {
        $oldErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        try {
            & ssh -O check -p $Port -o "ControlPath=$controlPath" $target 1>$null 2>$null
            $checkExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $oldErrorActionPreference
        }
        if ($checkExitCode -eq 0) {
            $SshControlPaths[$ServerIP] = $controlPath
            return
        }
        Remove-Item -LiteralPath $controlPath -Force -ErrorAction SilentlyContinue
    }

    Write-LocalInfo "Preparing reusable SSH connection to ${Label} (${ServerIP})"
    $args = @(
        "-M", "-N", "-f",
        "-p", $Port,
        "-o", "StrictHostKeyChecking=no",
        "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout=15",
        "-o", "ControlMaster=yes",
        "-o", "ControlPath=$controlPath",
        "-o", "ControlPersist=10m",
        "-i", $SshKeyPath,
        $target
    )
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & ssh @args 1>$null 2>$null
        $sshExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
    if ($sshExitCode -ne 0) {
        Write-LocalWarn "Reusable SSH connection is not available; continuing with normal SSH key login"
        $script:UseSshMultiplexing = $false
        return
    }
    $SshControlPaths[$ServerIP] = $controlPath
    [void]$StartedSshMasters.Add($ServerIP)
}

function Stop-SshMasters {
    foreach ($serverIP in $StartedSshMasters) {
        if ($SshControlPaths.ContainsKey($serverIP)) {
            $target = Get-RemoteTarget $serverIP
            $controlPath = $SshControlPaths[$serverIP]
            & ssh -O exit -p $Port -o "ControlPath=$controlPath" $target *> $null
            Remove-Item -LiteralPath $controlPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-Remote {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP,

        [Parameter(Mandatory = $true)]
        [string]$Command,

        [switch]$Tty
    )

    $target = Get-RemoteTarget $ServerIP
    $options = Get-SshOptions -ServerIP $ServerIP
    $args = @("-p", $Port) + $options
    if ($Tty) {
        $args += "-t"
    }
    $args += @($target, $Command)
    & ssh @args
    Assert-LastExitCode "Remote command failed on ${ServerIP}."
}

function Copy-RemoteFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP,

        [Parameter(Mandatory = $true)]
        [string]$LocalPath,

        [Parameter(Mandatory = $true)]
        [string]$RemotePath
    )

    $target = "$(Get-RemoteTarget $ServerIP):$RemotePath"
    $options = Get-SshOptions -ServerIP $ServerIP
    & scp -P $Port @options $LocalPath $target
    Assert-LastExitCode "SCP upload failed on ${ServerIP}."
}

function Reset-RemoteHostKey {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP
    )

    # 清掉 known_hosts 里这台服务器的所有旧 host key 条目。
    # 场景：
    #   - 服务器重装/重置 host key 后，旧条目会让 ssh 报 "REMOTE HOST IDENTIFICATION HAS CHANGED"
    #     并拒绝连接（即便 StrictHostKeyChecking=no 也会被拒，必须清掉旧条目）。
    #   - 本地客户端重装时 known_hosts 为空，本步骤空跑（ssh-keygen -R 不会报错）。
    # 配合 Get-SshOptions 里的 StrictHostKeyChecking=no，清完后下一次连接会自动接受新 host key。
    # 每次部署都跑一次 —— 无害，且能彻底防止"几台电脑/服务器轮换重装"导致的 host key mismatch。
    if (-not (Get-Command ssh-keygen -ErrorAction SilentlyContinue)) {
        return
    }
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & ssh-keygen -R $ServerIP 1>$null 2>$null
        # 顺便清非标准端口形式 [ip]:port（如果用了非 22 端口）
        if ($Port -ne 22) {
            & ssh-keygen -R "[$ServerIP]:$Port" 1>$null 2>$null
        }
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
}

function Install-DeployKey {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if ($SkipSshKeySetup) {
        return
    }

    # 先清掉本地缓存的旧 host key（防止服务器/客户端重装后 host key 不匹配卡住整个部署）
    Reset-RemoteHostKey -ServerIP $ServerIP

    if (Test-KeyLogin -ServerIP $ServerIP) {
        Write-LocalOk "SSH key login already works for ${Label} (${ServerIP})"
        return
    }

    Write-Host ""
    Write-Host "######################################################################" -ForegroundColor Yellow
    Write-Host "#  [需要你操作] 部署已暂停, 正在等待你手动输入密码                    #" -ForegroundColor Yellow
    Write-Host "######################################################################" -ForegroundColor Yellow
    Write-LocalWarn "目标 ${Label} (${ServerIP}) 的【免密钥登录失败】, 现在要用 root 密码把部署公钥重新装上去。"
    Write-LocalWarn "下面会出现 `"root@${ServerIP}'s password:`" 提示符, 请输入该服务器 root 密码 (输入时不显示字符, 正常现象)。"
    Write-LocalInfo "  → 密码输错会在这步 FAIL; 重新跑 s2_deploy_remote.cmd 再输一次即可。"
    Write-LocalWarn "  → 安全提示: 若这台服务器【以前能免密、现在突然要密码】, 可能 authorized_keys 被改或系统被重装,"
    Write-LocalWarn "     请先去阿里云控制台核对异常登录告警, 确认安全后再继续输入密码!"
    $publicKey = (Get-Content -Raw -Encoding ascii -Path "${SshKeyPath}.pub").Trim()
    $quotedKey = Quote-RemoteValue $publicKey
    $installCmd = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && (grep -qxF $quotedKey ~/.ssh/authorized_keys || echo $quotedKey >> ~/.ssh/authorized_keys) && chmod 600 ~/.ssh/authorized_keys"

    try {
        Invoke-Remote -ServerIP $ServerIP -Command $installCmd
    }
    catch {
        Write-LocalFail "在 ${Label} (${ServerIP}) 安装 deploy key 失败"
        Write-LocalFail "  常见原因: (1) 密码输错  (2) 服务器禁了 root SSH  (3) 网络不通"
        Write-LocalFail "  重试: 重新跑 s2_deploy_remote.cmd, 这次输对密码"
        throw
    }

    if (Test-KeyLogin -ServerIP $ServerIP) {
        Write-LocalOk "Deploy key installed for ${Label} (${ServerIP}); future runs should not ask for this password"
    }
    else {
        Write-LocalWarn "Deploy key was written, but passwordless login test did not pass yet; this run may still reuse the current connection"
    }
}

function Prepare-RemoteAccess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServerIP,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    Install-DeployKey -ServerIP $ServerIP -Label $Label
    if ($UseSshMultiplexing -and -not $SshControlPaths.ContainsKey($ServerIP) -and (Test-KeyLogin -ServerIP $ServerIP)) {
        Start-SshMaster -ServerIP $ServerIP -Label $Label
    }
}

Write-DeployHeader

try {
    if (-not $SkipCheck) {
        $script:CurrentPhase = "LOCAL 0 - static check"
        Write-DeploySection "部署前本地静态校验 (check.ps1)"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "check.ps1")
        if ($LASTEXITCODE -ne 0) {
            throw "本地静态校验未通过(后端编译/前端类型/单测)。修复后重试,或加 -SkipCheck 跳过。"
        }
        Write-LocalOk "本地静态校验通过"
    }

    Write-LocalStep 1 6 "Prepare SSH access" "Create/reuse deploy key, install authorized_keys, and open reusable connections when possible."
    Ensure-DeployKey
    Prepare-RemoteAccess -ServerIP $ComputeServerIP -Label "compute server"
    Prepare-RemoteAccess -ServerIP $EntryServerIP -Label "entry server"
    Write-LocalOk "SSH access ready for compute and entry servers"

    Write-LocalStep 2 6 "Package project" "Create a clean tar.gz archive, excluding node_modules, venv, dist, cache, and git metadata."
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
        database `
        deploy `
        frontend `
        README.md
    }
    finally {
        Pop-Location
    }

    Assert-LastExitCode "Local package creation failed. Check tar output above."
    $sizeKB = [math]::Round((Get-Item $TarName).Length / 1KB, 1)
    Write-LocalOk "Archive created: $TarName ($sizeKB KB)"

    Write-LocalStep 3 6 "Upload archive to compute server" "Target: ${ServerUser}@${ComputeServerIP}:/tmp/elys_project.tar.gz"
    Copy-RemoteFile -ServerIP $ComputeServerIP -LocalPath $TarName -RemotePath "/tmp/elys_project.tar.gz"
    Write-LocalOk "Compute server upload complete"

    Write-LocalStep 4 6 "Upload archive to entry server" "Target: ${ServerUser}@${EntryServerIP}:/tmp/elys_project.tar.gz"
    Copy-RemoteFile -ServerIP $EntryServerIP -LocalPath $TarName -RemotePath "/tmp/elys_project.tar.gz"
    Write-LocalOk "Entry server upload complete"

    Write-LocalStep 5 6 "Run remote compute deployment" "Role=compute; installs FastAPI, PostgreSQL, Redis, project data storage, and data Nginx."
    $resetDbArg = ""
    if ($ResetDb) {
        $resetDbArg = " --reset-db"
    }
    $resetStorageArg = ""
    if ($ResetStorage) {
        $resetStorageArg = " --reset-storage"
    }
    $resetDataRootArg = ""
    if ($ResetDataRoot) {
        $resetDataRootArg = " --reset-data-root"
    }
    $resetVenvArg = ""
    if ($ResetVenv) {
        $resetVenvArg = " --reset-venv"
    }
    $resetNodeModulesArg = ""
    if ($ResetNodeModules) {
        $resetNodeModulesArg = " --reset-node-modules"
    }
    $computeCmd = "rm -rf $RemoteTmp && mkdir -p $RemoteTmp && tar -xzf /tmp/elys_project.tar.gz -C $RemoteTmp && chmod +x $RemoteDeploy && rm -f /tmp/elys_project.tar.gz && $RemoteDeploy --role compute --entry-domain ${EntryDomain} --data-domain ${DataDomain} --entry-public-ip ${EntryServerIP} --compute-public-ip ${ComputeServerIP} --entry-access-host ${EntryAccessHost} --data-access-host ${DataAccessHost} --public-scheme ${PublicScheme} --studies-dir '${StudiesDir}' --extra-apt-packages '${ExtraAptPackages}' --use-cn-mirrors ${UseCnMirrors}${resetDbArg}${resetStorageArg}${resetDataRootArg}${resetVenvArg}"
    Invoke-Remote -ServerIP $ComputeServerIP -Command $computeCmd
    Write-LocalOk "Remote compute deployment complete"

    Write-LocalStep 6 6 "Run remote entry deployment" "Role=entry; builds Vue frontend and configures light API reverse proxy."
    $entryCmd = "rm -rf $RemoteTmp && mkdir -p $RemoteTmp && tar -xzf /tmp/elys_project.tar.gz -C $RemoteTmp && chmod +x $RemoteDeploy && rm -f /tmp/elys_project.tar.gz && $RemoteDeploy --role entry --entry-domain ${EntryDomain} --data-domain ${DataDomain} --entry-public-ip ${EntryServerIP} --compute-public-ip ${ComputeServerIP} --entry-access-host ${EntryAccessHost} --data-access-host ${DataAccessHost} --public-scheme ${PublicScheme} --data-upstream ${DataUpstream} --extra-apt-packages '${ExtraAptPackages}' --use-cn-mirrors ${UseCnMirrors}${resetNodeModulesArg}"
    Invoke-Remote -ServerIP $EntryServerIP -Command $entryCmd
    Write-LocalOk "Remote entry deployment complete"
}
catch {
    Write-FailureContext -ErrorMessage $_.Exception.Message
    throw
}
finally {
    Stop-SshMasters

    Write-Host ""
    Write-DeployRule DarkGray
    Write-Host "[LOCAL CLEANUP] Remove local archive" -ForegroundColor DarkGray
    Remove-Item $TarName -Force -ErrorAction SilentlyContinue
    Write-LocalOk "Cleanup complete"
}

Write-Host ""
Write-DeployRule Green
Write-Host " PASS " -BackgroundColor DarkGreen -ForegroundColor White -NoNewline
Write-Host "  部署成功 · ELYS DEPLOY SUCCESS" -ForegroundColor Green
Write-Host ""
Write-ConfigRow "Run ID" $DeployRunId Green
Write-ConfigRow "App" $EntryOrigin Cyan
Write-ConfigRow "Entry API health" "${EntryOrigin}/api/v1/health" Cyan
Write-ConfigRow "Data API health" "${DataOrigin}/api/v1/health" Cyan
Write-ConfigRow "API docs" "${DataOrigin}/docs" Cyan
Write-ConfigRow "Studies dir" $StudiesDir Cyan
Write-Host ""
Write-Host "  快速验证:" -ForegroundColor DarkGray
Write-Host "    curl.exe ${EntryOrigin}/api/v1/health" -ForegroundColor Gray
Write-Host "    curl.exe ${DataOrigin}/api/v1/health" -ForegroundColor Gray
Write-DeployRule Green
Write-Host ""
