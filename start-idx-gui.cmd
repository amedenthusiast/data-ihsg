@echo off
where pyw.exe >nul 2>nul
if not errorlevel 1 (
  start "" pyw.exe "%~dp0idx_gui.py"
  exit /b 0
)
where pythonw.exe >nul 2>nul
if not errorlevel 1 (
  start "" pythonw.exe "%~dp0idx_gui.py"
  exit /b 0
)
echo Python 3 for Windows is required. Install Python with Tkinter from python.org first.
pause
exit /b 1
