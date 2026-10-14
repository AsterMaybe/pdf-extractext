@echo off
setlocal
cd /d "%~dp0"

REM ==========================================================================
REM  Vegeta - prueba de carga fija (throughput constante, modelo abierto)
REM    - 50 req/s durante 30 s  =  1500 solicitudes
REM    - timeout del cliente: 30 s
REM    - rota los 4 PDFs de prueba; cada solicitud es un documento distinto
REM      (SHA-256 propio) para que Redis nunca sirva una cache hit.
REM
REM  Uso:
REM      run-test.bat              ejecuta la prueba
REM      run-test.bat -start       arranca los servicios y luego prueba
REM      run-test.bat -regen       regenera los PDFs de prueba antes
REM ==========================================================================

REM ---- Parametros ----
set RATE=50
set DURATION=30s
set TIMEOUT=30s
set GENN=1600
set REQS=1500
set BASE=http://127.0.0.1
set URL=%BASE%/extract
set XHOST=extract.localhost
set TOOLS=%~dp0..\loadtest-tools
set GEN=%TOOLS%\gen-variants.exe
set GENINFO=%TOOLS%\bodies\gen-info.txt
set SRC=%~dp02020-Scrum-Guide-Spanish-Latin-South-American.pdf,%~dp0Filosofia Lean.pdf,%~dp0Essential-Kanban-Condensed-Spanish.pdf,%~dp0scrum_manager_historias_usuario.pdf

echo ============================================================
echo  Vegeta - carga fija (modelo abierto)
echo  %RATE% req/s x %DURATION% = %REQS% solicitudes
echo  Rotando 4 PDFs de prueba / %GENN% documentos distintos
echo ============================================================
echo.

if not exist "%~dp0vegeta.exe" (
    echo [ERROR] no se encuentra vegeta.exe junto a este .bat
    exit /b 1
)

if /i "%~1"=="-start" (
    echo [0/3] Arrancando servicios...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\dev.ps1" up
    if errorlevel 1 ( echo [ERROR] no se pudieron arrancar los servicios & exit /b 1 )
)

REM ---- Comprobar que el extractor responde ----
curl.exe -fsS -m 5 -H "Host: %XHOST%" %BASE%/api/v1/health >nul 2>&1
if errorlevel 1 (
    echo [ERROR] el extractor no responde en %XHOST% ^(%URL%^)
    echo         Arranca los servicios con:  scripts\start.bat
    echo         o ejecuta este script asi:   run-test.bat -start
    exit /b 1
)
echo [OK] extractor accesible en %XHOST%.
echo.

REM ---- Fixtures: reutiliza si siguen siendo los correctos ----
set NEEDGEN=
if /i "%~1"=="-regen" set NEEDGEN=1
if /i "%~2"=="-regen" set NEEDGEN=1
if not exist "%GENINFO%" set NEEDGEN=1
if defined NEEDGEN goto :generate
powershell -NoProfile -Command "$l=Get-Content -LiteralPath '%GENINFO%' -ErrorAction SilentlyContinue; if (($l -contains 'n=%GENN%') -and ($l -contains 'sources=%SRC%')) { exit 0 } else { exit 1 }"
if errorlevel 1 goto :generate

echo [1/3] Documentos de prueba al dia ^(%GENN% docs^). Reescribiendo targets...
"%GEN%" -targets-only -targets "%~dp0." -n %GENN% -url %URL% -host %XHOST% -body-ref "../loadtest-tools/bodies"
if errorlevel 1 ( echo [ERROR] no se pudieron escribir los targets & exit /b 1 )
goto :attack

:generate
echo [1/3] Generando %GENN% documentos distintos desde 4 PDFs ^(round-robin^)...
echo       Puede tardar unos minutos y usar unos 10 GB de disco.
del /q "%TOOLS%\bodies\body_*.bin"   >nul 2>&1
del /q "%TOOLS%\bodies\gen-info.txt" >nul 2>&1
del /q "%TOOLS%\variants\doc_*.pdf"  >nul 2>&1
"%GEN%" -source "%SRC%" -n %GENN% -pdf-dir "%TOOLS%\variants" -body-dir "%TOOLS%\bodies" -targets "%~dp0." -body-ref "../loadtest-tools/bodies" -url %URL% -host %XHOST%
if errorlevel 1 ( echo [ERROR] fallo la generacion de documentos & exit /b 1 )

:attack
if not exist results mkdir results
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set STAMP=%%i
set OUT=results\parse-%STAMP%.bin

echo.
echo [2/3] Ataque: %RATE% req/s durante %DURATION% ^(timeout %TIMEOUT%^)...
vegeta.exe attack -targets "%~dp0targets-parse.txt" -rate %RATE% -duration %DURATION% -timeout %TIMEOUT% -lazy -output "%OUT%"
if errorlevel 1 ( echo [ERROR] fallo el ataque & exit /b 1 )

echo.
echo [3/3] Resultados
echo ============================================================
vegeta.exe report "%OUT%"
echo ============================================================
echo.
echo Archivo de resultados: %OUT%
echo.
echo Como leer las metricas:
echo    throughput     3er numero de "Requests"      ^(objetivo ~50 req/s^)
echo    exitosas       "Status Codes"  200:NNNN
echo    timeouts       "Status Codes"  0:NNNN
echo    latencia P50   3er numero de "Latencies"     ^(columna 50^)

endlocal
