# Windows Installation Guide

This guide covers installing Exo-Trace-Archiver on Windows Server or Windows desktop OS using the automated installer. Everything runs natively from Python — no IIS, no Task Scheduler.

## Architecture

```
┌─────────────────────────────────────────────┐
│           Windows Service (NSSM)            │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Django Server (python manage.py      │  │
│  │  runserver 0.0.0.0:8000)              │  │
│  │                                       │  │
│  │  ┌─────────────┐ ┌─────────────────┐  │  │
│  │  │  REST API    │ │ React Frontend  │  │  │
│  │  │  /api/*      │ │ (built static)  │  │  │
│  │  └─────────────┘ └─────────────────┘  │  │
│  │                                       │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │  APScheduler (built-in)         │  │  │
│  │  │  Daily pulls at configured time │  │  │
│  │  └─────────────────────────────────┘  │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  SQLite Database (db.sqlite3)               │
└─────────────────────────────────────────────┘
```

- **Single process** — Django serves both the API and the built React frontend
- **Built-in scheduler** — APScheduler handles daily trace pulls (no Task Scheduler needed)
- **NSSM** — Runs the Python server as a Windows service with auto-restart
- **WhiteNoise** — Efficiently serves static files without a separate web server

## Prerequisites

The installer will automatically download and install these if missing:

| Component | Version | Notes |
|-----------|---------|-------|
| Python    | 3.12+   | Installed silently with pip |
| Node.js   | 20 LTS  | Only needed during install (to build frontend) |
| NSSM      | 2.24    | Downloaded automatically |

## Quick Install

1. Download or clone the repository to your Windows machine
2. Open **PowerShell as Administrator**
3. Run:

```powershell
.\Install.ps1
```

That's it. The installer will:
- Install Python and Node.js if not present
- Create a virtual environment and install dependencies
- Build the React frontend
- Run database migrations
- Prompt you to create an admin user
- Register and start a Windows service

## Installer Options

```powershell
# Install with defaults (C:\ExoTraceArchiver, port 8000)
.\Install.ps1

# Custom install location and port
.\Install.ps1 -InstallPath "D:\Apps\ExoTrace" -Port 9000

# Custom service name
.\Install.ps1 -ServiceName "MyExoTraceService"

# Skip auto-installing Python/Node (if already installed)
.\Install.ps1 -SkipPythonInstall -SkipNodeInstall

# Install without registering as a service (for testing)
.\Install.ps1 -SkipServiceInstall

# Uninstall
.\Install.ps1 -Uninstall
```

## Managing the Service

Use the `Manage-Service.ps1` script:

```powershell
# Check status
.\Manage-Service.ps1 -Action status

# Start / Stop / Restart
.\Manage-Service.ps1 -Action start
.\Manage-Service.ps1 -Action stop
.\Manage-Service.ps1 -Action restart

# View logs
.\Manage-Service.ps1 -Action logs
.\Manage-Service.ps1 -Action logs -Tail 200

# Update (pulls new deps, rebuilds frontend, runs migrations)
.\Manage-Service.ps1 -Action update
```

Or use standard Windows service commands:

```powershell
Start-Service ExoTraceArchiver
Stop-Service ExoTraceArchiver
Get-Service ExoTraceArchiver
```

The service also appears in `services.msc`.

## Post-Install Configuration

### 1. Edit the .env file

Located at `C:\ExoTraceArchiver\backend\.env` (or your custom install path):

```ini
# Required: Microsoft 365 / Azure AD credentials
MS365_TENANT_ID=your-tenant-id
MS365_CLIENT_ID=your-client-id
MS365_AUTH_METHOD=certificate
MS365_CERTIFICATE_PATH=C:\ExoTraceArchiver\backend\certificates\ExoTraceArchiver.pfx
MS365_CERTIFICATE_THUMBPRINT=your-certificate-thumbprint
MS365_CERTIFICATE_PASSWORD=your-certificate-password

# API method (graph recommended)
MS365_API_METHOD=graph
```

After editing, restart the service:

```powershell
.\Manage-Service.ps1 -Action restart
```

### 2. Generate a certificate (if needed)

```powershell
.\GenerateCert.ps1
```

This creates a self-signed certificate and provides instructions for uploading it to Azure AD.

### 3. Access the web interface

Open your browser to:
- **Web Interface**: `http://localhost:8000`
- **Admin Panel**: `http://localhost:8000/admin/`

## Directory Structure (after install)

```
C:\ExoTraceArchiver\
├── Install.ps1              # Installer (re-runnable)
├── Manage-Service.ps1       # Service management
├── GenerateCert.ps1         # Certificate generator
│
├── backend\
│   ├── .env                 # Configuration (edit this!)
│   ├── db.sqlite3           # SQLite database
│   ├── manage.py            # Django management
│   ├── venv\                # Python virtual environment
│   ├── certificates\        # Certificate storage
│   ├── logs\                # Application and service logs
│   │   ├── exo_trace_archiver.log
│   │   ├── service-stdout.log
│   │   └── service-stderr.log
│   └── staticfiles\         # Collected static files
│
├── frontend\
│   ├── dist\                # Built React app
│   └── ...
│
└── nssm\                    # NSSM service manager
```

## Firewall

The installer automatically creates a Windows Firewall rule allowing inbound TCP on the configured port for **Domain** and **Private** network profiles.

If you need to allow access from Public networks:

```powershell
Set-NetFirewallRule -DisplayName "Exo-Trace-Archiver" -Profile Domain,Private,Public
```

## Accessing from Other Machines

By default, the server binds to `0.0.0.0` (all interfaces). To access from another machine on your network, use:

```
http://<server-ip>:8000
```

Make sure to add the server's hostname/IP to `ALLOWED_HOSTS` in `.env`:

```ini
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100,server-hostname
```

## Updating

When you have a new version of the application:

1. Copy the updated files to the install directory
2. Run:

```powershell
.\Manage-Service.ps1 -Action update
```

This will stop the service, update dependencies, rebuild the frontend, run migrations, and restart.

## Troubleshooting

### Service won't start
```powershell
# Check the error log
Get-Content C:\ExoTraceArchiver\backend\logs\service-stderr.log -Tail 50

# Try running manually to see errors
cd C:\ExoTraceArchiver\backend
C:\ExoTraceArchiver\backend\venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

### Port already in use
```powershell
# Find what's using the port
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
Get-Process -Id <PID>

# Reinstall on a different port
.\Install.ps1 -Port 9000
```

### Database issues
```powershell
# Re-run migrations
cd C:\ExoTraceArchiver\backend
.\venv\Scripts\python.exe manage.py migrate
```

### Reset admin password
```powershell
cd C:\ExoTraceArchiver\backend
.\venv\Scripts\python.exe manage.py changepassword <username>
```

## Uninstalling

```powershell
.\Install.ps1 -Uninstall
```

This will:
- Stop and remove the Windows service
- Remove the firewall rule
- Optionally delete the installation directory
