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
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
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

    class Meta:
        unique_together = [("user", "tenant")]
        ordering = ["-is_default", "tenant__name"]

    def __str__(self) -> str:
        return f"{self.user.username} @ {self.tenant.name} ({self.role})"
