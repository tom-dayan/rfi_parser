@echo off
title OLI Knowledge Base - Updating...

echo ============================================
echo    OLI Knowledge Base - Update
echo ============================================
echo.

:: Navigate to the project root
cd /d %~dp0

echo [1/4] Pulling latest changes from git...
git pull origin main
if errorlevel 1 (
    echo [ERROR] Git pull failed. Please check your connection or resolve conflicts.
    pause
    exit /b 1
)
echo.

echo [2/4] Updating backend dependencies...
cd backend
call venv\Scripts\activate
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Some backend packages may have failed to install.
)
cd ..
echo.

echo [3/4] Updating frontend dependencies...
cd frontend
call npm install --silent
if errorlevel 1 (
    echo [WARNING] Some frontend packages may have failed to install.
)
cd ..
echo.

echo [4/4] Update complete!
echo.
echo ============================================
echo    Update finished successfully!
echo    You can now run start.bat
echo ============================================
echo.

pause
