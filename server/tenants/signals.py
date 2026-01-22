"""
Signals para la app tenants.
Maneja la creación automática de membresías cuando se crean nuevos usuarios.
"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from tenants.models import Tenant, Membership, MembershipRole


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_default_membership(sender, instance, created, **kwargs):
    """
    Signal que se ejecuta después de crear un nuevo usuario.
    Asigna automáticamente una membresía de tipo VIEWER al tenant por defecto.
    
    Comportamiento:
    - Solo se ejecuta cuando se CREA un usuario (no en actualizaciones)
    - Busca el tenant "default" (o el primer tenant activo si no existe)
    - Crea una membresía con rol VIEWER y la marca como default
    """
    if not created:
        return
    
    # Evitar crear membresía para superusers (ya tienen todos los permisos)
    if instance.is_superuser:
        return
    
    # Buscar el tenant por defecto
    try:
        # Primero intentar con slug "default"
        default_tenant = Tenant.objects.filter(slug="default", is_active=True).first()
        
        # Si no existe, usar el primer tenant activo
        if not default_tenant:
            default_tenant = Tenant.objects.filter(is_active=True).first()
        
        if default_tenant:
            # Verificar que no exista ya una membresía para este usuario/tenant
            membership, membership_created = Membership.objects.get_or_create(
                user=instance,
                tenant=default_tenant,
                defaults={
                    "role": MembershipRole.VIEWER,
                    "is_default": True,
                }
            )
            
            if membership_created:
                print(f"[Signal] Membresía creada: {instance.username} -> {default_tenant.name} (Viewer)")
    
    except Exception as e:
        # Log del error pero no fallar silenciosamente
        print(f"[Signal] Error creando membresía default para {instance.username}: {e}")
