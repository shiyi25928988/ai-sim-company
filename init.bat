@echo off
setlocal enabledelayedexpansion
title ai-sim-company environment init

REM ====================================================================
REM  ai-sim-company - environment init
REM  Checks Python / Node / Redis, installs deps, builds the frontend.
REM  Run once on a fresh checkout (or after pulling dependency changes).
REM ====================================================================

set ROOT=%~dp0
cd /d %ROOT%

echo ============================================================
echo  ai-sim-company environment init
echo ============================================================

REM --- 1. Python ---
echo [1/6] Python...
where python >nul 2>&1
if !errorlevel! neq 0 (
  echo   [ERROR] python not found in PATH. Install Python 3.12+.
  pause & exit /b 1
)
for /f "delims=" %%v in ('python --version') do echo   %%v

REM --- 2. Node.js ---
echo [2/6] Node.js...
where node >nul 2>&1
if !errorlevel! neq 0 (
  echo   [ERROR] node not found in PATH. Install Node.js 18+.
  pause & exit /b 1
)
for /f "delims=" %%v in ('node --version') do echo   node %%v
for /f "delims=" %%v in ('npm --version') do echo   npm %%v

REM --- 3. Redis (optional, only needed to run) ---
echo [3/6] Redis (optional)...
REM Read REDIS_* from .env (manual parse - python-dotenv isn't installed until step 4).
REM If .env can't be read or redis isn't installed yet, skip the check instead of
REM reporting a misleading "not reachable on localhost".
python -c "import importlib.util,os,sys; (print('  Redis check skipped: redis module not installed yet (installed in step 4)') or sys.exit(0)) if importlib.util.find_spec('redis') is None else None; (print('  Redis check skipped: .env not created yet (copy .env.example .env)') or sys.exit(0)) if not os.path.exists('.env') else None; import redis; cfg=dict((k.strip(),v.strip()) for k,v in (line.split('=',1) for line in open('.env',encoding='utf-8') if '=' in line and not line.lstrip().startswith('#'))); h=cfg.get('REDIS_HOST','localhost'); p=int(cfg.get('REDIS_PORT','6379')); pw=cfg.get('REDIS_PASSWORD',''); db=int(cfg.get('REDIS_DB','0')); redis.Redis(host=h,port=p,password=pw,db=db,socket_connect_timeout=3).ping(); print('  Redis OK:',h,p,'db'+str(db))" 2>nul
if !errorlevel! neq 0 echo   Redis not reachable per .env (REDIS_HOST/PORT/PASSWORD) - start it before start.bat.

REM --- 4. Backend deps ---
echo [4/6] Installing backend deps (requirements-dev.txt)...
python -m pip install -r requirements-dev.txt
if !errorlevel! neq 0 (
  echo   [ERROR] pip install failed.
  pause & exit /b 1
)

REM --- 5. Backend import check ---
echo [5/6] Backend import check...
python -c "from aisim.api.server import app; print('  backend imports OK')"
if !errorlevel! neq 0 (
  echo   [ERROR] backend import failed.
  pause & exit /b 1
)

REM --- 6. Frontend install + build ---
echo [6/6] Frontend: npm install + build...
cd /d %ROOT%frontend
call npm install
if !errorlevel! neq 0 (
  echo   [ERROR] npm install failed.
  cd /d %ROOT% & pause & exit /b 1
)
call npm run build
if !errorlevel! neq 0 (
  echo   [ERROR] npm run build failed.
  cd /d %ROOT% & pause & exit /b 1
)
cd /d %ROOT%

echo.
echo ============================================================
echo  Init complete:
echo    - Python / Node checked
echo    - Backend deps installed (pip install -r requirements-dev.txt)
echo    - Backend imports OK
echo    - Frontend deps installed + built (npm run build)
echo  Next: copy .env.example .env, fill LLM_API_KEY, then start.bat
echo ============================================================
endlocal
