$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$taskIscc = 'C:\Users\DELL Pro\AppData\Local\Programs\Inno Setup 6\ISCC.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create .venv and install requirements-desktop.txt first.' }
if (-not (Test-Path -LiteralPath $taskIscc)) { throw 'Install Inno Setup 6 first.' }
foreach ($taskTool in @('ffmpeg','ffprobe','node')) {
    if (-not (Get-Command $taskTool -ErrorAction SilentlyContinue)) { throw "Missing $taskTool" }
}
& $taskPython -m PyInstaller --noconfirm --clean --onefile --console --name LoqtaWorker --collect-data yt_dlp_ejs --distpath dist worker.py
if ($LASTEXITCODE -ne 0) { throw 'Worker build failed.' }
& $taskPython -m PyInstaller --noconfirm --clean --onedir --windowed --name Loqta --collect-all webview --add-data 'templates;templates' --add-data 'static;static' --distpath dist desktop.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
$taskOutput = Join-Path $PSScriptRoot 'dist\Loqta'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'dist\LoqtaWorker.exe') -Destination (Join-Path $taskOutput 'LoqtaWorker.exe') -Force
$taskTools = Join-Path $taskOutput 'tools'
New-Item -ItemType Directory -Path $taskTools -Force | Out-Null
foreach ($taskTool in @('ffmpeg','ffprobe','node')) {
    $taskSource = (Get-Command $taskTool).Source
    Copy-Item -LiteralPath $taskSource -Destination (Join-Path $taskTools "$taskTool.exe") -Force
}
& $taskIscc (Join-Path $PSScriptRoot 'installer.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
Write-Host (Join-Path $PSScriptRoot 'release\Loqta-Setup-1.0.0.exe')
