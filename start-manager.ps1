# Pwnagotchi Fleet Manager - Quick Start Guide
# PowerShell script for Windows

Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Pwnagotchi Fleet Manager - Quick Start                   ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✓ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python not found! Install Python 3.8+ first." -ForegroundColor Red
    exit 1
}

# Check/Install dependencies
Write-Host "`n[2/5] Checking dependencies..." -ForegroundColor Yellow

$requiredPackages = @("requests", "pycryptodome", "PySocks", "tabulate", "colorama")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    $installed = python -c "import $package" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $package" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $package (not installed)" -ForegroundColor Red
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host "`n  Installing missing packages..." -ForegroundColor Yellow
    pip install $missingPackages
}

# Check for existing pwnies
Write-Host "`n[3/5] Checking for existing pwnies..." -ForegroundColor Yellow
if (Test-Path "./fake_pwnies") {
    $pwnieCount = (Get-ChildItem "./fake_pwnies" -Filter "*.json").Count
    if ($pwnieCount -gt 0) {
        Write-Host "  ✓ Found $pwnieCount existing pwnies" -ForegroundColor Green
        $createNew = Read-Host "  Create more pwnies? (y/n)"
    } else {
        Write-Host "  ℹ No pwnies found" -ForegroundColor Yellow
        $createNew = "y"
    }
} else {
    Write-Host "  ℹ No pwnies directory found" -ForegroundColor Yellow
    $createNew = "y"
}

# Create pwnies if needed
if ($createNew -eq "y") {
    Write-Host "`n[4/5] Creating pwnies..." -ForegroundColor Yellow
    
    $count = Read-Host "  How many pwnies to create? (default: 10)"
    if ([string]::IsNullOrWhiteSpace($count)) { $count = 10 }
    
    $useTor = Read-Host "  Use Tor for each pwnie? (y/n, default: y)"
    if ([string]::IsNullOrWhiteSpace($useTor)) { $useTor = "y" }
    
    $pwned = Read-Host "  Initial pwned networks? (number or 'random', default: random)"
    if ([string]::IsNullOrWhiteSpace($pwned)) { $pwned = "random" }
    
    Write-Host "`n  Creating $count pwnies..." -ForegroundColor Cyan
    
    # Run for 30 seconds to let them enroll
    Write-Host "  Running for 30 seconds to enroll and initialize..." -ForegroundColor Yellow
    $arguments = "pwnagotchi-gen.py --count $count --pwned $pwned --yes"
    if ($useTor -eq 'y') { $arguments += " --tor" }
    $process = Start-Process -FilePath "python" -ArgumentList $arguments -PassThru -NoNewWindow
    Start-Sleep -Seconds 30
    Stop-Process -Id $process.Id -Force
    
    Write-Host "  ✓ Pwnies created and saved" -ForegroundColor Green
} else {
    Write-Host "`n[4/5] Skipping pwnie creation" -ForegroundColor Yellow
}

# Launch manager
Write-Host "`n[5/5] Launching Fleet Manager..." -ForegroundColor Yellow
Write-Host ""

$mode = Read-Host "  Launch mode: [1] CLI  [2] Web UI  (default: 1)"
if ([string]::IsNullOrWhiteSpace($mode)) { $mode = "1" }

Write-Host ""
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan

if ($mode -eq "2") {
    Write-Host "Starting Web UI Dashboard..." -ForegroundColor Green
    Write-Host "Open your browser to: http://localhost:5000" -ForegroundColor Yellow
    Write-Host ""
    python pwnie-manager.py --webui
} else {
    Write-Host "Starting Interactive CLI..." -ForegroundColor Green
    Write-Host ""
    Write-Host "Quick Commands:" -ForegroundColor Yellow
    Write-Host "  list        - List all pwnies" -ForegroundColor Gray
    Write-Host "  boot all    - Start all pwnies" -ForegroundColor Gray
    Write-Host "  monitor     - Real-time monitoring" -ForegroundColor Gray
    Write-Host "  help        - Show all commands" -ForegroundColor Gray
    Write-Host ""
    python pwnie-manager.py
}

Write-Host "`n════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "Goodbye!" -ForegroundColor Green
