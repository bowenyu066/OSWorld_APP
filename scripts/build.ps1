# OSWorld Annotator Kit Build Script
# This script packages the application into a standalone executable

param(
    [switch]$Clean = $false,
    [switch]$Debug = $false,
    [string]$OutputDir = "dist"
)

# Set error action preference
$ErrorActionPreference = "Stop"

Write-Host "🚀 OSWorld Annotator Kit Build Script" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DistDir = Join-Path $ProjectRoot $OutputDir

Write-Host "📁 Project Root: $ProjectRoot" -ForegroundColor Green
Write-Host "📦 Output Directory: $DistDir" -ForegroundColor Green

# Clean previous builds if requested
if ($Clean -or (Test-Path $DistDir)) {
    Write-Host "🧹 Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path $DistDir) {
        Remove-Item -Path $DistDir -Recurse -Force
        Write-Host "   ✓ Removed existing dist directory" -ForegroundColor Green
    }
}

# Create output directory
New-Item -ItemType Directory -Path $DistDir -Force | Out-Null

# Check if Python is available
try {
    $PythonVersion = python --version 2>&1
    Write-Host "🐍 Python Version: $PythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python and add it to PATH." -ForegroundColor Red
    exit 1
}

# Check if required packages are installed
Write-Host "📋 Checking required packages..." -ForegroundColor Yellow

$RequiredPackages = @("pyinstaller", "PySide6", "pydantic", "requests", "rich")
$MissingPackages = @()

foreach ($Package in $RequiredPackages) {
    try {
        python -c "import $($Package.ToLower())" 2>$null
        Write-Host "   ✓ $Package" -ForegroundColor Green
    } catch {
        $MissingPackages += $Package
        Write-Host "   ❌ $Package (missing)" -ForegroundColor Red
    }
}

if ($MissingPackages.Count -gt 0) {
    Write-Host "📦 Installing missing packages..." -ForegroundColor Yellow
    foreach ($Package in $MissingPackages) {
        Write-Host "   Installing $Package..." -ForegroundColor Cyan
        python -m pip install $Package
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Failed to install $Package" -ForegroundColor Red
            exit 1
        }
    }
}

# Create icon if it doesn't exist
$IconPath = Join-Path $ProjectRoot "assets\icon.ico"
if (-not (Test-Path $IconPath)) {
    Write-Host "🎨 Creating application icon..." -ForegroundColor Yellow
    $AssetsDir = Join-Path $ProjectRoot "assets"
    New-Item -ItemType Directory -Path $AssetsDir -Force | Out-Null
    
    # Create a simple icon (you can replace this with a proper icon file)
    Write-Host "   ⚠️  Using default icon (consider adding a custom icon.ico to assets/)" -ForegroundColor Yellow
}

# Prepare PyInstaller arguments
$PyInstallerArgs = @(
    "--noconsole"
    "--onefile"
    "--name", "AnnotatorKit"
    "--distpath", $DistDir
    "--workpath", (Join-Path $ProjectRoot "build")
    "--specpath", (Join-Path $ProjectRoot "build")
)

# Add icon if available
if (Test-Path $IconPath) {
    $PyInstallerArgs += "--icon", $IconPath
}

# Add debug options if requested
if ($Debug) {
    $PyInstallerArgs += "--debug", "all"
    Write-Host "🐛 Debug mode enabled" -ForegroundColor Yellow
}

# Add hidden imports for common packages
$HiddenImports = @(
    "PySide6.QtCore",
    "PySide6.QtWidgets", 
    "PySide6.QtGui",
    "pydantic",
    "requests",
    "rich",
    "pathlib",
    "json",
    "subprocess",
    "threading"
)

foreach ($Import in $HiddenImports) {
    $PyInstallerArgs += "--hidden-import", $Import
}

# Add data files
$DataFiles = @(
    "config.yaml;.",
    "tasks;tasks",
    "evaluators;evaluators"
)

foreach ($DataFile in $DataFiles) {
    $PyInstallerArgs += "--add-data", $DataFile
}

# Main entry point
$MainScript = Join-Path $ProjectRoot "app\gui.py"
$PyInstallerArgs += $MainScript

Write-Host "🔨 Building executable..." -ForegroundColor Yellow
Write-Host "   Command: pyinstaller $($PyInstallerArgs -join ' ')" -ForegroundColor Cyan

# Change to project directory
Push-Location $ProjectRoot

try {
    # Run PyInstaller
    & python -m PyInstaller @PyInstallerArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Build completed successfully!" -ForegroundColor Green
        
        $ExePath = Join-Path $DistDir "AnnotatorKit.exe"
        if (Test-Path $ExePath) {
            $FileSize = (Get-Item $ExePath).Length / 1MB
            Write-Host "📦 Executable created: $ExePath" -ForegroundColor Green
            Write-Host "📏 File size: $([math]::Round($FileSize, 2)) MB" -ForegroundColor Green
            
            # Create additional files
            Write-Host "📝 Creating additional files..." -ForegroundColor Yellow
            
            # Create README for distribution
            $ReadmePath = Join-Path $DistDir "README.txt"
            $ReadmeContent = @"
OSWorld Annotator Kit - Day 3 Enhanced Edition
==============================================

This is a standalone executable for the OSWorld Annotator Kit.

Quick Start:
1. Ensure VMware Workstation is installed and running
2. Configure your VM path in config.yaml (if needed)
3. Run AnnotatorKit.exe
4. Load tasks from the tasks directory
5. Start annotating!

Features:
- Comprehensive action type support with fallback handling
- Enhanced GUI with retry/skip functionality
- Batch task workflow with filtering and navigation
- Robust error handling and timeout management
- Modern UI with status updates and progress tracking

For support and documentation, visit the project repository.

Built on: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Version: 3.0 (Day 3 Enhanced)
"@
            Set-Content -Path $ReadmePath -Value $ReadmeContent -Encoding UTF8
            
            # Create batch file for easy launching
            $BatchPath = Join-Path $DistDir "run_annotator.bat"
            $BatchContent = @"
@echo off
echo Starting OSWorld Annotator Kit...
echo.
AnnotatorKit.exe
if errorlevel 1 (
    echo.
    echo Application exited with error code %errorlevel%
    pause
)
"@
            Set-Content -Path $BatchPath -Value $BatchContent -Encoding ASCII
            
            Write-Host "   ✓ Created README.txt" -ForegroundColor Green
            Write-Host "   ✓ Created run_annotator.bat" -ForegroundColor Green
            
        } else {
            Write-Host "❌ Executable not found at expected location" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "❌ Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

# Clean up build artifacts if not in debug mode
if (-not $Debug) {
    Write-Host "🧹 Cleaning up build artifacts..." -ForegroundColor Yellow
    $BuildDir = Join-Path $ProjectRoot "build"
    if (Test-Path $BuildDir) {
        Remove-Item -Path $BuildDir -Recurse -Force
        Write-Host "   ✓ Removed build directory" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "🎉 Build process completed!" -ForegroundColor Green
Write-Host "📦 Executable location: $DistDir\AnnotatorKit.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "To test the build:" -ForegroundColor Yellow
Write-Host "   cd $DistDir" -ForegroundColor White
Write-Host "   .\AnnotatorKit.exe" -ForegroundColor White
Write-Host ""
