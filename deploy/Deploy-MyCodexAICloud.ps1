[CmdletBinding()]
param([switch]$SkipInstall)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$workerRoot = Join-Path $projectRoot 'cloud\worker'
$config = Get-Content -LiteralPath (Join-Path $workerRoot 'wrangler.jsonc') -Raw -Encoding UTF8
if ($config -match 'REPLACE_WITH_') { throw 'wrangler.jsonc ยังมีค่า REPLACE_WITH_ กรุณารัน Set-MyCodexAICloudConfig.ps1 ก่อน' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'ยังไม่พบ Node.js/npm ให้ติดตั้ง Node.js LTS จาก https://nodejs.org แล้วเปิด PowerShell ใหม่'
}

Push-Location $workerRoot
try {
    if (-not $SkipInstall) { npm install }
    npx wrangler whoami
    npx wrangler d1 migrations apply mycodexai-cloud --remote
    npx wrangler deploy
} finally {
    Pop-Location
}

Write-Host 'Deploy เสร็จแล้ว ให้คัดลอก workers.dev URL ไปตั้งเป็น MYCODEXAI_CLOUD_URL ใน GitHub Actions secrets' -ForegroundColor Green
