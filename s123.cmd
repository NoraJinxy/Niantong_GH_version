@echo off
REM ============================================================
REM  s123 = s1 (buy ECS) + s2 (deploy) + s3 (test), full chain from scratch.
REM  Arguments are forwarded to the buy step (s1_buy_ecs).
REM
REM  Usage:
REM    s123 -LaunchTemplateName elys-compute
REM         DRY RUN (no charge): only validates the buy args, then STOPS.
REM         Does NOT deploy or test.
REM    s123 -LaunchTemplateName elys-compute -Yes
REM         REAL BUY (costs money) -^> auto-writes the new public IP back to
REM         the profile -^> deploy -^> UPLOAD the 04_group dataset (s3_test default).
REM
REM  Notes: the compute server public IP is written by s1 into
REM         deploy/profiles/aliyun-test.env (COMPUTE_SERVER_IP) and read by s2,
REM         so the IP handoff is automatic - no manual editing needed.
REM         Without -Yes it is a dry run: never charges, never proceeds.
REM         Stops immediately if any step fails.
REM         Release the bought instance later with s4_release_ecs.
REM ============================================================
setlocal
cd /d "%~dp0"

REM Detect -Yes (real buy). Without it, treat as dry run and stop after buy.
set "HASYES="
for %%A in (%*) do (
    if /I "%%~A"=="-Yes" set "HASYES=1"
)

call "%~dp0s1_buy_ecs.cmd" %*
if errorlevel 1 (
    echo.
    echo [s123] Buy ECS FAILED - stopped.
    exit /b 1
)

if not defined HASYES (
    echo.
    echo [s123] Buy ECS was a DRY RUN ^(no -Yes^): nothing bought, profile IP unchanged.
    echo        Stopped - did NOT deploy or test.
    echo        To really buy and continue: s123 -LaunchTemplateName elys-compute -Yes
    exit /b 0
)

call "%~dp0s2_deploy.cmd"
if errorlevel 1 (
    echo.
    echo [s123] Deploy FAILED - stopped, tests not run.
    exit /b 1
)

call "%~dp0s3_test.cmd"
if errorlevel 1 (
    echo.
    echo [s123] Tests FAILED.
    exit /b 1
)

echo.
echo [s123] DONE: buy ECS + deploy + tests all passed.
