@echo off
setlocal
echo Resetting ai-sim-company data...
echo (stops services, clears SQLite + frontend .next cache)
echo.

REM 1. Stop services first
call "%~dp0stop.bat"
echo.

REM 2. Delete SQLite (persisted state: agents/profiles/tasks/skills/hub_state)
if exist "%~dp0data\aisim.db" (
  del /q "%~dp0data\aisim.db" "%~dp0data\aisim.db-wal" "%~dp0data\aisim.db-shm" 2>nul
  echo SQLite deleted
) else (
  echo No SQLite file found.
)

REM 4. Clear frontend .next cache (forces a clean recompile on next start)
if exist "%~dp0frontend\.next" (
  rmdir /s /q "%~dp0frontend\.next"
  echo .next cache cleared
)

echo.
echo Reset complete. Run start.bat for a fresh start.
endlocal
