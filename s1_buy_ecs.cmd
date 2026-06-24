@echo off
cls
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\step_banner.ps1" -Step 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\buy_ecs.ps1" %*
