@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%elys_project\backend"
set "FRONTEND_DIR=%PROJECT_ROOT%elys_project\frontend\elys-web"
set "LOCAL_DATA=%PROJECT_ROOT%local_data"
set "VENV_DIR=%BACKEND_DIR%\.venv"

echo.
echo ======================================================
echo   ELYS Local Dev Environment
echo ======================================================

REM --- 1. Docker infra ---
echo.
echo [1/4] Starting Docker containers (PostgreSQL + Redis)...
docker compose -f docker-compose.local.yml up -d
if errorlevel 1 (
    echo.
    echo [X] Docker failed. Is Docker Desktop running?
    pause & exit /b 1
)

REM --- 2. Wait for PostgreSQL ---
echo [2/4] Waiting for PostgreSQL to be ready...
:wait_pg
docker compose -f docker-compose.local.yml exec -T postgres pg_isready -U postgres -q >nul 2>nul
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_pg
)
echo       PostgreSQL ready.

REM --- 3. Local data directories ---
if not exist "%LOCAL_DATA%\studies" mkdir "%LOCAL_DATA%\studies"
if not exist "%LOCAL_DATA%\storage\datasets" mkdir "%LOCAL_DATA%\storage\datasets"
if not exist "%LOCAL_DATA%\storage\studies" mkdir "%LOCAL_DATA%\storage\studies"
if not exist "%LOCAL_DATA%\storage\trash" mkdir "%LOCAL_DATA%\storage\trash"

REM --- 4. Python venv ---
echo [3/4] Checking Python backend...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo       First run: creating venv and installing dependencies...
    echo       This may take a few minutes (mne + scipy are large).
    python -m venv "%VENV_DIR%"
    if errorlevel 1 ( echo [X] python -m venv failed. Python 3.11+ required. & pause & exit /b 1 )
    "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip --quiet
    "%VENV_DIR%\Scripts\python.exe" -m pip install -r "%BACKEND_DIR%\requirements.txt"
    if errorlevel 1 ( echo [X] pip install failed. See errors above. & pause & exit /b 1 )
    echo       Dependencies installed.
)

REM --- 5. Node modules ---
if not exist "%FRONTEND_DIR%\node_modules" (
    echo       First run: installing npm packages...
    pushd "%FRONTEND_DIR%"
    npm install
    popd
    if errorlevel 1 ( echo [X] npm install failed. & pause & exit /b 1 )
)

REM --- 6. Launch in new windows ---
echo [4/4] Launching backend and frontend...

start "ELYS Backend (uvicorn :8000)" cmd /k ^
  "cd /d "%BACKEND_DIR%" ^
  && set STUDIES_DIR=%LOCAL_DATA%\studies ^
  && set ELYS_STORAGE_ROOT=%LOCAL_DATA%\storage ^
  && set DATASETS_STORAGE_ROOT=%LOCAL_DATA%\storage\datasets ^
  && set STUDIES_STORAGE_ROOT=%LOCAL_DATA%\storage\studies ^
  && set TRASH_STORAGE_ROOT=%LOCAL_DATA%\storage\trash ^
  && set DEBUG=True ^
  && "%VENV_DIR%\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port 8000 --reload"

start "ELYS Frontend (vite :3000)" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo.
echo ======================================================
echo   ELYS Local Dev Ready!
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000/docs
echo   Health:    http://localhost:8000/api/v1/health
echo ======================================================
echo.
echo   Two terminal windows opened (backend + frontend).
echo   To stop everything: run stop_local.cmd
echo.
pause
