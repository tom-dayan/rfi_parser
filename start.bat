@echo off
title OLI Knowledge Base - Starting...

echo ============================================
echo    OLI Knowledge Base
echo    Starting application...
echo ============================================
echo.

:: Check if Python virtual environment exists
if not exist "backend\venv\Scripts\activate.bat" (
    echo [ERROR] Python virtual environment not found.
    echo Please run the setup first:
    echo   cd backend
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

:: Check if node_modules exists
if not exist "frontend\node_modules" (
    echo [ERROR] Frontend dependencies not installed.
    echo Please run: cd frontend ^&^& npm install
    pause
    exit /b 1
)

echo [1/2] Starting Backend Server...
start "OLI Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\activate && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: Wait a moment for backend to start
timeout /t 3 /nobreak > nul

echo [2/2] Starting Frontend Server...
start "OLI Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: Wait for frontend to start
timeout /t 5 /nobreak > nul

echo.
echo ============================================
echo    Application Started!
echo ============================================
echo.
echo    Open your browser to: http://localhost:5173
echo.
echo    To stop the application, close the two
echo    command prompt windows that opened.
echo.
echo ============================================

:: Open browser automatically
start http://localhost:5173

echo.
echo Press any key to close this window...
pause > nul
