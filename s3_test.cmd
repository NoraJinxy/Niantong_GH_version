@echo off
cls
REM Step3 test runner.
REM Usage:
REM   s3_test.cmd        (no arg) 04_group FULL: upload + ERP + PSD Grand Average  <-- default (= -4)
REM   s3_test.cmd -1     01_erp_basic        (ERP, time-domain average; full upload + pipeline)
REM   s3_test.cmd -2     02_erd_ers          (ERD/ERS, TFR motor imagery; full)
REM   s3_test.cmd -3     03_resting_state    (Resting-state PSD, Welch; full)
REM   s3_test.cmd -4     04_group            (Group ERP + rest PSD Grand Average; full upload + pipeline)
REM   s3_test.cmd -4u    04_group UPLOAD only (build dataset + upload, skip pipeline)
REM   s3_test.cmd -all   run cases 1..3 in sequence (full each)

set "ARG=%~1"

REM --- No argument: run the 4th test case in full (upload + ERP + Grand Average) ---
if "%ARG%"=="" (
    call "%~dp0elys_scripts\start.cmd" 04_group
    goto :eof
)

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
if "%ARG%"=="-4" (
    call "%~dp0elys_scripts\start.cmd" 04_group
    goto :eof
)
if /i "%ARG%"=="-4u" (
    call "%~dp0elys_scripts\start.cmd" 04_group setup
    goto :eof
)

if "%ARG%"=="-all" (
    call "%~dp0elys_scripts\start.cmd" 01_erp_basic
    if errorlevel 1 exit /b 1
    call "%~dp0elys_scripts\start.cmd" 02_erd_ers
    if errorlevel 1 exit /b 1
    call "%~dp0elys_scripts\start.cmd" 03_resting_state
    goto :eof
)

echo Unknown argument: %ARG%
echo Usage: s3_test.cmd [-1^|-2^|-3^|-4^|-4u^|-all]   (no arg = 04_group full)
exit /b 1
