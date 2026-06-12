@echo off
cls
setlocal
cd /d "%~dp0"
powershell -NoProfile -Command "Write-Host ''; Write-Host ' STEP 1 ' -BackgroundColor DarkMagenta -ForegroundColor White -NoNewline; Write-Host '  BUY ECS' -ForegroundColor White -NoNewline; Write-Host '  Buy Aliyun spot ECS instance' -ForegroundColor DarkGray; Write-Host ''"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\buy_ecs.ps1" %*
