param(
    [int]$Keep = 14
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$logDir = Join-Path $projectRoot "backup\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path $logDir "nightly-backup-$stamp.log"

Start-Transcript -Path $logFile -Append | Out-Null

try {
    & (Join-Path $PSScriptRoot "backup-postgres.ps1") -Keep $Keep -StartDb
    Write-Host "Nightly backup completed."
}
catch {
    Write-Error $_
    throw
}
finally {
    Stop-Transcript | Out-Null
}

