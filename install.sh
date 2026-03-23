#!/bin/bash

################################################################################
# Exo-Trace-Archiver Installation Script for Ubuntu 24.04
#
# FULLY AUTOMATED - Zero interaction required!
#
# This script will:
# - Install all required dependencies
# - Clone and set up Exo-Trace-Archiver
# - Configure PostgreSQL database
# - Build and deploy the application
# - Set up Nginx to serve on port 80 (or 443 with HTTPS)
# - Optionally configure HTTPS with Let's Encrypt
# - Create systemd services for auto-start (backend + scheduler)
# - Create default admin account
#
# Usage:
#   Basic: sudo bash install.sh
#   With domain: PUBLIC_DOMAIN=yourdomain.com sudo -E bash install.sh
#   With HTTPS: PUBLIC_DOMAIN=yourdomain.com ENABLE_HTTPS=true ADMIN_EMAIL=admin@yourdomain.com sudo -E bash install.sh
#
# Environment Variables:
#   PUBLIC_DOMAIN - Your domain name or public IP (required for HTTPS)
#   ENABLE_HTTPS - Set to 'true' to enable HTTPS with Let's Encrypt (requires valid domain, not IP)
#   ADMIN_EMAIL - Admin email for Let's Encrypt notifications (recommended for HTTPS)
#
# Default admin credentials:
#   Username: admin
#   Password: Adm1n@Secure#2026!
#   (You should change this after first login!)
################################################################################

set -e  # Exit on any error
export DEBIAN_FRONTEND=noninteractive  # Non-interactive mode

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root (use sudo)"
    exit 1
fi

# Check Ubuntu version
log_info "Checking Ubuntu version..."
if ! grep -q "24.04" /etc/os-release; then
    log_warning "This script is designed for Ubuntu 24.04. You are running a different version."
    log_warning "Installation will continue, but some features may not work as expected."
fi

# Configuration
INSTALL_DIR="/opt/exo-trace-archiver"
DB_NAME="exo_trace_archiver"
DB_USER="exo_trace_archiver"
DB_PASSWORD=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 64)
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="Adm1n@Secure#2026!"
USER_PROVIDED_EMAIL="$ADMIN_EMAIL"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@exo-trace-archiver.local}"
GITHUB_REPO="https://github.com/Jurgens92/Exo-Trace-Archiver.git"

# Auto-detect server IP (private)
DETECTED_IP=$(hostname -I | awk '{print $1}')
if [ -z "$DETECTED_IP" ]; then
    DETECTED_IP="localhost"
fi

# Get public IP/domain from environment variable or use detected IP
if [ -z "$PUBLIC_DOMAIN" ]; then
    log_info "Detected private IP: $DETECTED_IP"
    log_warning "If you're accessing this server from outside your network, you need to specify the public IP or domain."
    log_info "You can set it via environment variable: PUBLIC_DOMAIN=your.domain.com sudo -E bash install.sh"
    log_info "Using detected IP: $DETECTED_IP"
    DOMAIN="$DETECTED_IP"
else
    log_info "Using public domain/IP: $PUBLIC_DOMAIN"
    DOMAIN="$PUBLIC_DOMAIN"
fi

