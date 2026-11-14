@echo off
setlocal
cd /d "%~dp0"

:: 1. If venv exists, launch directly
if exist ".venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
    exit /b 0
)

:: 2. Find system python
set "PY="
where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY=py"
) else (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY=python"
    )
)

if "%PY%"=="" (
    echo ============================================================
    echo [ERROR] Python was not found on this computer.
    echo Please install Python 3.10+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    echo ============================================================
    pause
    exit /b 1
)

echo ============================================================
echo   WPT Coil Designer - First-time Setup
echo ============================================================
echo Creating virtual environment...
%PY% -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create .venv.
    pause
    exit /b 1
)

echo Installing package and dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e .
if %errorlevel% neq 0 (
    echo [WARNING] Some packages could not be installed automatically.
    pause
)

echo Launching application...
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0
