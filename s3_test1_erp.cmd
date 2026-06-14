@echo off
cls
REM Step3 test case 1: ERP basic (oddball, time-domain average).
REM start.cmd prints the step3 banner after its chcp/venv setup, then runs setup+run.
call "%~dp0elys_scripts\start.cmd" 01_erp_basic
