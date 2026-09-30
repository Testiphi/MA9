# ============================================================================
# 05AN-N  tools/build_host_witness.ps1
#
# Offline build for the host frame-witness prototype. Uses ONLY the MSVC that is
# already installed (vswhere lookup) -- it never installs a compiler or any
# dependency, never calls LoadLibrary, never touches MFA, and never copies the
# produced artifacts into a plugins directory, deps/, .venv/ or install/.
#
# Outputs (all under -OutDir, default <repo>/MA9-evidence/20260930-05AN-N/build):
#     host_witness.dll            plugin prototype (pe-inspected only, never loaded)
#     test_host_witness_core.exe  fake-backend suite, runs with no device
#     dumpbin_exports.txt / dumpbin_dependents.txt
#     build_host_witness.log      full transcript
#
# Usage:
#   pwsh -File tools/build_host_witness.ps1
#   pwsh -File tools/build_host_witness.ps1 -OutDir <dir> -RunTests
# ============================================================================

[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$OutDir = '',
    [string]$MaaPluginInclude = '',
    [string]$FixtureDir = '',
    [switch]$RunTests,
    [switch]$EmitFixture,
    [switch]$SkipDumpbin
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- paths
if (-not $RepoRoot) {
    # this script lives in <repo>/tools/
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
$SrcDir = Join-Path $RepoRoot 'MA9-worktrees/duel-scan/agent/native/host_witness'
if (-not (Test-Path $SrcDir)) {
    $SrcDir = Join-Path $RepoRoot 'agent/native/host_witness'
}
if (-not $OutDir) {
    $OutDir = Join-Path $RepoRoot 'MA9-evidence/20260930-05AN-N/build'
}
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$ObjDir = Join-Path $OutDir 'obj'
if (-not (Test-Path $ObjDir)) { New-Item -ItemType Directory -Path $ObjDir -Force | Out-Null }

$LogPath = Join-Path $OutDir 'build_host_witness.log'
# Truncate in place rather than delete: on this machine a delete can be routed
# through the OS trash and fail closed, which would abort the build. Never
# Remove-Item an artifact this script owns.
Set-Content -Path $LogPath -Value '' -Encoding UTF8

function Log([string]$m) {
    $line = "$m"
    Write-Host $line
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}
function LogRaw([string]$m) { Add-Content -Path $LogPath -Value $m -Encoding UTF8 }

Log "05AN-N build_host_witness"
Log "repo_root = $RepoRoot"
Log "src_dir   = $SrcDir"
Log "out_dir   = $OutDir"
Log "timestamp = $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK')"

# ---------------------------------------------------------------- sources
$CoreSrc = Join-Path $SrcDir 'host_witness_core.cpp'
$PluginSrc = Join-Path $SrcDir 'host_witness.cpp'
$TestSrc = Join-Path $SrcDir 'tests/test_host_witness_core.cpp'
foreach ($f in @($CoreSrc, $PluginSrc, $TestSrc)) {
    if (-not (Test-Path $f)) { throw "missing source: $f" }
    Log "source    = $f"
}

# ---------------------------------------------------------------- toolchain
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
if (-not (Test-Path $vswhere)) { throw "vswhere not found: $vswhere (no compiler; deliver source only)" }
$vsPath = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsPath) { throw "no MSVC x64 toolset found via vswhere" }
$vsPath = $vsPath.Trim()
Log "vs_install = $vsPath"

$msvcRoot = Get-ChildItem (Join-Path $vsPath 'VC/Tools/MSVC') -Directory |
    Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $msvcRoot) { throw "no MSVC toolset directory" }
$msvc = $msvcRoot.FullName
Log "msvc       = $msvc"

$sdkRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits/10'
$sdkVer = Get-ChildItem (Join-Path $sdkRoot 'Include') -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'ucrt') } |
    Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $sdkVer) { throw "no Windows SDK with ucrt" }
$sdk = $sdkVer.FullName
Log "sdk        = $sdk"

$cl = Join-Path $msvc 'bin/Hostx64/x64/cl.exe'
$dumpbin = Join-Path $msvc 'bin/Hostx64/x64/dumpbin.exe'
if (-not (Test-Path $cl)) { throw "cl.exe missing: $cl" }

$sdkLibRoot = Join-Path $sdkRoot ('Lib/' + $sdkVer.Name)
$sdkBinRoot = Join-Path $sdkRoot ('bin/' + $sdkVer.Name + '/x64')
$msvcBin = Join-Path $msvc 'bin/Hostx64/x64'
$env:INCLUDE = "$msvc\include;$sdk\ucrt;$sdk\um;$sdk\shared;$sdk\winrt"
$env:LIB = "$msvc\lib\x64;$sdkLibRoot\ucrt\x64;$sdkLibRoot\um\x64"
$env:Path = "$msvcBin;$sdkBinRoot;$env:Path"
$env:_CL_ = ''
$env:_LINK_ = ''

