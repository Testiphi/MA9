[CmdletBinding()]
param(
    [string]$Version = "v0.0.0-local"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Mfa = Join-Path $Root "build\mfa"
$Install = Join-Path $Root "install"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Run tools/setup_dev.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $Root "deps\bin"))) {
    throw "Missing MaaFramework runtime in deps/. Run tools/prepare_release_deps.ps1 first."
}
if (-not (Test-Path -LiteralPath $Mfa)) {
    throw "Missing MFAAvalonia files. Run tools/prepare_release_deps.ps1 first."
}

& $Python (Join-Path $Root "tools\build_agent.py") --clean
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python (Join-Path $Root "tools\build_selection_gui.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$RootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
$InstallFull = [System.IO.Path]::GetFullPath($Install)
if (-not $InstallFull.StartsWith("$RootFull\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace unexpected install path: $InstallFull"
}
if (Test-Path -LiteralPath $InstallFull) {
    Remove-Item -LiteralPath $InstallFull -Recurse -Force
}
New-Item -ItemType Directory -Path $Install -Force | Out-Null
Copy-Item -Path (Join-Path $Mfa "*") -Destination $Install -Recurse -Force

Push-Location $Root
try {
    & $Python "tools\install.py" $Version win x86_64
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

Write-Host "Windows package assembled in $Install"
