@echo off
REM Arranca todos los stacks (docker compose up -d) y espera a que estén healthy.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" up
echo.
pause
