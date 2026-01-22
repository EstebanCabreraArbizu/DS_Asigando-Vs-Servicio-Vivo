from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard:main", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/v1/", include("api_v1.urls")),
    path("dashboard/", include("dashboard.urls")),
]
