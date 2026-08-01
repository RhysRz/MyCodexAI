[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\MyCodexAI'
)

$ErrorActionPreference = 'Stop'
$watcher = Join-Path $PSScriptRoot 'Watch-MyCodexAI.ps1'
if (-not (Test-Path -LiteralPath $watcher -PathType Leaf)) { throw "Watchdog script not found: $watcher" }

$taskName = 'MyCodexAI Recovery'
$command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$watcher`" -ProjectRoot `"$ProjectRoot`""
schtasks.exe /Create /TN $taskName /SC ONLOGON /RL LIMITED /TR $command /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "Windows rejected creation of '$taskName'. Run this script from an elevated PowerShell window, or use the Startup fallback script."
}
Write-Host "Installed '$taskName'. It starts MyCodexAI after this Windows user signs in."
