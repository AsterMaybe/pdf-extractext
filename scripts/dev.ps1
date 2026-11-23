#Requires -Version 5.1
<#
.SYNOPSIS
  Orquesta los cuatro stacks Docker Compose del proyecto con un solo comando.

.DESCRIPTION
  Levanta / apaga / inspecciona los stacks en el orden correcto:

      consul -> microservicio-db -> microservicio-go -> traefik -> monolitico (app)

  Crea de forma idempotente la red compartida y el volumen externo de Mongo.
  Espera a que cada stack reporte "healthy" antes de continuar.
  Descubre autom�ticamente la ubicaci�n de los microservicios.

.PARAMETER Command
  up       Arranca todo (sin reconstruir im�genes).        [default]
  rebuild  Igual que up pero reconstruye im�genes (--build).
  down     Baja todo en orden inverso.
  restart  down + up.
  logs     Sigue (tail -f) los logs de los cuatro stacks en paralelo.
  ps       Muestra el estado de cada stack.

.PARAMETER Timeout
  Segundos a esperar por stack para alcanzar "healthy" (default 180).

.PARAMETER DbPath
  Ruta opcional a microservicio-db (default: auto-detect ../microservicio-db desde project root).

.PARAMETER GoPath
  Ruta opcional a microservicio-go (default: auto-detect ../microservicio-go desde project root).

.EXAMPLE
  .\dev.ps1 up
  .\dev.ps1 rebuild
  .\dev.ps1 ps
  .\dev.ps1 logs
  .\dev.ps1 down
  .\dev.ps1 up -DbPath "C:\ruta\personalizada\microservicio-db"
#>
[CmdletBinding()]
param(
    [ValidateSet('up', 'rebuild', 'down', 'restart', 'logs', 'ps')]
    [string]$Command = 'up',

    [int]$Timeout = 180,

    [string]$DbPath = '',
    [string]$GoPath = ''
)

$ErrorActionPreference = 'Stop'

# -- Descubrir rutas del proyecto din�micamente ----------------------------------
# Script est� en: monolitico/scripts/
# Monolitico dir: monolitico/
# Project root:   monolitico/..
$ScriptDir     = $PSScriptRoot
$MonoliticoDir = Split-Path -Parent $ScriptDir
$ProjectRoot   = Split-Path -Parent $MonoliticoDir

# Auto-detectar microservicios (permitir override por par�metro)
$DbDir = if ($DbPath) { $DbPath } else { Join-Path $ProjectRoot 'microservicio-db' }
$GoDir = if ($GoPath) { $GoPath } else { Join-Path $ProjectRoot 'microservicio-go' }

# Validar que existen
if (-not (Test-Path -LiteralPath $DbDir)) {
    throw "No se encuentra microservicio-db en: $DbDir`nUsa -DbPath para especificar ruta personalizada."
}
if (-not (Test-Path -LiteralPath $GoDir)) {
    throw "No se encuentra microservicio-go en: $GoDir`nUsa -GoPath para especificar ruta personalizada."
}

Write-Host "Proyecto: $ProjectRoot" -ForegroundColor DarkGray
Write-Host "Monolitico: $MonoliticoDir" -ForegroundColor DarkGray
Write-Host "DB: $DbDir" -ForegroundColor DarkGray
Write-Host "Go: $GoDir" -ForegroundColor DarkGray

# -- Infraestructura compartida (se crea si no existe) -------------------------
$NetworkName = 'test_network'
$VolumeName  = 'pdf-extractext_mongo_data'

