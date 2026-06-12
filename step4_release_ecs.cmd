@echo off
cls
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\step_banner.ps1" -Step 4
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\release_ecs.ps1" %*
