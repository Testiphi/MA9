[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$SkipNode
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$OcrAssets = Join-Path $Root "assets\MaaCommonAssets\OCR"

if (-not (Test-Path -LiteralPath $OcrAssets)) {
    $Git = Get-Command git -ErrorAction Stop
    $GitRoot = Split-Path -Parent (Split-Path -Parent $Git.Source)
    $env:PATH = "$(Join-Path $GitRoot 'usr\bin');$(Join-Path $GitRoot 'mingw64\bin');$env:PATH"
    & $Git.Source -C $Root submodule update --init --depth 1 assets/MaaCommonAssets
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($Clean -and (Test-Path -LiteralPath $Venv)) {
    Remove-Item -LiteralPath $Venv -Recurse -Force
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $Python = Get-Command python -ErrorAction Stop
    & $Python.Source -m venv $Venv
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $Root "agent\requirements-dev.txt")
& $VenvPython -m pip install -r (Join-Path $Root "tools\requirements.txt")

if (-not $SkipNode) {
    $Npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($null -ne $Npm) {
        Push-Location $Root
        try {
            & $Npm.Source ci
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Warning "npm not found; Maa resource checker dependencies were not installed."
    }
}

Write-Host "MA9 development environment is ready: $VenvPython"
Write-Host "Open assets/interface.json in MFA/Maa Pipeline Support to use the project Agent."
