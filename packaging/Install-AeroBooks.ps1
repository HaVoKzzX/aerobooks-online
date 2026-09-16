# Fallback installer if Inno Setup is not available.
# Right-click -> Run with PowerShell, or double-click Install AeroBooks.bat
# Copies dist\AeroBooks into Program Files and creates shortcuts.

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $script = $PSCommandPath
        Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$script`""
        )
        exit
    }
}

Assert-Admin

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root "dist\AeroBooks"
if (-not (Test-Path (Join-Path $source "AeroBooks.exe"))) {
    throw "Build output not found at $source. Run packaging\build_installer.ps1 first."
}

$dest = Join-Path $env:ProgramFiles "AeroBooks"
Write-Host "Installing AeroBooks to $dest"

if (Test-Path $dest) {
    Remove-Item -Recurse -Force $dest
}
New-Item -ItemType Directory -Path $dest | Out-Null
Copy-Item -Path (Join-Path $source "*") -Destination $dest -Recurse -Force

$exe = Join-Path $dest "AeroBooks.exe"
$w = New-Object -ComObject WScript.Shell

$startDir = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\AeroBooks"
New-Item -ItemType Directory -Path $startDir -Force | Out-Null
$sc = $w.CreateShortcut((Join-Path $startDir "AeroBooks.lnk"))
$sc.TargetPath = $exe
$sc.WorkingDirectory = $dest
$sc.Description = "AeroBooks — CFI invoicing"
$sc.Save()

$desk = [Environment]::GetFolderPath("CommonDesktopDirectory")
$sc2 = $w.CreateShortcut((Join-Path $desk "AeroBooks.lnk"))
$sc2.TargetPath = $exe
$sc2.WorkingDirectory = $dest
$sc2.Description = "AeroBooks — CFI invoicing"
$sc2.Save()

$uninst = Join-Path $dest "Uninstall-AeroBooks.ps1"
@"
#Requires -Version 5.1
`$id = [Security.Principal.WindowsIdentity]::GetCurrent()
`$p = New-Object Security.Principal.WindowsPrincipal(`$id)
if (-not `$p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File',"`$PSCommandPath"
    exit
}
Remove-Item -LiteralPath '$dest' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath '$startDir' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path '$desk' 'AeroBooks.lnk') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AeroBooks' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'AeroBooks removed. Your data in AppData\Local\AeroBooks was left in place.'
pause
"@ | Set-Content -Path $uninst -Encoding UTF8

$reg = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AeroBooks"
New-Item -Path $reg -Force | Out-Null
New-ItemProperty -Path $reg -Name DisplayName -Value "AeroBooks" -Force | Out-Null
New-ItemProperty -Path $reg -Name DisplayVersion -Value "1.1.0" -Force | Out-Null
New-ItemProperty -Path $reg -Name Publisher -Value "AeroBooks" -Force | Out-Null
New-ItemProperty -Path $reg -Name InstallLocation -Value $dest -Force | Out-Null
New-ItemProperty -Path $reg -Name DisplayIcon -Value $exe -Force | Out-Null
New-ItemProperty -Path $reg -Name UninstallString -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninst`"" -Force | Out-Null
New-ItemProperty -Path $reg -Name NoModify -PropertyType DWord -Value 1 -Force | Out-Null

Write-Host ""
Write-Host "Installed. Data stays in $env:LOCALAPPDATA\AeroBooks"
Write-Host "Backups: $env:USERPROFILE\Documents\AeroBooks Backups"
Write-Host ""
Start-Process $exe
