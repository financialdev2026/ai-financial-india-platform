@echo off
title FORESIGHT AI Financial Platform

echo ==========================================
echo      FORESIGHT AI Starting...
echo ==========================================

echo.
echo [1/2] Running Backend Pipeline...
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
set "CODEX_PYTHON=C:\Users\Uday Lowalekar\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

"%PYTHON_EXE%" -c "import sys" >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%CODEX_PYTHON%" (
        set "PYTHON_EXE=%CODEX_PYTHON%"
    )
)

set "PYTHONPATH=%~dp0backend"

cd /d "%~dp0backend"

"%PYTHON_EXE%" src\run_pipeline.py

if %errorlevel% neq 0 (
    echo.
    echo Backend pipeline failed. The frontend can still run from the latest generated data bundle.
)

cd /d "%~dp0"

echo.
echo [2/2] Starting Frontend...

cd frontend

start cmd /k "npm run dev"

timeout /t 3 >nul

start http://localhost:5173

echo.
echo ==========================================
echo      Project Started Successfully
echo ==========================================

pause
