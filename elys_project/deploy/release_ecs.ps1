<#
.SYNOPSIS
  释放(退还)阿里云 ECS 计算服实例。与 step1 buy_ecs 配对。

.EXAMPLE
  .\step4_release_ecs.cmd -List
  .\step4_release_ecs.cmd -InstanceId i-wz9xxxxxxxxx
  .\step4_release_ecs.cmd -InstanceId i-wz9xxxxxxxxx -Yes -UpdateProfile
  .\step4_release_ecs.cmd -Yes -UpdateProfile
#>
param(
    [string]$RegionId        = "cn-shenzhen",
    [string]$InstanceId      = "",
    [string]$Profile         = "aliyun-test",
    [string]$AccessKeyId     = $env:ALIBABA_CLOUD_ACCESS_KEY_ID,
    [string]$AccessKeySecret = $env:ALIBABA_CLOUD_ACCESS_KEY_SECRET,
    [switch]$List,
    [switch]$Yes,
    [switch]$UpdateProfile
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Accent    = [ConsoleColor]::DarkRed   # step4 主色:释放=红
$rule      = '  ' + (([string][char]0x2500) * 64)

if (-not (Get-Command aliyun -ErrorAction SilentlyContinue)) {
    Write-Host "[X] 未找到 aliyun CLI。" -ForegroundColor Red
    exit 1
}

function Invoke-Aliyun {
    param([string[]]$CallArgs)
    $full = New-Object System.Collections.Generic.List[string]
    $full.AddRange($CallArgs)
    $full.AddRange([string[]]@("--RegionId", $RegionId))
    if ($AccessKeyId)     { $full.AddRange([string[]]@("--access-key-id",     $AccessKeyId)) }
    if ($AccessKeySecret) { $full.AddRange([string[]]@("--access-key-secret", $AccessKeySecret)) }
    $oldEnc = [Console]::OutputEncoding
    $oldEap = $ErrorActionPreference
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $ErrorActionPreference = "Continue"
    try   { $raw = & aliyun @($full.ToArray()) 2>&1 }
    finally {
        [Console]::OutputEncoding = $oldEnc
        $ErrorActionPreference = $oldEap
    }
    $text   = $raw | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ } }
    $joined = $text -join "`n"
    if ($LASTEXITCODE -ne 0) { throw "aliyun 调用失败 (exit $LASTEXITCODE)：`n$joined" }
    return ($joined | ConvertFrom-Json)
}

function Get-AllInstances {
    (Invoke-Aliyun @("ecs", "DescribeInstances", "--PageSize", "50")).Instances.Instance
}

function Get-ProfileIp {
    $path = Join-Path $ScriptDir "profiles\$Profile.env"
    if (-not (Test-Path $path)) { return "" }
    foreach ($line in Get-Content $path -Encoding UTF8) {
        if ($line -match '^\s*COMPUTE_SERVER_IP=(.+)') { return $Matches[1].Trim() }
    }
    return ""
}

function Clear-ProfileIp {
    $path = Join-Path $ScriptDir "profiles\$Profile.env"
    if (-not (Test-Path $path)) { Write-Host "  ⚠ 没找到 $path，跳过清空。" -ForegroundColor Yellow; return }
    $enc = New-Object System.Text.UTF8Encoding($false)
    $out = Get-Content $path -Encoding UTF8 | ForEach-Object { if ($_ -match '^\s*COMPUTE_SERVER_IP=') { "COMPUTE_SERVER_IP=" } else { $_ } }
    [System.IO.File]::WriteAllLines($path, [string[]]$out, $enc)
    Write-Host "[OK] 已清空 $Profile.env 的 COMPUTE_SERVER_IP" -ForegroundColor Green
}

function Write-InstanceIp {
    param($Inst)
    if ($Inst.PublicIpAddress.IpAddress.Count -gt 0) { return $Inst.PublicIpAddress.IpAddress[0] }
    if ($Inst.EipAddress.IpAddress) { return $Inst.EipAddress.IpAddress }
    return "-"
}

# ── -List：列出所有实例 ─────────────────────────────────────────────────────
if ($List) {
    Write-Host "── 实例列表 ──" -ForegroundColor $Accent
    $insts = Get-AllInstances
    if (-not $insts) { Write-Host "  (空)" -ForegroundColor DarkGray; return }
    $insts | ForEach-Object {
        [PSCustomObject]@{
            InstanceId = $_.InstanceId
            名称       = $_.InstanceName
            状态       = $_.Status
            公网IP     = (Write-InstanceIp $_)
            规格       = $_.InstanceType
            创建时间   = $_.CreationTime
        }
    } | Format-Table -AutoSize
    Write-Host "  释放指定实例:  .\step4_release_ecs.cmd -InstanceId <id> [-Yes] [-UpdateProfile]" -ForegroundColor DarkGray
    return
}

