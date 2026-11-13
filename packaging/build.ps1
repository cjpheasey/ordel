# Builds dist\Ordel\Ordel.exe, then the installer if Inno Setup is installed.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)
# Tools are run through python -m: the .exe launchers in .venv\Scripts break if the project folder is moved or renamed.
.venv\Scripts\python -m pip install -q pyinstaller
.venv\Scripts\python packaging\make_icon.py
.venv\Scripts\python -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\studio_hub.spec
# Never package a half-built app (e.g. dist\Ordel locked because Ordel is running from it).
if ($LASTEXITCODE) { Write-Host "App build failed (is Ordel running from dist\Ordel?): no installer made."; exit $LASTEXITCODE }
# Inno Setup 7 or 6, wherever it was installed (Program Files, either kind, or a per-user install).
$iscc = @("${env:ProgramFiles}", "${env:ProgramFiles(x86)}", "$env:LOCALAPPDATA\Programs") |
    ForEach-Object { "$_\Inno Setup 7\ISCC.exe"; "$_\Inno Setup 6\ISCC.exe" } |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) { & $iscc packaging\installer.iss } else { Write-Host "Inno Setup not found: skipped the installer. dist\Ordel is ready to run." }
