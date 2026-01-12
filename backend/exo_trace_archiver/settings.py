"""
Django settings for exo_trace_archiver project.

This project provides a web interface and API for archiving Microsoft 365
Exchange Online message trace logs. It uses Microsoft Graph API (preferred)
or Exchange Online PowerShell for retrieving message traces.

Security Note: All sensitive credentials are loaded from environment variables.
Never commit .env files or secrets to version control.
"""

import os
from pathlib import Path
from datetime import timedelta

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize django-environ
env = environ.Env(
    # Set default values and casting
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
    CORS_ALLOWED_ORIGINS=(list, ['http://localhost:5173', 'http://127.0.0.1:5173']),
)

# Read .env file if it exists
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-this-in-production-use-strong-random-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_filters',
    # Local apps
    'accounts.apps.AccountsConfig',
    'traces.apps.TracesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # Must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'exo_trace_archiver.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'exo_trace_archiver.wsgi.application'

# Database
# Using SQLite for simplicity. For production, consider PostgreSQL.
# To switch to PostgreSQL later:
# 1. Install psycopg2-binary
# 2. Update DATABASE_URL in .env: postgres://user:password@localhost:5432/dbname
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}')
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (uploaded files like certificates)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Create certificates directory (more restrictive location for sensitive files)
CERTIFICATES_DIR = BASE_DIR / 'certificates'
CERTIFICATES_DIR.mkdir(exist_ok=True)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Configuration
# Required for React frontend to communicate with Django API
CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS')
CORS_ALLOW_CREDENTIALS = True

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'manual_pull': '10/hour',  # Limit manual pulls to prevent abuse
    },
}

# =============================================================================
# Microsoft 365 / Exchange Online Configuration
# =============================================================================
#
# Authentication Methods (in order of preference):
# 1. Microsoft Graph API (public preview as of Jan 2026) - Recommended
# 2. Exchange Online PowerShell with certificate authentication
# 3. Exchange Online PowerShell with client secret (less secure)
#
# Required Azure AD App Registration Permissions:
# - For Graph API: Reports.Read.All (Application permission)
# - For PowerShell: Exchange.ManageAsApp (Application permission)
#
# Certificate-based auth is preferred for unattended/script scenarios.
# =============================================================================

# Azure AD / Microsoft Entra ID App Registration
MS365_TENANT_ID = env('MS365_TENANT_ID', default='')
MS365_CLIENT_ID = env('MS365_CLIENT_ID', default='')

# Authentication method: 'certificate' (preferred) or 'secret'
MS365_AUTH_METHOD = env('MS365_AUTH_METHOD', default='certificate')

# For client secret authentication (less secure, not recommended for production)
MS365_CLIENT_SECRET = env('MS365_CLIENT_SECRET', default='')

# For certificate authentication (recommended)
# Path to the .pfx or .pem certificate file
MS365_CERTIFICATE_PATH = env('MS365_CERTIFICATE_PATH', default='')
# Certificate thumbprint (required for Exchange Online PowerShell)
MS365_CERTIFICATE_THUMBPRINT = env('MS365_CERTIFICATE_THUMBPRINT', default='')
# Certificate private key password (if the certificate is password-protected)
MS365_CERTIFICATE_PASSWORD = env('MS365_CERTIFICATE_PASSWORD', default='')

# API method: 'graph' (preferred, in preview) or 'powershell' (fallback)
MS365_API_METHOD = env('MS365_API_METHOD', default='graph')

# Exchange organization name (for PowerShell connection)
MS365_ORGANIZATION = env('MS365_ORGANIZATION', default='')

# Message trace configuration
# Default lookback period in days (Exchange Online keeps traces for 10 days)
MESSAGE_TRACE_LOOKBACK_DAYS = env.int('MESSAGE_TRACE_LOOKBACK_DAYS', default=1)

# Maximum records per API call (Graph API limit is 1000)
MESSAGE_TRACE_PAGE_SIZE = env.int('MESSAGE_TRACE_PAGE_SIZE', default=1000)

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'exo_trace_archiver.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'traces': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
(BASE_DIR / 'logs').mkdir(exist_ok=True)

# Scheduled task configuration
# The daily pull runs at 01:00 UTC to get yesterday's message traces
DAILY_PULL_HOUR = env.int('DAILY_PULL_HOUR', default=1)
DAILY_PULL_MINUTE = env.int('DAILY_PULL_MINUTE', default=0)
