<#
.SYNOPSIS
  在【计算服务器】上把后端切到 OSS 存储后端（或用 -Disable 切回 local）。

.DESCRIPTION
  通过 systemd drop-in override 注入 OSS 环境变量，给 elys-backend / elys-worker 两个服务：
    /etc/systemd/system/<svc>.service.d/oss.conf
  drop-in 在 .d/ 目录，重部署重写 .service 主文件不会动它、重启自动合并——能扛住「重部署清空→跑 s3」循环。

  为什么不改 backend/.env：deploy.sh 每次部署都重写 .env，手改会被冲掉；drop-in 不会。

  服务器 IP/用户/端口从 deploy profile 读（同 deploy_remote.ps1）。
  OSS 凭证从本机 env / 仓库外文件 ~/.elys/oss.env 读，经 SSH 写进服务器 root-only 文件，不落仓库。

.EXAMPLE
  $env:OSS_AK="LTAI..."; $env:OSS_SK="..."; .\enable_oss_remote.ps1

.EXAMPLE
  .\enable_oss_remote.ps1 -Disable     # 切回 local 后端
#>
param(
    [string]$Bucket = "elys-oss-test1",
    [string]$Endpoint = "oss-cn-shenzhen-internal.aliyuncs.com",
    [string]$Profile = "aliyun-test",
    [string]$ComputeServerIP = "",
    [string]$ServerUser = "",
    [int]$Port = 0,
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\elys_deploy_ed25519",
    [switch]$Disable
)

$ErrorActionPreference = "Stop"

function Test-OssPlaceholder {
    param([string]$v)
    if ([string]::IsNullOrWhiteSpace($v)) { return $true }
    if ($v -match '[^\x00-\x7F]') { return $true }
    if ($v -like '*你的*') { return $true }
    return $false
}

function Resolve-OssCred {
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

# ---- 读 deploy profile ----
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ProfilePath = Join-Path $RepoRoot "elys_project\deploy\profiles\$Profile.env"
$ProfileValues = @{}
if (Test-Path -LiteralPath $ProfilePath) {
    foreach ($line in Get-Content -LiteralPath $ProfilePath) {
        $t = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($t) -or $t.StartsWith("#")) { continue }
        $eq = $t.IndexOf("="); if ($eq -lt 1) { continue }
        $ProfileValues[$t.Substring(0, $eq).Trim().ToUpper()] = $t.Substring($eq + 1).Trim().Trim('"').Trim("'")
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
if ([string]::IsNullOrWhiteSpace($ComputeServerIP)) {
    Write-Host "[FAIL] 找不到计算服务器 IP（profile COMPUTE_SERVER_IP 为空）。先 buy_ecs 或用 -ComputeServerIP。" -ForegroundColor Red
    exit 1
}

$Target = "${ServerUser}@${ComputeServerIP}"
$SshOpts = @("-o", "StrictHostKeyChecking=no", "-o", "IdentitiesOnly=yes", "-o", "ConnectTimeout=15", "-i", $SshKeyPath)

if ($Disable) {
    Write-Host "切回 local 后端 -> $Target" -ForegroundColor Cyan
    $remoteCmd = @"
set -e
rm -f /etc/systemd/system/elys-backend.service.d/oss.conf /etc/systemd/system/elys-worker.service.d/oss.conf
systemctl daemon-reload
systemctl restart elys-backend elys-worker
echo OSS_DISABLED
"@
    & ssh -p $Port @SshOpts $Target $remoteCmd
    if ($LASTEXITCODE -eq 0) { Write-Host "[OK] 已切回 local 后端（drop-in 已删、服务已重启）" -ForegroundColor Green }
    exit $LASTEXITCODE
}

# ---- 解析凭证 ----
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
    Write-Host "[FAIL] 没拿到有效凭证（为空 / 含中文 / 占位符）。去 RAM 控制台拿真实 AccessKey。" -ForegroundColor Red
    exit 1
}

Write-Host ("切到 OSS 后端 -> {0}  桶 {1} | 内网 {2}" -f $Target, $Bucket, $Endpoint) -ForegroundColor Cyan
# 远端命令纯 ASCII、无双引号（避开 PS5.1 传 ssh 的引号 mangle）；值由 PS 插入，heredoc 用引号定界符不让 bash 再展开。
$remoteCmd = @"
set -e
for svc in elys-backend elys-worker; do
  D=/etc/systemd/system/`$svc.service.d
  mkdir -p `$D
  cat > `$D/oss.conf <<'CONF'
[Service]
Environment=STORAGE_BACKEND=oss
Environment=OSS_ENDPOINT=$Endpoint
Environment=OSS_BUCKET=$Bucket
Environment=OSS_ACCESS_KEY_ID=$ak
Environment=OSS_ACCESS_KEY_SECRET=$sk
CONF
  chmod 600 `$D/oss.conf
done
systemctl daemon-reload
systemctl restart elys-backend elys-worker
echo OSS_ENABLED
"@
& ssh -p $Port @SshOpts $Target $remoteCmd
$rc = $LASTEXITCODE
if ($rc -eq 0) {
    Write-Host "[OK] 后端已切到 OSS（drop-in 写入 + 服务重启）。上传/处理数据后去 OSS 控制台看「文件数量」0->N。" -ForegroundColor Green
    Write-Host "     切回：.\enable_oss_remote.ps1 -Disable" -ForegroundColor DarkGray
} else {
    Write-Host "[FAIL] 切换失败（看上面 ssh 输出）。" -ForegroundColor Red
}
exit $rc
