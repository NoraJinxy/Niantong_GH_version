@echo off
cls
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\step_banner.ps1" -Step 3
REM Thin shim -- real launcher is in elys_scripts\start.cmd
call "%~dp0elys_scripts\start.cmd" %*