# -- Stacks en orden de arranque -----------------------------------------------
# Dir es relativo a $ProjectRoot, excepto consul y monolitico que usan rutas especiales
$Stacks = @(
    # Consul: compose est� en monolitico/ (mismo nivel que microservicios desde project root)
    [pscustomobject]@{ Name = 'consul';  Dir = 'monolitico';                 Compose = 'docker-compose.consul.yml';  Env = '.env'; Build = $false; Wait = @('consul') }

    # microservicio-db: est� en project root
    [pscustomobject]@{ Name = 'db';      Dir = 'microservicio-db';           Compose = 'docker-compose.yml';         Env = '.env'; Build = $true;  Wait = @('mongo', 'redis', 'microservicio-db-go') }

    # microservicio-go: est� en project root
    [pscustomobject]@{ Name = 'go';      Dir = 'microservicio-go';           Compose = 'docker-compose.yml';         Env = '.env'; Build = $true;  Wait = @('api') }

    # Traefik: compose est� en monolitico/
    [pscustomobject]@{ Name = 'traefik'; Dir = 'monolitico';                 Compose = 'docker-compose.traefik.yml'; Env = '.env'; Build = $false; Wait = @('traefik') }

    # App: compose est� en monolitico/
    [pscustomobject]@{ Name = 'app';     Dir = 'monolitico';                 Compose = 'docker-compose.app.yml';     Env = '.env'; Build = $true;  Wait = @('myapp') }
)

# -- Helpers -------------------------------------------------------------------
function Get-ComposeFileArgs {
    param([object]$Stack)
    $dir     = Join-Path $ProjectRoot $Stack.Dir
    $file    = Join-Path $dir  $Stack.Compose
    $envFile = Join-Path $dir  $Stack.Env
    $a = @()
    if (Test-Path -LiteralPath $envFile) { $a += @('--env-file', $envFile) }
    $a += @('-f', $file)
    return , $a
}

function Invoke-Compose {
    param([object]$Stack, [string[]]$ComposeArgs)
    $dir  = Join-Path $ProjectRoot $Stack.Dir
    $all  = @((Get-ComposeFileArgs $Stack) + $ComposeArgs)
    Push-Location $dir
    # Docker Compose escribe el progreso por stderr; lo reemitimos por stdout
    # para que no se muestre como error nativo.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $code = 0
    try {
        & docker compose @all 2>&1 | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prevEAP
        Pop-Location
    }
    if ($code -ne 0) {
        throw "docker compose fall� en el stack '$($Stack.Name)' (exit $code)"
    }
}

function Get-ServiceContainerIds {
    param([object]$Stack, [string]$Service)
    $dir  = Join-Path $ProjectRoot $Stack.Dir
    $all  = @((Get-ComposeFileArgs $Stack) + @('ps', '-q', $Service))
    Push-Location $dir
    try {
        $ids = & docker compose @all 2>$null
        if ($LASTEXITCODE -ne 0) { throw "docker compose ps fall� en '$($Stack.Name)'" }
    }
    finally { Pop-Location }
    return @($ids | Where-Object { $_ -and $_.Trim() })
}

function Get-ContainerState {
    param([string]$Id)
    # Returns "healthy" if:
    # - Docker health check exists and is "healthy", OR
    # - No Docker health check exists (nil) and container is "running"
    # This allows services using Consul health checks (no Docker healthcheck) to pass Wait-Healthy
    $inspect = & docker inspect --format '{{json .State}}' $Id 2>$null
    if (-not $inspect) { return 'unknown' }
    $state = $inspect | ConvertFrom-Json
    if ($state.Health) {
        return $state.Health.Status
    } else {
        if ($state.Status -eq 'running') { return 'healthy' }
        return $state.Status
    }
}

function Wait-Healthy {
    param([object]$Stack, [int]$TimeoutSec)
    if ($Stack.Wait.Count -eq 0) { return }
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    foreach ($svc in $Stack.Wait) {
        $ids = Get-ServiceContainerIds $Stack $svc
        if ($ids.Count -eq 0) { throw "No hay contenedores para el servicio '$svc' en el stack '$($Stack.Name)'." }
        Write-Host ("  esperando '{0}' ..." -f $svc) -ForegroundColor DarkGray
        while ($true) {
            $allHealthy = $true
            foreach ($id in $ids) {
                if ((Get-ContainerState $id) -ne 'healthy') { $allHealthy = $false; break }
            }
            if ($allHealthy) { break }
            if ((Get-Date) -gt $deadline) {
                $cur = ($ids | ForEach-Object { "{0}={1}" -f (Get-ContainerState $_), $_ }) -join ', '
                throw "Timeout esperando '$svc' en '$($Stack.Name)'. Estado actual: $cur"
            }
            Start-Sleep -Seconds 2
        }
    }
}

