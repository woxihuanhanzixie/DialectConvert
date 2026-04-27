$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $projectRoot
$projectEnv = Join-Path $projectRoot ".env"
$workspaceEnv = Join-Path $workspaceRoot ".env"

Write-Host "Starting Demo1 web demo with conda env fireredasr2s..." -ForegroundColor Green

if (!(Test-Path $projectEnv) -and !(Test-Path $workspaceEnv)) {
    Write-Warning "No .env file found in project or workspace root. TTS/OpenAI-style APIs may fail until you copy .env.example to .env and fill in the keys."
}

# Ensure ffmpeg is discoverable for microphone/upload formats like webm/mp3/m4a.
$ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpegCmd) {
    $wingetFfmpeg = "C:\Users\34005\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin"
    if (Test-Path (Join-Path $wingetFfmpeg "ffmpeg.exe")) {
        $env:Path = "$wingetFfmpeg;$env:Path"
        Write-Host "ffmpeg added to PATH from WinGet package directory." -ForegroundColor Yellow
    } else {
        Write-Warning "ffmpeg is not found. Non-wav uploads/recordings may fail conversion."
    }
}

Write-Host "OpenVoice uses the current conda Python by default. Set OPENVOICE_PYTHON only when you really need a separate interpreter." -ForegroundColor Yellow
conda run -n fireredasr2s python -m web_demo.app
