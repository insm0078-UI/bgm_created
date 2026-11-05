# Run AI BGM Studio in development mode against a local ACE-Step checkout.
# Usage: powershell -ExecutionPolicy Bypass -File dev.ps1 [-AceStepRoot D:\project\ACE-Step-1.5]
param(
    [string]$AceStepRoot = (Join-Path $PSScriptRoot "..\..\ACE-Step-1.5")
)

$AceStepRoot = (Resolve-Path $AceStepRoot).Path
$env:BGM_ACESTEP_ROOT = $AceStepRoot
$env:BGM_PYTHON = Join-Path $AceStepRoot ".venv\Scripts\python.exe"
$env:BGM_ENGINE_DIR = (Resolve-Path (Join-Path $PSScriptRoot "..\engine")).Path
$env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"

if (-not (Test-Path $env:BGM_PYTHON)) {
    Write-Error "Python not found: $env:BGM_PYTHON (run 'uv sync --python 3.11' in ACE-Step first)"
    exit 1
}

Set-Location $PSScriptRoot
npm run tauri dev
