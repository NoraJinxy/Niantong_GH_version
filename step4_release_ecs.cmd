@echo off
cls
setlocal
cd /d "%~dp0"
powershell -NoProfile -Command "Write-Host ''; Write-Host ' STEP 4 ' -BackgroundColor DarkMagenta -ForegroundColor White -NoNewline; Write-Host '  RELEASE ECS' -ForegroundColor White -NoNewline; Write-Host '  Terminate compute instance' -ForegroundColor DarkGray; Write-Host ''"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0elys_project\deploy\release_ecs.ps1" %*
