# Exo-Trace-Archiver

A production-ready web application for archiving and searching Microsoft 365 Exchange Online message trace logs.

## Features

- **Message Trace Archiving**: Automatically pull and store Exchange Online message traces
- **Searchable Interface**: Filter and search traces by sender, recipient, date, status, and direction
- **Dashboard**: Real-time statistics and activity overview
- **Scheduled Pulls**: Daily automated retrieval of message traces (configurable via UI)
- **Manual Pulls**: On-demand trace retrieval via API or web interface
- **Auto Domain Discovery**: Automatically detect organization domains from Microsoft 365 (optional)
- **Auto Domain Refresh**: Keeps domains up-to-date automatically with configurable intervals
- **Direction Classification**: Smart classification of emails as Inbound, Outbound, or Internal
- **Multi-Tenant Support**: Manage multiple Microsoft 365 tenants in one application
- **Configurable Settings**: Adjust pull schedules and domain refresh intervals from the UI
- **Secure Authentication**: Token-based API authentication with admin-only access
- **Modern UI**: Responsive React frontend with Tailwind CSS

## Architecture

```
exo-trace-archiver/
├── backend/                    # Django REST Framework API
│   ├── exo_trace_archiver/     # Django project settings
│   ├── traces/                 # Main application
│   │   ├── models.py           # MessageTraceLog, PullHistory
│   │   ├── views.py            # API endpoints
│   │   ├── tasks.py            # Pull task logic
│   │   ├── ms365_client.py     # Microsoft 365 integration
│   │   └── management/commands/
│   │       ├── pull_traces.py  # Manual pull command
│   │       └── run_scheduler.py # Scheduler daemon
│   └── requirements.txt
│
└── frontend/                   # React + TypeScript + Vite
    ├── src/
    │   ├── api/                # API client and types
    │   ├── components/         # Reusable UI components
    │   ├── hooks/              # React Query hooks
    │   └── pages/              # Page components
    └── package.json
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- Microsoft 365 tenant with Exchange Online
- Azure AD app registration with appropriate permissions

## Microsoft Entra ID (Azure AD) App Registration

### Step 1: Create App Registration

1. Go to [Azure Portal](https://portal.azure.com) > **Azure Active Directory** > **App registrations**
2. Click **New registration**
3. Enter a name (e.g., "Exo-Trace-Archiver")
4. Select **Accounts in this organizational directory only**
5. Click **Register**

### Step 2: Configure API Permissions

Navigate to **API permissions** and add the following:

**For Microsoft Graph API (Recommended):**
- `Reports.Read.All` (Application permission) - **Required** for message traces
- `Domain.Read.All` (Application permission) - **Optional** for automatic domain discovery

**For Exchange Online PowerShell (Fallback):**
- `Exchange.ManageAsApp` (Application permission)

After adding permissions, click **Grant admin consent**.

**Note:** `Domain.Read.All` is optional and only needed if you want to use the automatic domain discovery feature. See [DOMAIN_DISCOVERY.md](DOMAIN_DISCOVERY.md) for details.

### Step 3: Authentication Setup

#### Option A: Certificate Authentication (Recommended)

Certificate-based authentication is more secure for unattended/service scenarios.

**Windows (using included script):**

A PowerShell script is included to generate certificates easily:

```powershell
# Run from the project root directory
.\GenerateCert.ps1

# Or customize the output
.\GenerateCert.ps1 -OutputPath "C:\MyCerts" -CertName "MyApp" -Password "MyPassword123!"
```

This will generate:
- `ExoTraceArchiver.cer` - Public certificate (upload to Azure AD)
- `ExoTraceArchiver.pfx` - Private key + certificate (upload to Exo-Trace-Archiver)

**Linux/macOS:**

```bash
# Generate certificate
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 730 -nodes \
  -subj "/CN=ExoTraceArchiver"

# Convert to PFX (you'll be prompted for a password)
openssl pkcs12 -export -out ExoTraceArchiver.pfx -inkey key.pem -in cert.pem