# Check if HTTPS should be enabled
USE_HTTPS=false
if [ "$ENABLE_HTTPS" = "true" ]; then
    # Validate that DOMAIN is not an IP address (Let's Encrypt requires a domain)
    if [[ $DOMAIN =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "HTTPS requires a valid domain name, not an IP address."
        log_error "Please set PUBLIC_DOMAIN to a domain name that points to this server."
        exit 1
    fi
    log_info "HTTPS will be enabled for domain: $DOMAIN"
    USE_HTTPS=true
else
    log_info "HTTPS not enabled. Set ENABLE_HTTPS=true to enable SSL/TLS."
fi

log_info "Starting Exo-Trace-Archiver installation..."
echo "========================================"

# Update system
log_info "Updating system packages..."
apt-get update
apt-get upgrade -y

# Install system dependencies
log_info "Installing system dependencies..."
PACKAGES="python3.12 python3.12-venv python3-pip postgresql postgresql-contrib nginx git curl build-essential libpq-dev python3-dev"

# Add certbot if HTTPS is enabled
if [ "$USE_HTTPS" = "true" ]; then
    log_info "HTTPS enabled - adding certbot to installation"
    PACKAGES="$PACKAGES certbot python3-certbot-nginx"
fi

apt-get install -y $PACKAGES

log_success "System dependencies installed"

# Install PowerShell 7 (required for Exchange Online PowerShell fallback)
log_info "Installing PowerShell 7..."
if ! command -v pwsh &> /dev/null; then
    # Get Ubuntu version codename
    UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "noble")

    # Download and register the Microsoft repository GPG keys
    curl -fsSL https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/packages-microsoft-prod.deb -o /tmp/packages-microsoft-prod.deb
    dpkg -i /tmp/packages-microsoft-prod.deb
    rm -f /tmp/packages-microsoft-prod.deb

    apt-get update
    apt-get install -y powershell

    if command -v pwsh &> /dev/null; then
        log_success "PowerShell $(pwsh --version) installed"

        # Install ExchangeOnlineManagement module for PowerShell
        log_info "Installing ExchangeOnlineManagement PowerShell module..."
        pwsh -NoProfile -NonInteractive -Command "
            Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
            Install-Module -Name ExchangeOnlineManagement -Scope AllUsers -Force -AllowClobber
        "
        if [ $? -eq 0 ]; then
            log_success "ExchangeOnlineManagement module installed"
        else
            log_warning "Failed to install ExchangeOnlineManagement module."
            log_warning "PowerShell fallback for Exchange Online will not work until installed."
            log_warning "You can install it manually: pwsh -Command 'Install-Module ExchangeOnlineManagement -Scope AllUsers -Force'"
        fi
    else
        log_warning "PowerShell installation failed. Exchange Online PowerShell fallback will not be available."
        log_warning "The application will use Microsoft Graph API instead (recommended)."
    fi
else
    log_success "PowerShell already installed: $(pwsh --version)"
fi

# Install Node.js 20.x (LTS)
log_info "Installing Node.js 20.x..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
log_success "Node.js $(node --version) and npm $(npm --version) installed"

# Configure PostgreSQL
log_info "Configuring PostgreSQL database..."
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || log_warning "User $DB_USER already exists"
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null || log_warning "Database $DB_NAME already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -c "ALTER USER $DB_USER CREATEDB;" # For running tests
log_success "PostgreSQL database configured"

# Clone repository
log_info "Cloning Exo-Trace-Archiver repository..."
if [ -d "$INSTALL_DIR" ]; then
    log_warning "Installation directory already exists. Backing up to ${INSTALL_DIR}.backup"
    mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%s)"
fi

git clone "$GITHUB_REPO" "$INSTALL_DIR"
cd "$INSTALL_DIR"
log_success "Repository cloned to $INSTALL_DIR"

# Set up Python virtual environment
log_info "Setting up Python virtual environment..."
cd "$INSTALL_DIR/backend"
python3.12 -m venv venv
source venv/bin/activate

# Install Python dependencies
log_info "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install psycopg2-binary gunicorn
log_success "Python dependencies installed"

# Create backend .env file
log_info "Creating backend environment configuration..."
cat > "$INSTALL_DIR/backend/.env" <<EOF
# Django Settings
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$DOMAIN,localhost,127.0.0.1

# Database (PostgreSQL)
DATABASE_URL=postgres://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME

# CORS - Restrict to deployment origin for security
CORS_ALLOWED_ORIGINS=http://$DOMAIN

# HTTPS - will be enabled after SSL certificate is obtained
SECURE_SSL_REDIRECT=False

# Microsoft 365 / Exchange Online Configuration
# Authentication method: 'certificate' (preferred) or 'secret'
MS365_TENANT_ID=
MS365_CLIENT_ID=
MS365_AUTH_METHOD=certificate
MS365_CLIENT_SECRET=
MS365_CERTIFICATE_PATH=
MS365_CERTIFICATE_THUMBPRINT=
MS365_CERTIFICATE_PASSWORD=

