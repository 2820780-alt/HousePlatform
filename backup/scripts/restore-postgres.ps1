param(
    [Parameter(Mandatory = $true)]
    [string]$DumpFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$composeFile = Join-Path $projectRoot "docker-compose.yml"
$dumpPath = Resolve-Path $DumpFile
$fileName = Split-Path $dumpPath -Leaf
$containerFile = "/tmp/$fileName"

$containerId = docker compose -f $composeFile ps -q db
if ([string]::IsNullOrWhiteSpace($containerId)) {
    throw "PostgreSQL container is not running. Start it with: docker compose up -d db"
}

Write-Host "Restoring backup into buildplatform database: $dumpPath"
Write-Host "Existing database objects may be replaced."

docker cp $dumpPath "${containerId}:$containerFile"

docker compose -f $composeFile exec -T db pg_restore `
    --clean `
    --if-exists `
    --no-owner `
    -U platform `
    -d buildplatform `
    $containerFile

docker compose -f $composeFile exec -T db rm -f $containerFile

Write-Host "Restore completed."

