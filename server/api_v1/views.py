"""
Views para la API v1 - Autenticación y perfil de usuario.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from api_v1.serializers import (
    CustomTokenObtainPairSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    SwitchTenantSerializer,
    MembershipSerializer,
)
from tenants.models import Membership, Tenant

User = get_user_model()


def health(_request):
    """Health check endpoint - returns {"status": "ok"}"""
    return JsonResponse({"status": "ok"})


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Login endpoint que retorna JWT access/refresh tokens.
    
    POST /api/v1/auth/login/
    {
        "username": "usuario",
        "password": "contraseña"
    }
    
    Response:
    {
        "access": "eyJ...",
        "refresh": "eyJ...",
        "user": {...},
        "tenant": {...},
        "role": "coordinator",
        "permissions": [...]
    }
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """
    Logout endpoint que invalida el refresh token.
    
    POST /api/v1/auth/logout/
    {
        "refresh": "eyJ..."
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response(
                {"message": "Sesión cerrada exitosamente"},
                status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {"error": {"code": "invalid_token", "message": "Token inválido"}},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserProfileView(APIView):
    """
    Obtiene o actualiza el perfil del usuario autenticado.
    
    GET /api/v1/users/me/
    PATCH /api/v1/users/me/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """
    Permite al usuario cambiar su contraseña.
    
    POST /api/v1/users/me/password/
    {
        "old_password": "actual",
        "new_password": "nueva",
        "confirm_password": "nueva"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        
        return Response({"message": "Contraseña actualizada exitosamente"})


class SwitchTenantView(APIView):
    """
    Cambia el tenant activo del usuario.
    Retorna nuevos tokens JWT con el tenant actualizado.
    
    POST /api/v1/users/me/switch-tenant/
    {
        "tenant_id": "uuid" or "tenant_slug": "slug"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = SwitchTenantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Buscar el tenant
        tenant_id = serializer.validated_data.get("tenant_id")
        tenant_slug = serializer.validated_data.get("tenant_slug")
        
        try:
            if tenant_id:
                tenant = Tenant.objects.get(id=tenant_id, is_active=True)
            else:
                tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Tenant.DoesNotExist:
            return Response(
                {"error": {"code": "tenant_not_found", "message": "Tenant no encontrado"}},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar que el usuario tenga membership
        try:
            membership = Membership.objects.get(
                user=request.user,
                tenant=tenant
            )
        except Membership.DoesNotExist:
            return Response(
                {"error": {"code": "access_denied", "message": "No tienes acceso a este tenant"}},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Actualizar memberships: quitar default de otros, poner en este
        Membership.objects.filter(user=request.user).update(is_default=False)
        membership.is_default = True
        membership.save()
        
        # Generar nuevos tokens con el tenant actualizado
        refresh = RefreshToken.for_user(request.user)
        
        # Agregar claims del tenant
        refresh["tenant_id"] = str(tenant.id)
        refresh["tenant_slug"] = tenant.slug
        refresh["role"] = membership.role
        
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "tenant": {
                "id": str(tenant.id),
                "slug": tenant.slug,
                "name": tenant.name,
            },
            "role": membership.role,
            "message": f"Cambiado a tenant: {tenant.name}"
        })
