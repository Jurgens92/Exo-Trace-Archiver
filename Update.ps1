#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Exo-Trace-Archiver Update Script

.DESCRIPTION
    Updates an existing Exo-Trace-Archiver installation with the latest code.
    Can update from a local source directory (e.g., a git clone) or from a
    GitHub release.

    Preserves all user data: database, .env config, certificates, and logs.

.PARAMETER InstallPath
    Path to the existing installation. Defaults to C:\ExoTraceArchiver.

.PARAMETER SourcePath
    Path to the updated source files (e.g., a git clone or extracted release).
    Defaults to the directory containing this script.

.PARAMETER ServiceName
    Windows service name. Defaults to ExoTraceArchiver.

.PARAMETER SkipFrontend
    Skip rebuilding the frontend (faster if only backend changes).

.PARAMETER SkipDeps
    Skip updating Python/Node dependencies (faster if only code changes).

.PARAMETER Force
    Skip the confirmation prompt.

.EXAMPLE
    .\Update.ps1
    Update from the current directory to C:\ExoTraceArchiver.

.EXAMPLE
    .\Update.ps1 -InstallPath "D:\Apps\ExoTrace"
    Update a custom installation path.

.EXAMPLE
    .\Update.ps1 -SkipFrontend
    Update only the backend (faster).

.EXAMPLE
    .\Update.ps1 -SkipDeps -SkipFrontend
    Quick update: code-only, no dependency install or frontend rebuild.
#>

