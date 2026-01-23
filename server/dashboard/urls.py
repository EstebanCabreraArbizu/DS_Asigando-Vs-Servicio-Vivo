"""
Dashboard URLs - Rutas para el dashboard de métricas y visualización.
"""
from django.urls import path, include
from . import views

app_name = "dashboard"

urlpatterns = [
    # Autenticación personalizada
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    
    # Vista principal del dashboard
    path("", views.DashboardView.as_view(), name="main"),
    
    # Vista de upload con drag & drop
    path("upload/", views.UploadView.as_view(), name="upload"),
    
    # API endpoints para métricas
    path("api/metrics/", views.MetricsAPIView.as_view(), name="api_metrics"),
    path("api/periods/", views.PeriodsAPIView.as_view(), name="api_periods"),
    path("api/compare/", views.CompareAPIView.as_view(), name="api_compare"),
    path("api/details/", views.DetailsAPIView.as_view(), name="api_details"),
    
    # API endpoints para tablas paginadas
    path("api/clients/", views.ClientsAPIView.as_view(), name="api_clients"),
    path("api/units/", views.UnitsAPIView.as_view(), name="api_units"),
    path("api/services/", views.ServicesAPIView.as_view(), name="api_services"),
    
    # API endpoints del core (Jobs, etc) montados bajo dashboard
    path("api/v1/", include("api_v1.urls")),
]
