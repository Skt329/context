@echo off
title ContextAI
color 0A

echo.
echo  ╔══════════════════════════════════════╗
echo  ║         ContextAI Launcher           ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ─── 1. Start Python Backend ────────────────────────────────
echo [1/2] Starting backend (port 8742)...

if not exist "backend\.venv\Scripts\python.exe" (
    echo ERROR: Python venv not found at backend\.venv
    echo Run:  cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

start "ContextAI-Backend" /min cmd /c "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8742 --reload"

:: Wait for backend to be ready
echo     Waiting for backend...
set /a attempts=0
:wait_backend
set /a attempts+=1
if %attempts% gtr 30 (
    echo     WARNING: Backend did not respond in 15s — continuing anyway.
    goto start_tauri
)
timeout /t 1 /nobreak >nul 2>&1
curl -s -o nul -w "" http://localhost:8742/api/health >nul 2>&1
if errorlevel 1 goto wait_backend
echo     Backend ready.

:: ─── 2. Launch Tauri Native App ─────────────────────────────
:start_tauri
echo [2/2] Launching ContextAI native window...
echo.
echo  ══════════════════════════════════════
echo   ContextAI is starting as a native
echo   desktop application via Tauri.
echo  ══════════════════════════════════════
echo.

:: npm run tauri dev starts Vite + Tauri native window together
call npm run tauri dev

:: When Tauri window is closed, kill the backend
echo.
echo  Shutting down backend...
taskkill /FI "WINDOWTITLE eq ContextAI-Backend" >nul 2>&1
echo  Done.
