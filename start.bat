@echo off
setlocal enabledelayedexpansion
title ai-sim-company launcher

REM ====================================================================
REM  ai-sim-company - one-click local startup (non-containerized)
REM  Starts: Redis + Backend (FastAPI :8000) + Frontend (Next.js :3000)
REM ====================================================================

set ROOT=%~dp0
cd /d %ROOT%

REM --- Local dev environment (simulated agents, local Redis) ---
set AGENT_BACKEND=simulated
set REDIS_HOST=localhost
set REDIS_PORT=6379
set REDIS_PASSWORD=123456

if "!LLM_API_KEY!"=="" (
  echo [WARN] LLM_API_KEY not in env - if not set here, make sure .env has it.
  echo        Without it agent LLM calls will fail.
)

REM --- 1. Redis (checked via python redis client; redis-cli may not be on PATH) ---
echo [1/3] Redis...
python -c "import redis; redis.Redis(host='localhost',port=6379,password='123456').ping()" >nul 2>&1
if "!errorlevel!"=="0" (
  echo       already running.
  goto :start_services
)
where redis-server >nul 2>&1
if "!errorlevel!"=="0" (
  echo       starting redis-server...
  start "Redis" redis-server --port 6379 --requirepass 123456
  timeout /t 2 >nul
  goto :start_services
)
echo [ERROR] Redis not reachable on localhost:6379 and redis-server not in PATH.
echo         Start Redis with password 123456 first, then re-run this script.
exit /b 1

:start_services
REM --- 2. Backend (FastAPI :8000) ---
echo [2/3] Backend (FastAPI on :8000)...
start "ai-sim-backend" cmd /k "cd /d %ROOT% && python -m uvicorn aisim.api.server:app --host 0.0.0.0 --port 8000"

REM --- 3. Frontend (Next.js :3000) ---
echo [3/3] Frontend (Next.js on :3000)...
start "ai-sim-frontend" cmd /k "cd /d %ROOT%frontend && npm run dev"

echo.
echo ============================================================
echo  Services starting in separate windows:
echo    Backend  : http://localhost:8000
echo    Frontend : http://localhost:3000
echo    Redis    : localhost:6379, password 123456
echo  Close those windows to stop.
echo ============================================================
echo  Open http://localhost:3000 once the frontend window shows Ready.
echo  If port 3000 is taken, Next.js picks another - check the frontend window.
echo.
endlocal
