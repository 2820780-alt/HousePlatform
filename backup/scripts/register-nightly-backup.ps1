param(
    [string]$TaskName = "HousePlatformNightlyBackup",
    [string]$At = "23:00",
    [int]$Keep = 14
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptPath = Resolve-Path (Join-Path $PSScriptRoot "nightly-backup.ps1")
$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -Keep $Keep"

schtasks.exe /Create `
    /TN $TaskName `
    /SC DAILY `
    /ST $At `
    /TR $taskCommand `
    /F | Out-Null

Write-Host "Scheduled task created: $TaskName"
Write-Host "Daily run time: $At"
Write-Host "Backup script: $scriptPath"
Write-Host "To test now: schtasks /Run /TN $TaskName"

