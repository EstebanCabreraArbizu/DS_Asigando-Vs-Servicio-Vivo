from django.contrib import admin

from tenants.models import Tenant, Membership


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "tenant", "role", "is_default", "created_at"]
    list_filter = ["role", "is_default", "tenant"]
    search_fields = ["user__username", "tenant__name"]
    raw_id_fields = ["user", "tenant"]
