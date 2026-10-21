# FlowPilot Development Environment Runner
$ErrorActionPreference = "Stop"

Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " Starting FlowPilot Development Environment..." -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan

# Start backend uvicorn process
$backend = Start-Process python -ArgumentList "-m", "uvicorn", "server.main:app", "--port", "8000", "--reload" -PassThru

# Start frontend vite process in frontend directory
$frontend = Start-Process npm -ArgumentList "run", "dev" -WorkingDirectory "frontend" -PassThru

Write-Host "`nBackend API:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend App: http://localhost:5173" -ForegroundColor Green
Write-Host "`nPress Ctrl+C to stop both services...`n" -ForegroundColor Yellow

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
}
