@echo off
cls
setlocal
cd /d "%~dp0"
powershell -NoProfile -Command "Write-Host ''; Write-Host ' STEP 2 ' -BackgroundColor DarkMagenta -ForegroundColor White -NoNewline; Write-Host '  DEPLOY' -ForegroundColor White -NoNewline; Write-Host '  Push & deploy to Aliyun servers' -ForegroundColor DarkGray; Write-Host ''"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\deploy_remote.ps1" %*
