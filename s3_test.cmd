@echo off
cls
REM Step3 test runner.
REM Usage:
REM   s3_test.cmd        run all 3 test cases sequentially
REM   s3_test.cmd -1     01_erp_basic        (ERP, time-domain average)
REM   s3_test.cmd -2     02_erd_ers          (ERD/ERS, TFR motor imagery)
REM   s3_test.cmd -3     03_resting_state    (Resting-state PSD, Welch)

set "ARG=%~1"

if "%ARG%"=="-1" (
    call "%~dp0elys_scripts\start.cmd" 01_erp_basic
    goto :eof
)
if "%ARG%"=="-2" (
    call "%~dp0elys_scripts\start.cmd" 02_erd_ers
    goto :eof
)
if "%ARG%"=="-3" (
    call "%~dp0elys_scripts\start.cmd" 03_resting_state
    goto :eof
)
if not "%ARG%"=="" (
    echo Unknown argument: %ARG%
    echo Usage: s3_test.cmd [-1^|-2^|-3]
    exit /b 1
)

REM --- No argument: run all three in sequence ---
call "%~dp0elys_scripts\start.cmd" 01_erp_basic
if errorlevel 1 exit /b 1

call "%~dp0elys_scripts\start.cmd" 02_erd_ers
if errorlevel 1 exit /b 1

call "%~dp0elys_scripts\start.cmd" 03_resting_state
