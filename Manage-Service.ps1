<#
.SYNOPSIS
    Manage the Exo-Trace-Archiver Windows service.

.DESCRIPTION
    Start, stop, restart, check status, or view logs for the Exo-Trace-Archiver service.

.EXAMPLE
    .\Manage-Service.ps1 -Action start
    .\Manage-Service.ps1 -Action stop
    .\Manage-Service.ps1 -Action restart
    .\Manage-Service.ps1 -Action status
    .\Manage-Service.ps1 -Action logs
    .\Manage-Service.ps1 -Action logs -Tail 100
    .\Manage-Service.ps1 -Action update
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "update")]
    [string]$Action,

    [string]$ServiceName = "ExoTraceArchiver",
    [int]$Port = 8000,
    [int]$Tail = 50
)

$InstallPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $InstallPath "backend"
$FrontendDir = Join-Path $InstallPath "frontend"
$VenvDir = Join-Path $BackendDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$LogsDir = Join-Path $BackendDir "logs"

function Write-Status {
    param([string]$Label, [string]$Value, [string]$Color = "White")
    Write-Host "  $Label" -NoNewline -ForegroundColor Gray
    Write-Host "$Value" -ForegroundColor $Color
}

switch ($Action) {
    "start" {
        Write-Host "Starting $ServiceName..." -ForegroundColor Cyan
        Start-Service $ServiceName
        Start-Sleep -Seconds 3
        $svc = Get-Service $ServiceName
        if ($svc.Status -eq "Running") {
            Write-Host "  Service started successfully." -ForegroundColor Green
            Write-Host "  Web interface: http://localhost:$Port" -ForegroundColor Yellow
        } else {
            Write-Host "  Service failed to start. Check logs:" -ForegroundColor Red
            Write-Host "  $LogsDir\service-stderr.log" -ForegroundColor Red
        }
    }

    "stop" {
        Write-Host "Stopping $ServiceName..." -ForegroundColor Cyan
        Stop-Service $ServiceName -Force
        Write-Host "  Service stopped." -ForegroundColor Green
    }

    "restart" {
        Write-Host "Restarting $ServiceName..." -ForegroundColor Cyan
        Restart-Service $ServiceName -Force
        Start-Sleep -Seconds 3
        $svc = Get-Service $ServiceName
        if ($svc.Status -eq "Running") {
            Write-Host "  Service restarted successfully." -ForegroundColor Green
        } else {
            Write-Host "  Service failed to restart. Check logs." -ForegroundColor Red
        }
    }

    "status" {
        Write-Host ""
        Write-Host "  Exo-Trace-Archiver Status" -ForegroundColor Cyan
        Write-Host "  =========================" -ForegroundColor Cyan

        $svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
        if ($svc) {
            $color = if ($svc.Status -eq "Running") { "Green" } else { "Red" }
            Write-Status "Service:       " $svc.Status $color
            Write-Status "Startup Type:  " $svc.StartType "White"
        } else {
            Write-Status "Service:       " "Not Installed" "Red"
        }

        Write-Status "Install Path:  " $InstallPath "White"
        Write-Status "Web URL:       " "http://localhost:$Port" "Yellow"

        # Check if port is listening
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            Write-Status "Port $Port`:      " "Listening" "Green"
        } else {
            Write-Status "Port $Port`:      " "Not Listening" "Red"
        }

        # Database size
        $dbFile = Join-Path $BackendDir "db.sqlite3"
        if (Test-Path $dbFile) {
            $dbSize = [math]::Round((Get-Item $dbFile).Length / 1MB, 2)
            Write-Status "Database:      " "$dbSize MB" "White"
        }

        # Log file size
        $logFile = Join-Path $LogsDir "exo_trace_archiver.log"
        if (Test-Path $logFile) {
            $logSize = [math]::Round((Get-Item $logFile).Length / 1MB, 2)
            Write-Status "Log File:      " "$logSize MB" "White"
        }

        Write-Host ""
    }

    "logs" {
        $logFiles = @(
            (Join-Path $LogsDir "service-stdout.log"),
            (Join-Path $LogsDir "service-stderr.log"),
            (Join-Path $LogsDir "exo_trace_archiver.log")
        )

        Write-Host ""
        Write-Host "  Available log files:" -ForegroundColor Cyan
        $logFiles | ForEach-Object {
            if (Test-Path $_) {
                $size = [math]::Round((Get-Item $_).Length / 1KB, 1)
                Write-Host "    $_ ($size KB)" -ForegroundColor Gray
            }
        }

        Write-Host ""
        Write-Host "  === Last $Tail lines of application log ===" -ForegroundColor Yellow
        $appLog = Join-Path $LogsDir "exo_trace_archiver.log"
        if (Test-Path $appLog) {
            Get-Content $appLog -Tail $Tail
        } else {
            Write-Host "  No application log found." -ForegroundColor Gray
        }

        Write-Host ""
        Write-Host "  === Last $Tail lines of service stderr ===" -ForegroundColor Yellow
        $errLog = Join-Path $LogsDir "service-stderr.log"
        if (Test-Path $errLog) {
            Get-Content $errLog -Tail $Tail
        } else {
            Write-Host "  No service error log found." -ForegroundColor Gray
        }
    }

    "update" {
        Write-Host "Updating Exo-Trace-Archiver..." -ForegroundColor Cyan

        # Stop service
        $svc = Get-Service $ServiceName -ErrorAction SilentlyContinue
        $wasRunning = $svc -and $svc.Status -eq "Running"
        if ($wasRunning) {
            Write-Host "  Stopping service..." -ForegroundColor Yellow
            Stop-Service $ServiceName -Force
            Start-Sleep -Seconds 2
        }

        # Update Python dependencies
        Write-Host "  Updating Python dependencies..." -ForegroundColor Yellow
        $venvPip = Join-Path $VenvDir "Scripts\pip.exe"
        & $venvPip install -r (Join-Path $BackendDir "requirements.txt") --quiet --upgrade

        # Rebuild frontend
        Write-Host "  Rebuilding frontend..." -ForegroundColor Yellow
        Push-Location $FrontendDir
        try {
            npm install --silent 2>$null
            npm run build 2>$null
        } finally {
            Pop-Location
        }

        # Run migrations
        Write-Host "  Running database migrations..." -ForegroundColor Yellow
        & $VenvPython (Join-Path $BackendDir "manage.py") migrate --no-input 2>$null

        # Collect static files
        Write-Host "  Collecting static files..." -ForegroundColor Yellow
        & $VenvPython (Join-Path $BackendDir "manage.py") collectstatic --no-input 2>$null

        # Restart service if it was running
        if ($wasRunning) {
            Write-Host "  Starting service..." -ForegroundColor Yellow
            Start-Service $ServiceName
            Start-Sleep -Seconds 3
            $svc = Get-Service $ServiceName
            if ($svc.Status -eq "Running") {
                Write-Host "  Update complete. Service is running." -ForegroundColor Green
            } else {
                Write-Host "  Update complete but service failed to start. Check logs." -ForegroundColor Red
            }
        } else {
            Write-Host "  Update complete. Service was not running (start it manually)." -ForegroundColor Green
        }
    }
}
