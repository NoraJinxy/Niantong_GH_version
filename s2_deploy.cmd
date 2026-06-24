@echo off
cls
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\step_banner.ps1" -Step 2
REM [debug] clear OSS test bucket alongside local RESET (best-effort; only when profile RESET_STORAGE=true; skipped if no creds/python; never blocks deploy)
where python >nul 2>nul && python "%~dp0elys_scripts\oss_smoke\clear_oss.py" %*
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\deploy_remote.ps1" %*
