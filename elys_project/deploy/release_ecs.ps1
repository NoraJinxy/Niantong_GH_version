<#
.SYNOPSIS
  Release (terminate) an Alibaba Cloud ECS compute instance.

.EXAMPLE
  .\release_ecs.cmd -List
  .\release_ecs.cmd -InstanceId i-wz9xxxxxxxxx
  .\release_ecs.cmd -InstanceId i-wz9xxxxxxxxx -Yes -UpdateProfile
  .\release_ecs.cmd -Yes -UpdateProfile
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

if (-not (Get-Command aliyun -ErrorAction SilentlyContinue)) {
    Write-Host "[X] aliyun CLI not found." -ForegroundColor Red
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
    if ($LASTEXITCODE -ne 0) { throw "aliyun failed (exit $LASTEXITCODE):`n$joined" }
    return ($joined | ConvertFrom-Json)
}

function Get-ProfileIp {
    $path = Join-Path $ScriptDir "profiles\$Profile.env"
    if (-not (Test-Path $path)) { return "" }
    foreach ($line in Get-Content $path) {
        if ($line -match '^\s*COMPUTE_SERVER_IP=(.+)') { return $Matches[1].Trim() }
    }
    return ""
}

function Clear-ProfileIp {
    $path = Join-Path $ScriptDir "profiles\$Profile.env"
    if (-not (Test-Path $path)) { Write-Host "  [WARN] $path not found, skipping." -ForegroundColor Yellow; return }
    $enc = New-Object System.Text.UTF8Encoding($false)
    $out = Get-Content $path | ForEach-Object { if ($_ -match '^\s*COMPUTE_SERVER_IP=') { "COMPUTE_SERVER_IP=" } else { $_ } }
    [System.IO.File]::WriteAllLines($path, [string[]]$out, $enc)
    Write-Host "  [OK] COMPUTE_SERVER_IP cleared in $Profile.env" -ForegroundColor Green
}

# -List
if ($List) {
    Write-Host "== Instances ==" -ForegroundColor Cyan
    $insts = (Invoke-Aliyun @("ecs", "DescribeInstances", "--PageSize", "50")).Instances.Instance
    if (-not $insts) { Write-Host "  (none)" -ForegroundColor Gray; return }
    $insts | ForEach-Object {
        $ip = if ($_.PublicIpAddress.IpAddress.Count -gt 0) { $_.PublicIpAddress.IpAddress[0] }
              elseif ($_.EipAddress.IpAddress) { $_.EipAddress.IpAddress }
              else { "-" }
        [PSCustomObject]@{
            InstanceId   = $_.InstanceId
            Name         = $_.InstanceName
            Status       = $_.Status
            PublicIP     = $ip
            Type         = $_.InstanceType
            Created      = $_.CreationTime
        }
    } | Format-Table -AutoSize
    Write-Host "To release:  .\release_ecs.cmd -InstanceId <id> [-Yes] [-UpdateProfile]" -ForegroundColor Yellow
    return
}

function Get-AllInstances {
    (Invoke-Aliyun @("ecs", "DescribeInstances", "--PageSize", "50")).Instances.Instance
}

# Resolve InstanceId from profile IP if not given
if (-not $InstanceId) {
    $profileIp = Get-ProfileIp
    if (-not $profileIp) {
        Write-Host "[X] No -InstanceId and COMPUTE_SERVER_IP is empty in $Profile.env" -ForegroundColor Red
        Write-Host "    Run:  .\release_ecs.cmd -List"
        exit 1
    }
    Write-Host "  Looking up instance by IP $profileIp ..." -ForegroundColor Gray
    $all  = Get-AllInstances
    $inst = $all | Where-Object {
        ($_.PublicIpAddress.IpAddress -contains $profileIp) -or ($_.EipAddress.IpAddress -eq $profileIp)
    } | Select-Object -First 1
    if (-not $inst) {
        Write-Host "  No instance found for IP $profileIp (already released?)" -ForegroundColor Yellow
        if ($UpdateProfile) { Clear-ProfileIp }
        exit 0
    }
    $InstanceId = $inst.InstanceId
    Write-Host "  Found: $InstanceId ($($inst.InstanceName))" -ForegroundColor Gray
}

# Fetch details (filter in PS to avoid --InstanceIds JSON quoting issues on Windows)
$all  = Get-AllInstances
$inst = $all | Where-Object { $_.InstanceId -eq $InstanceId } | Select-Object -First 1
if (-not $inst) {
    Write-Host "[X] Instance $InstanceId not found (already released?)." -ForegroundColor Yellow
    if ($UpdateProfile) { Clear-ProfileIp }
    exit 0
}

$ip = if ($inst.PublicIpAddress.IpAddress.Count -gt 0) { $inst.PublicIpAddress.IpAddress[0] }
      elseif ($inst.EipAddress.IpAddress) { $inst.EipAddress.IpAddress }
      else { "-" }

Write-Host ("=" * 56)
Write-Host ("  InstanceId : " + $InstanceId)
Write-Host ("  Name       : " + $inst.InstanceName)
Write-Host ("  Status     : " + $inst.Status)
Write-Host ("  PublicIP   : " + $ip)
Write-Host ("  Type       : " + $inst.InstanceType)
if ($Yes) {
    Write-Host "  Mode       : RELEASE -- permanent delete, irreversible!" -ForegroundColor Red
} else {
    Write-Host "  Mode       : DryRun (no action)" -ForegroundColor Yellow
}
Write-Host ("=" * 56)

if (-not $Yes) {
    Write-Host ""
    Write-Host "[DryRun] Add -Yes to actually release:" -ForegroundColor Yellow
    $extra = if ($UpdateProfile) { " -UpdateProfile" } else { "" }
    Write-Host "  .\release_ecs.cmd -InstanceId $InstanceId -Yes$extra"
    return
}

# Release
Write-Host ""
Write-Host "Releasing $InstanceId ..." -ForegroundColor Red
try {
    Invoke-Aliyun @("ecs", "DeleteInstance", "--InstanceId", $InstanceId, "--Force", "true") | Out-Null
    Write-Host "[OK] Release command sent. Instance will terminate in seconds." -ForegroundColor Green
} catch {
    if ($_ -match "ChargeTypeViolation") {
        Write-Host "[!] This instance is a subscription (monthly/annual) instance." -ForegroundColor Yellow
        Write-Host "    DeleteInstance API only works for pay-as-you-go / spot instances." -ForegroundColor Yellow
        Write-Host "    To release it: go to the ECS console and disable auto-renewal," -ForegroundColor Yellow
        Write-Host "    or submit a refund request. It will be released on expiry." -ForegroundColor Yellow
        exit 2
    }
    throw
}

if ($UpdateProfile) { Clear-ProfileIp }

Write-Host ""
Write-Host "Next time: .\buy_ecs.cmd -Yes -UpdateProfile" -ForegroundColor Gray
