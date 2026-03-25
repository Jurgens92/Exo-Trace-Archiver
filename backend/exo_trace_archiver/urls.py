"""
URL configuration for exo_trace_archiver project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from rest_framework.authtoken.views import obtain_auth_token

from .views import serve_frontend

urlpatterns = [
    path('admin/', admin.site.urls),
    # DRF token authentication endpoint
    path('api/auth/token/', obtain_auth_token, name='api_token_auth'),
    # Accounts app API endpoints (users, tenants, permissions)
    path('api/accounts/', include('accounts.urls')),
    # Traces app API endpoints
    path('api/', include('traces.urls')),
    # Serve React frontend for all non-API routes (SPA catch-all)
    re_path(r'^(?!api/|admin/|static/|media/).*$', serve_frontend, name='frontend'),
]
