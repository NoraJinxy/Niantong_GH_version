<#
.SYNOPSIS
  从 Windows 一键在【计算服务器】上跑 oss_smoke.py，验证 OSS【内网】endpoint 通不通。

.DESCRIPTION
  内网 endpoint (oss-cn-shenzhen-internal.aliyuncs.com) 只能在同地域 ECS 上解析，本机 laptop 测不了。
  本脚本：scp 上传 oss_smoke.py -> 在 /tmp 建临时 venv 装 oss2 -> 用内网 endpoint 跑冒烟 -> 清理临时文件。

  服务器 IP / 用户 / 端口从 deploy profile (elys_project/deploy/profiles/<profile>.env) 读，
  与 deploy_remote.ps1 同源（计算服 IP 每次部署会变，这里自动跟随，不用两头改）。

  OSS 凭证从本机环境变量 OSS_AK / OSS_SK 读，经 SSH 注入远端运行，不落盘、不进仓库。

.EXAMPLE
  $env:OSS_AK="LTAI..."; $env:OSS_SK="..."; .\run_oss_smoke_remote.ps1

.EXAMPLE
  # 临时指定计算服 IP（profile 没填 / 想测别的机器）
  $env:OSS_AK="LTAI..."; $env:OSS_SK="..."; .\run_oss_smoke_remote.ps1 -ComputeServerIP 1.2.3.4
#>
param(
    [string]$Bucket = "",
    [string]$Region = "",
    [string]$Profile = "aliyun-test",
    [string]$ComputeServerIP = "",
    [string]$ServerUser = "",
    [int]$Port = 0,
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\elys_deploy_ed25519",
    [switch]$KeepObject
)

$ErrorActionPreference = "Stop"

function Test-OssPlaceholder {
    param([string]$v)
    if ([string]::IsNullOrWhiteSpace($v)) { return $true }
    if ($v -match '[^\x00-\x7F]') { return $true }   # 含非 ASCII（中文占位符）
    if ($v -like '*你的*') { return $true }
    return $false
}

function Resolve-OssCred {
    # 取凭证：当前会话 -> 用户级环境变量 -> 仓库外凭证文件 -> 当场提示粘贴。任一步拿到非占位符就用它。
    param([string]$ProcVal, [string]$EnvName, [string]$FileVal, [string]$Prompt, [switch]$Secret)
    $val = $ProcVal
    if (Test-OssPlaceholder $val) { $val = [Environment]::GetEnvironmentVariable($EnvName, "User") }
    if (Test-OssPlaceholder $val) { $val = $FileVal }
    if (Test-OssPlaceholder $val) {
        if ($Secret) {
            $sec = Read-Host $Prompt -AsSecureString
            $val = [System.Net.NetworkCredential]::new("", $sec).Password
        } else {
            $val = Read-Host $Prompt
        }
    }
    if ($null -ne $val) { $val = $val.Trim() }
    return $val
}

# ---- 读 deploy profile（与 config.py / deploy_remote.ps1 同一份单一事实源）----
# 本脚本在 elys_scripts/oss_smoke/ 下，上溯两层到 repo 根。
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ProfilePath = Join-Path $RepoRoot "elys_project\deploy\profiles\$Profile.env"

$ProfileValues = @{}
if (Test-Path -LiteralPath $ProfilePath) {
    foreach ($line in Get-Content -LiteralPath $ProfilePath) {
        $t = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($t) -or $t.StartsWith("#")) { continue }
        $eq = $t.IndexOf("=")
        if ($eq -lt 1) { continue }
        $k = $t.Substring(0, $eq).Trim()
        $v = $t.Substring($eq + 1).Trim().Trim('"').Trim("'")
        $ProfileValues[$k] = $v
    }
}

if ([string]::IsNullOrWhiteSpace($ComputeServerIP) -and $ProfileValues.ContainsKey("COMPUTE_SERVER_IP")) {
    $ComputeServerIP = $ProfileValues["COMPUTE_SERVER_IP"]
}
if ([string]::IsNullOrWhiteSpace($ServerUser)) {
    if ($ProfileValues.ContainsKey("SERVER_USER")) { $ServerUser = $ProfileValues["SERVER_USER"] } else { $ServerUser = "root" }
}
if ($Port -eq 0) {
    if ($ProfileValues.ContainsKey("SSH_PORT")) { $Port = [int]$ProfileValues["SSH_PORT"] } else { $Port = 22 }
}
# OSS 桶/地域：命令行参数 > ACTIVE_SET 的 ${ACTIVE}_OSS_BUCKET > profile 扁平 OSS_BUCKET > 默认
$ossActiveSet = ""
if ($ProfileValues.ContainsKey("ACTIVE_SET")) { $ossActiveSet = "$($ProfileValues['ACTIVE_SET'])".Trim() }
if (-not $Bucket -and $ossActiveSet) { $Bucket = $ProfileValues[$ossActiveSet.ToUpper() + "_OSS_BUCKET"] }
if (-not $Bucket) { $Bucket = $ProfileValues["OSS_BUCKET"] }
if (-not $Bucket) { $Bucket = "elys-oss-test1" }
if (-not $Region) { $Region = $ProfileValues["OSS_REGION"] }
if (-not $Region) { $Region = "cn-shenzhen" }
$UseCnMirror = $true
if ($ProfileValues.ContainsKey("USE_CN_MIRRORS")) {
    $UseCnMirror = ($ProfileValues["USE_CN_MIRRORS"].Trim().ToLowerInvariant() -eq "true")
}

