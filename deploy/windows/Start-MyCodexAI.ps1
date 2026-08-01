[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\MyCodexAI',
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$python = Join-Path $ProjectRoot 'venv\Scripts\python.exe'
$logDirectory = Join-Path $ProjectRoot '.mycodexai\logs'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "MyCodexAI Python runtime was not found at $python"
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $listener) {
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    Start-Process -FilePath $python `
        -ArgumentList @('-m','uvicorn','main:app','--host','127.0.0.1','--port',$Port,'--proxy-headers','--forwarded-allow-ips','127.0.0.1') `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDirectory 'uvicorn.stdout.log') `
        -RedirectStandardError (Join-Path $logDirectory 'uvicorn.stderr.log') | Out-Null
}

# The quick tunnel is optional and is intentionally not recreated here: its public
# URL changes after every recreation. A named/domain tunnel should be used for a
# stable production URL.
for ($attempt = 0; $attempt -lt 12; $attempt++) {
    try {
        $docker = Get-Command docker -ErrorAction Stop
        $existingTunnel = & $docker.Source ps -a --filter 'name=^/mycodexai-quick-tunnel$' --format '{{.Names}}' 2>$null
        if ($existingTunnel -eq 'mycodexai-quick-tunnel') {
            & $docker.Source start mycodexai-quick-tunnel 2>$null | Out-Null
            break
        }
    } catch { }
    Start-Sleep -Seconds 5
}