# ---------------------------------------------------------------- official plugin header
$headerArg = @()
$hwRoot = Join-Path $RepoRoot '3rdparty/include'
if (-not (Test-Path (Join-Path $hwRoot 'MaaPlugin/MaaPluginAPI.h'))) {
    $hwRoot = Join-Path $RepoRoot 'MA9-evidence/20260930-05AN-H/official-src/3rdparty/include'
}
if ($MaaPluginInclude) { $hwRoot = $MaaPluginInclude }
if (Test-Path (Join-Path $hwRoot 'MaaPlugin/MaaPluginAPI.h')) {
    $headerArg = @('-DHOST_WITNESS_HAVE_MAA_PLUGIN_HEADER=1', "-I$hwRoot")
    Log "maa_plugin_header = $hwRoot (official header used)"
}
else {
    Log "maa_plugin_header = (absent; plugin self-declares the same 3 exports)"
}

# NOTE: the produced DLL is NOT bit-reproducible. Two builds of byte-identical
# inputs differ in 49 bytes, dominated by the COFF time-date stamp, and `/Brepro`
# (compiler and linker, both forms) does not remove it on this toolchain. The
# artifact hash must therefore be taken from the DELIVERED binary; it cannot be
# re-derived by rebuilding. See the N1 report for the measurement.
$common = @('-nologo', '-std:c++17', '-MT', '-EHsc', '-W4', '-O2', '-utf-8', '-DWIN32_LEAN_AND_MEAN')

# ---------------------------------------------------------------- build test exe
$testExe = Join-Path $OutDir 'test_host_witness_core.exe'
$coreObj = Join-Path $ObjDir 'core_for_tests.obj'
$testObj = Join-Path $ObjDir 'tests.obj'

Log ''
Log '--- compile core (for tests) ---'
$args1 = $common + @('-c', "-I$SrcDir", "-Fo$coreObj", $CoreSrc)
Log "cl $($args1 -join ' ')"
$out = & $cl @args1 2>&1
$out | ForEach-Object { LogRaw $_ }
$code = $LASTEXITCODE
Log "exit=$code"
if ($code -ne 0) { throw "core compile failed (exit $code)" }

Log '--- compile tests ---'
$args2 = $common + @('-c', "-I$SrcDir", "-Fo$testObj", $TestSrc)
Log "cl $($args2 -join ' ')"
$out = & $cl @args2 2>&1
$out | ForEach-Object { LogRaw $_ }
$code = $LASTEXITCODE
Log "exit=$code"
if ($code -ne 0) { throw "test compile failed (exit $code)" }

Log '--- link test exe ---'
$args3 = @('-nologo', "-Fe$testExe", $coreObj, $testObj)
Log "cl $($args3 -join ' ')"
$out = & $cl @args3 2>&1
$out | ForEach-Object { LogRaw $_ }
$code = $LASTEXITCODE
Log "exit=$code"
if ($code -ne 0) { throw "test link failed (exit $code)" }

# ---------------------------------------------------------------- build plugin dll
$dll = Join-Path $OutDir 'host_witness.dll'
$pluginObj = Join-Path $ObjDir 'plugin.obj'
$coreObjDll = Join-Path $ObjDir 'core_for_dll.obj'

Log ''
Log '--- compile core (for dll) ---'
$args4 = $common + @('-c', "-I$SrcDir", "-Fo$coreObjDll", $CoreSrc)
Log "cl $($args4 -join ' ')"
$out = & $cl @args4 2>&1
$out | ForEach-Object { LogRaw $_ }
$code = $LASTEXITCODE
Log "exit=$code"
if ($code -ne 0) { throw "core(dll) compile failed (exit $code)" }

Log '--- compile plugin ---'
$args5 = $common + @('-c') + $headerArg + @("-I$SrcDir", "-Fo$pluginObj", $PluginSrc)
Log "cl $($args5 -join ' ')"
$out = & $cl @args5 2>&1
$out | ForEach-Object { LogRaw $_ }
$code = $LASTEXITCODE
Log "exit=$code"
if ($code -ne 0) { throw "plugin compile failed (exit $code)" }

Log '--- link plugin dll (advapi32 for the directory ACL only) ---'
$args6 = @('-nologo', '-LD', "-Fe$dll", $pluginObj, $coreObjDll, 'advapi32.lib')
Log "cl $($args6 -join ' ')"
$out = & $cl @args6 2>&1
$out | ForEach-Object { LogRaw $_ }
$code = $LASTEXITCODE
Log "exit=$code"
if ($code -ne 0) { throw "plugin link failed (exit $code)" }