# API method: 'graph' (preferred) or 'powershell'
MS365_API_METHOD=graph
MS365_ORGANIZATION=

# Message trace configuration
MESSAGE_TRACE_LOOKBACK_DAYS=1
MESSAGE_TRACE_PAGE_SIZE=1000
MESSAGE_TRACE_MAX_RECORDS=50000

# Scheduler (daily pull time in UTC)
DAILY_PULL_HOUR=1
DAILY_PULL_MINUTE=0
EOF

chmod 600 "$INSTALL_DIR/backend/.env"
log_success "Backend environment configured"

# Create logs directory
mkdir -p "$INSTALL_DIR/backend/logs"

# Create certificates directory
mkdir -p "$INSTALL_DIR/backend/certificates"
chmod 700 "$INSTALL_DIR/backend/certificates"

# Run Django migrations
log_info "Running database migrations..."
python manage.py makemigrations
python manage.py migrate
log_success "Database migrations completed"

# Create Django superuser (non-interactive)
log_info "Creating Django superuser..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$ADMIN_USERNAME').exists():
    user = User.objects.create_superuser(
        username='$ADMIN_USERNAME',
        email='$ADMIN_EMAIL',
        password='$ADMIN_PASSWORD'
    )
    print('Superuser created successfully')
else:
    print('Superuser already exists')
"
log_success "Superuser created: $ADMIN_USERNAME"

# Collect static files
log_info "Collecting Django static files..."
python manage.py collectstatic --noinput
log_success "Static files collected"

deactivate

# Set up frontend
log_info "Setting up frontend..."
cd "$INSTALL_DIR/frontend"

# Create frontend .env file
# Set VITE_API_URL to empty string so the frontend uses window.location.origin
# This makes the frontend automatically use the same domain/IP it's accessed from
cat > "$INSTALL_DIR/frontend/.env" <<EOF
VITE_API_URL=
EOF

log_info "Installing frontend dependencies..."
npm install

log_info "Building frontend..."
npm run build
log_success "Frontend built successfully"

# Install gunicorn if not already installed
log_info "Installing gunicorn..."
source "$INSTALL_DIR/backend/venv/bin/activate"
pip install gunicorn
deactivate

