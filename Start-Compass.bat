@echo off
title Compass Launcher
setlocal

REM ============================================================
REM  Market Risk Scenario Simulation - one-click launcher
REM  Double-click this file to start the backend + frontend,
REM  then open the app in your browser.
REM ============================================================

set "ROOT=%~dp0"
set "NODEDIR=C:\Users\703313047\node"

echo.
echo   Starting Market Risk Scenario Simulation...
echo   Project: %ROOT%
echo.

REM --- Free ports 8000 (backend) and 3000 (frontend) if already in use ---
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

REM --- Terminal 1: Backend (FastAPI on http://localhost:8000) ---
start "Compass Backend" cmd /k "cd /d "%ROOT%" && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

REM --- Terminal 2: Frontend (Next.js on http://localhost:3000) ---
start "Compass Frontend" cmd /k "set "PATH=%NODEDIR%;%PATH%" && cd /d "%ROOT%frontend" && "%NODEDIR%\npm.cmd" run dev"

REM --- Wait for the servers to come up, then open the browser ---
echo   Waiting for the servers to start...
timeout /t 10 /nobreak >nul
start "" http://localhost:3000

echo.
echo   Opened http://localhost:3000
echo   Two windows are running the backend and frontend.
echo   Close those windows (or press Ctrl+C in each) to stop the app.
echo.
timeout /t 4 /nobreak >nul
endlocal
