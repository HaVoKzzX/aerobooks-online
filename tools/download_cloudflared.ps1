$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $here | Out-Null
$dest = Join-Path $here "cloudflared.exe"
$url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
Write-Host "Downloading cloudflared from GitHub..."
Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
if (-not (Test-Path $dest)) {
    throw "Download failed"
}
Write-Host "Saved $dest"