# ---- 前置校验 ----
# 读仓库外明文凭证文件 ~/.elys/oss.env（KEY=VALUE），作为环境变量之后的来源
$CredFile = Join-Path $env:USERPROFILE ".elys\oss.env"
$fileCreds = @{}
if (Test-Path -LiteralPath $CredFile) {
    foreach ($line in Get-Content -LiteralPath $CredFile) {
        $t = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($t) -or $t.StartsWith("#")) { continue }
        $eq = $t.IndexOf("="); if ($eq -lt 1) { continue }
        $fileCreds[$t.Substring(0, $eq).Trim().ToUpper()] = $t.Substring($eq + 1).Trim().Trim('"').Trim("'")
    }
}
$ak = Resolve-OssCred -ProcVal $env:OSS_AK -EnvName "OSS_AK" -FileVal $fileCreds["OSS_AK"] -Prompt "粘贴 AccessKey ID (LTAI 开头)"
$sk = Resolve-OssCred -ProcVal $env:OSS_SK -EnvName "OSS_SK" -FileVal $fileCreds["OSS_SK"] -Prompt "粘贴 AccessKey Secret (输入时不显示)" -Secret
if ((Test-OssPlaceholder $ak) -or (Test-OssPlaceholder $sk)) {
    Write-Host "[FAIL] 没拿到有效凭证（为空 / 含中文 / 还是占位符）。去 RAM 控制台拿真实 AccessKey。" -ForegroundColor Red
    exit 1
}
if ([string]::IsNullOrWhiteSpace($ComputeServerIP)) {
    Write-Host "[FAIL] 找不到计算服务器 IP。profile ($ProfilePath) 里 COMPUTE_SERVER_IP 为空" -ForegroundColor Red
    Write-Host "       先 .\buy_ecs.cmd 买实例，或用 -ComputeServerIP 显式指定。" -ForegroundColor Yellow
    exit 1
}
$LocalScript = Join-Path $PSScriptRoot "oss_smoke.py"
if (-not (Test-Path -LiteralPath $LocalScript)) {
    Write-Host "[FAIL] 找不到 oss_smoke.py：$LocalScript" -ForegroundColor Red
    exit 1
}

$Target = "${ServerUser}@${ComputeServerIP}"
$SshOpts = @(
    "-o", "StrictHostKeyChecking=no",
    "-o", "IdentitiesOnly=yes",
    "-o", "ConnectTimeout=15",
    "-i", $SshKeyPath
)

Write-Host ("=" * 70) -ForegroundColor DarkCyan
Write-Host " 远程 OSS 内网冒烟  ->  $Target  (port $Port)" -ForegroundColor Cyan
Write-Host ("   桶 {0} | 地域 {1} | 内网 endpoint | CN 镜像装 oss2={2}" -f $Bucket, $Region, $UseCnMirror) -ForegroundColor DarkGray
Write-Host ("=" * 70) -ForegroundColor DarkCyan

# ---- 1) 上传脚本 ----
Write-Host "[1/2] 上传 oss_smoke.py -> /tmp/oss_smoke.py" -ForegroundColor DarkGray
& scp -P $Port @SshOpts $LocalScript "${Target}:/tmp/oss_smoke.py"
if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] scp 上传失败（SSH key / 网络 / IP？）" -ForegroundColor Red; exit 1 }

# ---- 2) 远端：临时 venv 装 oss2，用内网 endpoint 跑，跑完清理 ----
$keepArg = ""
if ($KeepObject) { $keepArg = " --keep" }
$pipMirror = ""
if ($UseCnMirror) { $pipMirror = " -i https://pypi.tuna.tsinghua.edu.cn/simple" }

# 注意：AK/SK 以单引号包裹注入远端命令；阿里云 AccessKey 不含单引号，安全。
# 仅用于测试凭证；生产应给 ECS 挂 RAM 角色、不传明文 Key。
$remoteCmd = @"
set -e
LIBS=/tmp/oss_smoke_libs
# NO double-quotes below -- PS5.1 mangles embedded double-quotes passed to ssh.exe.
# Install oss2 into a target dir (avoids nested-venv pip-target quirks), run via PYTHONPATH.
PY=NONE
for cand in /var/www/elys/backend/venv/bin/python python3.11 python3; do
  if command -v `$cand >/dev/null 2>&1 && `$cand -m pip --version >/dev/null 2>&1; then PY=`$cand; break; fi
done
if [ `$PY = NONE ]; then echo '[FAIL] no python with pip on server (tried backend venv / python3.11 / python3)'; exit 3; fi
echo '[i] using' `$PY
rm -rf `$LIBS
`$PY -m pip install --target `$LIBS oss2$pipMirror
echo '[i] oss2 installed, running smoke...'
set +e
PYTHONPATH=`$LIBS OSS_AK='$ak' OSS_SK='$sk' `$PY /tmp/oss_smoke.py --where compute --bucket '$Bucket' --region '$Region'$keepArg
rc=`$?
set -e
rm -rf `$LIBS /tmp/oss_smoke.py
exit `$rc
"@

Write-Host "[2/2] 远端建临时 venv + 装 oss2 + 跑内网冒烟..." -ForegroundColor DarkGray
& ssh -p $Port @SshOpts $Target $remoteCmd
$rc = $LASTEXITCODE

Write-Host ("=" * 70) -ForegroundColor DarkCyan
if ($rc -eq 0) {
    Write-Host " [PASS] 计算服务器 -> OSS 内网通道、桶、权限 全部打通。" -ForegroundColor Green
} else {
    Write-Host " [FAIL] 远端冒烟未通过（看上面 oss_smoke 的逐步报告定位）。" -ForegroundColor Red
}
Write-Host ("=" * 70) -ForegroundColor DarkCyan
exit $rc
