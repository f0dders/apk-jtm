@echo off
setlocal enabledelayedexpansion
title APK-JTM -- Just tell me if it's dodgy!

cd /d "%~dp0"

echo.
echo   APK-JTM -- Just tell me if it's dodgy!
echo   -------------------------------------
echo.

:: ── Check Python ─────────────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Python is not installed or not in PATH.
    echo.
    echo   Please install Python 3.10 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_FULL=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_FULL%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if %PY_MAJOR% lss 3 (
    echo   [ERROR] Python 3.10 or newer is required.
    echo   Your version: %PY_FULL%
    echo   Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
if %PY_MAJOR% equ 3 if %PY_MINOR% lss 10 (
    echo   [ERROR] Python 3.10 or newer is required.
    echo   Your version: %PY_FULL%
    echo   Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo   [OK] Python %PY_FULL%

:: ── Virtual environment ───────────────────────────────────────────────────────
if not exist ".venv\" (
    echo   Creating virtual environment (first run only)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo   [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

:: ── Install / update dependencies ────────────────────────────────────────────
echo   Checking dependencies...
pip install -r requirements.txt --upgrade -q
if %errorlevel% neq 0 (
    echo.
    echo   [ERROR] Failed to install dependencies.
    echo   Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)

echo   [OK] Dependencies ready
echo.

:: ── Check Docker / MobSF hint ────────────────────────────────────────────────
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   [NOTE] Docker is not installed.
    echo   MobSF requires Docker Desktop: https://www.docker.com/products/docker-desktop
    echo   You can still use the app with an existing MobSF JSON report.
    echo.
) else (
    echo   Starting MobSF via Docker...
    if not exist "%USERPROFILE%\.mobsf" mkdir "%USERPROFILE%\.mobsf"
    docker start mobsf >nul 2>&1 || docker run -d --name mobsf -p 8000:8000 -v "%USERPROFILE%\.mobsf:/home/mobsf/.MobSF" opensecurity/mobile-security-framework-mobsf >nul 2>&1
    echo   [OK] MobSF available at http://localhost:8000
    echo.
)

:: ── Launch ────────────────────────────────────────────────────────────────────
echo   Starting APK Analyser...
echo   Your browser will open automatically.
echo.
echo   -- Server output --------------------------
echo.

python launch.py

echo.
echo   Server stopped. Press any key to close.
pause &gt;nul
