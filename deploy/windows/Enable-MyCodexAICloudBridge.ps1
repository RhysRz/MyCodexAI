[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\MyCodexAI',
    [Parameter(Mandatory = $true)]
    [string]$CloudUrl,
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'
$envFile = Join-Path $ProjectRoot '.env'
$launcher = Join-Path $ProjectRoot 'deploy\windows\Start-MyCodexAI.ps1'
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) { throw "MyCodexAI .env was not found at $envFile" }
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "MyCodexAI launcher was not found at $launcher" }

$uri = $null
if (-not [Uri]::TryCreate($CloudUrl.TrimEnd('/'), [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https') {
    throw 'CloudUrl must be an HTTPS address, for example https://mycodexai-cloud.example.workers.dev'
}

$secureToken = Read-Host 'Paste the one-time Bridge token (it will not be displayed)' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $bridgeToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
}
if ([string]::IsNullOrWhiteSpace($bridgeToken) -or $bridgeToken.Length -lt 32) { throw 'Bridge token is missing or too short.' }

$values = [ordered]@{
    CLOUD_BRIDGE_ENABLED = 'true'
    CLOUD_BRIDGE_URL = $CloudUrl.TrimEnd('/')
    CLOUD_BRIDGE_TOKEN = $bridgeToken
    CLOUD_BRIDGE_POLL_SECONDS = '8'
}
$lines = [Collections.Generic.List[string]](Get-Content -LiteralPath $envFile -Encoding UTF8)
foreach ($entry in $values.GetEnumerator()) {
    $prefix = "$($entry.Key)="
    $index = -1
    for ($lineIndex = 0; $lineIndex -lt $lines.Count; $lineIndex++) {
        if ($lines[$lineIndex].StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { $index = $lineIndex; break }
    }
    $line = "$prefix$($entry.Value)"
    if ($index -ge 0) { $lines[$index] = $line } else { $lines.Add($line) }
}
$bridgeToken = $null
$lines | Set-Content -LiteralPath $envFile -Encoding UTF8
Write-Host 'Cloud Bridge is configured. The token was stored only in the ignored local .env file.'

if ($Restart) {
    $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) { Stop-Process -Id $listener.OwningProcess }
    & $launcher -ProjectRoot $ProjectRoot
    Write-Host 'MyCodexAI restarted with the outbound Cloud Bridge enabled.'
} else {
    Write-Host 'Restart MyCodexAI when ready, or rerun with -Restart.'
}