# ── 未给 -InstanceId 时，按 profile 里的 IP 反查 ────────────────────────────
if (-not $InstanceId) {
    $profileIp = Get-ProfileIp
    if (-not $profileIp) {
        Write-Host "[X] 没给 -InstanceId，且 $Profile.env 的 COMPUTE_SERVER_IP 为空。" -ForegroundColor Red
        Write-Host "    先查实例:  .\step4_release_ecs.cmd -List" -ForegroundColor DarkGray
        exit 1
    }
    Write-Host "  按 IP $profileIp 反查实例 ..." -ForegroundColor DarkGray
    $all  = Get-AllInstances
    $inst = $all | Where-Object {
        ($_.PublicIpAddress.IpAddress -contains $profileIp) -or ($_.EipAddress.IpAddress -eq $profileIp)
    } | Select-Object -First 1
    if (-not $inst) {
        Write-Host "  该 IP 没对应实例（已经释放过了？）" -ForegroundColor Yellow
        if ($UpdateProfile) { Clear-ProfileIp }
        exit 0
    }
    $InstanceId = $inst.InstanceId
    Write-Host "  找到: $InstanceId ($($inst.InstanceName))" -ForegroundColor DarkGray
}

# ── 取实例详情（在 PS 里过滤，绕开 --InstanceIds 的 Windows 引号坑）────────
$all  = Get-AllInstances
$inst = $all | Where-Object { $_.InstanceId -eq $InstanceId } | Select-Object -First 1
if (-not $inst) {
    Write-Host "[X] 实例 $InstanceId 不存在（已经释放过了？）" -ForegroundColor Yellow
    if ($UpdateProfile) { Clear-ProfileIp }
    exit 0
}

$ip = Write-InstanceIp $inst

Write-Host $rule -ForegroundColor $Accent
Write-Host "  实例 ID     " -ForegroundColor DarkGray -NoNewline
Write-Host $InstanceId -ForegroundColor White
Write-Host "  名称        " -ForegroundColor DarkGray -NoNewline
Write-Host $inst.InstanceName
Write-Host "  状态        " -ForegroundColor DarkGray -NoNewline
Write-Host $inst.Status
Write-Host "  公网 IP     " -ForegroundColor DarkGray -NoNewline
Write-Host $ip -ForegroundColor Cyan
Write-Host "  规格        " -ForegroundColor DarkGray -NoNewline
Write-Host $inst.InstanceType
Write-Host "  执行模式    " -ForegroundColor DarkGray -NoNewline
if ($Yes) { Write-Host " 释放 " -BackgroundColor DarkRed -ForegroundColor White -NoNewline; Write-Host "  永久删除，不可恢复！" -ForegroundColor Red }
else      { Write-Host " 演练 " -BackgroundColor DarkYellow -ForegroundColor Black -NoNewline; Write-Host "  DryRun 不执行任何操作" -ForegroundColor Yellow }
Write-Host $rule -ForegroundColor $Accent

if (-not $Yes) {
    Write-Host ""
    Write-Host "  [演练] 确认无误后真正释放，加 -Yes：" -ForegroundColor Yellow
    $extra = if ($UpdateProfile) { " -UpdateProfile" } else { "" }
    Write-Host "    .\step4_release_ecs.cmd -InstanceId $InstanceId -Yes$extra" -ForegroundColor Gray
    return
}

# ── 真正释放 ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  正在释放 $InstanceId ..." -ForegroundColor Red
try {
    Invoke-Aliyun @("ecs", "DeleteInstance", "--InstanceId", $InstanceId, "--Force", "true") | Out-Null
    Write-Host ""
    Write-Host " PASS " -BackgroundColor DarkGreen -ForegroundColor White -NoNewline
    Write-Host "  释放指令已下发，实例将在数秒内销毁。" -ForegroundColor Green
} catch {
    if ($_ -match "ChargeTypeViolation") {
        Write-Host ""
        Write-Host " FAIL " -BackgroundColor DarkRed -ForegroundColor White -NoNewline
        Write-Host "  这是包年包月实例，API 删不了。" -ForegroundColor Yellow
        Write-Host "        DeleteInstance 只支持按量/抢占式实例；" -ForegroundColor Yellow
        Write-Host "        包月实例请到 ECS 控制台关闭自动续费或申请退款，到期自动释放。" -ForegroundColor Yellow
        exit 2
    }
    throw
}

if ($UpdateProfile) { Clear-ProfileIp }

Write-Host ""
Write-Host "  下次开机:  .\step1_buy_ecs.cmd -Yes -UpdateProfile" -ForegroundColor DarkGray
