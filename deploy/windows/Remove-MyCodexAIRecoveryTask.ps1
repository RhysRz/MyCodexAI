[CmdletBinding()]
param()

schtasks.exe /Delete /TN 'MyCodexAI Recovery' /F | Out-Host
