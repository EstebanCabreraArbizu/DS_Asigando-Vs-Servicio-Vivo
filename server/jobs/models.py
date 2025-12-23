from __future__ import annotations

import uuid

from django.db import models


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
    return f"jobs/{instance.id}/inputs/{filename}"


def artifact_upload_path(instance: "Artifact", filename: str) -> str:
    return f"jobs/{instance.job_id}/artifacts/{filename}"


class AnalysisJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Tenant se conectará formalmente en la EPIC 2 (RLS). Por ahora es opcional.
    tenant_id = models.UUIDField(null=True, blank=True)

    period_month = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=JobStatus.choices, default=JobStatus.QUEUED)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    input_personal_asignado = models.FileField(upload_to=job_upload_path)
    input_servicio_vivo = models.FileField(upload_to=job_upload_path)

    error_message = models.TextField(blank=True, default="")


class Artifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(AnalysisJob, on_delete=models.CASCADE, related_name="artifacts")
    kind = models.CharField(max_length=20, choices=ArtifactKind.choices)
    file = models.FileField(upload_to=artifact_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)
