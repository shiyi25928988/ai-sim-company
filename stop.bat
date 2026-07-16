@echo off
setlocal
echo Stopping ai-sim-company services...

REM Kill processes listening on service ports (backend 8000, frontend 3000-3002)
for %%P in (8000 3000 3001 3002) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr "LISTENING"') do (
    echo   killing PID %%A ^(port %%P^)
    taskkill /F /PID %%A >nul 2>&1
  )
)

REM Close the launcher cmd windows (Redis is left alone - it may be a shared service)
taskkill /F /FI "WINDOWTITLE eq ai-sim-backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq ai-sim-frontend*" >nul 2>&1

echo Done.
endlocal
