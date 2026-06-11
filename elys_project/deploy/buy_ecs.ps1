<#
.SYNOPSIS
  按「自己制定的启动模板(LaunchTemplate) + 抢占式(Spot)」购买阿里云 ECS。
  无需 Python —— 底层用官方 aliyun CLI，跟 deploy_remote 一样 cmd → ps1。

.DESCRIPTION
  Purpose: 一键按启动模板开一台抢占式(便宜) ECS 计算服，拿到公网 IP 可回写 deploy profile。
  Related: deploy_remote.ps1 / deploy/profiles/*.env (COMPUTE_SERVER_IP，计算服 IP 单一数据源)。

  两种路径（优先启动模板）：
    ① 启动模板：-LaunchTemplateName 或 -LaunchTemplateId，规格(镜像/机型/安全组/交换机/盘)全在模板里，
       本脚本只叠加抢占式策略 + 数量；想临时改某项就单独给对应参数覆盖模板。
    ② 显式配置：不给模板时，靠 -InstanceType/-SecurityGroupId/-VSwitchId 等逐项指定。

  默认是【演练 DryRun】：只校验参数、不下单、不花钱。加 -Yes 才真正购买。
  抢占式默认 SpotAsPriceGo（系统按市场价自动出价，比按量便宜，但库存紧张时可能被释放）。

  前置（一次性）：
    1) 安装 aliyun CLI（单个 exe）：https://github.com/aliyun/aliyun-cli/releases
    2) 配置凭证：运行 `aliyun configure`，或设环境变量
       $env:ALIBABA_CLOUD_ACCESS_KEY_ID / $env:ALIBABA_CLOUD_ACCESS_KEY_SECRET

.EXAMPLE
  # 先看账号里有哪些 启动模板 / 安全组 / 交换机 / 镜像
  .\buy_ecs.cmd -List

.EXAMPLE
  # 演练：按模板 elys-compute 抢占式购买（只校验，不花钱）
  .\buy_ecs.cmd -LaunchTemplateName elys-compute

.EXAMPLE
  # 真买，并把拿到的公网 IP 写回 aliyun-test.env 的 COMPUTE_SERVER_IP
  .\buy_ecs.cmd -LaunchTemplateName elys-compute -Yes -UpdateProfile

.EXAMPLE
  # 设每小时上限价的抢占式
  .\buy_ecs.cmd -LaunchTemplateName elys-compute -SpotStrategy SpotWithPriceLimit -SpotPriceLimit 0.5 -Yes
#>
param(
    [string]$RegionId = "cn-shenzhen",   # 华南1(深圳)，跟现有计算服一致

    # ① 启动模板（自己在控制台「实例启动模板」里制定的那个）
    [string]$LaunchTemplateName = "",
    [string]$LaunchTemplateId = "lt-wz9agq2ncd0z03h1x46h",
    [string]$LaunchTemplateVersion = "",  # 留空=模板默认版本

    # ② 抢占式 Spot
    [ValidateSet("SpotAsPriceGo", "SpotWithPriceLimit", "NoSpot")]
    [string]$SpotStrategy = "SpotAsPriceGo",
    [double]$SpotPriceLimit = 0,           # 仅 SpotWithPriceLimit：每小时上限价
    [int]$SpotDuration = -1,               # 保护期小时 0-6；0=无保护期(最便宜)；-1=不设(用阿里云默认)
    [ValidateSet("", "Terminate", "Stop")]
    [string]$SpotInterruptionBehavior = "",

    [int]$Amount = 1,

    # ③ 覆盖项（用启动模板时留空即可，模板已含；给了则覆盖模板对应字段）
    [string]$InstanceType = "",
    [string]$ImageId = "",
    [string]$ImageFamily = "acs:ubuntu_22_04_x64",
    [string]$ZoneId = "",
    [string]$SecurityGroupId = "",
    [string]$VSwitchId = "",
    [string]$SystemDiskCategory = "",
    [int]$SystemDiskSize = 0,
    [int]$InternetMaxBandwidthOut = -1,    # Mbps，>0 才分配公网 IP；-1=不设(用模板)
    [string]$InternetChargeType = "",
    [string]$Password = "",                # 8-30 位，大小写/数字/符号至少三类
    [string]$KeyPairName = "",             # 优先于密码
    [string]$InstanceName = "",

    # 凭证：默认读环境变量（不进仓库）；也可先 aliyun configure
    [string]$AccessKeyId = $env:ALIBABA_CLOUD_ACCESS_KEY_ID,
    [string]$AccessKeySecret = $env:ALIBABA_CLOUD_ACCESS_KEY_SECRET,

    [string]$Profile = "aliyun-test",      # -UpdateProfile 时回写哪个 profile

    [switch]$List,
    [switch]$Yes,
    [switch]$UpdateProfile
)

$ErrorActionPreference = "Stop"

# ── 前置检查：aliyun CLI ───────────────────────────────────────────────────
if (-not (Get-Command aliyun -ErrorAction SilentlyContinue)) {
    Write-Host @'
[X] 未找到 aliyun CLI。请先安装（单个 exe，比装 Python SDK 省事）：
  1. 下载  https://github.com/aliyun/aliyun-cli/releases  （aliyun-cli-windows-*-amd64.zip）
  2. 解压出 aliyun.exe，放进 PATH 目录（或把它所在目录加入系统 Path）
  3. 配置凭证（二选一）：
     A) 运行  aliyun configure   交互式填 AccessKey / Secret / Region
     B) 设环境变量（本脚本默认读取）：
        $env:ALIBABA_CLOUD_ACCESS_KEY_ID="LTAI..."
        $env:ALIBABA_CLOUD_ACCESS_KEY_SECRET="..."
'@
    exit 1
}

# ── aliyun 调用封装：自动带 RegionId + 凭证，返回解析后的 JSON ───────────────
function Invoke-Aliyun {
    param([string[]]$CallArgs)
    $full = New-Object System.Collections.Generic.List[string]
    $full.AddRange($CallArgs)
    $full.AddRange([string[]]@("--RegionId", $RegionId))
    if ($AccessKeyId) { $full.AddRange([string[]]@("--access-key-id", $AccessKeyId)) }
    if ($AccessKeySecret) { $full.AddRange([string[]]@("--access-key-secret", $AccessKeySecret)) }
    $oldEnc = [Console]::OutputEncoding
    $oldEap = $ErrorActionPreference
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $ErrorActionPreference = "Continue"
    try { $raw = & aliyun @($full.ToArray()) 2>&1 }
    finally {
        [Console]::OutputEncoding = $oldEnc
        $ErrorActionPreference = $oldEap
    }
    $text = $raw | ForEach-Object { if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ } }
    $joined = $text -join "`n"
    if ($LASTEXITCODE -ne 0) {
        if ($joined -match 'DryRunOperation') { return $null }  # DryRun 校验通过，阿里云用非零码表示"验证成功但未下单"
        throw "aliyun 调用失败 (exit $LASTEXITCODE)：`n$joined"
    }
    return ($joined | ConvertFrom-Json)
}

# ── -List：列出填参要用的资源 ──────────────────────────────────────────────
if ($List) {
    Write-Host "== 启动模板 (-LaunchTemplateName / -LaunchTemplateId) ==" -ForegroundColor Cyan
    (Invoke-Aliyun @("ecs", "DescribeLaunchTemplates")).LaunchTemplateSets.LaunchTemplateSet |
        Format-Table LaunchTemplateId, LaunchTemplateName, DefaultVersionNumber, LatestVersionNumber -AutoSize

    Write-Host "== 安全组 (-SecurityGroupId) ==" -ForegroundColor Cyan
    (Invoke-Aliyun @("ecs", "DescribeSecurityGroups", "--MaxResults", "50")).SecurityGroups.SecurityGroup |
        Format-Table SecurityGroupId, SecurityGroupName, VpcId -AutoSize

    Write-Host "== 交换机 (-VSwitchId) ==" -ForegroundColor Cyan
    (Invoke-Aliyun @("vpc", "DescribeVSwitches", "--PageSize", "50")).VSwitches.VSwitch |
        Format-Table VSwitchId, ZoneId, CidrBlock, VSwitchName -AutoSize

    Write-Host "== 最新镜像 ($ImageFamily) (-ImageId，留空自动取最新) ==" -ForegroundColor Cyan
    (Invoke-Aliyun @("ecs", "DescribeImages", "--ImageOwnerAlias", "system", "--ImageFamily", $ImageFamily, "--Status", "Available", "--PageSize", "10")).Images.Image |
        Sort-Object CreationTime -Descending | Select-Object -First 5 |
        Format-Table ImageId, OSName -AutoSize
    return
}

# ── 自动选最新镜像（仅显式模式且未给 ImageId 时）───────────────────────────
function Resolve-LatestImage {
    $imgs = (Invoke-Aliyun @("ecs", "DescribeImages", "--ImageOwnerAlias", "system", "--ImageFamily", $ImageFamily, "--Status", "Available", "--PageSize", "100")).Images.Image |
        Sort-Object CreationTime -Descending
    if (-not $imgs) { throw "找不到镜像族 $ImageFamily 的可用系统镜像，请用 -ImageId 指定。" }
    Write-Host "自动选用镜像: $($imgs[0].ImageId) ($($imgs[0].OSName))"
    return $imgs[0].ImageId
}

# ── 组装 RunInstances 参数 ─────────────────────────────────────────────────
$a = New-Object System.Collections.Generic.List[string]
$a.AddRange([string[]]@("ecs", "RunInstances"))
$a.AddRange([string[]]@("--Amount", "$Amount"))
$a.AddRange([string[]]@("--MinAmount", "$Amount"))
$a.AddRange([string[]]@("--ClientToken", ([guid]::NewGuid().ToString("N"))))  # 幂等：网络重试不会重复下单
if ($Amount -gt 1) { $a.AddRange([string[]]@("--UniqueSuffix", "true")) }

# 抢占式
$a.AddRange([string[]]@("--SpotStrategy", $SpotStrategy))
if ($SpotStrategy -eq "SpotWithPriceLimit") {
    if ($SpotPriceLimit -le 0) { throw "-SpotStrategy SpotWithPriceLimit 需要 -SpotPriceLimit（每小时上限价，如 0.5）。" }
    $a.AddRange([string[]]@("--SpotPriceLimit", "$SpotPriceLimit"))
}
if ($SpotDuration -ge 0) { $a.AddRange([string[]]@("--SpotDuration", "$SpotDuration")) }
if ($SpotInterruptionBehavior) { $a.AddRange([string[]]@("--SpotInterruptionBehavior", $SpotInterruptionBehavior)) }

# DryRun：默认 true(演练)，-Yes 才 false(真买)
if ($Yes) { $a.AddRange([string[]]@("--DryRun", "false")) } else { $a.AddRange([string[]]@("--DryRun", "true")) }

$useTemplate = ($LaunchTemplateName -ne "") -or ($LaunchTemplateId -ne "")

if ($useTemplate) {
    if ($LaunchTemplateId) { $a.AddRange([string[]]@("--LaunchTemplateId", $LaunchTemplateId)) }
    if ($LaunchTemplateName) { $a.AddRange([string[]]@("--LaunchTemplateName", $LaunchTemplateName)) }
    if ($LaunchTemplateVersion) { $a.AddRange([string[]]@("--LaunchTemplateVersion", $LaunchTemplateVersion)) }
    # 覆盖项：只下发显式设置的，避免清空模板里的值
    if ($InstanceType) { $a.AddRange([string[]]@("--InstanceType", $InstanceType)) }
    if ($ImageId) { $a.AddRange([string[]]@("--ImageId", $ImageId)) }
    if ($ZoneId) { $a.AddRange([string[]]@("--ZoneId", $ZoneId)) }
    if ($SecurityGroupId) { $a.AddRange([string[]]@("--SecurityGroupId", $SecurityGroupId)) }
    if ($VSwitchId) { $a.AddRange([string[]]@("--VSwitchId", $VSwitchId)) }
    if ($SystemDiskCategory) { $a.AddRange([string[]]@("--SystemDisk.Category", $SystemDiskCategory)) }
    if ($SystemDiskSize -gt 0) { $a.AddRange([string[]]@("--SystemDisk.Size", "$SystemDiskSize")) }
    if ($InternetChargeType) { $a.AddRange([string[]]@("--InternetChargeType", $InternetChargeType)) }
    if ($InternetMaxBandwidthOut -ge 0) { $a.AddRange([string[]]@("--InternetMaxBandwidthOut", "$InternetMaxBandwidthOut")) }
    if ($Password) { $a.AddRange([string[]]@("--Password", $Password)) }
    if ($KeyPairName) { $a.AddRange([string[]]@("--KeyPairName", $KeyPairName)) }
    if ($InstanceName) { $a.AddRange([string[]]@("--InstanceName", $InstanceName)) }
}
else {
    if (-not $SecurityGroupId -or -not $VSwitchId) {
        throw "没用启动模板时，必须给 -SecurityGroupId 和 -VSwitchId（先跑 .\buy_ecs.cmd -List 查），或改用 -LaunchTemplateName。"
    }
    $it = if ($InstanceType) { $InstanceType } else { "ecs.e-c1m2.large" }
    $img = if ($ImageId) { $ImageId } else { Resolve-LatestImage }
    $a.AddRange([string[]]@("--InstanceType", $it))
    $a.AddRange([string[]]@("--ImageId", $img))
    $a.AddRange([string[]]@("--SecurityGroupId", $SecurityGroupId))
    $a.AddRange([string[]]@("--VSwitchId", $VSwitchId))
    if ($ZoneId) { $a.AddRange([string[]]@("--ZoneId", $ZoneId)) }
    $cat = if ($SystemDiskCategory) { $SystemDiskCategory } else { "cloud_essd" }
    $sz = if ($SystemDiskSize -gt 0) { $SystemDiskSize } else { 40 }
    $a.AddRange([string[]]@("--SystemDisk.Category", $cat))
    $a.AddRange([string[]]@("--SystemDisk.Size", "$sz"))
    $ict = if ($InternetChargeType) { $InternetChargeType } else { "PayByTraffic" }
    $bw = if ($InternetMaxBandwidthOut -ge 0) { $InternetMaxBandwidthOut } else { 5 }
    $a.AddRange([string[]]@("--InternetChargeType", $ict))
    $a.AddRange([string[]]@("--InternetMaxBandwidthOut", "$bw"))
    $nm = if ($InstanceName) { $InstanceName } else { "elys-compute" }
    $a.AddRange([string[]]@("--InstanceName", $nm))
    $a.AddRange([string[]]@("--HostName", $nm))
    if ($Password) { $a.AddRange([string[]]@("--Password", $Password)) }
    if ($KeyPairName) { $a.AddRange([string[]]@("--KeyPairName", $KeyPairName)) }
    $a.AddRange([string[]]@("--Tag.1.Key", "project", "--Tag.1.Value", "elys"))
}

# ── 概要 ───────────────────────────────────────────────────────────────────
Write-Host ("=" * 64)
if ($useTemplate) {
    $lt = if ($LaunchTemplateId) { $LaunchTemplateId } else { $LaunchTemplateName }
    $ver = if ($LaunchTemplateVersion) { $LaunchTemplateVersion } else { "默认" }
    Write-Host "  启动模板    : $lt (版本 $ver)"
}
else {
    Write-Host "  模式        : 显式配置（无启动模板）"
}
Write-Host "  抢占式策略  : $SpotStrategy"
Write-Host "  地域 / 数量 : $RegionId / $Amount"
$mode = if ($Yes) { "真买(会扣费)" } else { "演练 DryRun(不花钱)" }
Write-Host "  执行模式    : $mode"
Write-Host ("=" * 64)

# ── 执行 ───────────────────────────────────────────────────────────────────
$res = Invoke-Aliyun $a.ToArray()

if (-not $Yes) {
    Write-Host "[OK] DryRun 校验通过：参数没问题，没有真正下单、没有花钱。" -ForegroundColor Green
    Write-Host "     确认无误后真买：在原命令后加  -Yes"
    return
}

$instanceId = $res.InstanceIdSets.InstanceIdSet[0]
Write-Host "[OK] 已下单（抢占式）实例: $instanceId" -ForegroundColor Green

# ── 轮询到 Running，取公网 IP ──────────────────────────────────────────────
$ip = ""
$priv = ""
$deadline = (Get-Date).AddSeconds(300)
while ((Get-Date) -lt $deadline) {
    $all  = (Invoke-Aliyun @("ecs", "DescribeInstances", "--PageSize", "50")).Instances.Instance
    $inst = $all | Where-Object { $_.InstanceId -eq $instanceId } | Select-Object -First 1
    if ($inst -and $inst.Status -eq "Running") {
        if ($inst.PublicIpAddress.IpAddress.Count -gt 0) { $ip = $inst.PublicIpAddress.IpAddress[0] }
        elseif ($inst.EipAddress.IpAddress) { $ip = $inst.EipAddress.IpAddress }
        if ($inst.VpcAttributes.PrivateIpAddress.IpAddress.Count -gt 0) { $priv = $inst.VpcAttributes.PrivateIpAddress.IpAddress[0] }
        break
    }
    $st = if ($inst) { $inst.Status } else { "未知" }
    Write-Host "  …等待启动中（当前状态: $st）"
    Start-Sleep -Seconds 5
}
if (-not $ip -and -not $priv) { Write-Host "  ⚠ 等待 Running 超时或未拿到 IP，请到 ECS 控制台查看。" -ForegroundColor Yellow }

Write-Host ("-" * 64)
Write-Host "  实例 ID  : $instanceId"
$ipShow = if ($ip) { $ip } else { "(无，检查带宽/模板是否分配了公网)" }
Write-Host "  公网 IP  : $ipShow"
Write-Host "  内网 IP  : $priv"
if ($ip) { Write-Host "  SSH      : ssh root@$ip" }
Write-Host "  ⚠ 抢占式实例库存紧张时可能被自动释放，重要数据别只放这台。" -ForegroundColor Yellow
Write-Host ("-" * 64)

# ── 可选：回写 profile 的 COMPUTE_SERVER_IP ────────────────────────────────
if ($UpdateProfile -and $ip) {
    $profilePath = Join-Path $PSScriptRoot "profiles\$Profile.env"
    if (Test-Path $profilePath) {
        $lines = Get-Content -Path $profilePath
        $hit = $false
        $out = foreach ($line in $lines) {
            if ($line -match '^\s*COMPUTE_SERVER_IP=') { $hit = $true; "COMPUTE_SERVER_IP=$ip" }
            else { $line }
        }
        if (-not $hit) { $out += "COMPUTE_SERVER_IP=$ip" }
        $enc = New-Object System.Text.UTF8Encoding($false)   # UTF-8 无 BOM，跟现有 .env 一致
        [System.IO.File]::WriteAllLines($profilePath, [string[]]$out, $enc)
        Write-Host "[OK] 已把 COMPUTE_SERVER_IP=$ip 写回 $Profile.env" -ForegroundColor Green
        Write-Host "     接着就能部署：  .\deploy_remote.cmd -Profile $Profile"
    }
    else {
        Write-Host "  ⚠ 没找到 $profilePath，跳过回写。" -ForegroundColor Yellow
    }
}
elseif ($ip) {
    Write-Host "提示：把这 IP 设为 ELYS 计算服，加 -UpdateProfile 自动回写 $Profile.env。"
}
