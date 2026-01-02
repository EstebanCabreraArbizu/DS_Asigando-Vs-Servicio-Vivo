"""
Permisos personalizados para el sistema PA vs SV.

Define quién puede realizar qué acciones basándose en:
- Rol del usuario en el tenant (owner, admin, coordinator, analyst, viewer)
- Tipo de operación (CRUD sobre jobs, archivos, etc.)

Roles y sus permisos:
- OWNER: Control total del tenant
- ADMIN: Gestión de usuarios y configuración
- COORDINATOR: Subir, modificar y eliminar archivos Excel
- ANALYST: Ver datos y exportar reportes
- VIEWER: Solo lectura
"""
from __future__ import annotations

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from tenants.models import Membership, MembershipRole


class IsTenantMember(permissions.BasePermission):
    """
    Verifica que el usuario sea miembro del tenant solicitado.
    El tenant se obtiene de:
    1. Header X-Tenant-ID
    2. Query param ?tenant=<slug>
    3. Tenant por defecto del usuario
    """
    message = "No tienes acceso a este tenant."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        
        tenant_id = self._get_tenant_id(request)
        if not tenant_id:
            # Si no se especifica tenant, permitir y usar el default
            return request.user.memberships.exists()
        
        return Membership.objects.filter(
            user=request.user,
            tenant_id=tenant_id,
            tenant__is_active=True
        ).exists()

    def _get_tenant_id(self, request: Request) -> str | None:
        """Extrae el tenant ID de la request."""
        # Primero intentar header
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        if tenant_id:
            return tenant_id
        
        # Luego query param
        tenant_slug = request.query_params.get("tenant")
        if tenant_slug:
            from tenants.models import Tenant
            try:
                return str(Tenant.objects.get(slug=tenant_slug).id)
            except Tenant.DoesNotExist:
                return None
        
        return None


class HasTenantRole(permissions.BasePermission):
    """
    Base class para verificar roles específicos en el tenant.
    Subclases definen los roles permitidos.
    """
    allowed_roles: list[str] = []
    message = "No tienes el rol necesario para esta acción."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers siempre tienen acceso
        if request.user.is_superuser:
            return True
        
        tenant_id = self._get_tenant_id(request)
        
        if tenant_id:
            membership = Membership.objects.filter(
                user=request.user,
                tenant_id=tenant_id,
                tenant__is_active=True
            ).first()
        else:
            # Usar membership default
            membership = request.user.memberships.filter(
                is_default=True,
                tenant__is_active=True
            ).first()
            if not membership:
                membership = request.user.memberships.filter(
                    tenant__is_active=True
                ).first()
        
        if not membership:
            return False
        
        return membership.role in self.allowed_roles

    def _get_tenant_id(self, request: Request) -> str | None:
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        if tenant_id:
            return tenant_id
        
        tenant_slug = request.query_params.get("tenant")
        if tenant_slug:
            from tenants.models import Tenant
            try:
                return str(Tenant.objects.get(slug=tenant_slug).id)
            except Tenant.DoesNotExist:
                return None
        
        return None


class IsAdminOrOwner(HasTenantRole):
    """
    Permiso para acciones administrativas.
    Solo OWNER y ADMIN pueden:
    - Gestionar usuarios del tenant
    - Configurar el tenant
    - Ver logs de auditoría
    """
    allowed_roles = [MembershipRole.OWNER, MembershipRole.ADMIN]
    message = "Solo administradores pueden realizar esta acción."


class CanManageFiles(HasTenantRole):
    """
    Permiso para gestión de archivos Excel (subir, modificar, eliminar).
    OWNER, ADMIN y COORDINATOR pueden:
    - Subir archivos PA y SV
    - Eliminar jobs/archivos
    - Re-procesar análisis
    """
    allowed_roles = [
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
        "coordinator",  # Rol personalizado que agregaremos
    ]
    message = "No tienes permiso para gestionar archivos."


class CanDeleteFiles(HasTenantRole):
    """
    Permiso específico para eliminación de archivos.
    Más restrictivo que CanManageFiles.
    Solo OWNER y ADMIN pueden eliminar.
    """
    allowed_roles = [MembershipRole.OWNER, MembershipRole.ADMIN]
    message = "Solo administradores pueden eliminar archivos."


class CanViewAnalysis(HasTenantRole):
    """
    Permiso para ver datos de análisis.
    Todos los roles pueden ver (excepto usuarios sin membership).
    """
    allowed_roles = [
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
        "coordinator",
        MembershipRole.ANALYST,
        MembershipRole.VIEWER,
    ]
    message = "No tienes acceso a los datos de análisis."


class CanExportData(HasTenantRole):
    """
    Permiso para exportar datos (descargar Excel).
    OWNER, ADMIN, COORDINATOR y ANALYST pueden exportar.
    """
    allowed_roles = [
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
        "coordinator",
        MembershipRole.ANALYST,
    ]
    message = "No tienes permiso para exportar datos."


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permite lectura a cualquier autenticado,
    pero escritura solo al owner del objeto.
    """
    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        # Lectura permitida para todos los autenticados
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Escritura solo para el owner/creator
        if hasattr(obj, "created_by"):
            return obj.created_by == request.user
        
        return False


# Utilidad para obtener el tenant actual del usuario
def get_user_tenant(request: Request):
    """
    Obtiene el tenant actual basándose en la request.
    Prioridad:
    1. Header X-Tenant-ID
    2. Query param ?tenant=<slug>
    3. Tenant default del usuario
    4. Primer tenant del usuario
    """
    from tenants.models import Tenant
    
    user = request.user
    if not user or not user.is_authenticated:
        return None
    
    # 1. Header X-Tenant-ID
    tenant_id = request.META.get("HTTP_X_TENANT_ID")
    if tenant_id:
        membership = user.memberships.filter(tenant_id=tenant_id).first()
        if membership:
            return membership.tenant
    
    # 2. Query param
    tenant_slug = request.query_params.get("tenant")
    if tenant_slug:
        membership = user.memberships.filter(tenant__slug=tenant_slug).first()
        if membership:
            return membership.tenant
    
    # 3. Default tenant
    membership = user.memberships.filter(is_default=True).first()
    if membership:
        return membership.tenant
    
    # 4. Primer tenant disponible
    membership = user.memberships.first()
    if membership:
        return membership.tenant
    
    return None


def get_user_role(request: Request) -> str | None:
    """Obtiene el rol del usuario en el tenant actual."""
    from tenants.models import Tenant
    
    user = request.user
    if not user or not user.is_authenticated:
        return None
    
    if user.is_superuser:
        return MembershipRole.OWNER
    
    tenant = get_user_tenant(request)
    if not tenant:
        return None
    
    membership = user.memberships.filter(tenant=tenant).first()
    return membership.role if membership else None
