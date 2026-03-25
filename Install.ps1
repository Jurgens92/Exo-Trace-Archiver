#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Exo-Trace-Archiver Windows Installer

.DESCRIPTION
    Fully automated installer for Exo-Trace-Archiver on Windows.
    Installs Python (if needed), Node.js (if needed), NSSM (for Windows service),
    sets up the backend and frontend, and registers as a Windows service.

.PARAMETER InstallPath
    Installation directory. Defaults to C:\ExoTraceArchiver.

.PARAMETER ServiceName
    Windows service name. Defaults to ExoTraceArchiver.

.PARAMETER Port
    Port for the web server. Defaults to 8000.

.PARAMETER SkipPythonInstall
    Skip automatic Python installation (use if Python is already installed).

.PARAMETER SkipNodeInstall
    Skip automatic Node.js installation (use if Node.js is already installed).

.PARAMETER SkipServiceInstall
    Skip Windows service registration (useful for testing).

.PARAMETER Uninstall
    Remove the Windows service and optionally the installation directory.

.EXAMPLE
    .\Install.ps1
    Install with all defaults to C:\ExoTraceArchiver on port 8000.

.EXAMPLE
    .\Install.ps1 -InstallPath "D:\Apps\ExoTrace" -Port 9000
    Install to a custom directory on port 9000.

.EXAMPLE
    .\Install.ps1 -Uninstall
    Remove the Windows service.
#>

