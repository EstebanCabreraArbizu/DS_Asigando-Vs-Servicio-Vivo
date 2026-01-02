from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from tenants.models import Tenant


class JobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class ArtifactKind(models.TextChoices):
    EXCEL = "excel", "Excel"
    PARQUET = "parquet", "Parquet"
    LOG = "log", "Log"


def job_upload_path(instance: "AnalysisJob", filename: str) -> str:
    tenant_slug = instance.tenant.slug if instance.tenant else "default"
    return f"tenants/{tenant_slug}/jobs/{instance.id}/inputs/{filename}"


def artifact_upload_path(instance: "Artifact", filename: str) -> str:
    tenant_slug = instance.job.tenant.slug if instance.job.tenant else "default"
    return f"tenants/{tenant_slug}/jobs/{instance.job_id}/artifacts/{filename}"


class AnalysisJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="jobs",
        help_text="Tenant dueño de este job"
    )

    period_month = models.DateField(null=True, blank=True, help_text="Mes del análisis (YYYY-MM-01)")
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.QUEUED)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Usuario que creó el job (auditoría)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_jobs",
        help_text="Usuario que creó este job"
    )

    input_personal_asignado = models.FileField(upload_to=job_upload_path, max_length=500)
    input_servicio_vivo = models.FileField(upload_to=job_upload_path, max_length=500)

    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        # Índice para queries por tenant + periodo (dashboard histórico)
        indexes = [
            models.Index(fields=["tenant", "period_month"]),
            models.Index(fields=["tenant", "status"]),
        ]

    def __str__(self) -> str:
        return f"Job {self.id} ({self.tenant.slug}) - {self.status}"


class Artifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(AnalysisJob, on_delete=models.CASCADE, related_name="artifacts")
    kind = models.CharField(max_length=20, choices=ArtifactKind.choices)
    file = models.FileField(upload_to=artifact_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.kind} - Job {self.job_id}"


class AnalysisSnapshot(models.Model):
    """
    Agregados pre-calculados por tenant/periodo para el dashboard.
    Permite consultas rápidas sin escanear Parquets.
    Se genera automáticamente al finalizar un job exitoso.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="snapshots"
    )
    job = models.OneToOneField(
        AnalysisJob,
        on_delete=models.CASCADE,
        related_name="snapshot",
        help_text="Job que generó este snapshot"
    )
    period_month = models.DateField(help_text="Mes del análisis (YYYY-MM-01)")

    # Métricas agregadas (JSON flexible para evolucionar sin migraciones)
    metrics = models.JSONField(default=dict, help_text="Métricas agregadas del análisis")
    # Ejemplo de estructura metrics:
    # {
    #   "total_personal_asignado": 1500,
    #   "total_servicio_vivo": 1450,
    #   "diferencia_absoluta": 50,
    #   "coincidencias": 1400,
    #   "solo_en_pa": 100,
    #   "solo_en_sv": 50,
    #   "por_tipo_servicio": {...},
    #   "por_ubicacion": {...},
    # }

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_month"]
        unique_together = [("tenant", "period_month")]
        indexes = [
            models.Index(fields=["tenant", "period_month"]),
        ]

    def __str__(self) -> str:
        return f"Snapshot {self.tenant.slug} - {self.period_month}"
