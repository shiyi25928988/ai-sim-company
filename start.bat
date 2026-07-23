@echo off
setlocal enabledelayedexpansion
title ai-sim-company launcher

REM ====================================================================
REM  ai-sim-company - one-click local startup (no Redis needed)
REM  Starts: Backend (FastAPI :8000) + Frontend (Next.js :3000)
REM ====================================================================

set ROOT=%~dp0
cd /d %ROOT%

set AGENT_BACKEND=simulated

if "!LLM_API_KEY!"=="" (
  echo [WARN] LLM_API_KEY not in env - if not set here, make sure .env has it.
  echo        Without it agent LLM calls will fail.
)

echo [1/2] Backend (FastAPI on :8000)...
start "ai-sim-backend" cmd /k "cd /d %ROOT% && python -m uvicorn aisim.api.server:app --host 0.0.0.0 --port 8000"

echo [2/2] Frontend (Next.js on :3000)...
start "ai-sim-frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo.
echo ============================================================
echo  Services starting in separate windows:
echo    Backend  : http://localhost:8000
echo    Frontend : http://localhost:3000
echo  Close those windows to stop.
echo ============================================================
echo  Open http://localhost:3000 once the frontend window shows Ready.
echo  If port 3000 is taken, Next.js picks another - check the frontend window.
echo.
endlocal