# Get the thumbprint
openssl x509 -in cert.pem -noout -fingerprint -sha1 | sed 's/://g' | cut -d= -f2
```

**Upload certificates:**

1. **Azure AD App Registration:**
   - Go to **Certificates & secrets** > **Certificates**
   - Upload the `.cer` file (public certificate)
   - Note the **Thumbprint** displayed

2. **Exo-Trace-Archiver (per tenant):**
   - Go to **Admin** > **Tenants** > Edit tenant
   - Upload the `.pfx` file
   - Enter the **Certificate Thumbprint**
   - Enter the **Certificate Password** (the one used when creating the PFX)

3. Record these values:
   - **Tenant ID**: From Azure AD Overview page
   - **Client ID**: From Azure AD Overview page
   - **Certificate Thumbprint**: From Certificates & secrets

#### Option B: Client Secret (Simpler but Less Secure)

1. Go to **Certificates & secrets** > **Client secrets**
2. Click **New client secret**
3. Set an expiration and click **Add**
4. **Copy the secret value immediately** (it won't be shown again)

### Step 4: Exchange Online Configuration (for PowerShell method)

If using PowerShell instead of Graph API:

1. Connect to Exchange Online PowerShell as admin:
   ```powershell
   Connect-ExchangeOnline
   ```

2. Register the service principal:
   ```powershell
   New-ServicePrincipal -AppId <Your-Client-ID> -ServiceId <Your-Client-ID> -DisplayName "Exo-Trace-Archiver"
   ```

3. Assign the Exchange Administrator role:
   ```powershell
   Add-RoleGroupMember -Identity "Exchange Administrator" -Member <Your-Client-ID>
   ```

## Installation

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env  # or use your preferred editor
```

### Configure Environment Variables

Edit `backend/.env`:

```env
# Django
SECRET_KEY=your-secret-key-here  # Generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DEBUG=True  # Set to False in production
ALLOWED_HOSTS=localhost,127.0.0.1

# Microsoft 365
MS365_TENANT_ID=your-tenant-id
MS365_CLIENT_ID=your-client-id
MS365_AUTH_METHOD=certificate  # or 'secret'
MS365_API_METHOD=graph  # or 'powershell'

# For certificate auth
MS365_CERTIFICATE_PATH=/path/to/certificate.pem
MS365_CERTIFICATE_THUMBPRINT=ABC123...

# For secret auth
MS365_CLIENT_SECRET=your-client-secret

# Exchange organization (required for PowerShell)
MS365_ORGANIZATION=yourorg.onmicrosoft.com
```

### Initialize Database

```bash
# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install
```

## Running the Application

### Development Mode

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python manage.py runserver
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Access the application at http://localhost:5173

### Production Deployment

**Backend:**
```bash
# Install production server
pip install gunicorn

# Run with gunicorn
gunicorn exo_trace_archiver.wsgi:application --bind 0.0.0.0:8000
```

**Frontend:**
```bash
# Build for production
npm run build

# Serve the dist/ folder with nginx or similar
```

## Running the Scheduler

### Option 1: Built-in Scheduler (Simple)

```bash
python manage.py run_scheduler
```

This starts an in-process scheduler that runs daily pulls at 01:00 UTC.

### Option 2: Cron (Recommended for Production)

Add to crontab:
```bash
# Run daily at 01:00 UTC
0 1 * * * cd /path/to/backend && /path/to/venv/bin/python manage.py pull_traces >> /var/log/exo-trace.log 2>&1
```

### Option 3: Systemd Service

Create `/etc/systemd/system/exo-trace-scheduler.service`:
```ini
[Unit]
Description=Exo-Trace-Archiver Scheduler
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/venv/bin/python manage.py run_scheduler
Restart=always

[Install]
WantedBy=multi-user.target
```

## Manual Pull Commands

```bash
# Pull yesterday's traces (default)
python manage.py pull_traces

# Pull specific date range
python manage.py pull_traces --start-date 2024-01-01 --end-date 2024-01-07

# Pull last 7 days
python manage.py pull_traces --days 7

# Dry run (show what would be pulled)
python manage.py pull_traces --dry-run
```

## API Endpoints

### Authentication

Obtain an API token:
```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}'
```

Response:
```json
{"token": "abc123..."}
```

Use the token in subsequent requests:
```bash
curl -H "Authorization: Token abc123..." http://localhost:8000/api/traces/
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/traces/` | GET | List/search message traces |
| `/api/traces/<id>/` | GET | Get trace details |
| `/api/pull-history/` | GET | List pull history |
| `/api/manual-pull/` | POST | Trigger manual pull (admin only) |
| `/api/dashboard/` | GET | Dashboard statistics |
| `/api/config/` | GET | View configuration (admin only) |

### Query Parameters for `/api/traces/`

| Parameter | Description |
|-----------|-------------|
| `search` | Search in sender, recipient, subject |
| `start_date` | Filter by received date >= (ISO 8601) |
| `end_date` | Filter by received date <= (ISO 8601) |
| `sender` | Exact sender email |
| `sender_contains` | Sender contains |
| `recipient` | Exact recipient email |
| `status` | Delivery status (Delivered, Failed, etc.) |
| `direction` | Inbound, Outbound, Internal |
| `page` | Page number |
| `ordering` | Sort field (prefix with - for descending) |

