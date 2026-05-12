$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$workspaceRoot = Split-Path -Parent $projectRoot
$toolsRoot = Join-Path $workspaceRoot "tools"
$archivePath = Join-Path $toolsRoot "ffmpeg-master-latest-win64-gpl.zip"
$extractRoot = Join-Path $toolsRoot "ffmpeg"
$downloadUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

New-Item -ItemType Directory -Force -Path $toolsRoot | Out-Null

Write-Host "Downloading ffmpeg from GitHub..." -ForegroundColor Green
Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath

if (Test-Path $extractRoot) {
    Remove-Item -LiteralPath $extractRoot -Recurse -Force
}

Write-Host "Extracting ffmpeg..." -ForegroundColor Green
Expand-Archive -LiteralPath $archivePath -DestinationPath $extractRoot -Force

$ffmpeg = Get-ChildItem -Path $extractRoot -Recurse -Filter ffmpeg.exe | Select-Object -First 1
if (-not $ffmpeg) {
    throw "ffmpeg.exe was not found after extracting $archivePath"
}

Write-Host "ffmpeg installed at: $($ffmpeg.FullName)" -ForegroundColor Green
Write-Host "Restart Demo1 with start_demo1_web.ps1, or set FFMPEG_BINARY to this path for the current process." -ForegroundColor Yellow
