@echo off
REM Sigue los logs de los cuatro stacks. Ctrl+C para salir.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" logs
