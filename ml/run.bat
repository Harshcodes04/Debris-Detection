@echo off
REM SIH PS57 - detection demo. Double-click this.
REM
REM Finds a usable Python rather than hardcoding one path, so it works on a
REM teammate's machine as well as the one it was written on. Preference order:
REM a .venv beside this file, then the author's environment, then the py
REM launcher's 3.11.
setlocal
cd /d "%~dp0"

set "PY="

REM 1. a virtual environment sitting next to this script
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

REM 2. the environment this was developed in
if not defined PY if exist "C:\Users\aksha\sih-venv\Scripts\python.exe" set "PY=C:\Users\aksha\sih-venv\Scripts\python.exe"

REM 3. the py launcher, pinned to 3.11 - PyTorch has no wheels for 3.14, so a
REM    bare `python` on a current install fails on `import torch`
if not defined PY (
    py -3.11 -c "import ultralytics" >nul 2>&1
    if not errorlevel 1 set "PY=py -3.11"
)

if not defined PY (
    echo.
    echo   No Python 3.11 with ultralytics was found.
    echo.
    echo   Set one up from this folder:
    echo.
    echo       py -3.11 -m venv .venv
    echo       .venv\Scripts\activate
    echo       pip install -r requirements.txt
    echo.
    echo   Python 3.11 specifically - PyTorch has no wheels for 3.14.
    echo.
    pause
    exit /b 1
)

%PY% pipeline.py --live %*
pause
