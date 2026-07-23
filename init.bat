@echo off
setlocal enabledelayedexpansion
title ai-sim-company environment init

REM ====================================================================
REM  ai-sim-company - environment init
REM  Checks Python / Node / MCP tools (npx, uvx), installs deps, builds frontend.
REM  Run once on a fresh checkout (or after pulling dependency changes).
REM ====================================================================

set ROOT=%~dp0
cd /d %ROOT%

echo ============================================================
echo  ai-sim-company environment init
echo  Checks Python/Node/MCP tools, installs deps, builds frontend
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

REM --- 3. MCP tools (npx / uvx) - needed by many MCP servers ---
echo [3/6] MCP tools (npx / uvx)...
where npx >nul 2>&1
if !errorlevel! neq 0 (
  echo   [WARN] npx not found - comes with Node.js, needed for npx-based MCP servers.
) else (
  for /f "delims=" %%v in ('npx --version') do echo   npx %%v
)
where uvx >nul 2>&1
if !errorlevel! neq 0 (
  echo   [WARN] uvx not found - install with "pip install uv", needed for uvx-based MCP servers.
) else (
  for /f "delims=" %%v in ('uvx --version') do echo   uvx %%v
)

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
echo    - Python / Node / MCP tools (npx, uvx) checked
echo    - Backend deps installed (pip install -r requirements-dev.txt)
echo    - Backend imports OK
echo    - Frontend deps installed + built (npm run build)
echo  Next: copy .env.example .env, fill LLM_API_KEY, then start.bat
echo ============================================================
endlocal
