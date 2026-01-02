"""
Serializers para la API v1, incluyendo JWT customizado.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from tenants.models import Membership, Tenant

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer JWT personalizado que incluye información adicional en el token:
    - tenant_id: ID del tenant activo
    - tenant_slug: Slug del tenant activo
    - role: Rol del usuario en el tenant
    - permissions: Lista de permisos basados en el rol
    """
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Obtener membership del usuario
        membership = self._get_active_membership()
        
        if membership:
            # Agregar info del tenant a la respuesta
            data["tenant"] = {
                "id": str(membership.tenant.id),
                "slug": membership.tenant.slug,
                "name": membership.tenant.name,
            }
            data["role"] = membership.role
            data["permissions"] = self._get_role_permissions(membership.role)
        else:
            data["tenant"] = None
            data["role"] = None
            data["permissions"] = []
        
        # Info del usuario
        data["user"] = {
            "id": self.user.id,
            "username": self.user.username,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "is_superuser": self.user.is_superuser,
        }
        
        return data
    
    def _get_active_membership(self) -> Membership | None:
        """Obtiene el membership activo del usuario."""
        # Primero intentar el default
        membership = self.user.memberships.filter(
            is_default=True,
            tenant__is_active=True
        ).select_related("tenant").first()
        
        if not membership:
            # Si no hay default, usar el primero
            membership = self.user.memberships.filter(
                tenant__is_active=True
            ).select_related("tenant").first()
        
        return membership
    
    def _get_role_permissions(self, role: str) -> list[str]:
        """Retorna lista de permisos basados en el rol."""
        permissions = {
            "owner": [
                "tenant.manage",
                "users.manage",
                "files.upload",
                "files.delete",
                "files.download",
                "analysis.view",
                "analysis.export",
                "audit.view",
            ],
            "admin": [
                "users.manage",
                "files.upload",
                "files.delete",
                "files.download",
                "analysis.view",
                "analysis.export",
                "audit.view",
            ],
            "coordinator": [
                "files.upload",
                "files.delete",
                "files.download",
                "analysis.view",
                "analysis.export",
            ],
            "analyst": [
                "files.download",
                "analysis.view",
                "analysis.export",
            ],
            "viewer": [
                "analysis.view",
            ],
        }
        return permissions.get(role, [])

    @classmethod
    def get_token(cls, user):
        """Override para agregar claims personalizados al token JWT."""
        token = super().get_token(user)
        
        # Agregar claims al token
        membership = user.memberships.filter(
            is_default=True,
            tenant__is_active=True
        ).select_related("tenant").first()
        
        if not membership:
            membership = user.memberships.filter(
                tenant__is_active=True
            ).select_related("tenant").first()
        
        if membership:
            token["tenant_id"] = str(membership.tenant.id)
            token["tenant_slug"] = membership.tenant.slug
            token["role"] = membership.role
        
        token["username"] = user.username
        token["email"] = user.email
        
        return token


class TenantSerializer(serializers.ModelSerializer):
    """Serializer para información de tenant."""
    
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class MembershipSerializer(serializers.ModelSerializer):
    """Serializer para memberships de usuario."""
    tenant = TenantSerializer(read_only=True)
    
    class Meta:
        model = Membership
        fields = ["id", "tenant", "role", "is_default", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer para perfil de usuario con sus memberships."""
    memberships = MembershipSerializer(many=True, read_only=True)
    
    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "is_active", "date_joined", "memberships"
        ]
        read_only_fields = ["id", "date_joined"]


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer para cambio de contraseña."""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=10)
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Las contraseñas no coinciden."
            })
        return attrs
    
    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Contraseña actual incorrecta.")
        return value


class SwitchTenantSerializer(serializers.Serializer):
    """Serializer para cambiar de tenant activo."""
    tenant_id = serializers.UUIDField(required=False)
    tenant_slug = serializers.SlugField(required=False)
    
    def validate(self, attrs):
        if not attrs.get("tenant_id") and not attrs.get("tenant_slug"):
            raise serializers.ValidationError(
                "Debe proporcionar tenant_id o tenant_slug."
            )
        return attrs
