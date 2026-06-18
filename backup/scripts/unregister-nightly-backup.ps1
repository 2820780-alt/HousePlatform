param(
    [string]$TaskName = "HousePlatformNightlyBackup"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

schtasks.exe /Delete /TN $TaskName /F | Out-Null

Write-Host "Scheduled task removed: $TaskName"
