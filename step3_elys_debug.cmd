@echo off
cls
REM Thin shim -- start.cmd prints the step3 banner after its chcp/venv setup
call "%~dp0elys_scripts\start.cmd" %*