param(
    [string]$InstallPath = "C:\ExoTraceArchiver",
    [string]$ServiceName = "ExoTraceArchiver",
    [int]$Port = 8000,
    [switch]$SkipPythonInstall,
    [switch]$SkipNodeInstall,
    [switch]$SkipServiceInstall,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Speed up Invoke-WebRequest

# ============================================================================
# Configuration
# ============================================================================
$PythonVersion = "3.12.8"
$NodeVersion = "20.18.1"
$NssmVersion = "2.24"
$NssmUrl = "https://nssm.cc/release/nssm-$NssmVersion.zip"
$NssmFallbackUrl = "https://nssm.cc/ci/nssm-$NssmVersion-101-g897c7ad.zip"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
$NodeUrl = "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-x64.msi"

$BackendDir = Join-Path $InstallPath "backend"
$FrontendDir = Join-Path $InstallPath "frontend"
$VenvDir = Join-Path $BackendDir "venv"
$NssmDir = Join-Path $InstallPath "nssm"
$LogsDir = Join-Path $BackendDir "logs"

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

function Test-CommandExists {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# ============================================================================
# Uninstall
# ============================================================================

if ($Uninstall) {
    Write-Step "Uninstalling Exo-Trace-Archiver"

    # Stop and remove service
    $nssmExe = Get-ChildItem -Path $NssmDir -Filter "nssm.exe" -Recurse -ErrorAction SilentlyContinue |
               Where-Object { $_.DirectoryName -like "*win64*" } |
               Select-Object -First 1 -ExpandProperty FullName
    if ($nssmExe) {
        Write-Info "Stopping service '$ServiceName'..."
        & $nssmExe stop $ServiceName 2>$null
        Start-Sleep -Seconds 2
        Write-Info "Removing service '$ServiceName'..."
        & $nssmExe remove $ServiceName confirm 2>$null
        Write-Success "Service removed."
    } else {
        # Try with sc.exe as fallback
        sc.exe stop $ServiceName 2>$null
        sc.exe delete $ServiceName 2>$null
    }

    # Remove firewall rule
    Remove-NetFirewallRule -DisplayName "Exo-Trace-Archiver" -ErrorAction SilentlyContinue
    Write-Success "Firewall rule removed."

    $removeFiles = Read-Host "Remove installation directory '$InstallPath'? (y/N)"
    if ($removeFiles -eq 'y') {
        Remove-Item -Path $InstallPath -Recurse -Force -ErrorAction SilentlyContinue
        Write-Success "Installation directory removed."
    }

    Write-Host ""
    Write-Host "Uninstall complete." -ForegroundColor Green
    exit 0
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Exo-Trace-Archiver Windows Installer" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Install Path:  $InstallPath"
Write-Host "  Service Name:  $ServiceName"
Write-Host "  Web Port:      $Port"
Write-Host ""

# Check for admin rights
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Fail "This installer must be run as Administrator."
    Write-Host "  Right-click PowerShell and select 'Run as Administrator'."
    exit 1
}

# ============================================================================
# Step 1: Install Python (if needed)
# ============================================================================

Write-Step "Step 1: Checking Python"

$pythonExe = $null
if (Test-CommandExists "python") {
    $pyVer = python --version 2>&1
    Write-Success "Python found: $pyVer"
    $pythonExe = (Get-Command python).Source
} elseif (Test-CommandExists "python3") {
    $pyVer = python3 --version 2>&1
    Write-Success "Python found: $pyVer"
    $pythonExe = (Get-Command python3).Source
} else {
    if ($SkipPythonInstall) {
        Write-Fail "Python not found and -SkipPythonInstall was specified."
        Write-Host "  Install Python 3.11+ from https://www.python.org/downloads/"
        exit 1
    }

    Write-Info "Python not found. Downloading Python $PythonVersion..."
    $pyInstaller = Join-Path $env:TEMP "python-$PythonVersion-amd64.exe"
    Invoke-WebRequest -Uri $PythonUrl -OutFile $pyInstaller

    Write-Info "Installing Python $PythonVersion (silent install)..."
    Start-Process -FilePath $pyInstaller -ArgumentList `
        "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_pip=1" `
        -Wait -NoNewWindow

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
                [System.Environment]::GetEnvironmentVariable("Path", "User")

    if (Test-CommandExists "python") {
        $pythonExe = (Get-Command python).Source
        Write-Success "Python $PythonVersion installed successfully."
    } else {
        Write-Fail "Python installation failed. Please install manually."
        exit 1
    }

    Remove-Item $pyInstaller -ErrorAction SilentlyContinue
}

# ============================================================================
# Step 2: Install Node.js (if needed)
# ============================================================================

Write-Step "Step 2: Checking Node.js"

if (Test-CommandExists "node") {
    $nodeVer = node --version 2>&1
    Write-Success "Node.js found: $nodeVer"
} else {
    if ($SkipNodeInstall) {
        Write-Fail "Node.js not found and -SkipNodeInstall was specified."
        Write-Host "  Install Node.js 18+ from https://nodejs.org/"
        exit 1
    }

    Write-Info "Node.js not found. Downloading Node.js $NodeVersion..."
    $nodeInstaller = Join-Path $env:TEMP "node-v$NodeVersion-x64.msi"
    Invoke-WebRequest -Uri $NodeUrl -OutFile $nodeInstaller

    Write-Info "Installing Node.js $NodeVersion (silent install)..."
    Start-Process -FilePath "msiexec.exe" -ArgumentList `
        "/i", "`"$nodeInstaller`"", "/quiet", "/norestart" `
        -Wait -NoNewWindow

    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
                [System.Environment]::GetEnvironmentVariable("Path", "User")

    if (Test-CommandExists "node") {
        Write-Success "Node.js $NodeVersion installed successfully."
    } else {
        Write-Fail "Node.js installation failed. Please install manually."
        exit 1
    }

    Remove-Item $nodeInstaller -ErrorAction SilentlyContinue
}

# ============================================================================
# Step 3: Install Exchange Online Management PowerShell Module
# ============================================================================

Write-Step "Step 3: Checking Exchange Online Management module"

$ErrorActionPreference = "Continue"
$exoModule = Get-Module -ListAvailable -Name ExchangeOnlineManagement 2>$null
$ErrorActionPreference = "Stop"

if ($exoModule) {
    Write-Success "ExchangeOnlineManagement module found: v$($exoModule.Version)"
} else {
    Write-Info "Installing ExchangeOnlineManagement PowerShell module..."
    Write-Info "(Required for PowerShell API method; optional if using Graph API)"
    $ErrorActionPreference = "Continue"
    Install-Module -Name ExchangeOnlineManagement -Force -Scope AllUsers -AllowClobber 2>&1 | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) {
            # Suppress NuGet provider prompts written to stderr
        } else {
            Write-Host "  $_"
        }
    }
    $ErrorActionPreference = "Stop"

    $exoModule = Get-Module -ListAvailable -Name ExchangeOnlineManagement -ErrorAction SilentlyContinue
    if ($exoModule) {
        Write-Success "ExchangeOnlineManagement module installed: v$($exoModule.Version)"
    } else {
        Write-Info "Could not install ExchangeOnlineManagement module."
        Write-Host "  This is optional — Graph API method works without it." -ForegroundColor Gray
        Write-Host "  To install manually later: Install-Module -Name ExchangeOnlineManagement -Force" -ForegroundColor Gray
    }
}

