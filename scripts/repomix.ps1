# Pack the repo with Repomix, skipping Windows-locked pytest temp dirs
# (.test-tmp-*) that cause: Permission denied while scanning directory.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $env:TEMP 'flowpilot-repomix'
$outputName = 'repomix-output.xml'

if (Test-Path $stage) {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Path $stage | Out-Null

$sourceDirs = @(
    'server',
    'frontend',
    'tests',
    'docs',
    'scripts',
    'generated',
    '.internal'
)

$excludeDirs = @(
    'node_modules',
    'dist',
    '.vite',
    '__pycache__',
    '.pytest_cache'
)

foreach ($dir in $sourceDirs) {
    $from = Join-Path $root $dir
    if (-not (Test-Path -LiteralPath $from)) { continue }
    $to = Join-Path $stage $dir
    & robocopy $from $to /E /NFL /NDL /NJH /NJS /nc /ns /np /XD @excludeDirs | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed copying $dir (exit $LASTEXITCODE)"
    }
}

$rootFiles = @(
    '.env.example',
    '.gitignore',
    'LICENSE',
    'package.json',
    'README.md',
    'requirements.txt',
    'requirements-dev.txt',
    'REVIEW_STATUS.md',
    'repomix.config.json'
)
foreach ($file in $rootFiles) {
    $from = Join-Path $root $file
    if (Test-Path -LiteralPath $from) {
        Copy-Item -LiteralPath $from -Destination (Join-Path $stage $file) -Force
    }
}

Push-Location $stage
try {
    npx --yes repomix
    if ($LASTEXITCODE -ne 0) {
        throw "repomix failed with exit code $LASTEXITCODE"
    }
    Copy-Item -LiteralPath (Join-Path $stage $outputName) -Destination (Join-Path $root $outputName) -Force
}
finally {
    Pop-Location
}

Write-Host "Packed to $(Join-Path $root $outputName)" -ForegroundColor Green
