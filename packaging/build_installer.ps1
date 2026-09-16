# Build AeroBooks.exe (Python + all libraries bundled) and a Windows installer.
# Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv (Join-Path $Root ".venv")
}

Write-Host "Installing / updating build tools..."
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $Root "requirements.txt")
& $venvPython -m pip install pyinstaller

Write-Host "Building icon..."
& $venvPython (Join-Path $Root "packaging\make_icon.py")

Write-Host "Packaging AeroBooks (this takes a few minutes)..."
$pyinstaller = Join-Path $Root ".venv\Scripts\pyinstaller.exe"
& $pyinstaller --noconfirm --clean (Join-Path $Root "packaging\AeroBooks.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $Root "dist\AeroBooks\AeroBooks.exe"
if (-not (Test-Path $exe)) { throw "AeroBooks.exe was not produced" }

Copy-Item (Join-Path $Root "packaging\aerobooks.ico") (Join-Path $Root "dist\AeroBooks\aerobooks.ico") -Force
if (Test-Path (Join-Path $Root "packaging\aerobooks-setup.ico")) {
    Copy-Item (Join-Path $Root "packaging\aerobooks-setup.ico") (Join-Path $Root "dist\AeroBooks\aerobooks-setup.ico") -Force
}
Copy-Item (Join-Path $Root "README.md") (Join-Path $Root "dist\AeroBooks\README.md") -Force

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Write-Host "Inno Setup not found — attempting winget install..."
    try {
        winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
        $iscc = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    } catch {
        Write-Host "winget could not install Inno Setup."
    }
}

New-Item -ItemType Directory -Path (Join-Path $Root "installer") -Force | Out-Null

if ($iscc) {
    Write-Host "Building AeroBooks-Setup.exe with Inno Setup..."
    & $iscc (Join-Path $Root "packaging\AeroBooks.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compile failed" }
    $setup = Join-Path $Root "installer\AeroBooks-Setup.exe"
    if (Test-Path $setup) {
        Copy-Item $setup (Join-Path $env:USERPROFILE "Desktop\AeroBooks-Setup.exe") -Force
        Write-Host "Installer: $setup"
        Write-Host "Copied to Desktop as AeroBooks-Setup.exe"
    }
} else {
    Write-Host "Inno Setup is not installed. Creating a zip + PowerShell installer instead."
    $zip = Join-Path $Root "installer\AeroBooks-Portable.zip"
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $Root "dist\AeroBooks\*") -DestinationPath $zip
    Copy-Item (Join-Path $Root "packaging\Install-AeroBooks.ps1") (Join-Path $Root "installer\Install-AeroBooks.ps1") -Force
    $bat = @"
@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\packaging\Install-AeroBooks.ps1"
"@
    Set-Content -Path (Join-Path $Root "installer\Install AeroBooks.bat") -Value $bat -Encoding ASCII
    Write-Host "Portable zip: $zip"
    Write-Host "To install into Program Files, right-click installer\Install AeroBooks.bat and Run as administrator."
}

Write-Host "Done."