## Extending the Application

### Switching to PostgreSQL

1. Install the PostgreSQL adapter:
   ```bash
   pip install psycopg2-binary
   ```

2. Update `.env`:
   ```env
   DATABASE_URL=postgres://user:password@localhost:5432/exo_trace_archiver
   ```

3. Run migrations:
   ```bash
   python manage.py migrate
   ```

### Adding CSV Export

The `/api/traces/export/` endpoint is stubbed for future implementation. To add CSV export:

1. Implement the export view in `traces/views.py`
2. Add appropriate rate limiting
3. Consider background processing for large exports

### Adding User Authentication

The current implementation uses Django's built-in authentication. To add more sophisticated user management:

1. Create a custom User model
2. Add user registration/invitation flow
3. Implement role-based permissions
4. Consider SSO integration with Azure AD

## Multi-Tenant Configuration

Exo-Trace-Archiver supports multiple Microsoft 365 tenants. Each tenant requires its own Azure AD app registration and certificate.

### Adding a New Tenant

1. **Create Azure AD App Registration** (see Step 1-3 above) in the target tenant
2. **Generate a certificate** using `GenerateCert.ps1` (use a unique name per tenant)
3. **Upload the `.cer`** to the Azure AD app registration
4. **In Exo-Trace-Archiver:**
   - Go to **Admin** > **Tenants** > **Add Tenant**
   - Enter the tenant name, Tenant ID, and Client ID
   - Select authentication method (Certificate recommended)
   - Upload the `.pfx` file
   - Enter the certificate thumbprint and password
   - Click **Test Connection** to verify

### Per-Tenant Settings

| Field | Description |
|-------|-------------|
| Name | Display name for the tenant |
| Tenant ID | Azure AD Directory (tenant) ID |
| Client ID | Azure AD Application (client) ID |
| Auth Method | Certificate or Client Secret |
| Certificate | The `.pfx` file with private key |
| Thumbprint | SHA-1 fingerprint of the certificate |
| Password | Password used when creating the PFX |
| API Method | Graph API (recommended) or PowerShell |
| Organization | Exchange organization domain (for PowerShell) |

## Troubleshooting

### Common Issues

**Authentication Errors:**
- Verify tenant ID and client ID are correct
- Ensure admin consent has been granted
- Check certificate thumbprint matches

**No Traces Returned:**
- Exchange Online only retains traces for 10 days
- Verify date range is within retention period
- Check if the organization has message trace data

**PowerShell Errors:**
- Ensure ExchangeOnlineManagement module is installed
- Verify PowerShell 7 is available (`pwsh` command)
- Check service principal has correct permissions

### Certificate Issues

**"Could not deserialize PKCS12 data":**
- The certificate password is incorrect or missing
- The PFX file may be corrupted
- Verify the password in tenant settings matches the one used when creating the PFX

**"Could not parse the provided public key":**
- The certificate file format is not supported
- Ensure you're uploading a `.pfx` file (not `.cer` or `.pem`)
- The `cryptography` library may need to be installed: `pip install cryptography`

**"Certificate file not found":**
- The uploaded certificate file was deleted or moved
- Re-upload the certificate in tenant settings

**Verifying a PFX file (Windows):**
```powershell
# Test if the PFX can be loaded with the password
certutil -dump "C:\path\to\certificate.pfx"
# You'll be prompted for the password
```

**Verifying a PFX file (Linux/macOS):**
```bash
# Test if the PFX can be loaded
openssl pkcs12 -info -in certificate.pfx -noout
# Enter the password when prompted
```

### Logs

Backend logs are stored in `backend/logs/exo_trace_archiver.log`

Enable debug logging in `.env`:
```env
DEBUG=True
```

## Important Notes

### Exchange Online Limitations

- Message traces are retained for only **10 days**
- The legacy Reporting Web Service is deprecated (sunset ~March 18, 2026)
- Microsoft Graph API message trace support is in **public preview** as of January 2026
- Use `Get-MessageTraceV2` cmdlet for PowerShell (replaces legacy `Get-MessageTrace`)

### Security Considerations

- Never commit `.env` or certificate files to version control
- Use certificate authentication for production
- Set `DEBUG=False` in production
- Use HTTPS in production
- Regularly rotate client secrets/certificates
- Implement proper backup for the database

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review Microsoft's Exchange Online documentation
