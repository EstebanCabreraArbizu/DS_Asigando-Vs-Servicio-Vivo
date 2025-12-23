from __future__ import annotations

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from jobs.models import AnalysisJob, ArtifactKind
from jobs.serializers import AnalysisJobCreateSerializer, AnalysisJobStatusSerializer
from jobs.tasks import run_analysis_job
from tenants.models import Tenant


def get_tenant_for_user(user):
    """
    Obtiene el tenant activo del usuario (por ahora usa el default o el primero).
    En producción, esto se obtendría de la sesión o header X-Tenant-ID.
    """
    membership = user.memberships.filter(is_default=True).first()
    if not membership:
        membership = user.memberships.first()
    if membership:
        return membership.tenant
    # Fallback: tenant "default" para desarrollo
    tenant, _ = Tenant.objects.get_or_create(
        slug="default",
        defaults={"name": "Default Tenant"}
    )
    return tenant


class JobCreateView(APIView):
    # permission_classes = [IsAuthenticated]  # Descomentar cuando auth esté listo

    def post(self, request):
        serializer = AnalysisJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Obtener tenant del usuario autenticado (o default para dev)
        if request.user.is_authenticated:
            tenant = get_tenant_for_user(request.user)
        else:
            tenant, _ = Tenant.objects.get_or_create(
                slug="default",
                defaults={"name": "Default Tenant"}
            )

        job = AnalysisJob.objects.create(
            tenant=tenant,
            period_month=serializer.validated_data.get("period_month"),
            input_personal_asignado=serializer.validated_data["input_personal_asignado"],
            input_servicio_vivo=serializer.validated_data["input_servicio_vivo"],
        )

        run_analysis_job.delay(str(job.id))

        return Response({"job_id": str(job.id)}, status=status.HTTP_202_ACCEPTED)


class JobStatusView(APIView):
    def get(self, request, job_id: str):
        job = get_object_or_404(AnalysisJob, id=job_id)
        # TODO: Verificar que el usuario tenga acceso al tenant del job
        return Response(AnalysisJobStatusSerializer(job).data)


class JobDownloadExcelView(APIView):
    def get(self, request, job_id: str):
        job = get_object_or_404(AnalysisJob, id=job_id)
        # TODO: Verificar que el usuario tenga acceso al tenant del job
        artifact = job.artifacts.filter(kind=ArtifactKind.EXCEL).order_by("-created_at").first()
        if not artifact:
            return Response({"detail": "Excel aún no disponible"}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(artifact.file.open("rb"), as_attachment=True, filename=artifact.file.name.split("/")[-1])

