@echo off
REM Electron Build Script for EEG Application (Windows)
REM Builds both frontend and backend into desktop apps

echo =========================================
echo EEG Electron Build Script (Windows)
echo =========================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"
set "BACKEND_DIR=%PROJECT_ROOT%backend"

echo Project root: %PROJECT_ROOT%
echo Frontend: %FRONTEND_DIR%
echo Backend: %BACKEND_DIR%
echo.

REM Default target
set "TARGET=%~1"
if "%~1"=="" set "TARGET=win"

REM Check dependencies
echo [INFO] Checking dependencies...

node --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed
    exit /b 1
)

npm --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm is not installed
    exit /b 1
)

python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed
    exit /b 1
)

echo [INFO] All dependencies found
echo.

REM Setup backend
echo [INFO] Setting up backend...
cd /d "%BACKEND_DIR%"

if not exist "venv" (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
python manage.py migrate --quiet

echo [INFO] Backend setup complete
echo.

REM Build frontend
echo [INFO] Building frontend...
cd /d "%FRONTEND_DIR%"

if not exist "node_modules" (
    echo [INFO] Installing npm dependencies...
    call npm install
)

call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed
    exit /b 1
)

echo [INFO] Frontend build complete
echo.

REM Build Electron app
echo [INFO] Building Electron app for Windows...

npm list electron > nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing Electron dependencies...
    call npm install --save-dev electron electron-builder
)

call npm run electron:build:win
if errorlevel 1 (
    echo [ERROR] Electron build failed
    exit /b 1
)

echo.
echo =========================================
echo Build completed successfully!
echo =========================================
echo.
echo Output location:
echo   %FRONTEND_DIR%\release\
echo.

if exist "%FRONTEND_DIR%\release" (
    echo Built files:
    dir /b "%FRONTEND_DIR%\release"
)

echo.
pause