# ============================================================================
# Step 4: Copy Application Files
# ============================================================================

Write-Step "Step 4: Setting up application directory"

if (-not (Test-Path $InstallPath)) {
    New-Item -ItemType Directory -Force -Path $InstallPath | Out-Null
    Write-Success "Created $InstallPath"
}

# Copy project files to install path (skip if already there)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($scriptDir -ne $InstallPath) {
    Write-Info "Copying application files to $InstallPath..."

    # Copy backend
    if (Test-Path (Join-Path $scriptDir "backend")) {
        Copy-Item -Path (Join-Path $scriptDir "backend") -Destination $InstallPath -Recurse -Force
        Write-Success "Backend files copied."
    }

    # Copy frontend
    if (Test-Path (Join-Path $scriptDir "frontend")) {
        Copy-Item -Path (Join-Path $scriptDir "frontend") -Destination $InstallPath -Recurse -Force
        Write-Success "Frontend files copied."
    }

    # Copy other files
    @("GenerateCert.ps1", "README.md") | ForEach-Object {
        $src = Join-Path $scriptDir $_
        if (Test-Path $src) {
            Copy-Item -Path $src -Destination $InstallPath -Force
        }
    }
} else {
    Write-Success "Already running from install directory."
}

# Create required directories
@($LogsDir, (Join-Path $BackendDir "certificates")) | ForEach-Object {
    if (-not (Test-Path $_)) {
        New-Item -ItemType Directory -Force -Path $_ | Out-Null
    }
}

# ============================================================================
# Step 5: Set up Python Virtual Environment
# ============================================================================

Write-Step "Step 5: Setting up Python virtual environment"

$venvPython = Join-Path $VenvDir "Scripts\python.exe"
$venvPip = Join-Path $VenvDir "Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Info "Creating virtual environment..."
    python -m venv $VenvDir
    Write-Success "Virtual environment created."
} else {
    Write-Success "Virtual environment already exists."
}

Write-Info "Installing Python dependencies..."
& $venvPython -m pip install --upgrade pip --quiet 2>$null
& $venvPip install -r (Join-Path $BackendDir "requirements.txt") --quiet
Write-Success "Python dependencies installed."

# ============================================================================
# Step 6: Build Frontend
# ============================================================================

Write-Step "Step 6: Building frontend"

Push-Location $FrontendDir
try {
    Write-Info "Installing Node.js dependencies..."
    npm install --silent 2>$null
    Write-Success "Node.js dependencies installed."

    Write-Info "Building React frontend (this may take a minute)..."
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Frontend build failed. Check the TypeScript errors above."
        Write-Host "  You can fix the errors and re-run the installer to retry." -ForegroundColor Yellow
        exit 1
    }
    Write-Success "Frontend built successfully."
} finally {
    Pop-Location
}

# ============================================================================
# Step 7: Configure Django
# ============================================================================

Write-Step "Step 7: Configuring Django"

$envFile = Join-Path $BackendDir ".env"
if (-not (Test-Path $envFile)) {
    $envExample = Join-Path $BackendDir ".env.example"
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Info "Created .env from .env.example"
    }

    # Generate a random SECRET_KEY
    $chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
    $secretKey = -join ((1..50) | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })

    # Update .env with production values
    $envContent = Get-Content $envFile -Raw
    $envContent = $envContent -replace "SECRET_KEY=.*", "SECRET_KEY=$secretKey"
    $envContent = $envContent -replace "DEBUG=.*", "DEBUG=False"
    $envContent = $envContent -replace "ALLOWED_HOSTS=.*", "ALLOWED_HOSTS=localhost,127.0.0.1,$env:COMPUTERNAME"
    $envContent = $envContent -replace "CORS_ALLOWED_ORIGINS=.*", "CORS_ALLOWED_ORIGINS=http://localhost:$Port,http://127.0.0.1:$Port"
    # Use absolute path for SQLite database to avoid working directory issues
    $dbPath = (Join-Path $BackendDir "db.sqlite3") -replace '\\', '/'
    $envContent = $envContent -replace "DATABASE_URL=.*", "DATABASE_URL=sqlite:///$dbPath"
    Set-Content $envFile $envContent
    Write-Success ".env configured with production defaults."
    Write-Info "IMPORTANT: Edit $envFile to add your Microsoft 365 credentials."
} else {
    Write-Success ".env already exists, keeping existing configuration."
}

