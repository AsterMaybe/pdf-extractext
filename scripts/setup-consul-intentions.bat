@echo off
REM Setup Consul Connect Intentions for Service Mesh
REM Run this after all services are registered with Consul

set CONSUL_ADDR=%CONSUL_HTTP_ADDR%
if "%CONSUL_ADDR%"=="" set CONSUL_ADDR=http://localhost:8500

set CONSUL_TOKEN=%CONSUL_HTTP_TOKEN%
if "%CONSUL_TOKEN%"=="" set CONSUL_TOKEN=dev-bootstrap-token

echo Setting up Consul Connect intentions...
echo Consul address: %CONSUL_ADDR%

REM Function to create/check intention
:CREATE_INTENTION
set SRC=%1
set DST=%2
set ACTION=%3
if "%ACTION%"=="" set ACTION=allow

echo Creating intention: %SRC% -> %DST% (%ACTION%)

REM Check if intention exists
consul intention check -src "%SRC%" -dst "%DST%" -http-addr "%CONSUL_ADDR%" -token "%CONSUL_TOKEN%" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo   Intention already exists: %SRC% -> %DST% (%ACTION%)
) else (
    consul intention create -src "%SRC%" -dst "%DST%" -action "%ACTION%" -http-addr "%CONSUL_ADDR%" -token "%CONSUL_TOKEN%"
    echo   Created: %SRC% -> %DST% (%ACTION%)
)
goto :EOF

REM Wait for Consul to be ready
echo Waiting for Consul to be ready...
:WAIT_CONSUL
curl -sf "%CONSUL_ADDR%/v1/status/leader" -H "X-Consul-Token: %CONSUL_TOKEN%" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    timeout /t 2 /nobreak >nul
    goto WAIT_CONSUL
)
echo Consul is ready!

REM Create intentions (deny by default, so we explicitly allow)
REM Service-to-service intentions for mTLS
REM monolitico -> microservicio-go (for PDF extraction)
call :CREATE_INTENTION "monolitico" "microservicio-go" "allow"

REM monolitico -> microservicio-db (for document persistence)
call :CREATE_INTENTION "monolitico" "microservicio-db" "allow"

REM microservicio-go -> redis (for cache) - if redis has sidecar
REM call :CREATE_INTENTION "microservicio-go" "redis" "allow"

REM microservicio-db -> mongo (for database) - if mongo has sidecar
REM call :CREATE_INTENTION "microservicio-db" "mongo" "allow"

REM Sidecar-to-sidecar intentions (internal, for Connect proxy authorization)
REM These are automatically created when sidecars are registered with intentions above
REM call :CREATE_INTENTION "monolitico-sidecar" "microservicio-go-sidecar" "allow"
REM call :CREATE_INTENTION "monolitico-sidecar" "microservicio-db-sidecar" "allow"

echo.
echo Listing all intentions:
consul intention list -http-addr "%CONSUL_ADDR%" -token "%CONSUL_TOKEN%"

echo.
echo Intentions setup complete!
echo.
echo Note: Intentions for redis and mongo are commented out since they don't have sidecars.
echo If you deploy redis/mongo with Consul Connect sidecars, uncomment those lines.