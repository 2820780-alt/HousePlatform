param(
    [string]$OutputDir = "backup\dumps",
    [int]$Keep = 14
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$composeFile = Join-Path $projectRoot "docker-compose.yml"
$outputPath = Join-Path $projectRoot $OutputDir

New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$containerId = docker compose -f $composeFile ps -q db
if ([string]::IsNullOrWhiteSpace($containerId)) {
    throw "PostgreSQL container is not running. Start it with: docker compose up -d db"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$fileName = "houseplatform-$stamp.dump"
$containerFile = "/tmp/$fileName"
$localFile = Join-Path $outputPath $fileName

docker compose -f $composeFile exec -T db pg_dump `
    -U platform `
    -d buildplatform `
    -Fc `
    -f $containerFile

docker cp "${containerId}:$containerFile" $localFile
docker compose -f $composeFile exec -T db rm -f $containerFile

$oldBackups = Get-ChildItem -Path $outputPath -Filter "*.dump" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $Keep

foreach ($backup in $oldBackups) {
    Remove-Item -LiteralPath $backup.FullName -Force
}

Write-Host "Backup created: $localFile"

