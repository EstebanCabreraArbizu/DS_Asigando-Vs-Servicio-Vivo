from __future__ import annotations

import datetime as dt

from rest_framework import serializers

from jobs.models import AnalysisJob, JobStatus, Artifact, ArtifactKind


class AnalysisJobCreateSerializer(serializers.ModelSerializer):
    # En formato YYYY-MM (ej: 2025-12)
    period_month = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = AnalysisJob
        fields = [
            "id",
            "period_month",
            "input_personal_asignado",
            "input_servicio_vivo",
        ]
        read_only_fields = ["id"]

    def validate_period_month(self, value: str):
        if not value:
            return None
        if len(value) != 7 or value[4] != "-":
            raise serializers.ValidationError("Formato esperado YYYY-MM")
        # Se normaliza al día 1 del mes
        try:
            year = int(value[0:4])
            month = int(value[5:7])
        except ValueError:
            raise serializers.ValidationError("Formato esperado YYYY-MM")
        if month < 1 or month > 12:
            raise serializers.ValidationError("Mes inválido")
        return dt.date(year, month, 1)


class AnalysisJobStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisJob
        fields = ["id", "status", "created_at", "updated_at", "error_message"]


class ArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artifact
        fields = ["id", "kind", "file", "created_at"]
