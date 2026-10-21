# scripts/contract_check.ps1
# Export OpenAPI schema and verify frontend TypeScript types match

$ErrorActionPreference = "Stop"

Write-Host "Exporting OpenAPI schema..."
python server/export_openapi.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to export OpenAPI schema"
    exit 1
}

$typesFile = "frontend/src/api/types.ts"
$checkFile = "frontend/src/api/types.ts.check"

if (Test-Path $typesFile) {
    Write-Host "Checking generated types against $typesFile..."
    npx -y openapi-typescript generated/openapi.json -o $checkFile
    if ($LASTEXITCODE -ne 0) {
        Write-Error "openapi-typescript generation failed"
        if (Test-Path $checkFile) { Remove-Item $checkFile }
        exit 1
    }

    git diff --no-index $typesFile $checkFile
    $diffResult = $LASTEXITCODE
    if (Test-Path $checkFile) { Remove-Item $checkFile }

    if ($diffResult -ne 0) {
        Write-Error "Contract check failed: frontend/src/api/types.ts has drifted from generated/openapi.json"
        exit 1
    }
    Write-Host "Contract check passed: types are in sync."
} else {
    Write-Host "Notice: $typesFile not found yet (will be generated in TASK-014). OpenAPI schema exported successfully."
}

exit 0
