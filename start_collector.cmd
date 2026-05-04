@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON_EXE=%ROOT%venv\Scripts\python.exe"

if exist "%PYTHON_EXE%" goto run

for /f "usebackq delims=" %%I in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do set "PYTHON_EXE=%%I"
if exist "%PYTHON_EXE%" goto run

set "PYTHON_EXE=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if exist "%PYTHON_EXE%" goto run

echo Python bulunamadi.
echo Bu proje klasorunden calistirmak icin once yeni bir PowerShell penceresi acin
echo veya `py -3 collector.py` komutunu kullanin.
exit /b 1

:run
echo Kullanilan Python: %PYTHON_EXE%
set "PYTHONUNBUFFERED=1"
if /I "%~1"=="--check" (
    "%PYTHON_EXE%" -c "import collector; print('collector-import:ok')"
    exit /b %ERRORLEVEL%
)
"%PYTHON_EXE%" "%ROOT%collector.py" %*
exit /b %ERRORLEVEL%
