# Build the Windows GUI exe and package it with offsets.toml and config.json.
#
# Usage:
#   ./scripts/build-exe.ps1
#
# Works with normal CPython and with Python builds that ship Tcl 9 inside zip
# files (for example Python 3.14+), where PyInstaller needs the Tcl/Tk data
# added explicitly.

param(
    [string]$Name = "FM24CAGrowth",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$excludes = @(
    "unittest",
    "doctest",
    "pydoc",
    "pydoc_data",
    "test",
    "ensurepip",
    "pip",
    "setuptools",
    "pkg_resources",
    "email",
    "http",
    "urllib",
    "xml",
    "multiprocessing",
    "concurrent",
    "asyncio",
    "sqlite3",
    "decimal",
    "ssl",
    "_ssl",
    "hashlib",
    "_hashlib",
    "secrets",
    "bz2",
    "lzma",
    "_bz2",
    "_lzma"
)

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm", "--clean",
    "--onefile", "--windowed",
    "--collect-submodules", "pymem"
)
foreach ($module in $excludes) {
    $arguments += @("--exclude-module", $module)
}

# Python 3.14+ can report Tcl 9 from a zipfs path such as
# //zipfs:/lib/tcl/tcl_library. PyInstaller cannot find the data there, so
# extract the bundled zips and pass them to --add-data.
$tclLibrary = & $Python -c "import tkinter; print(tkinter.Tcl().eval('info library'))"
if ($tclLibrary -like "//zipfs:*") {
    $pythonRoot = Split-Path -Parent (& $Python -c "import sys; print(sys.executable)")
    $tclRoot = Join-Path $pythonRoot "tcl"
    $zipTcl = Get-ChildItem -Path $tclRoot -Filter "libtcl*.zip" | Select-Object -First 1
    $zipTk = Get-ChildItem -Path $tclRoot -Filter "libtk*.zip" | Select-Object -First 1
    if (-not $zipTcl -or -not $zipTk) {
        throw "Cannot find libtcl*.zip or libtk*.zip in $tclRoot"
    }

    $extract = Join-Path $env:TEMP "fm24-tcl-data"
    if (Test-Path $extract) {
        Remove-Item -Recurse -Force $extract
    }
    New-Item -ItemType Directory -Path $extract | Out-Null
    Expand-Archive -Path $zipTcl.FullName -DestinationPath $extract
    Expand-Archive -Path $zipTk.FullName -DestinationPath $extract

    $arguments += @(
        "--add-data", "$extract\tcl_library;_tcl_data",
        "--add-data", "$extract\tk_library;_tk_data"
    )
}

$arguments += @(
    "--name", $Name,
    "src\fm24_ca_growth_gui.pyw"
)

& $Python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Copy-Item "src\offsets.toml" "dist\offsets.toml" -Force
Copy-Item "src\config.json" "dist\config.json" -Force
Compress-Archive `
    -Path "dist\$Name.exe", "dist\offsets.toml", "dist\config.json" `
    -DestinationPath "dist\$Name-windows.zip" `
    -Force

Write-Host "Built dist\$Name.exe and dist\$Name-windows.zip"
