[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f-]{20,}$')][string]$DatabaseId,
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9-]{1,39}$')][string]$GitHubOwner,
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z0-9._-]{1,100}$')][string]$GitHubRepo,
    [string]$PublicOrigin = 'REPLACE_AFTER_FIRST_DEPLOY'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $projectRoot 'cloud\worker\wrangler.jsonc'
if (-not (Test-Path -LiteralPath $configPath)) { throw "ไม่พบ $configPath" }

$content = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8
$content = $content.Replace('REPLACE_WITH_D1_DATABASE_ID', $DatabaseId)
$content = $content.Replace('REPLACE_WITH_GITHUB_USERNAME', $GitHubOwner)
$content = $content.Replace('REPLACE_WITH_PRIVATE_REPOSITORY', $GitHubRepo)
if ($PublicOrigin -ne 'REPLACE_AFTER_FIRST_DEPLOY') {
    $content = $content.Replace('REPLACE_AFTER_FIRST_DEPLOY', $PublicOrigin.TrimEnd('/'))
}
[IO.File]::WriteAllText($configPath, $content, [Text.UTF8Encoding]::new($false))
Write-Host 'อัปเดต wrangler.jsonc แล้ว โดยไม่ได้แตะหรือบันทึก secret' -ForegroundColor Green
