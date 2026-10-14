<#
.SYNOPSIS
    Runs a Vegeta attack against POST /extract using the generated fixtures.

.DESCRIPTION
    Two profiles are available and they measure different things:

      parse  N distinct documents round robin. Nearly every request is a genuine
             cache miss, so this exercises the MuPDF parser and the CPU budget.
             This is the number to quote for parser capacity.
      cache  A single document replayed. Everything after the first request is
             served from Redis. This measures the cache path and is expected to
             be far faster; it is not a parser measurement.

    The distinction matters because the service caches on the SHA-256 of the
    uploaded bytes. Repeating one document, which is what a naive "echo POST
    /extract" style command does, measures the rejection path or the cache path
    and never the parser.

.PARAMETER Profile
    parse (default) or cache.

.PARAMETER Rate
    Requests per second. The default 300 matches the assignment's target.

.PARAMETER Duration
    Attack window, e.g. 60s.

.PARAMETER RateVsRequests
    Optional hard cap on total requests. Useful for the parse profile, where the
    document count must be at least as large as the request count or the tail of
    the run starts hitting the cache again.

.EXAMPLE
    .\run-variants.ps1 -Profile parse -RateVsRequests 200

.EXAMPLE
    .\run-variants.ps1 -Profile cache -Rate 300 -Duration 60s
#>
[CmdletBinding()]
param(
    [ValidateSet('parse', 'cache')]
    [string]$Profile = 'parse',

    [int]$Rate = 300,

    [string]$Duration = '60s',

    [string]$Url = '',

    [string]$Timeout = '30s',

    [int]$Workers = 10,

    [int]$RateVsRequests = 0,

    [string]$OutputDir = ''
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Vegeta resolves the "@body" references in a targets file relative to the
# process working directory, so the attack has to start from this folder.
Set-Location -LiteralPath $scriptDir

$vegeta = Join-Path $scriptDir 'vegeta.exe'
if (-not (Test-Path -LiteralPath $vegeta)) {
    throw "vegeta.exe not found in $scriptDir"
}

$targetsFile = Join-Path $scriptDir "targets-$Profile.txt"
if (-not (Test-Path -LiteralPath $targetsFile)) {
    throw "Missing $targetsFile. Generate the fixtures first: see ..\loadtest-tools\README.md"
}

$bodiesDir = Join-Path (Split-Path -Parent $scriptDir) 'loadtest-tools\bodies'
if (-not (Test-Path -LiteralPath $bodiesDir)) {
    throw "Missing fixture bodies at $bodiesDir. Generate them first: see ..\loadtest-tools\README.md"
}

# Count the distinct documents this profile will actually rotate through.
$bodyCount = (Get-ChildItem -LiteralPath $bodiesDir -Filter 'body_*.bin' -File).Count

if ($OutputDir -eq '') {
    $OutputDir = Join-Path $scriptDir 'results'
}
if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# An explicit URL is applied to a copy of the targets file rather than by
# rewriting the committed one, and the copy stays in this folder so the relative
# body references keep resolving.
$attackTargets = $targetsFile
if ($Url -ne '') {
    $attackTargets = Join-Path $scriptDir "targets-$Profile.tmp.txt"
    $content = Get-Content -LiteralPath $targetsFile -Raw
    $content = $content -replace '(?m)^POST\s+\S+', "POST $Url"
    # Windows PowerShell's -Encoding UTF8 writes a BOM, and Vegeta then reads the
    # first method as "﻿POST" and rejects the file.
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($attackTargets, $content, $utf8NoBom)
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$resultsFile = Join-Path $OutputDir "$Profile-$stamp.bin"

Write-Host "profile      $Profile"
Write-Host "target       $(if ($Url -ne '') { $Url } else { 'as generated in targets file' })"
Write-Host "bodies       $bodyCount distinct documents available"
Write-Host "rate         $Rate/s for $Duration"
if ($RateVsRequests -gt 0) {
    Write-Host "cap          $RateVsRequests requests"
    if ($bodyCount -lt $RateVsRequests) {
        Write-Warning "Only $bodyCount distinct documents for $RateVsRequests requests. Expect roughly $([math]::Round(100 * (1 - $bodyCount / $RateVsRequests), 1))% cache hits; regenerate with a larger -n for a clean parse measurement."
    }
}
Write-Host "results      $resultsFile"
Write-Host ''

$attackArgs = @(
    'attack',
    '-targets', $attackTargets,
    '-rate', $Rate,
    '-duration', $Duration,
    '-timeout', $Timeout,
    '-workers', $Workers,
    '-output', $resultsFile
)
# Note: do not pass "-keepalive true". Vegeta's keepalive is a bool flag, so the
# separate "true" becomes a stray positional argument, which makes Vegeta ignore
# -output and dump results to stdout instead. The flag already defaults to true.

if ($RateVsRequests -gt 0) {
    # max-workers bounds in-flight requests; for a fixed request budget use a
    # per-second rate with the matching window instead.
    $attackArgs += @('-max-workers', $RateVsRequests)
}

& $vegeta @attackArgs
if ($LASTEXITCODE -ne 0) {
    throw "vegeta attack failed with exit code $LASTEXITCODE"
}

if ($attackTargets -ne $targetsFile) {
    Remove-Item -LiteralPath $attackTargets -Force
}

Write-Host ''
& $vegeta report $resultsFile
if ($LASTEXITCODE -ne 0) {
    throw "vegeta report failed with exit code $LASTEXITCODE"
}

Write-Host ''
Write-Host "Verifying the document mix actually reached the service."
Write-Host 'A cache hit never persists a record, so the number of documents in'
Write-Host 'MongoDB equals the number of real parses. Compare it against the'
Write-Host 'request total above: equal means every request was a genuine parse.'