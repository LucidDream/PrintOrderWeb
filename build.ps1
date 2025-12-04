# PrintOrderWeb Build Script
# Run this script to create a production build
#
# Usage: .\build.ps1
#
# Prerequisites:
# - Python 3.11+ with virtual environment activated
# - PyInstaller installed: pip install pyinstaller
# - ConsumableClient.dll in ../CCAPIv2.0.0.2/

param(
    [switch]$Clean = $false,
    [switch]$SkipBuild = $false
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PrintOrderWeb Production Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment is activated
if (-not $env:VIRTUAL_ENV) {
    Write-Host "[WARNING] Virtual environment not activated" -ForegroundColor Yellow
    Write-Host "Activating .venv..." -ForegroundColor Yellow
    & .\.venv\Scripts\Activate.ps1
}

# Check for required files
Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Green

$dllPath = "..\CCAPIv2.0.0.2\ConsumableClient.dll"
if (-not (Test-Path $dllPath)) {
    Write-Host "[ERROR] ConsumableClient.dll not found at: $dllPath" -ForegroundColor Red
    exit 1
}
Write-Host "  - ConsumableClient.dll: Found" -ForegroundColor Gray

if (-not (Test-Path ".env.production")) {
    Write-Host "[ERROR] .env.production not found" -ForegroundColor Red
    exit 1
}
Write-Host "  - .env.production: Found" -ForegroundColor Gray

if (-not (Test-Path "docs\README_TESTER.md")) {
    Write-Host "[WARNING] docs\README_TESTER.md not found" -ForegroundColor Yellow
}
Write-Host "  - Documentation: Found" -ForegroundColor Gray

if (-not (Test-Path "sample_pdfs")) {
    Write-Host "[WARNING] sample_pdfs folder not found" -ForegroundColor Yellow
}
Write-Host "  - Sample PDFs: Found" -ForegroundColor Gray

# Clean previous builds
if ($Clean) {
    Write-Host ""
    Write-Host "[2/5] Cleaning previous builds..." -ForegroundColor Green
    if (Test-Path "build") {
        Remove-Item -Path "build" -Recurse -Force
        Write-Host "  - Removed build/" -ForegroundColor Gray
    }
    if (Test-Path "dist") {
        Remove-Item -Path "dist" -Recurse -Force
        Write-Host "  - Removed dist/" -ForegroundColor Gray
    }
} else {
    Write-Host ""
    Write-Host "[2/5] Skipping clean (use -Clean to remove previous builds)" -ForegroundColor Gray
}

# Run PyInstaller
if (-not $SkipBuild) {
    Write-Host ""
    Write-Host "[3/5] Running PyInstaller..." -ForegroundColor Green
    pyinstaller --clean --noconfirm print_order_web.spec

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] PyInstaller failed with exit code: $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "[3/5] Skipping build (use without -SkipBuild to run PyInstaller)" -ForegroundColor Gray
}

# Verify build output
Write-Host ""
Write-Host "[4/5] Verifying build output..." -ForegroundColor Green

$distFolder = "dist\PrintOrderWeb"
if (-not (Test-Path $distFolder)) {
    Write-Host "[ERROR] Build output not found at: $distFolder" -ForegroundColor Red
    exit 1
}

$requiredFiles = @(
    "PrintOrderWeb.exe",
    ".env",
    "_internal\ConsumableClient.dll",
    "_internal\templates",
    "_internal\static",
    "_internal\translations"
)

$allFound = $true
foreach ($file in $requiredFiles) {
    $fullPath = Join-Path $distFolder $file
    if (Test-Path $fullPath) {
        Write-Host "  - $file : Found" -ForegroundColor Gray
    } else {
        Write-Host "  - $file : MISSING" -ForegroundColor Red
        $allFound = $false
    }
}

# Check optional files
$optionalFiles = @(
    "README_TESTER.md",
    "TROUBLESHOOTING.md",
    "sample_pdfs"
)

foreach ($file in $optionalFiles) {
    $fullPath = Join-Path $distFolder $file
    if (Test-Path $fullPath) {
        Write-Host "  - $file : Found" -ForegroundColor Gray
    } else {
        Write-Host "  - $file : Not found (optional)" -ForegroundColor Yellow
    }
}

# Final summary
Write-Host ""
Write-Host "[5/5] Build Summary" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

if ($allFound) {
    $exeSize = (Get-Item "$distFolder\PrintOrderWeb.exe").Length / 1MB
    $totalSize = (Get-ChildItem $distFolder -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB

    Write-Host "Build completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Output location: $distFolder" -ForegroundColor White
    Write-Host "Executable size: $([math]::Round($exeSize, 2)) MB" -ForegroundColor White
    Write-Host "Total size: $([math]::Round($totalSize, 2)) MB" -ForegroundColor White
    Write-Host ""
    Write-Host "To create a ZIP for distribution:" -ForegroundColor Yellow
    Write-Host "  cd dist" -ForegroundColor Gray
    Write-Host "  Compress-Archive -Path PrintOrderWeb -DestinationPath PrintOrderWeb.zip" -ForegroundColor Gray
    Write-Host ""
    Write-Host "To test the build:" -ForegroundColor Yellow
    Write-Host "  .\dist\PrintOrderWeb\PrintOrderWeb.exe" -ForegroundColor Gray
} else {
    Write-Host "Build completed with warnings - some files missing" -ForegroundColor Yellow
}

Write-Host "========================================" -ForegroundColor Cyan
