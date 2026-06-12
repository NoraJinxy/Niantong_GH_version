@echo off
REM ===========================================================
REM  ELYS Debug Launcher
REM  - First run: creates .venv + installs requirements.txt
REM  - Later runs: activates .venv + opens interactive cmd
REM  - Exit: type  exit  in the shell
REM ===========================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM UTF-8 console + force Python UTF-8 stdout (GBK cannot encode the check/box glyphs)
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

REM --- 1) Find a REAL Python (reject the Microsoft Store stub) ---
set "PY_CMD="

REM 1a) py launcher (only if it actually works)
where py >nul 2>nul && (
  py -3 -c "import sys" >nul 2>nul && set "PY_CMD=py -3"
)

REM 1b) common Anaconda / standard install locations
if not defined PY_CMD (
  for %%P in (
    "C:\ProgramData\anaconda3\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
  ) do (
    if not defined PY_CMD if exist %%P set PY_CMD=%%P
  )
)

REM 1c) python on PATH, but skip the WindowsApps Store stub
if not defined PY_CMD (
  for /f "delims=" %%I in ('where python 2^>nul') do (
    if not defined PY_CMD (
      echo %%I | find /i "WindowsApps" >nul || set PY_CMD="%%I"
    )
  )
)

if not defined PY_CMD (
  echo.
  echo [X] No usable Python found ^(the Microsoft Store stub does not count^).
  echo     Install Python 3.10+ from https://www.python.org/downloads/
  echo     and check "Add python.exe to PATH", or install Anaconda.
  echo.
  pause
  exit /b 1
)
echo [setup] Using Python: %PY_CMD%

REM --- 2) Create venv if not exists ---
if not exist "%VENV_PY%" (
  echo.
  echo [setup] First run - creating venv at %CD%\%VENV_DIR% ...
  %PY_CMD% -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [X] Failed to create venv.
    pause
    exit /b 1
  )
  echo [setup] Installing dependencies ...
  "%VENV_PY%" -m pip install --quiet --upgrade pip
  "%VENV_PY%" -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo [X] pip install failed. See errors above.
    pause
    exit /b 1
  )
  echo [setup] Done.
)

REM --- 3) Activate venv ---
call "%VENV_DIR%\Scripts\activate.bat"

REM --- 3b) Step3 banner: printed AFTER chcp + venv so it is neither cleared by
REM         chcp nor scrolled off by first-run pip logs. Sits right above the test. ---
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\elys_project\deploy\step_banner.ps1" -Step 3

REM --- 4) Run ERP chain: setup (build dataset + upload) then run (pipeline) ---
powershell -NoProfile -Command "Write-Host ''; Write-Host ' 1/2 ' -BackgroundColor DarkGreen -ForegroundColor White -NoNewline; Write-Host '  setup: build dataset + upload data' -ForegroundColor White"
python projects\01_erp_basic\setup.py
if errorlevel 1 (
  powershell -NoProfile -Command "Write-Host ''; Write-Host ' FAIL ' -BackgroundColor DarkRed -ForegroundColor White -NoNewline; Write-Host '  setup failed - skip pipeline. See errors above.' -ForegroundColor Red"
  pause
  exit /b 1
)
powershell -NoProfile -Command "Write-Host ''; Write-Host ' 2/2 ' -BackgroundColor DarkGreen -ForegroundColor White -NoNewline; Write-Host '  run: ERP pipeline' -ForegroundColor White"
python projects\01_erp_basic\run.py
