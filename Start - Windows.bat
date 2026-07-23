@echo off
setlocal enabledelayedexpansion
title APK-JTM -- Just tell me if it's dodgy!

cd /d "%~dp0"

echo.
echo   APK-JTM -- Just tell me if it's dodgy!
echo   -----------------------------------------
echo.

:: ── Check for winget (Windows Package Manager) ───────────────────────────────
set WINGET_OK=0
where winget >nul 2>&1 && set WINGET_OK=1

:: ── Python version detection — prefer 3.12 for APKiD ─────────────────────────
:: Check for specific Python versions in preferred order
set PYTHON=
set PY_MINOR=0

for %%v in (3.12 3.13 3.11 3.10) do (
  if "!PYTHON!"=="" (
    where python%%v >nul 2>&1 && (
      set PYTHON=python%%v
      for /f "tokens=2 delims=." %%m in ("%%v") do set PY_MINOR=%%m
    )
  )
)

:: Fall back to default python3 / python
if "!PYTHON!"=="" (
  where python3 >nul 2>&1 && (
    for /f "tokens=2 delims= " %%v in ('python3 --version 2^>^&1') do (
      for /f "tokens=1,2 delims=." %%a in ("%%v") do (
        if %%a geq 3 if %%b geq 10 (
          set PYTHON=python3
          set PY_MINOR=%%b
        )
      )
    )
  )
)
if "!PYTHON!"=="" (
  where python >nul 2>&1 && (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do (
      for /f "tokens=1,2 delims=." %%a in ("%%v") do (
        if %%a geq 3 if %%b geq 10 (
          set PYTHON=python
          set PY_MINOR=%%b
        )
      )
    )
  )
)

:: No compatible Python found — try to install via winget
if "!PYTHON!"=="" (
  echo   [NOTE] No compatible Python found. Python 3.10+ is required.
  echo.
  if "!WINGET_OK!"=="1" (
    set /p INST_PY="  Install Python 3.12 via Windows Package Manager? [y/n] "
    if /i "!INST_PY!"=="y" (
      echo   Installing Python 3.12...
      winget install --id Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements
      echo   Python 3.12 installed. Please close and re-run this launcher.
      echo   (Windows may need a moment to update your PATH.)
      pause
      exit /b 0
    )
  )
  echo.
  echo   Install Python 3.12 from: https://www.python.org/downloads/
  echo   IMPORTANT: Check "Add Python to PATH" during installation.
  echo.
  pause
  exit /b 1
)

for /f "tokens=2 delims= " %%v in ('!PYTHON! --version 2^>^&1') do set PY_FULL=%%v
echo   [OK] Python %PY_FULL% (!PYTHON!)

:: Suggest Python 3.12 for APKiD if on incompatible version
if !PY_MINOR! geq 14 (
  echo   [NOTE] APKiD (packer analysis) is not yet available on Python %PY_FULL%.
  echo          Python 3.12 is needed for full functionality.
  echo.
  if "!WINGET_OK!"=="1" (
    set /p INST_312="  Install Python 3.12 alongside your current version? [y/n] "
    if /i "!INST_312!"=="y" (
      echo   Installing Python 3.12...
      winget install --id Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements
      set PYTHON=python3.12
      set PY_MINOR=12
      echo   [OK] Python 3.12 installed
    )
  ) else (
    echo          Install from: https://www.python.org/downloads/
  )
  echo.
)

:: ── Check internet connectivity ────────────────────────────────────────────────
:: Checked once, up front, so an offline launch skips the dependency step
:: deliberately rather than discovering it five retries at a time.
set ONLINE=1
curl -fsS --max-time 4 -o nul https://pypi.org/simple/ 2>nul
if !errorlevel! neq 0 set ONLINE=0

:: ── Virtual environment ───────────────────────────────────────────────────────
:: Detect venv Python version and rebuild if changed
set VENV_PY=
if exist ".venv\Scripts\python.exe" (
  for /f "tokens=2 delims= " %%v in ('".venv\Scripts\python.exe" --version 2^>^&1') do set VENV_PY=%%v
)
set WANT_PY=
for /f "tokens=2 delims= " %%v in ('!PYTHON! --version 2^>^&1') do set WANT_PY=%%v

if not "!VENV_PY!"=="!WANT_PY!" if exist ".venv\" (
  echo   Updating virtual environment to Python !WANT_PY!...
  rmdir /s /q .venv
)

