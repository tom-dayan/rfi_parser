@echo off
REM Windows setup script for RFI Parser MCP Server

echo.
echo ==============================================
echo RFI Parser - MCP Server Setup
echo ==============================================
echo.

REM Get the script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

cd /d "%PROJECT_ROOT%"

echo Project root: %PROJECT_ROOT%
echo.

REM Check for Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://python.org
    pause
    exit /b 1
)

REM Check Python version
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python 3.10 or higher is required
    python --version
    pause
    exit /b 1
)

python --version

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo.
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created at: %PROJECT_ROOT%\venv
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo.
echo Installing dependencies...
pip install -r backend\requirements.txt

echo.
echo ==============================================
echo Setup complete!
echo ==============================================
echo.
echo Next steps:
echo   1. Run the MCP setup: python scripts\setup_mcp.py
echo   2. Or manually configure Claude Desktop
echo.
echo To activate the virtual environment later:
echo   venv\Scripts\activate.bat
echo.

pause