# Run migrations
# Note: Django may write warnings to stderr (e.g., scheduler starting in AppConfig.ready).
# We temporarily relax error handling since $ErrorActionPreference=Stop treats any stderr as fatal.
Write-Info "Running database migrations..."
$ErrorActionPreference = "Continue"
& $venvPython (Join-Path $BackendDir "manage.py") migrate --no-input 2>&1 | ForEach-Object {
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        # Suppress Django warnings written to stderr
    } else {
        Write-Host "  $_"
    }
}
$ErrorActionPreference = "Stop"
Write-Success "Database migrations complete."

# Collect static files (includes the frontend build)
Write-Info "Collecting static files..."
$ErrorActionPreference = "Continue"
& $venvPython (Join-Path $BackendDir "manage.py") collectstatic --no-input 2>&1 | ForEach-Object {
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        # Suppress Django warnings written to stderr
    } else {
        Write-Host "  $_"
    }
}
$ErrorActionPreference = "Stop"
Write-Success "Static files collected."

# Check if superuser exists
Write-Info "Checking for admin user..."
$ErrorActionPreference = "Continue"
$userCheck = & $venvPython (Join-Path $BackendDir "manage.py") shell -c "from django.contrib.auth.models import User; print(User.objects.filter(is_superuser=True).exists())" 2>$null
$ErrorActionPreference = "Stop"
if ($userCheck -ne "True") {
    Write-Host ""
    Write-Host "  No admin user found. Let's create one:" -ForegroundColor Yellow
    $ErrorActionPreference = "Continue"
    & $venvPython (Join-Path $BackendDir "manage.py") createsuperuser
    $ErrorActionPreference = "Stop"
} else {
    Write-Success "Admin user already exists."
}

# ============================================================================
# Step 8: Install NSSM and Register Windows Service
# ============================================================================

