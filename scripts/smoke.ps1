# FlowPilot Golden Smoke Test Runner
$ErrorActionPreference = "Stop"

Write-Host "`n===============================================" -ForegroundColor Cyan
Write-Host " Running FlowPilot Golden Smoke Test..." -ForegroundColor Cyan
Write-Host "===============================================`n" -ForegroundColor Cyan

# Let pytest allocate a fresh temporary directory on each run. A fixed Windows
# basetemp can retain permissions from an earlier sandbox or another process.
python -m pytest tests/test_golden_smoke.py -v -p no:cacheprovider
if ($LASTEXITCODE -ne 0) {
    Write-Error "Golden Smoke Test FAILED"
    exit 1
}

Write-Host "`nGolden Smoke Test PASSED cleanly!`n" -ForegroundColor Green
exit 0
