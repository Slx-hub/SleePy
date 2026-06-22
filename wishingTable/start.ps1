# Run the WishingTable download server (manually — no autostart)
# Usage: .\start.ps1

Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# Auto-setup if venv doesn't exist
if (-not (Test-Path $venvPython)) {
    Write-Host "Setting up virtual environment..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create venv" -ForegroundColor Red
        exit 1
    }
    Write-Host "Installing requirements..."
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install requirements" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Starting WishingTable server on http://127.0.0.1:5001" -ForegroundColor Green
& $venvPython -m uvicorn server:app --host 127.0.0.1 --port 5001
