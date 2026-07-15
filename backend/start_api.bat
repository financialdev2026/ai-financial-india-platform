@echo off
title FORESIGHT AI Backend API

cd /d "%~dp0"

set "PYTHONUTF8=1"
set "PYTHON_EXE=%~dp0..\venv\Scripts\python.exe"
set "CODEX_PYTHON=C:\Users\Uday Lowalekar\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

"%PYTHON_EXE%" -c "import sys" >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%CODEX_PYTHON%" (
        set "PYTHON_EXE=%CODEX_PYTHON%"
    )
)

set "PYTHONPATH=%~dp0"

"%PYTHON_EXE%" -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
