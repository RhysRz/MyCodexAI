[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\MyCodexAI',
    [int]$Port = 8000,
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = 'Continue'
$starter = Join-Path $PSScriptRoot 'Start-MyCodexAI.ps1'
if (-not (Test-Path -LiteralPath $starter -PathType Leaf)) { throw "Starter script not found: $starter" }

while ($true) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $starter -ProjectRoot $ProjectRoot -Port $Port
    }
    Start-Sleep -Seconds $IntervalSeconds
}
