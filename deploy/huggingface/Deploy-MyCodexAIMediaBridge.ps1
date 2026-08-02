param(
    [string]$SpaceId = "RhysRz/mycodexai-media-bridge"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "MyCodexAI virtual environment was not found at $python"
}

$temporaryToken = $false
try {
    if (-not $env:HF_DEPLOY_TOKEN) {
        $secureToken = Read-Host "Paste a Hugging Face Write token (hidden, used once)" -AsSecureString
        $tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
        try {
            $env:HF_DEPLOY_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
        }
        $temporaryToken = $true
    }
    $env:MYCODEXAI_MEDIA_BRIDGE_SPACE = $SpaceId
    & $python -m pip install --disable-pip-version-check "huggingface_hub>=0.34,<1" "pynacl>=1.5,<2"
    if ($LASTEXITCODE -ne 0) { throw "Could not install deployment helpers" }
    & $python (Join-Path $PSScriptRoot "deploy_media_bridge.py")
    if ($LASTEXITCODE -ne 0) { throw "Media Bridge deployment failed" }
} finally {
    if ($temporaryToken) { Remove-Item Env:HF_DEPLOY_TOKEN -ErrorAction SilentlyContinue }
    Remove-Item Env:MYCODEXAI_MEDIA_BRIDGE_SPACE -ErrorAction SilentlyContinue
}
