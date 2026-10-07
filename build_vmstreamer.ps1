$ErrorActionPreference = "Stop"

$projectDir = $PSScriptRoot
$python = Join-Path $projectDir ".venv\Scripts\python.exe"
$entryPoint = Join-Path $projectDir "vmstreamer_launcher.py"
$icon = Join-Path $projectDir "vmstreamer.ico"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Could not find the project's virtual environment at $python. Run this build script from the VMStreamer project folder that contains .venv."
}

if (-not (Test-Path -LiteralPath $entryPoint)) {
    throw "Could not find vmstreamer_launcher.py beside this build script."
}

if (-not (Test-Path -LiteralPath $icon)) {
    throw "Could not find the VMStreamer icon at $icon."
}

$null = & $python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)"
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller could not be installed into the VMStreamer virtual environment."
    }
}

Push-Location $projectDir
try {
    & $python -m PyInstaller `
        --clean `
        --noconfirm `
        --onefile `
        --windowed `
        --name VMStreamer `
        --icon $icon `
        --add-data "$icon;." `
        --collect-all PySide6 `
        --collect-all pycaw `
        --collect-all comtypes `
        --collect-all voicemeeterlib `
        --collect-all winappaudiorouter `
        $entryPoint

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build VMStreamer.exe."
    }
}
finally {
    Pop-Location
}

Write-Host "Built: $(Join-Path $projectDir 'dist\VMStreamer.exe')"