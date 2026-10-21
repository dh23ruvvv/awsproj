# FlowPilot Seed Session Script
$ErrorActionPreference = "Stop"

$port = if ($env:FLOWPILOT_PORT) { $env:FLOWPILOT_PORT } else { "8000" }
$url = "http://localhost:$port/api/v1/sessions"

Write-Host "Creating seeded session at $url..." -ForegroundColor Cyan

try {
    $body = @{
        seed = $true
        demo_timestamp = "2026-10-22T09:00:00+05:30"
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $body
    Write-Host "`nSeeded session created successfully:" -ForegroundColor Green
    Write-Host "  Session ID:    $($response.session_id)" -ForegroundColor Cyan
    Write-Host "  State Version: $($response.state_version)" -ForegroundColor Cyan
    Write-Host "  Demo Timestamp: $($response.demo_timestamp)`n" -ForegroundColor Cyan
} catch {
    Write-Error "Failed to create seeded session. Make sure the server is running on port $port."
    exit 1
}
