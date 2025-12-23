from django.urls import path, include

from api_v1.views import health

urlpatterns = [
    path("health/", health),
    path("jobs/", include("jobs.urls")),
]
