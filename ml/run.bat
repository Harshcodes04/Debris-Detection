@echo off
REM SIH PS57 demo. Double-click this.
cd /d "%~dp0"
"C:\Users\aksha\sih-venv\Scripts\python.exe" pipeline.py --live %*
pause
