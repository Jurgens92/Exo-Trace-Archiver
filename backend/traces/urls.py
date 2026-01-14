"""
URL routing for the traces app API endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router for viewsets
router = DefaultRouter()
router.register(r'traces', views.MessageTraceLogViewSet, basename='traces')
router.register(r'pull-history', views.PullHistoryViewSet, basename='pull-history')

urlpatterns = [
    # ViewSet routes (traces/, pull-history/)
    path('', include(router.urls)),

    # Custom API views
    path('manual-pull/', views.ManualPullView.as_view(), name='manual-pull'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('config/', views.ConfigView.as_view(), name='config'),
    path('discover-domains/', views.DiscoverDomainsView.as_view(), name='discover-domains'),
]
