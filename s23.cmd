@echo off
REM ============================================================
REM  s23 = s2 (deploy) + s3 (test), chained.
REM  The everyday "redeploy + retest" combo.
REM
REM  Usage (any argument is forwarded to the test step s3_test):
REM    s23          deploy, then UPLOAD ONLY the 04_group dataset (s3_test default)
REM    s23 -1       deploy, then run 01_erp_basic (full upload + pipeline)
REM    s23 -2       deploy, then run 02_erd_ers (full)
REM    s23 -3       deploy, then run 03_resting_state (full)
REM    s23 -4       deploy, then upload 04_group (same as no arg)
REM    s23 -all     deploy, then run cases 1..3 in sequence (full each)
REM
REM  Notes: deploy uses the default profile (aliyun-test).
REM         Stops immediately if deploy fails (tests are not run).
REM ============================================================
setlocal
cd /d "%~dp0"

call "%~dp0s2_deploy.cmd"
if errorlevel 1 (
    echo.
    echo [s23] Deploy FAILED - stopped, tests not run.
    exit /b 1
)

call "%~dp0s3_test.cmd" %*
if errorlevel 1 (
    echo.
    echo [s23] Tests FAILED.
    exit /b 1
)

echo.
echo [s23] DONE: deploy + tests all passed.
