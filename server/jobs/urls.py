from django.urls import path

from jobs.views import JobCreateView, JobStatusView, JobDownloadExcelView, JobLatestDownloadView

urlpatterns = [
    path("", JobCreateView.as_view()),
    path("latest/download/", JobLatestDownloadView.as_view()),
    path("<uuid:job_id>/status/", JobStatusView.as_view()),
    path("<uuid:job_id>/excel/", JobDownloadExcelView.as_view()),
]
