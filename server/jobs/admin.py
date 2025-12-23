from django.contrib import admin

from jobs.models import AnalysisJob, Artifact, AnalysisSnapshot


class ArtifactInline(admin.TabularInline):
    model = Artifact
    extra = 0
    readonly_fields = ["id", "kind", "file", "created_at"]


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "period_month", "status", "created_at", "updated_at"]
    list_filter = ["status", "tenant", "period_month"]
    search_fields = ["id", "tenant__name", "tenant__slug"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["tenant"]
    inlines = [ArtifactInline]

    fieldsets = (
        (None, {
            "fields": ("id", "tenant", "period_month", "status")
        }),
        ("Archivos de entrada", {
            "fields": ("input_personal_asignado", "input_servicio_vivo")
        }),
        ("Estado", {
            "fields": ("error_message", "created_at", "updated_at")
        }),
    )


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ["id", "job", "kind", "file", "created_at"]
    list_filter = ["kind", "job__tenant"]
    search_fields = ["job__id"]
    raw_id_fields = ["job"]


@admin.register(AnalysisSnapshot)
class AnalysisSnapshotAdmin(admin.ModelAdmin):
    list_display = ["tenant", "period_month", "job", "created_at"]
    list_filter = ["tenant", "period_month"]
    search_fields = ["tenant__name", "tenant__slug"]
    raw_id_fields = ["tenant", "job"]
    readonly_fields = ["created_at", "updated_at"]
