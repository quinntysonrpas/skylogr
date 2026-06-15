@echo off
cd /d "%~dp0"
title Skylogr Setup
color 0B

echo.
echo  =====================================================
echo    Skylogr  ^|  First-Time Setup
echo  =====================================================
echo.
echo  This will install everything you need and put a
echo  shortcut on your desktop. Takes about 3-5 minutes.
echo.
echo  Press any key to begin, or close this window to cancel.
pause >nul
echo.

:: -------------------------------------------------------
:: Step 1 of 3 - Python
:: -------------------------------------------------------
echo  [1 of 3]  Checking for Python...
echo.
set PYTHON_EXE=python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    echo  [OK] %PY_VER% is already installed.
    echo.
    goto :install_packages
)

:: Python missing - try to install it automatically
echo  Python not found. Installing now...
echo.

:: --- Method 1: winget (Windows 10 21H1 and later, no admin needed) ---
winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  Using Windows Package Manager (winget)...
    echo.
    winget install -e --id Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
    if %errorlevel% equ 0 goto :find_python
    echo  winget install failed, trying direct download...
    echo.
)

:: --- Method 2: download installer directly ---
echo  Downloading Python 3.12 installer (~25MB)...
set PY_INSTALLER=%TEMP%\python312_installer.exe

:: Try curl (built into Windows 10 1803+)
curl -L --silent --show-error -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe" 2>nul
if not exist "%PY_INSTALLER%" (
    :: Fall back to PowerShell download
    powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe' -OutFile '%PY_INSTALLER%'"
)

if not exist "%PY_INSTALLER%" (
    echo.
    echo  Could not download Python. Check your internet connection.
    echo.
    echo  To install manually, go to:
    echo    https://www.python.org/downloads/
    echo.
    echo  Tick "Add Python to PATH" on the installer screen,
    echo  then close this window and run SETUP.bat again.
    echo.
    pause
    exit /b 1
)

echo  Download complete. Installing Python...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1
del "%PY_INSTALLER%" >nul 2>&1

:find_python
:: Locate the newly installed Python without needing a PATH refresh
:: Scan common per-user install paths (3.12, 3.13, 3.11, 3.10)
set PYTHON_EXE=
for %%v in (312 313 311 310) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        if "%PYTHON_EXE%"=="" set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe
    )
)
:: Also check the py launcher which can proxy to any installed version
if "%PYTHON_EXE%"=="" (
    py --version >nul 2>&1
    if %errorlevel% equ 0 set PYTHON_EXE=py
)
if "%PYTHON_EXE%"=="" (
    echo.
    echo  Python was installed, but the setup could not locate it.
    echo  Please close this window and run SETUP.bat again.
    echo  (Python should be found automatically on the second run.)
    echo.
    pause
    exit /b 1
)
echo  [OK] Python installed at: %PYTHON_EXE%
echo.

:install_packages
:: -------------------------------------------------------
:: Step 2 of 3 - Install packages
:: -------------------------------------------------------
echo  [2 of 3]  Installing required packages...
echo             (this may take a few minutes on first run)
echo.
%PYTHON_EXE% -m pip install -r requirements_new.txt
if %errorlevel% neq 0 (
    echo.
    echo  Package installation failed. Check your internet connection
    echo  and run SETUP.bat again.
    echo.
    pause
    exit /b 1
)
echo.
echo  [OK] All packages installed.
echo.

:: -------------------------------------------------------
:: Step 3 of 3 - Desktop shortcut
:: -------------------------------------------------------
echo  [3 of 3]  Creating desktop shortcut...
echo.
set VBSCRIPT=%TEMP%\skylogr_setup.vbs
echo Set oWS = WScript.CreateObject("WScript.Shell")           > "%VBSCRIPT%"
echo sLink = oWS.SpecialFolders("Desktop") ^& "\Skylogr.lnk" >> "%VBSCRIPT%"
echo Set oLink = oWS.CreateShortcut(sLink)                    >> "%VBSCRIPT%"
echo oLink.TargetPath     = "%CD%\START.bat"                  >> "%VBSCRIPT%"
echo oLink.WorkingDirectory = "%CD%"                          >> "%VBSCRIPT%"
echo oLink.IconLocation   = "%CD%\skylogr.ico, 0"             >> "%VBSCRIPT%"
echo oLink.Description    = "Skylogr - Drone Flight Logbook"  >> "%VBSCRIPT%"
echo oLink.Save                                               >> "%VBSCRIPT%"
cscript //nologo "%VBSCRIPT%"
del "%VBSCRIPT%" >nul 2>&1
echo  [OK] Skylogr shortcut added to your Desktop.
echo.

:: -------------------------------------------------------
:: Done
:: -------------------------------------------------------
echo  =====================================================
echo    Setup complete. You are ready to fly.
echo  =====================================================
echo.
echo  Launch Skylogr any time from the icon on your desktop.
echo.
set /p LAUNCH="  Start Skylogr now? (Y/N): "
if /i "%LAUNCH%"=="Y" (
    echo.
    start "" "%CD%\START.bat"
)
echo.
pause >nul
