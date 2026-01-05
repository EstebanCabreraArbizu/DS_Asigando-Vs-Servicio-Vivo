from django.urls import path

app_name = "jobs"

from jobs.views import (
    JobCreateView,
    JobStatusView,
    JobDeleteView,
    JobDownloadExcelView,
    JobLatestDownloadView,
    JobListView,
)

urlpatterns = [
    # Listado de jobs (GET) y crear job (POST)
    path("", JobListView.as_view(), name="job_list"),
    
    # Crear job (alternativo)
    path("create/", JobCreateView.as_view(), name="job_create"),
    
    # Último job exitoso
    path("latest/download/", JobLatestDownloadView.as_view(), name="job_latest_download"),
    
    # Operaciones por job ID
    path("<uuid:job_id>/", JobDeleteView.as_view(), name="job_delete"),
    path("<uuid:job_id>/status/", JobStatusView.as_view(), name="job_status"),
    path("<uuid:job_id>/excel/", JobDownloadExcelView.as_view(), name="job_download_excel"),
]