param(
    [string]$InstallPath = "C:\ExoTraceArchiver",
    [string]$SourcePath = "",
    [string]$ServiceName = "ExoTraceArchiver",
    [switch]$SkipFrontend,
    [switch]$SkipDeps,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ============================================================================
# Configuration
# ============================================================================

if (-not $SourcePath) {
    $SourcePath = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$BackendDir = Join-Path $InstallPath "backend"
$FrontendDir = Join-Path $InstallPath "frontend"
$VenvDir = Join-Path $BackendDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"
$LogsDir = Join-Path $BackendDir "logs"

$SrcBackend = Join-Path $SourcePath "backend"
$SrcFrontend = Join-Path $SourcePath "frontend"

# ============================================================================
# Helper Functions
# ============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "  [..] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Exo-Trace-Archiver Updater" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Source Path:   $SourcePath"
Write-Host "  Install Path:  $InstallPath"
Write-Host "  Service Name:  $ServiceName"
Write-Host ""

# Validate source
if (-not (Test-Path $SrcBackend)) {
    Write-Fail "Source backend directory not found: $SrcBackend"
    Write-Host "  Make sure you're running this script from the repository root," -ForegroundColor Yellow
    Write-Host "  or provide -SourcePath pointing to the updated source files." -ForegroundColor Yellow
    exit 1
}

# Validate installation
if (-not (Test-Path $BackendDir)) {
    Write-Fail "Installation not found at: $InstallPath"
    Write-Host "  Run Install.ps1 first to perform initial setup." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $VenvPython)) {
    Write-Fail "Python virtual environment not found: $VenvDir"
    Write-Host "  Run Install.ps1 to set up the virtual environment." -ForegroundColor Yellow
    exit 1
}

# Source and install must be different directories
$resolvedSource = (Resolve-Path $SourcePath).Path.TrimEnd('\')
$resolvedInstall = (Resolve-Path $InstallPath).Path.TrimEnd('\')
if ($resolvedSource -eq $resolvedInstall) {
    Write-Info "Source and install paths are the same directory."
    Write-Info "Skipping file copy - updating in-place."
    $inPlace = $true
} else {
    $inPlace = $false
}

# Confirmation
if (-not $Force) {
    Write-Host "  This will update the installation at $InstallPath" -ForegroundColor Yellow
    Write-Host "  Your database, .env config, and certificates will be preserved." -ForegroundColor Yellow
    Write-Host ""
    $confirm = Read-Host "  Continue? (Y/n)"
    if ($confirm -eq 'n') {
        Write-Host "  Update cancelled." -ForegroundColor Gray
        exit 0
    }
}

$updateStart = Get-Date

# ============================================================================
# Step 1: Stop Service
# ============================================================================

Write-Step "Step 1: Stopping service"

$svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
$wasRunning = $svc -and $svc.Status -eq "Running"

if ($wasRunning) {
    Write-Info "Stopping $ServiceName..."
    Stop-Service $ServiceName -Force
    Start-Sleep -Seconds 2

    # Verify it stopped
    $svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
    if ($svc.Status -eq "Running") {
        Write-Info "Service still running, waiting..."
        Start-Sleep -Seconds 5
        $svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
        if ($svc.Status -eq "Running") {
            Write-Fail "Could not stop service. Try: Stop-Service $ServiceName -Force"
            exit 1
        }
    }
    Write-Success "Service stopped."
} elseif ($svc) {
    Write-Success "Service exists but is already stopped."
} else {
    Write-Info "Service '$ServiceName' not found (running without a service)."
}

# ============================================================================
# Step 2: Backup
# ============================================================================

Write-Step "Step 2: Creating backup"

$backupDir = Join-Path $InstallPath "_backups"
$timestamp = (Get-Date -Format "yyyyMMdd_HHmmss")
$backupPath = Join-Path $backupDir $timestamp

New-Item -ItemType Directory -Force -Path $backupPath | Out-Null

# Backup database
$dbFile = Join-Path $BackendDir "db.sqlite3"
if (Test-Path $dbFile) {
    Copy-Item $dbFile (Join-Path $backupPath "db.sqlite3")
    Write-Success "Database backed up."
}

# Backup .env
$envFile = Join-Path $BackendDir ".env"
if (Test-Path $envFile) {
    Copy-Item $envFile (Join-Path $backupPath ".env")
    Write-Success ".env backed up."
}

# Backup certificates directory
$certsDir = Join-Path $BackendDir "certificates"
if (Test-Path $certsDir) {
    Copy-Item $certsDir (Join-Path $backupPath "certificates") -Recurse
    Write-Success "Certificates backed up."
}

Write-Success "Backup saved to: $backupPath"

# Clean up old backups (keep last 5)
$oldBackups = Get-ChildItem $backupDir -Directory | Sort-Object Name -Descending | Select-Object -Skip 5
if ($oldBackups) {
    $oldBackups | Remove-Item -Recurse -Force
    Write-Info "Cleaned up $($oldBackups.Count) old backup(s)."
}

# ============================================================================
# Step 3: Update Files
# ============================================================================

Write-Step "Step 3: Updating application files"

if (-not $inPlace) {
    # Files/directories to preserve (never overwrite)
    $preserveBackend = @(
        ".env",
        "db.sqlite3",
        "certificates",
        "logs",
        "venv"
    )

    # Update backend files
    Write-Info "Updating backend files..."

    # Copy all backend files except preserved ones
    Get-ChildItem $SrcBackend -Exclude $preserveBackend | ForEach-Object {
        $dest = Join-Path $BackendDir $_.Name
        if ($_.PSIsContainer) {
            # For directories, remove old and copy fresh
            if (Test-Path $dest) {
                Remove-Item $dest -Recurse -Force
            }
            Copy-Item $_.FullName $dest -Recurse -Force
        } else {
            Copy-Item $_.FullName $dest -Force
        }
    }
    Write-Success "Backend files updated."

    # Update frontend files
    if (-not $SkipFrontend) {
        Write-Info "Updating frontend files..."
        if (Test-Path $SrcFrontend) {
            # Preserve node_modules if it exists (npm install will update it)
            $nodeModules = Join-Path $FrontendDir "node_modules"
            $hadNodeModules = Test-Path $nodeModules

            # Remove old frontend files except node_modules
            Get-ChildItem $FrontendDir -Exclude "node_modules" -ErrorAction SilentlyContinue |
                Remove-Item -Recurse -Force

            # Copy new frontend files except node_modules
            Get-ChildItem $SrcFrontend -Exclude "node_modules" | ForEach-Object {
                Copy-Item $_.FullName (Join-Path $FrontendDir $_.Name) -Recurse -Force
            }
            Write-Success "Frontend files updated."
        } else {
            Write-Info "No frontend source found, skipping."
        }
    } else {
        Write-Info "Skipping frontend files (-SkipFrontend)."
    }

    # Update root scripts
    @("GenerateCert.ps1", "Update.ps1", "Manage-Service.ps1", "Install.ps1") | ForEach-Object {
        $src = Join-Path $SourcePath $_
        if (Test-Path $src) {
            Copy-Item $src $InstallPath -Force
        }
    }
    Write-Success "Root scripts updated."

} else {
    Write-Success "In-place update, no file copy needed."
}

# ============================================================================
# Step 4: Update Python Dependencies
# ============================================================================

Write-Step "Step 4: Updating Python dependencies"

if (-not $SkipDeps) {
    Write-Info "Upgrading pip..."
    & $VenvPython -m pip install --upgrade pip --quiet 2>$null
    Write-Info "Installing requirements..."
    & $VenvPip install -r (Join-Path $BackendDir "requirements.txt") --quiet --upgrade
    Write-Success "Python dependencies updated."
} else {
    Write-Info "Skipping dependency update (-SkipDeps)."
}

# ============================================================================
# Step 5: Run Database Migrations
# ============================================================================

Write-Step "Step 5: Running database migrations"

Write-Info "Applying migrations..."
$ErrorActionPreference = "Continue"
& $VenvPython (Join-Path $BackendDir "manage.py") migrate --no-input 2>&1 | ForEach-Object {
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        # Suppress Django warnings written to stderr (e.g., scheduler startup)
    } else {
        Write-Host "  $_"
    }
}
$ErrorActionPreference = "Stop"
Write-Success "Migrations complete."

# ============================================================================
# Step 6: Build Frontend
# ============================================================================

if (-not $SkipFrontend) {
    Write-Step "Step 6: Building frontend"

    if (Test-Path $FrontendDir) {
        Push-Location $FrontendDir
        try {
            if (-not $SkipDeps) {
                Write-Info "Installing Node.js dependencies..."
                npm install --silent 2>$null
                Write-Success "Node.js dependencies installed."
            }

            Write-Info "Building React frontend..."
            npm run build
            if ($LASTEXITCODE -ne 0) {
                Write-Fail "Frontend build failed. Check errors above."
                Write-Host "  The backend is already updated. You can fix frontend" -ForegroundColor Yellow
                Write-Host "  issues and re-run: .\Update.ps1 -SkipDeps" -ForegroundColor Yellow
                Pop-Location
                # Don't exit - backend is still usable
            } else {
                Write-Success "Frontend built successfully."
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Info "No frontend directory found, skipping build."
    }
} else {
    Write-Step "Step 6: Skipping frontend build (-SkipFrontend)"
}

# ============================================================================
# Step 7: Collect Static Files
# ============================================================================

Write-Step "Step 7: Collecting static files"

Write-Info "Running collectstatic..."
$ErrorActionPreference = "Continue"
& $VenvPython (Join-Path $BackendDir "manage.py") collectstatic --no-input 2>&1 | ForEach-Object {
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        # Suppress Django warnings written to stderr
    } else {
        Write-Host "  $_"
    }
}
$ErrorActionPreference = "Stop"
Write-Success "Static files collected."

# ============================================================================
# Step 8: Restart Service
# ============================================================================

Write-Step "Step 8: Restarting service"

if ($wasRunning) {
    Write-Info "Starting $ServiceName..."
    Start-Service $ServiceName
    Start-Sleep -Seconds 3

    $svc = Get-Service $ServiceName
    if ($svc.Status -eq "Running") {
        Write-Success "Service started successfully."
    } else {
        Write-Fail "Service failed to start. Check logs:"
        Write-Host "    $LogsDir\service-stderr.log" -ForegroundColor Red
        Write-Host ""
        Write-Host "  To restore from backup:" -ForegroundColor Yellow
        Write-Host "    Copy-Item '$backupPath\db.sqlite3' '$BackendDir\db.sqlite3'" -ForegroundColor Yellow
        Write-Host "    Copy-Item '$backupPath\.env' '$BackendDir\.env'" -ForegroundColor Yellow
    }
} elseif ($svc) {
    Write-Info "Service was not running before update. Start it with:"
    Write-Host "    Start-Service $ServiceName" -ForegroundColor Yellow
} else {
    Write-Info "No service installed. Run manually with:"
    Write-Host "    cd $BackendDir" -ForegroundColor Yellow
    Write-Host "    $VenvDir\Scripts\activate" -ForegroundColor Yellow
    Write-Host "    python manage.py runserver 0.0.0.0:8000" -ForegroundColor Yellow
}

# ============================================================================
# Complete
# ============================================================================

$duration = [math]::Round(((Get-Date) - $updateStart).TotalSeconds, 1)

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "   Update Complete!  ($duration seconds)" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backup:     $backupPath" -ForegroundColor White
Write-Host "  To rollback the database:" -ForegroundColor Yellow
Write-Host "    Stop-Service $ServiceName" -ForegroundColor Gray
Write-Host "    Copy-Item '$backupPath\db.sqlite3' '$BackendDir\db.sqlite3'" -ForegroundColor Gray
Write-Host "    Start-Service $ServiceName" -ForegroundColor Gray
Write-Host ""
