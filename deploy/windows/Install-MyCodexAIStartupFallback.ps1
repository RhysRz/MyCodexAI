[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\MyCodexAI'
)

$ErrorActionPreference = 'Stop'
$watcher = Join-Path $PSScriptRoot 'Watch-MyCodexAI.ps1'
$startup = [Environment]::GetFolderPath('Startup')
$launcher = Join-Path $startup 'MyCodexAI Recovery.cmd'

if (-not (Test-Path -LiteralPath $watcher -PathType Leaf)) { throw "Watchdog script not found: $watcher" }
@"
@echo off
start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$watcher" -ProjectRoot "$ProjectRoot"
"@ | Set-Content -LiteralPath $launcher -Encoding ASCII
Write-Host "Installed Startup fallback: $launcher"