# ---------------------------------------------------------------- PE static checks
$exportCheckOk = $true
$depCheckOk = $true
if (-not $SkipDumpbin) {
    if (-not (Test-Path $dumpbin)) { throw "dumpbin missing: $dumpbin" }

    Log ''
    Log '--- dumpbin /exports ---'
    $expTxt = Join-Path $OutDir 'dumpbin_exports.txt'
    & $dumpbin /nologo /exports $dll 2>&1 | Set-Content -Path $expTxt -Encoding UTF8
    Log "exit=$LASTEXITCODE  -> $expTxt"
    $expContent = Get-Content $expTxt -Raw
    LogRaw $expContent

    $need = @('GetApiVersion', 'GetPluginVersion', 'OnControllerEvent')
    $forbid = @('OnContextEvent', 'OnResourceEvent', 'OnTaskerEvent')
    # exported symbol lines look like:  "   1    0 00001234 GetApiVersion"
    $exported = @()
    foreach ($line in ($expContent -split "`r?`n")) {
        if ($line -match '^\s+\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]{8}\s+(\S+)\s*$') {
            $exported += $Matches[1]
        }
    }
    $exported = $exported | Sort-Object -Unique
    Log "exports_found = $($exported -join ',')"
    foreach ($n in $need) {
        if ($exported -notcontains $n) { $exportCheckOk = $false; Log "MISSING EXPORT: $n" }
    }
    foreach ($n in $forbid) {
        if ($exported -contains $n) { $exportCheckOk = $false; Log "FORBIDDEN EXPORT PRESENT: $n" }
    }
    if ($exported.Count -ne 3) { $exportCheckOk = $false; Log "EXPORT COUNT != 3 ($($exported.Count))" }
    Log "export_check = $(if ($exportCheckOk) { 'PASS' } else { 'FAIL' })"

    Log ''
    Log '--- dumpbin /dependents ---'
    $depTxt = Join-Path $OutDir 'dumpbin_dependents.txt'
    & $dumpbin /nologo /dependents $dll 2>&1 | Set-Content -Path $depTxt -Encoding UTF8
    Log "exit=$LASTEXITCODE  -> $depTxt"
    $depContent = Get-Content $depTxt -Raw
    LogRaw $depContent

    # a dynamically linked CRT would be an avoidable dependency surface
    $badDeps = @('MSVCP140', 'VCRUNTIME140', 'ucrtbase', 'MSVCR')
    foreach ($b in $badDeps) {
        if ($depContent -match [regex]::Escape($b)) { $depCheckOk = $false; Log "DYNAMIC CRT DEPENDENCY: $b" }
    }
    if ($depContent -notmatch 'KERNEL32\.dll') { $depCheckOk = $false; Log "KERNEL32.dll missing from dependents" }
    Log "dependent_check = $(if ($depCheckOk) { 'PASS' } else { 'FAIL' })"
}

# ---------------------------------------------------------------- run tests
$testExit = $null
if ($RunTests) {
    Log ''
    Log '--- run test_host_witness_core.exe (no device, no MFA, no Maa DLL) ---'
    $testLog = Join-Path $OutDir 'test_host_witness_core.log'
    $testOut = & $testExe 2>&1
    $testExit = $LASTEXITCODE
    $testOut | Set-Content -Path $testLog -Encoding UTF8
    Log "test_exit=$testExit"
    foreach ($l in $testOut) { LogRaw $l }
}

# ---------------------------------------------------------------- emit fixture
$fixtureExit = $null
if ($EmitFixture) {
    if (-not $FixtureDir) {
        $FixtureDir = Join-Path $RepoRoot 'MA9-evidence/20260930-05AN-N1-fixture'
    }
    Log ''
    Log "--- emit fixture (fake backends, real core serializers) -> $FixtureDir ---"
    if (-not (Test-Path $FixtureDir)) { New-Item -ItemType Directory -Path $FixtureDir -Force | Out-Null }
    $fixLog = Join-Path $OutDir 'fixture_emit.log'
    $fixOut = & $testExe '--emit-fixture' $FixtureDir 2>&1
    $fixtureExit = $LASTEXITCODE
    $fixOut | Set-Content -Path $fixLog -Encoding UTF8
    Log "fixture_exit=$fixtureExit"
    foreach ($l in $fixOut) { LogRaw $l }
    # static confirmation that no plugin/Maa binary was involved
    $stray = Get-ChildItem -Path $FixtureDir -Recurse -Filter '*.dll' -ErrorAction SilentlyContinue
    if ($stray) {
        Log "UNEXPECTED DLL under fixture dir: $($stray.FullName -join ',')"
        $fixtureExit = 9
    }
}

# ---------------------------------------------------------------- summary
Log ''
Log '--- summary ---'
foreach ($f in @($dll, $testExe)) {
    if (Test-Path $f) {
        $h = (Get-FileHash $f -Algorithm SHA256).Hash.ToLower()
        $sz = (Get-Item $f).Length
        Log "artifact = $f  size=$sz  sha256=$h"
    }
}
Log "export_check=$exportCheckOk dependent_check=$depCheckOk test_exit=$testExit fixture_exit=$fixtureExit"

if (-not $headerArg) { Log 'note: built WITHOUT the official plugin header (self-declared exports)' }
if (-not $exportCheckOk -or -not $depCheckOk) { exit 2 }
if ($RunTests -and $testExit -ne 0) { exit 3 }
if ($EmitFixture -and $fixtureExit -ne 0) { exit 4 }
exit 0
