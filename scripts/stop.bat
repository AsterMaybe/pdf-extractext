@echo off
REM Baja todos los stacks (docker compose down) en orden inverso.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" down
echo.
pause
