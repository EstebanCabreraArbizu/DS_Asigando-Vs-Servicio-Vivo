from django.urls import path

from jobs.views import JobCreateView, JobStatusView, JobDownloadExcelView

urlpatterns = [
    path("", JobCreateView.as_view()),
    path("<uuid:job_id>/status/", JobStatusView.as_view()),
    path("<uuid:job_id>/excel/", JobDownloadExcelView.as_view()),
]
