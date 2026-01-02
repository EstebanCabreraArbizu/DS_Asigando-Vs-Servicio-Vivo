from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from api_v1.views import (
    health,
    CustomTokenObtainPairView,
    LogoutView,
    UserProfileView,
    ChangePasswordView,
    SwitchTenantView,
)

urlpatterns = [
    # Health check
    path("health/", health),
    
    # ==========================================================================
    # Authentication (JWT)
    # ==========================================================================
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    
    # ==========================================================================
    # User Profile & Settings
    # ==========================================================================
    path("users/me/", UserProfileView.as_view(), name="user_profile"),
    path("users/me/password/", ChangePasswordView.as_view(), name="change_password"),
    path("users/me/switch-tenant/", SwitchTenantView.as_view(), name="switch_tenant"),
    
    # ==========================================================================
    # Jobs API
    # ==========================================================================
    path("jobs/", include("jobs.urls")),
]
