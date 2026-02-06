@echo off
REM OLILab - Setup Script for Windows
REM This script installs all dependencies and configures the application

setlocal EnableDelayedExpansion

echo.
echo ===================================================
echo         OLILab - Setup
echo      Document Analysis ^& AI Assistant
echo ===================================================
echo.

REM Get project root (parent of scripts directory)
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."
set "PROJECT_ROOT=%CD%"

echo Project root: %PROJECT_ROOT%
echo.

REM Check Python version
echo Checking Python installation...
set "PYTHON_CMD="

for %%P in (python py) do (
    %%P --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2 delims= " %%V in ('%%P --version 2^>^&1') do (
            set "VERSION=%%V"
            for /f "tokens=1,2 delims=." %%A in ("!VERSION!") do (
                if %%A geq 3 (
                    if %%B geq 10 (
                        set "PYTHON_CMD=%%P"
                        echo    Found Python !VERSION!
                        goto :found_python
                    )
                )
            )
        )
    )
)

echo.
echo ERROR: Python 3.10 or higher is required
echo.
echo Please install Python from: https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation
echo.
pause
exit /b 1

:found_python
echo.

REM Create backend virtual environment
echo Setting up Python environment...
if not exist "backend\venv" (
    echo    Creating virtual environment...
    %PYTHON_CMD% -m venv backend\venv
    echo    Virtual environment created
) else (
    echo    Virtual environment exists
)

REM Activate and install dependencies
echo.
echo Installing Python dependencies...
call backend\venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install -r backend\requirements.txt -q
echo    Python dependencies installed

REM Check for Node.js (optional)
echo.
echo Checking Node.js installation...
node --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f %%V in ('node --version') do echo    Found Node.js %%V
) else (
    echo    Node.js not found ^(optional, for frontend development^)
    echo    Install from: https://nodejs.org/
)

REM Create .env file if it doesn't exist
if not exist "backend\.env" (
    echo.
    echo Creating configuration file...
    (
        echo # OLILab Configuration
        echo.
        echo # AI Provider: ollama, claude, or gemini
        echo AI_PROVIDER=claude
        echo CLAUDE_API_KEY=your_api_key_here
        echo # GEMINI_API_KEY=your_api_key_here
        echo.
        echo # Shared folder root for project discovery
        echo # SHARED_FOLDERS_ROOT=C:\SharedFolders\Projects
        echo.
        echo # Auto-index on startup ^(set to false for faster startup^)
        echo AUTO_INDEX_ON_STARTUP=false
    ) > backend\.env
    echo    Created backend\.env ^(please edit with your API key^)
)

REM Setup frontend
echo.
echo Setting up frontend...
cd frontend
if not exist "node_modules" (
    where npm >nul 2>&1
    if !errorlevel! equ 0 (
        call npm install -q
        echo    Frontend dependencies installed
    ) else (
        echo    Skipping npm install ^(Node.js not found^)
    )
) else (
    echo    Frontend ready
)
cd ..

REM Create start script
echo.
echo Creating start script...
(
    echo @echo off
    echo REM Start OLILab
    echo.
    echo cd /d "%%~dp0"
    echo.
    echo echo.
    echo echo Starting OLILab...
    echo echo.
    echo.
    echo REM Start backend
    echo echo Starting backend server...
    echo start "OLI Backend" /D backend cmd /c "call venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    echo.
    echo REM Wait for backend
    echo timeout /t 3 /nobreak ^>nul
    echo.
    echo REM Start frontend
    echo echo Starting frontend...
    echo start "OLI Frontend" /D frontend cmd /c "npm run dev"
    echo.
    echo echo.
    echo echo ===================================================
    echo echo           OLILab Running
    echo echo ===================================================
    echo echo.
    echo echo   Frontend: http://localhost:5173
    echo echo   Backend:  http://localhost:8000
    echo echo   API Docs: http://localhost:8000/docs
    echo echo.
    echo echo Close this window to stop the application
    echo echo.
    echo pause
) > start.bat

echo.
echo ===================================================
echo              Setup Complete!
echo ===================================================
echo.
echo Next Steps:
echo.
echo    1. Edit configuration:
echo       Open backend\.env in a text editor
echo       - Add your Claude API key
echo       - Set your shared folders path
echo.
echo    2. Start the application:
echo       Double-click start.bat
echo.
echo    3. Open in browser:
echo       http://localhost:5173
echo.
echo    4. ^(Optional^) Setup Claude Desktop integration:
echo       python scripts\setup_mcp.py
echo.
pause