# Create systemd service for backend
log_info "Creating systemd service for Django backend..."
cat > /etc/systemd/system/exo-trace-backend.service <<EOF
[Unit]
Description=Exo-Trace-Archiver Django Backend
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/backend
Environment="PATH=$INSTALL_DIR/backend/venv/bin"
ExecStart=$INSTALL_DIR/backend/venv/bin/gunicorn exo_trace_archiver.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for scheduler
log_info "Creating systemd service for scheduler..."
cat > /etc/systemd/system/exo-trace-scheduler.service <<EOF
[Unit]
Description=Exo-Trace-Archiver Scheduler (Daily Trace Pulls)
After=network.target postgresql.service exo-trace-backend.service

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR/backend
Environment="PATH=$INSTALL_DIR/backend/venv/bin"
ExecStart=$INSTALL_DIR/backend/venv/bin/python manage.py run_scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Configure Nginx
log_info "Configuring Nginx..."
cat > /etc/nginx/sites-available/exo-trace-archiver <<'NGINX_EOF'
server {
    listen 80;
    server_name SERVER_NAME_PLACEHOLDER;
    client_max_body_size 100M;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Frontend - serve built React app
    location / {
        root INSTALL_DIR_PLACEHOLDER/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django Admin
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django Static Files
    location /static/ {
        alias INSTALL_DIR_PLACEHOLDER/backend/staticfiles/;
    }

    # Django Media Files
    location /media/ {
        alias INSTALL_DIR_PLACEHOLDER/backend/media/;
    }
}
NGINX_EOF

# Replace placeholders
sed -i "s|SERVER_NAME_PLACEHOLDER|$DOMAIN|g" /etc/nginx/sites-available/exo-trace-archiver
sed -i "s|INSTALL_DIR_PLACEHOLDER|$INSTALL_DIR|g" /etc/nginx/sites-available/exo-trace-archiver

# Enable Nginx site
ln -sf /etc/nginx/sites-available/exo-trace-archiver /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
log_info "Testing Nginx configuration..."
nginx -t

# Start services before certbot (certbot needs nginx running)
log_info "Starting services..."
systemctl daemon-reload
systemctl enable exo-trace-backend
systemctl enable exo-trace-scheduler
systemctl start exo-trace-backend
systemctl start exo-trace-scheduler
systemctl restart nginx

# Configure HTTPS with Let's Encrypt if enabled
if [ "$USE_HTTPS" = "true" ]; then
    log_info "Configuring HTTPS with Let's Encrypt..."
    log_warning "Make sure your domain $DOMAIN points to this server's public IP!"
    log_info "Certbot will automatically configure SSL and set up auto-renewal"

    # Determine admin email for Let's Encrypt
    if [ -z "$USER_PROVIDED_EMAIL" ]; then
        CERT_EMAIL="$ADMIN_EMAIL"
        log_warning "No ADMIN_EMAIL provided, using default: $CERT_EMAIL"
        log_warning "Let's Encrypt renewal warnings will be sent to this email."
        log_info "For production, set ADMIN_EMAIL environment variable for Let's Encrypt notifications"
    else
        CERT_EMAIL="$ADMIN_EMAIL"
    fi

    # Run certbot
    log_info "Running certbot for domain: $DOMAIN with email: $CERT_EMAIL"
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$CERT_EMAIL" --redirect

    if [ $? -eq 0 ]; then
        log_success "SSL certificate obtained and configured successfully!"
        log_info "Certbot will automatically renew certificates before they expire"
        PROTOCOL="https"

        # Now that HTTPS is confirmed working, enable SSL settings in backend .env
        log_info "Enabling HTTPS settings in backend configuration..."
        sed -i 's/^SECURE_SSL_REDIRECT=False$/SECURE_SSL_REDIRECT=True/' "$INSTALL_DIR/backend/.env"

        # Update CORS origin to HTTPS now that SSL is confirmed working
        sed -i "s|^CORS_ALLOWED_ORIGINS=http://$DOMAIN$|CORS_ALLOWED_ORIGINS=https://$DOMAIN|" "$INSTALL_DIR/backend/.env"

        # Add CSRF_TRUSTED_ORIGINS for the HTTPS domain (required by Django 4+)
        echo "" >> "$INSTALL_DIR/backend/.env"
        echo "# CSRF trusted origins for HTTPS" >> "$INSTALL_DIR/backend/.env"
        echo "CSRF_TRUSTED_ORIGINS=https://$DOMAIN" >> "$INSTALL_DIR/backend/.env"

        # Restart backend to pick up HTTPS settings
        systemctl restart exo-trace-backend
    else
        log_error "Failed to obtain SSL certificate. Check that:"
        log_error "  1. Domain $DOMAIN points to this server's public IP"
        log_error "  2. Port 80 is accessible from the internet"
        log_error "  3. No firewall is blocking the connection"
        log_warning "Continuing with HTTP only..."
        PROTOCOL="http"
    fi
else
    PROTOCOL="http"
fi

# Restart nginx after certbot modifications
systemctl restart nginx

log_success "Services started and enabled"

# Check service status
sleep 3
if systemctl is-active --quiet exo-trace-backend; then
    log_success "Exo-Trace-Archiver backend is running"
else
    log_error "Backend failed to start. Check logs with: journalctl -u exo-trace-backend -n 50"
fi

if systemctl is-active --quiet exo-trace-scheduler; then
    log_success "Exo-Trace-Archiver scheduler is running"
else
    log_error "Scheduler failed to start. Check logs with: journalctl -u exo-trace-scheduler -n 50"
fi

if systemctl is-active --quiet nginx; then
    log_success "Nginx is running"
else
    log_error "Nginx failed to start. Check logs with: journalctl -u nginx -n 50"
fi

# Final summary
echo ""
echo "========================================"
log_success "Exo-Trace-Archiver installation completed!"
echo "========================================"
echo ""
log_info "Installation Summary:"
echo "  - Installation directory: $INSTALL_DIR"
echo "  - Database: PostgreSQL ($DB_NAME)"
echo "  - Application URL: $PROTOCOL://$DOMAIN"
if [ "$USE_HTTPS" = "true" ] && [ "$PROTOCOL" = "https" ]; then
    echo "  - HTTPS: Enabled (Let's Encrypt SSL certificate configured)"
    echo "  - Auto-renewal: Enabled (certbot timer running)"
fi
echo ""
log_info "Database Credentials (save these securely):"
echo "  - Database: $DB_NAME"
echo "  - Username: $DB_USER"
echo "  - Password: $DB_PASSWORD"
echo ""
log_info "Admin Account:"
echo "  - Username: $ADMIN_USERNAME"
echo "  - Password: $ADMIN_PASSWORD"
echo "  - IMPORTANT: Change this password after first login!"
echo ""
log_info "Services:"
echo "  - exo-trace-backend  : Django API server (gunicorn on port 8000)"
echo "  - exo-trace-scheduler: Automated daily trace pulls"
echo "  - nginx              : Reverse proxy and frontend"
echo ""
log_info "Useful Commands:"
echo "  - View backend logs:   journalctl -u exo-trace-backend -f"
echo "  - View scheduler logs: journalctl -u exo-trace-scheduler -f"
echo "  - View nginx logs:     tail -f /var/log/nginx/error.log"
echo "  - Restart backend:     systemctl restart exo-trace-backend"
echo "  - Restart scheduler:   systemctl restart exo-trace-scheduler"
echo "  - Restart nginx:       systemctl restart nginx"
echo ""
log_info "Next Steps:"
echo "  1. Open $PROTOCOL://$DOMAIN in your browser"
echo "  2. Log in with:"
echo "     - Username: $ADMIN_USERNAME"
echo "     - Password: $ADMIN_PASSWORD"
echo "  3. Change your admin password immediately!"
echo "  4. Configure your Microsoft 365 tenant under Tenants page"
echo "     (or edit $INSTALL_DIR/backend/.env with your MS365 credentials)"
if [ "$USE_HTTPS" = "true" ] && [ "$PROTOCOL" = "https" ]; then
    echo "  5. Upload your Azure AD certificate to $INSTALL_DIR/backend/certificates/"
    echo "  6. Start using Exo-Trace-Archiver!"
else
    echo "  5. Upload your Azure AD certificate to $INSTALL_DIR/backend/certificates/"
    echo "  6. Start using Exo-Trace-Archiver!"
fi
echo ""
log_warning "Important: Save these credentials in a secure location!"
echo ""

# Save credentials to file
CREDENTIALS_FILE="$INSTALL_DIR/installation_credentials.txt"
cat > "$CREDENTIALS_FILE" <<EOF
Exo-Trace-Archiver Installation Credentials
Generated: $(date)

Application URL: $PROTOCOL://$DOMAIN
$(if [ "$USE_HTTPS" = "true" ] && [ "$PROTOCOL" = "https" ]; then echo "HTTPS: Enabled (Let's Encrypt)"; fi)

Database Credentials:
  Database: $DB_NAME
  Username: $DB_USER
  Password: $DB_PASSWORD

Admin Account:
  Username: $ADMIN_USERNAME
  Password: $ADMIN_PASSWORD
  IMPORTANT: Change this password after first login!

Backend .env location: $INSTALL_DIR/backend/.env
Certificates directory: $INSTALL_DIR/backend/certificates/
EOF

chmod 600 "$CREDENTIALS_FILE"
echo ""
log_success "All credentials have been saved to: $CREDENTIALS_FILE"
echo ""
