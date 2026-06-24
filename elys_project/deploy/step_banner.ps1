<#
.SYNOPSIS
  Shared banner for step1-4 cmd scripts: one unified layout, per-step accent color.
  Step colors: 1 buy=DarkCyan, 2 deploy=DarkMagenta, 3 test=DarkGreen, 4 release=DarkRed.
.EXAMPLE
  .\step_banner.ps1 -Step 2
#>
param(
    [Parameter(Mandatory = $true)][ValidateRange(1, 4)][int]$Step
)

$defs = @(
    @{ CN = '购买'; Title = 'BUY · 购买计算服'
       Desc = '按启动模板购买阿里云抢占式 ECS'
       Color = 'DarkCyan'
       Hint = '不带 -Yes 为演练(DryRun)不花钱 · -UpdateProfile 自动把新 IP 写回 profile' },
    @{ CN = '部署'; Title = 'DEPLOY · 远程部署'
       Desc = '本地打包上传，部署入口服 + 计算服'
       Color = 'DarkMagenta'
       Hint = '计算服 IP 取自 profiles/aliyun-test.env · 默认重置 DB / Storage / DataRoot' },
    @{ CN = '测试'; Title = 'TEST · 云端测试'
       Desc = '端到端调试脚本，验证整套部署'
       Color = 'DarkGreen'
       Hint = '需先完成 step2 部署 · 脚本从零自建研究项与数据，可重复跑' },
    @{ CN = '释放'; Title = 'RELEASE · 释放计算服'
       Desc = '释放抢占式实例，停止计费'
       Color = 'DarkRed'
       Hint = '-List 查看实例 · 不带 -Yes 为演练 · 包月老实例请走控制台释放' }
)

$cur   = $defs[$Step - 1]
$rule  = ([string][char]0x2500) * 68
$arrow = [string][char]0x2192

Write-Host ''
Write-Host ('  ' + $rule) -ForegroundColor $cur.Color
Write-Host '  ' -NoNewline
Write-Host (" STEP $Step ") -BackgroundColor $cur.Color -ForegroundColor White -NoNewline
Write-Host ('  ' + $cur.Title) -ForegroundColor White -NoNewline
Write-Host ('   ' + $cur.Desc) -ForegroundColor DarkGray
Write-Host ''
Write-Host '    ' -NoNewline
for ($i = 0; $i -lt 4; $i++) {
    $d = $defs[$i]
    if (($i + 1) -eq $Step) {
        Write-Host (" $($i + 1) $($d.CN) ") -BackgroundColor $d.Color -ForegroundColor White -NoNewline
    }
    else {
        Write-Host (" $($i + 1) $($d.CN) ") -ForegroundColor DarkGray -NoNewline
    }
    if ($i -lt 3) { Write-Host (' ' + $arrow + ' ') -ForegroundColor DarkGray -NoNewline }
}
Write-Host ''
Write-Host ('    ' + $cur.Hint) -ForegroundColor DarkGray
Write-Host ('  ' + $rule) -ForegroundColor $cur.Color
Write-Host ''
