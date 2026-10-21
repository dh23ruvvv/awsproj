# FlowPilot Development Environment Runner
$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " Starting FlowPilot Development Environment..." -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

$rootDir = Split-Path -Parent $PSScriptRoot
if (-not $rootDir) { $rootDir = (Get-Location).Path }
$frontendDir = Join-Path $rootDir "frontend"

# Start backend uvicorn process
$backend = Start-Process python -ArgumentList "-m", "uvicorn", "server.main:app", "--port", "8000", "--reload" -WorkingDirectory $rootDir -PassThru

# Start frontend vite process via cmd.exe for Windows npm batch compatibility
$frontend = Start-Process cmd.exe -ArgumentList "/c", "npm", "run", "dev" -WorkingDirectory $frontendDir -PassThru

Write-Host "`nBackend API:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend App: http://localhost:5173" -ForegroundColor Green
Write-Host "`nPress Ctrl+C to stop both services...`n" -ForegroundColor Yellow

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
}