if (-not $SkipServiceInstall) {
    Write-Step "Step 8: Setting up Windows service"

    # Download and extract NSSM
    # Look for nssm.exe in any subfolder (version in folder name may vary)
    $nssmExe = Get-ChildItem -Path $NssmDir -Filter "nssm.exe" -Recurse -ErrorAction SilentlyContinue |
               Where-Object { $_.DirectoryName -like "*win64*" } |
               Select-Object -First 1 -ExpandProperty FullName

    if (-not $nssmExe) {
        Write-Info "Downloading NSSM (Non-Sucking Service Manager)..."
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        $downloaded = $false

        # Try primary URL, then fallback
        foreach ($url in @($NssmUrl, $NssmFallbackUrl)) {
            try {
                Write-Info "Trying $url..."
                Invoke-WebRequest -Uri $url -OutFile $nssmZip -TimeoutSec 30
                $downloaded = $true
                break
            } catch {
                Write-Info "Download failed: $($_.Exception.Message)"
            }
        }

        if (-not $downloaded) {
            Write-Fail "Could not download NSSM. Please download manually from https://nssm.cc/"
            Write-Host "  Extract it to: $NssmDir" -ForegroundColor Yellow
            Write-Host "  Then re-run this installer." -ForegroundColor Yellow
            Write-Host ""
            Write-Host "  Alternatively, run with -SkipServiceInstall to install without a service." -ForegroundColor Yellow
            exit 1
        }

        Write-Info "Extracting NSSM..."
        Expand-Archive -Path $nssmZip -DestinationPath $NssmDir -Force
        Remove-Item $nssmZip -ErrorAction SilentlyContinue

        # Find the extracted nssm.exe
        $nssmExe = Get-ChildItem -Path $NssmDir -Filter "nssm.exe" -Recurse -ErrorAction SilentlyContinue |
                   Where-Object { $_.DirectoryName -like "*win64*" } |
                   Select-Object -First 1 -ExpandProperty FullName

        if (-not $nssmExe) {
            Write-Fail "NSSM extracted but nssm.exe not found in $NssmDir"
            exit 1
        }

        Write-Success "NSSM installed."
    } else {
        Write-Success "NSSM already installed."
    }

    # Stop existing service if running (may not exist yet — that's OK)
    $ErrorActionPreference = "Continue"
    & $nssmExe stop $ServiceName 2>$null
    Start-Sleep -Seconds 1

    # Remove existing service if it exists
    & $nssmExe remove $ServiceName confirm 2>$null

    # Install the service using NSSM
    # Point NSSM directly at the venv python.exe — no intermediate script needed.
    # The built-in APScheduler starts automatically when Django starts (in AppConfig.ready),
    # so a single process handles both the web server and scheduled pulls.
    Write-Info "Registering Windows service '$ServiceName'..."
    & $nssmExe install $ServiceName $venvPython "manage.py runserver 0.0.0.0:$Port --noreload"

    # Configure the service
    & $nssmExe set $ServiceName Description "Exo-Trace-Archiver - Exchange Online Message Trace Log Archiver"
    & $nssmExe set $ServiceName AppDirectory $BackendDir
    & $nssmExe set $ServiceName Start SERVICE_AUTO_START
    & $nssmExe set $ServiceName AppStdout (Join-Path $LogsDir "service-stdout.log")
    & $nssmExe set $ServiceName AppStderr (Join-Path $LogsDir "service-stderr.log")
    & $nssmExe set $ServiceName AppRotateFiles 1
    & $nssmExe set $ServiceName AppRotateBytes 10485760  # 10 MB
    & $nssmExe set $ServiceName AppStopMethodSkip 6
    & $nssmExe set $ServiceName AppStopMethodConsole 5000
    & $nssmExe set $ServiceName AppStopMethodWindow 5000
    & $nssmExe set $ServiceName AppStopMethodThreads 5000
    $ErrorActionPreference = "Stop"

    Write-Success "Windows service '$ServiceName' registered."

    # Add firewall rule
    Write-Info "Adding firewall rule for port $Port..."
    Remove-NetFirewallRule -DisplayName "Exo-Trace-Archiver" -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName "Exo-Trace-Archiver" `
        -Direction Inbound -Protocol TCP -LocalPort $Port `
        -Action Allow -Profile Domain,Private | Out-Null
    Write-Success "Firewall rule added (Domain and Private networks)."

} else {
    Write-Step "Step 8: Skipping service installation (--SkipServiceInstall)"
}

# ============================================================================
# Complete
# ============================================================================

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "   Installation Complete!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Install Location:  $InstallPath" -ForegroundColor White
Write-Host "  Web Interface:     http://localhost:$Port" -ForegroundColor White
Write-Host "  Admin Panel:       http://localhost:$Port/admin/" -ForegroundColor White
Write-Host ""

if (-not $SkipServiceInstall) {
    Write-Host "  Service Management:" -ForegroundColor Yellow
    Write-Host "    Start:   Start-Service $ServiceName"
    Write-Host "    Stop:    Stop-Service $ServiceName"
    Write-Host "    Status:  Get-Service $ServiceName"
    Write-Host "    Logs:    Get-Content '$LogsDir\service-stdout.log' -Tail 50"
    Write-Host ""
    Write-Host "  The service is set to start automatically on boot." -ForegroundColor Yellow
    Write-Host ""

    $startNow = Read-Host "Start the service now? (Y/n)"
    if ($startNow -ne 'n') {
        Start-Service $ServiceName
        Start-Sleep -Seconds 3
        $svc = Get-Service $ServiceName
        if ($svc.Status -eq 'Running') {
            Write-Success "Service started! Open http://localhost:$Port in your browser."
        } else {
            Write-Fail "Service failed to start. Check logs at: $LogsDir\service-stderr.log"
        }
    }
} else {
    Write-Host "  To run manually:" -ForegroundColor Yellow
    Write-Host "    cd $BackendDir"
    Write-Host "    $VenvDir\Scripts\activate"
    Write-Host "    python manage.py runserver 0.0.0.0:$Port"
    Write-Host ""
}

Write-Host "  Next Steps:" -ForegroundColor Yellow
Write-Host "    1. Edit $BackendDir\.env with your Microsoft 365 credentials"
Write-Host "    2. Upload your certificate via the web interface (Settings page)"
Write-Host "    3. Configure your tenant in the web interface"
Write-Host ""
Write-Host "  Uninstall:" -ForegroundColor Yellow
Write-Host "    .\Install.ps1 -Uninstall"
Write-Host ""
