from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Tenant(models.Model):
    """
    Representa una organización/cliente en el sistema multi-tenant.
    Cada tenant tiene sus propios datos aislados (jobs, artifacts, snapshots).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=100, unique=True, help_text="Identificador URL-safe")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class MembershipRole(models.TextChoices):
    """
    Roles disponibles para usuarios en un tenant.
    
    Permisos por rol:
    - OWNER: Control total del tenant (gestión de usuarios, configuración, todo)
    - ADMIN: Administración de usuarios y archivos (similar a owner pero sin eliminar tenant)
    - COORDINATOR: Gestión de archivos Excel (subir, modificar, eliminar, exportar)
    - ANALYST: Análisis de datos (ver dashboard, exportar reportes)
    - VIEWER: Solo lectura (ver dashboard sin exportar)
    """
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    COORDINATOR = "coordinator", "Coordinador"
    ANALYST = "analyst", "Analyst"
    VIEWER = "viewer", "Viewer"


class Membership(models.Model):
    """
    Asociación Usuario <-> Tenant con rol.
    Un usuario puede pertenecer a múltiples tenants con diferentes roles.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships"
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=MembershipRole.choices, default=MembershipRole.VIEWER)
    is_default = models.BooleanField(default=False, help_text="Tenant por defecto al iniciar sesión")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Campos de auditoría
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations_sent",
        help_text="Usuario que invitó a este miembro"
    )

    class Meta:
        unique_together = [("user", "tenant")]
        ordering = ["-is_default", "tenant__name"]

    def __str__(self) -> str:
        return f"{self.user.username} @ {self.tenant.name} ({self.role})"
    
    def can_upload_files(self) -> bool:
        """Verifica si el usuario puede subir archivos."""
        return self.role in [
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.COORDINATOR,
        ]
    
    def can_delete_files(self) -> bool:
        """Verifica si el usuario puede eliminar archivos."""
        return self.role in [
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        ]
    
    def can_export_data(self) -> bool:
        """Verifica si el usuario puede exportar datos."""
        return self.role in [
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.COORDINATOR,
            MembershipRole.ANALYST,
        ]
    
    def can_manage_users(self) -> bool:
        """Verifica si el usuario puede gestionar otros usuarios."""
        return self.role in [
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
        ]
