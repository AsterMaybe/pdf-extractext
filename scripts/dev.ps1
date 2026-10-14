#Requires -Version 5.1
<#
.SYNOPSIS
  Orquesta los cuatro stacks Docker Compose del proyecto con un solo comando.

.DESCRIPTION
  Levanta / apaga / inspecciona los stacks en el orden correcto:

      microservicio-db  ->  microservicio-go  ->  traefik  ->  monolitico (app)

  Crea de forma idempotente la red compartida y el volumen externo de Mongo.
  Espera a que cada stack reporte "healthy" antes de continuar.

.PARAMETER Command
  up       Arranca todo (sin reconstruir imágenes).        [default]
  rebuild  Igual que up pero reconstruye imágenes (--build).
  down     Baja todo en orden inverso.
  restart  down + up.
  logs     Sigue (tail -f) los logs de los cuatro stacks en paralelo.
  ps       Muestra el estado de cada stack.

.PARAMETER Timeout
  Segundos a esperar por stack para alcanzar "healthy" (default 180).

.EXAMPLE
  .\scripts\dev.ps1 up
  .\scripts\dev.ps1 rebuild
  .\scripts\dev.ps1 ps
  .\scripts\dev.ps1 logs
  .\scripts\dev.ps1 down
#>
[CmdletBinding()]
param(
    [ValidateSet('up', 'rebuild', 'down', 'restart', 'logs', 'ps')]
    [string]$Command = 'up',

    [int]$Timeout = 180
)

$ErrorActionPreference = 'Stop'

# ── Raíz del proyecto (carpeta padre de scripts/) ─────────────────────────────
$Root = Split-Path -Parent $PSScriptRoot

# ── Infraestructura compartida (se crea si no existe) ─────────────────────────
$NetworkName = 'test_network'
$VolumeName  = 'pdf-extractext_mongo_data'

# ── Stacks en orden de arranque ───────────────────────────────────────────────
# Wait = servicios cuyo healthcheck debe estar "healthy" antes de seguir.
$Stacks = @(
    [pscustomobject]@{ Name = 'db';      Dir = 'microservicio-db'; Compose = 'docker-compose.yml';         Env = '.env'; Build = $true;  Wait = @('mongo', 'redis', 'microservicio-db-go') }
    [pscustomobject]@{ Name = 'go';      Dir = 'microservicio-go'; Compose = 'docker-compose.yml';         Env = '.env'; Build = $true;  Wait = @('api') }
    [pscustomobject]@{ Name = 'traefik'; Dir = 'monolitico';       Compose = 'docker-compose.traefik.yml'; Env = '.env'; Build = $false; Wait = @() }
    [pscustomobject]@{ Name = 'app';     Dir = 'monolitico';       Compose = 'docker-compose.app.yml';     Env = '.env'; Build = $true;  Wait = @('myapp') }
)

# ── Helpers ───────────────────────────────────────────────────────────────────
function Get-ComposeFileArgs {
    param([object]$Stack)
    $dir     = Join-Path $Root $Stack.Dir
    $file    = Join-Path $dir  $Stack.Compose
    $envFile = Join-Path $dir  $Stack.Env
    $a = @()
    if (Test-Path -LiteralPath $envFile) { $a += @('--env-file', $envFile) }
    $a += @('-f', $file)
    return , $a
}

function Invoke-Compose {
    param([object]$Stack, [string[]]$ComposeArgs)
    $dir  = Join-Path $Root $Stack.Dir
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
        throw "docker compose falló en el stack '$($Stack.Name)' (exit $code)"
    }
}

function Get-ServiceContainerIds {
    param([object]$Stack, [string]$Service)
    $dir  = Join-Path $Root $Stack.Dir
    $all  = @((Get-ComposeFileArgs $Stack) + @('ps', '-q', $Service))
    Push-Location $dir
    try {
        $ids = & docker compose @all 2>$null
        if ($LASTEXITCODE -ne 0) { throw "docker compose ps falló en '$($Stack.Name)'" }
    }
    finally { Pop-Location }
    return @($ids | Where-Object { $_ -and $_.Trim() })
}

function Get-ContainerState {
    param([string]$Id)
    $s = & docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $Id 2>$null
    return ($s | Select-Object -First 1)
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
    Write-Host "    Monolito   http://api.localhost/docs"
    Write-Host "    Extractor  http://extract.localhost/api/v1/health"
    Write-Host "    Traefik    http://localhost:8080/dashboard/"
    Write-Host ""
}

function Invoke-Up {
    param([switch]$Build)
    Ensure-Infrastructure
    foreach ($stack in $Stacks) {
        if ($stack.Build -and $Build) { Start-Stack $stack -Build } else { Start-Stack $stack }
    }
    Show-Banner
}

function Invoke-Down {
    for ($i = $Stacks.Count - 1; $i -ge 0; $i--) { Stop-Stack $Stacks[$i] }
}

function Invoke-Logs {
    $jobs = foreach ($stack in $Stacks) {
        Start-Job -ScriptBlock {
            param($Root, $Dir, $Compose, $Env)
            Set-Location (Join-Path $Root $Dir)
            $a = @()
            $envFile = Join-Path $Root (Join-Path $Dir $Env)
            if (Test-Path -LiteralPath $envFile) { $a += @('--env-file', $envFile) }
            $a += @('-f', (Join-Path $Root (Join-Path $Dir $Compose)))
            & docker compose @a logs -f --tail=100
        } -ArgumentList $Root, $stack.Dir, $stack.Compose, $stack.Env
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

# ── Dispatch ──────────────────────────────────────────────────────────────────
Write-Host "Proyecto: $Root" -ForegroundColor DarkGray
switch ($Command) {
    'up'      { Invoke-Up }
    'rebuild' { Invoke-Up -Build }
    'down'    { Invoke-Down }
    'restart' { Invoke-Down; Invoke-Up }
    'logs'    { Invoke-Logs }
    'ps'      { Invoke-Ps }
}
