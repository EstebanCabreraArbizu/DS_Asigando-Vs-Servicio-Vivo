import os

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path, include
from django.views.generic import RedirectView
from django.views.i18n import JavaScriptCatalog

# Ruta del admin configurable por variable de entorno (Obs 7: ruta no predecible)
ADMIN_URL = os.getenv("DJANGO_ADMIN_URL", "panel-gestion").strip("/") + "/"

# Personalización del sitio admin (banner de advertencia)
admin.site.site_header = "PA vs SV — Panel de Administración"
admin.site.site_title = "PA vs SV Admin"
admin.site.index_title = "⚠ Acceso restringido. Actividad monitoreada."

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="dashboard:main", permanent=False)),
    # Endpoint jsi18n explícito ANTES de admin.site.urls para que no sea
    # interceptado por AdminIPRestrictionMiddleware vía Http404.
    # Django admin lo necesita para definir interpolate(), gettext(), ngettext(), etc.
    path(
        ADMIN_URL + "jsi18n/",
        staff_member_required(JavaScriptCatalog.as_view(), login_url=ADMIN_URL + "login/"),
        name="admin-jsi18n",
    ),
    path(ADMIN_URL, admin.site.urls),
    path("captcha/", include("captcha.urls")),  # django-simple-captcha image serving
    # path("api/v1/", include("api_v1.urls")),  # Moved to dashboard.urls
    path("dashboard/", include("dashboard.urls")),
]
