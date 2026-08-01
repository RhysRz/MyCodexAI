[CmdletBinding()]
param()

$launcher = Join-Path ([Environment]::GetFolderPath('Startup')) 'MyCodexAI Recovery.cmd'
Remove-Item -LiteralPath $launcher -Force -ErrorAction SilentlyContinue
