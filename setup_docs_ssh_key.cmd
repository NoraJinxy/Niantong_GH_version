@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0wiki\setup_docs_ssh_key.ps1" %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
    echo.
    echo setup_docs_ssh_key failed with exit code %EXITCODE%.
)
exit /b %EXITCODE%
