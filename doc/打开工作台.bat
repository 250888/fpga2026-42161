@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0启动工作台.py"
    goto :done
)
python -c "import sys;sys.exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>nul
if not errorlevel 1 (
    python "%~dp0启动工作台.py"
    goto :done
)
echo Python 3.8+ was not found.
echo For simulation, open the HTML directly in Chrome or Edge.
echo For serial use, install Python 3 and run this launcher again.
pause
exit /b 1
:done
if errorlevel 1 pause
endlocal