if not exist ".venv\" (
  echo   Creating virtual environment (first run only)...
  !PYTHON! -m venv .venv
  if !errorlevel! neq 0 (
    echo   [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat

:: ── Core dependencies ─────────────────────────────────────────────────────────
if !ONLINE! equ 0 (
  echo   No internet - skipping dependency updates, using what's already installed.
  python -c "import fastapi, uvicorn" >nul 2>&1
  if !errorlevel! neq 0 (
    echo.
    echo   [ERROR] Dependencies are not installed, and there is no internet to fetch them.
    echo   The first run needs a connection once. After that the app runs offline.
    echo   For a machine that will never have one, use the offline install bundle
    echo   ^(see docs/OFFLINE.md^).
    echo.
    pause
    exit /b 1
  )
  echo   [OK] Dependencies ready ^(offline^)
) else (
  echo   Checking dependencies...
  pip install -r requirements.txt --upgrade --retries 2 --timeout 15 -q >"%TEMP%\apkjtm-pip.log" 2>&1
  if !errorlevel! neq 0 (
    python -c "import fastapi, uvicorn" >nul 2>&1
    if !errorlevel! equ 0 (
      type "%TEMP%\apkjtm-pip.log"
      echo   [NOTE] Could not update dependencies ^(see above^) - continuing with the installed versions.
    ) else (
      echo.
      echo   [ERROR] Failed to install dependencies, and none are installed to fall back on.
      type "%TEMP%\apkjtm-pip.log"
      del "%TEMP%\apkjtm-pip.log" >nul 2>&1
      pause
      exit /b 1
    )
  ) else (
    echo   [OK] Dependencies ready
  )
  del "%TEMP%\apkjtm-pip.log" >nul 2>&1

  :: ── APKiD (optional) ────────────────────────────────────────────────────────
  pip install apkid -q --retries 2 --timeout 15 >nul 2>&1
  if !errorlevel! equ 0 (
    echo   [OK] APKiD ready ^(packer analysis enabled^)
  ) else (
    echo   [NOTE] APKiD unavailable on Python %PY_FULL% -- packer analysis skipped
    if !PY_MINOR! geq 14 (
      echo          To enable: install Python 3.12 and re-run this launcher
    )
  )

  :: ── Quark-Engine (pure Python -- no native build tools needed) ──────────────
  pip install quark-engine -q --retries 2 --timeout 15 >nul 2>&1
  if !errorlevel! equ 0 (
    if not exist "%USERPROFILE%\.quark-engine\quark-rules\rules" (
      echo   Fetching Quark-Engine rule database ^(one-time, needs internet^)...
      freshquark >nul 2>&1
    )
    if exist "%USERPROFILE%\.quark-engine\quark-rules\rules" (
      echo   [OK] Quark-Engine ready ^(behavioural pattern analysis enabled^)
    ) else (
      echo   [NOTE] Quark-Engine rule database unavailable - run 'freshquark' manually later
    )
  ) else (
    echo   [NOTE] Quark-Engine install failed -- behavioural analysis skipped
  )
)

:: Optional tools already installed from an earlier online run still work
:: offline, so report them rather than staying silent about them.
if !ONLINE! equ 0 (
  where apkid >nul 2>&1 && echo   [OK] APKiD ready ^(packer analysis enabled^)
  if exist "%USERPROFILE%\.quark-engine\quark-rules\rules" (
    where quark >nul 2>&1 && echo   [OK] Quark-Engine ready ^(behavioural pattern analysis enabled^)
  )
)
echo.

:: ── Docker ────────────────────────────────────────────────────────────────────
where docker >nul 2>&1
if !errorlevel! neq 0 (
  echo   [NOTE] Docker not found.
  echo   Docker is required to run MobSF for APK scanning.
  echo   You can still load an existing MobSF JSON report without Docker.
  echo.
  echo   Install Docker Desktop: https://www.docker.com/products/docker-desktop
  echo   (Docker Desktop must be installed manually.)
  echo.
) else (
  curl -s --max-time 3 http://localhost:8000 >nul 2>&1
  if !errorlevel! neq 0 (
    :: docker run on a missing image triggers a pull, which offline means a
    :: long wait and a failure. Only reach for it when the image is already
    :: local or there is a connection to fetch it with.
    docker image inspect opensecurity/mobile-security-framework-mobsf >nul 2>&1
    if !errorlevel! equ 0 (
      set IMAGE_LOCAL=1
    ) else (
      set IMAGE_LOCAL=0
    )

    if !IMAGE_LOCAL! equ 1 (
      set TRY_RUN=1
    ) else if !ONLINE! equ 1 (
      set TRY_RUN=1
    ) else (
      set TRY_RUN=0
    )

    if !TRY_RUN! equ 1 (
      echo   Starting MobSF via Docker...
      if not exist "%USERPROFILE%\.mobsf" mkdir "%USERPROFILE%\.mobsf"
      docker run -d --name mobsf -p 8000:8000 -v "%USERPROFILE%\.mobsf:/home/mobsf/.MobSF" opensecurity/mobile-security-framework-mobsf >nul 2>&1
      if !errorlevel! neq 0 docker start mobsf >nul 2>&1
      echo   [OK] MobSF starting at http://localhost:8000
    ) else (
      docker start mobsf >nul 2>&1
      if !errorlevel! equ 0 (
        echo   [OK] MobSF starting at http://localhost:8000
      ) else (
        echo   [NOTE] MobSF isn't running and its image isn't downloaded yet -
        echo          scanning needs a connection once to fetch it. You can still load
        echo          an existing MobSF JSON report offline.
      )
    )
  ) else (
    echo   [OK] MobSF already running
  )
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
pause >nul
