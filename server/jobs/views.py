from __future__ import annotations

from django.http import FileResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from jobs.models import AnalysisJob, ArtifactKind
from jobs.serializers import AnalysisJobCreateSerializer, AnalysisJobStatusSerializer
from jobs.tasks import run_analysis_job


class JobCreateView(APIView):
    def post(self, request):
        serializer = AnalysisJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        job = AnalysisJob.objects.create(
            period_month=serializer.validated_data.get("period_month"),
            input_personal_asignado=serializer.validated_data["input_personal_asignado"],
            input_servicio_vivo=serializer.validated_data["input_servicio_vivo"],
        )

        run_analysis_job.delay(str(job.id))

        return Response({"job_id": str(job.id)}, status=status.HTTP_202_ACCEPTED)


class JobStatusView(APIView):
    def get(self, request, job_id: str):
        job = AnalysisJob.objects.get(id=job_id)
        return Response(AnalysisJobStatusSerializer(job).data)


class JobDownloadExcelView(APIView):
    def get(self, request, job_id: str):
        job = AnalysisJob.objects.get(id=job_id)
        artifact = job.artifacts.filter(kind=ArtifactKind.EXCEL).order_by("-created_at").first()
        if not artifact:
            return Response({"detail": "Excel aún no disponible"}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(artifact.file.open("rb"), as_attachment=True, filename=artifact.file.name.split("/")[-1])
