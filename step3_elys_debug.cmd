@echo off
cls
powershell -NoProfile -Command "Write-Host ''; Write-Host ' STEP 3 ' -BackgroundColor DarkMagenta -ForegroundColor White -NoNewline; Write-Host '  DEBUG' -ForegroundColor White -NoNewline; Write-Host '  Run cloud debug test suite' -ForegroundColor DarkGray; Write-Host ''"
REM Thin shim -- real launcher is in elys_scripts\start.cmd
call "%~dp0elys_scripts\start.cmd" %*
