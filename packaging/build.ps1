# Builds dist\Mise\Mise.exe, then the installer if Inno Setup is installed.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)
.venv\Scripts\pip install -q pyinstaller
.venv\Scripts\python packaging\make_icon.py
.venv\Scripts\pyinstaller --noconfirm --clean --distpath dist --workpath build packaging\studio_hub.spec
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) { & $iscc packaging\installer.iss } else { Write-Host "Inno Setup 6 not found: skipped the installer. dist\Mise is ready to run." }
