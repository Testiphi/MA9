[CmdletBinding()]
param(
    [string]$MaaFrameworkVersion = "v5.13.0",
    [string]$MFAAvaloniaVersion = "v2.12.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Downloads = Join-Path $Root "build\downloads"
$MfaDestination = Join-Path $Root "build\mfa"
$Headers = @{ "User-Agent" = "MA9-build-script" }

function Get-ReleaseAsset {
    param(
        [string]$Repository,
        [string]$Version,
        [string]$NamePattern
    )

    $Release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/$Repository/releases/tags/$Version" `
        -Headers $Headers
    $Matches = @($Release.assets | Where-Object { $_.name -like $NamePattern })
    if ($Matches.Count -ne 1) {
        $Names = ($Release.assets.name -join ", ")
        throw "Expected one $Repository asset matching '$NamePattern', found $($Matches.Count). Available: $Names"
    }
    return $Matches[0]
}

function Save-And-ExpandAsset {
    param(
        [object]$Asset,
        [string]$Destination
    )

    New-Item -ItemType Directory -Path $Downloads -Force | Out-Null
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $Archive = Join-Path $Downloads $Asset.name
    Invoke-WebRequest -Uri $Asset.browser_download_url -Headers $Headers -OutFile $Archive
    Expand-Archive -LiteralPath $Archive -DestinationPath $Destination -Force
}

$MaaAsset = Get-ReleaseAsset `
    -Repository "MaaXYZ/MaaFramework" `
    -Version $MaaFrameworkVersion `
    -NamePattern "MAA-win-x86_64*.zip"
$MfaAsset = Get-ReleaseAsset `
    -Repository "MaaXYZ/MFAAvalonia" `
    -Version $MFAAvaloniaVersion `
    -NamePattern "MFAAvalonia-*-win-x64*.zip"

Save-And-ExpandAsset -Asset $MaaAsset -Destination (Join-Path $Root "deps")
Save-And-ExpandAsset -Asset $MfaAsset -Destination $MfaDestination

$BundledRuntime = Join-Path $MfaDestination "runtimes"
$MfaRoot = [System.IO.Path]::GetFullPath($MfaDestination).TrimEnd('\')
$RuntimeRoot = [System.IO.Path]::GetFullPath($BundledRuntime)
if (-not $RuntimeRoot.StartsWith("$MfaRoot\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove unexpected runtime path: $RuntimeRoot"
}
if (Test-Path -LiteralPath $RuntimeRoot) {
    Remove-Item -LiteralPath $RuntimeRoot -Recurse -Force
}

Write-Host "MaaFramework prepared in $(Join-Path $Root 'deps')"
Write-Host "MFAAvalonia prepared in $MfaDestination"
