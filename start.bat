@echo off
setlocal enabledelayedexpansion
title ai-sim-company launcher

REM ====================================================================
REM  ai-sim-company - one-click local startup (non-containerized)
REM  Starts: Redis + Backend (FastAPI :8000) + Frontend (Next.js :3000)
REM ====================================================================

set ROOT=%~dp0
cd /d %ROOT%

REM --- Local dev environment (simulated agents; Redis config comes from .env) ---
set AGENT_BACKEND=simulated
REM Do NOT set REDIS_HOST/PORT/PASSWORD/DB here: .env is the single source of truth
REM (aisim/__init__.py loads .env with override=False; a shell value would shadow it).

if "!LLM_API_KEY!"=="" (
  echo [WARN] LLM_API_KEY not in env - if not set here, make sure .env has it.
  echo        Without it agent LLM calls will fail.
)

REM --- 1. Redis (reachability check against the host configured in .env) ---
echo [1/3] Redis...
python -c "from dotenv import load_dotenv; import os,redis; load_dotenv('.env'); h=os.environ.get('REDIS_HOST','localhost'); p=int(os.environ.get('REDIS_PORT','6379')); pw=os.environ.get('REDIS_PASSWORD',''); db=int(os.environ.get('REDIS_DB','0')); redis.Redis(host=h,port=p,password=pw,db=db,socket_connect_timeout=3).ping(); print('reachable:',h,p,'db'+str(db))"
if "!errorlevel!"=="0" (
  goto :start_services
)
echo [ERROR] Redis not reachable per .env (REDIS_HOST/PORT/PASSWORD/REDIS_DB).
echo         Verify .env points to a running Redis, then re-run this script.
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