function Ensure-Infrastructure {
    $null = docker network inspect $NetworkName 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Creando red '$NetworkName'..." -ForegroundColor Cyan
        $null = docker network create $NetworkName
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear la red '$NetworkName'." }
    }
    else { Write-Host "Red '$NetworkName' ya existe." -ForegroundColor DarkGray }

    $null = docker volume inspect $VolumeName 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Creando volumen '$VolumeName'..." -ForegroundColor Cyan
        $null = docker volume create $VolumeName
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el volumen '$VolumeName'." }
    }
    else { Write-Host "Volumen '$VolumeName' ya existe." -ForegroundColor DarkGray }
}

function Start-Stack {
    param([object]$Stack, [switch]$Build)
    $argv = @('up', '-d')
    if ($Build -and $Stack.Build) { $argv += '--build' }
    Write-Host ("==> [{0}] docker compose {1}" -f $Stack.Name, ($argv -join ' ')) -ForegroundColor Green
    Invoke-Compose $Stack $argv
    Wait-Healthy $Stack $Timeout
}

function Stop-Stack {
    param([object]$Stack)
    Write-Host ("==> [{0}] docker compose down" -f $Stack.Name) -ForegroundColor Yellow
    Invoke-Compose $Stack @('down')
}

function Show-Banner {
    Write-Host ""
    Write-Host "  Servicios disponibles:" -ForegroundColor Cyan
    Write-Host "    Consul UI     http://localhost:8500"
    Write-Host "    Monolito      http://api.localhost/docs"
    Write-Host "    Extractor     http://extract.localhost/api/v1/health"
    Write-Host "    Traefik       http://localhost:8080/dashboard/"
    Write-Host ""
}

function Invoke-Up {
    param([switch]$Build)
    Ensure-Infrastructure
    foreach ($stack in $Stacks) {
        if ($stack.Build -and $Build) { Start-Stack $stack -Build } else { Start-Stack $stack }
    }
    Cleanup-ConnectProxies
    Show-Banner
}

function Cleanup-ConnectProxies {
    Write-Host "Limpiando connect-proxy services obsoletos..." -ForegroundColor DarkGray
    # Note: Connect is currently disabled in consul config, so these proxies shouldn't exist.
    # This function is kept for future use when Connect/mTLS is enabled.
    # Skipping actual cleanup since Connect is disabled - no connect-proxy services exist.
    # If Connect is enabled in the future, implement using Consul HTTP API directly via Invoke-WebRequest
    # to avoid PowerShell/docker compose argument parsing issues.
    Start-Sleep -Seconds 1
}

function Invoke-Down {
    for ($i = $Stacks.Count - 1; $i -ge 0; $i--) { Stop-Stack $Stacks[$i] }
}

function Invoke-Logs {
    $jobs = foreach ($stack in $Stacks) {
        Start-Job -ScriptBlock {
            param($ProjectRoot, $Dir, $Compose, $Env)
            Set-Location (Join-Path $ProjectRoot $Dir)
            $a = @()
            $envFile = Join-Path $ProjectRoot (Join-Path $Dir $Env)
            if (Test-Path -LiteralPath $envFile) { $a += @('--env-file', $envFile) }
            $a += @('-f', (Join-Path $ProjectRoot (Join-Path $Dir $Compose)))
            & docker compose @a logs -f --tail=100
        } -ArgumentList $ProjectRoot, $stack.Dir, $stack.Compose, $stack.Env
    }
    try { Receive-Job -Job $jobs -Wait }
    finally { $jobs | Remove-Job -Force }
}

function Invoke-Ps {
    foreach ($stack in $Stacks) {
        Write-Host ("==> [{0}]" -f $stack.Name) -ForegroundColor Green
        Invoke-Compose $stack @('ps')
    }
}

# -- Dispatch ------------------------------------------------------------------
switch ($Command) {
    'up'      { Invoke-Up }
    'rebuild' { Invoke-Up -Build }
    'down'    { Invoke-Down }
    'restart' { Invoke-Down; Invoke-Up }
    'logs'    { Invoke-Logs }
    'ps'      { Invoke-Ps }
}
