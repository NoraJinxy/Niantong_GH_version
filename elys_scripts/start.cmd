@echo off
REM ===========================================================
REM  ELYS Debug Launcher
REM  - First run: creates .venv + installs requirements.txt
REM  - Later runs: activates .venv + opens interactive cmd
REM  - Exit: type  exit  in the shell
REM ===========================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

REM --- 1) Check Python ---
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo.
    echo [X] Python not found.
    echo     Install Python 3.10+ from https://www.python.org/downloads/
    echo     Make sure to check "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
  )
  set "PY_CMD=python"
) else (
  set "PY_CMD=py -3"
)

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

REM --- 4) Run ERP chain: setup (build dataset + upload) then run (pipeline) ---
echo.
echo [1/2] setup: build dataset + upload data
python projects\01_erp_basic\setup.py
if errorlevel 1 (
  echo.
  echo [X] setup failed - skip pipeline. See errors above.
  pause
  exit /b 1
)
echo.
echo [2/2] run: ERP pipeline
python projects\01_erp_basic\run.py
echo.
pause
