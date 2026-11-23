@echo off
REM Arranca todos los stacks reconstruyendo imagenes (docker compose up -d --build).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" rebuild
echo.
pause
