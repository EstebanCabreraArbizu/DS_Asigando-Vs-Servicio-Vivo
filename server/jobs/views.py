from __future__ import annotations

import logging

from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api_v1.permissions import (
    CanManageFiles,
    CanDeleteFiles,
    CanViewAnalysis,
    CanExportData,
    get_user_tenant,
)
from api_v1.exceptions import ErrorResponse
from jobs.models import AnalysisJob, ArtifactKind, JobStatus
from jobs.serializers import AnalysisJobCreateSerializer, AnalysisJobStatusSerializer
from jobs.tasks import run_analysis_job
from jobs.services import get_storage_service, StorageException
from tenants.models import Tenant

logger = logging.getLogger(__name__)


class IsAuthenticatedOrSessionAuth(IsAuthenticated):
    """
    Permite autenticación JWT o Session (para el dashboard).
    """
    def has_permission(self, request, view):
        # Si hay usuario autenticado por sesión, permitir
        if request.user and request.user.is_authenticated:
            return True
        return super().has_permission(request, view)


class CanManageFilesOrSession(CanManageFiles):
    """
    Permite gestión de archivos con JWT o Session auth.
    Para Session auth, verifica que sea staff o superuser.
    """
    def has_permission(self, request, view):
        # Si es superuser o staff, permitir
        if request.user and request.user.is_authenticated:
            if request.user.is_superuser or request.user.is_staff:
                return True
        return super().has_permission(request, view)


class CanDeleteFilesOrSession(CanDeleteFiles):
    """
    Permite eliminar archivos con JWT o Session auth.
    """
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            if request.user.is_superuser or request.user.is_staff:
                return True
        return super().has_permission(request, view)


class CanViewAnalysisOrSession(CanViewAnalysis):
    """
    Permite ver análisis con JWT o Session auth.
    """
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return True  # Cualquier usuario autenticado puede ver
        return super().has_permission(request, view)


class CanExportDataOrSession(CanExportData):
    """
    Permite exportar datos con JWT o Session auth.
    """
    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return True  # Cualquier usuario autenticado puede exportar
        return super().has_permission(request, view)


def get_tenant_for_user(user, request=None):
    """
    Obtiene el tenant activo del usuario.
    
    Prioridad:
    1. Header X-Tenant-ID
    2. Query param ?tenant=<slug>
    3. Tenant por defecto del usuario
    4. Primer tenant disponible
    5. Fallback: tenant "default" para desarrollo
    """
    if request:
        tenant = get_user_tenant(request)
        if tenant:
            return tenant
    
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
    """
    Crea un nuevo job de análisis.
    
    POST /api/v1/jobs/
    POST /api/v1/jobs/create/
    Content-Type: multipart/form-data
    
    Parámetros:
    - input_personal_asignado: Archivo Excel con PA
    - input_servicio_vivo: Archivo Excel con SV
    - period_month: Fecha del período (YYYY-MM-01)
    
    Permisos: admin, coordinator, staff, superuser
    """
    # Permitir JWT o Session (sin CSRF para APIs internas)
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrSessionAuth, CanManageFilesOrSession]

    def post(self, request):
        serializer = AnalysisJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tenant = get_tenant_for_user(request.user, request)
        
        # Validar archivos
        pa_file = serializer.validated_data["input_personal_asignado"]
        sv_file = serializer.validated_data["input_servicio_vivo"]
        
        # Validar extensiones permitidas
        allowed_extensions = [".xlsx", ".xls", ".csv"]
        for f in [pa_file, sv_file]:
            ext = f.name.lower().split(".")[-1] if "." in f.name else ""
            if f".{ext}" not in allowed_extensions:
                return ErrorResponse.bad_request(
                    f"Tipo de archivo no permitido: {f.name}. Use: {', '.join(allowed_extensions)}",
                    code="invalid_file_type"
                )

        job = AnalysisJob.objects.create(
            tenant=tenant,
            period_month=serializer.validated_data.get("period_month"),
            input_personal_asignado=pa_file,
            input_servicio_vivo=sv_file,
            created_by=request.user if request.user.is_authenticated else None,
        )
        
        username = request.user.username if request.user.is_authenticated else "anonymous"
        logger.info(f"Job {job.id} created by {username} for tenant {tenant.slug}")

        run_analysis_job.delay(str(job.id))

        return Response(
            {
                "job_id": str(job.id),
                "status": job.status,
                "message": "Job creado exitosamente. El análisis está en proceso."
            },
            status=status.HTTP_202_ACCEPTED
        )


class JobStatusView(APIView):
    """
    Obtiene el estado de un job.
    
    GET /api/v1/jobs/<job_id>/status/
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrSessionAuth, CanViewAnalysisOrSession]
    
    def get(self, request, job_id: str):
        job = get_object_or_404(AnalysisJob, id=job_id)
        
        # Verificar acceso al tenant
        tenant = get_tenant_for_user(request.user, request)
        if job.tenant != tenant and not request.user.is_superuser:
            return ErrorResponse.forbidden("No tienes acceso a este job")
        
        return Response(AnalysisJobStatusSerializer(job).data)


class JobDeleteView(APIView):
    """
    Elimina un job y todos sus archivos asociados.
    
    DELETE /api/v1/jobs/<job_id>/
    
    Permisos: admin only
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrSessionAuth, CanDeleteFilesOrSession]
    
    def delete(self, request, job_id: str):
        job = get_object_or_404(AnalysisJob, id=job_id)
        
        # Verificar acceso al tenant
        tenant = get_tenant_for_user(request.user, request)
        if job.tenant != tenant and not request.user.is_superuser:
            return ErrorResponse.forbidden("No tienes acceso a este job")
        
        try:
            # Eliminar archivos del storage
            storage = get_storage_service()
            prefix = f"tenants/{job.tenant.slug}/jobs/{job.id}/"
            
            deleted_count = storage.delete_folder(prefix, bucket_type="inputs")
            deleted_count += storage.delete_folder(prefix, bucket_type="artifacts")
            
            logger.info(f"Deleted {deleted_count} files for job {job.id}")
        except StorageException as e:
            logger.warning(f"Error deleting files for job {job.id}: {e}")
        
        # Guardar info para log antes de eliminar
        job_info = f"Job {job.id} ({job.period_month})"
        
        # Eliminar job (cascade eliminará artifacts)
        job.delete()
        
        logger.info(f"{job_info} deleted by {request.user.username}")
        
        return Response(
            {"message": f"Job eliminado exitosamente"},
            status=status.HTTP_200_OK
        )


class JobDownloadExcelView(APIView):
    """
    Descarga el Excel resultante de un job.
    
    GET /api/v1/jobs/<job_id>/excel/
    
    Permisos: admin, coordinator, analyst
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrSessionAuth, CanExportDataOrSession]
    
    def get(self, request, job_id: str):
        job = get_object_or_404(AnalysisJob, id=job_id)
        
        # Verificar acceso al tenant
        tenant = get_tenant_for_user(request.user, request)
        if job.tenant != tenant and not request.user.is_superuser:
            return ErrorResponse.forbidden("No tienes acceso a este job")
        
        artifact = job.artifacts.filter(kind=ArtifactKind.EXCEL).order_by("-created_at").first()
        if not artifact:
            return ErrorResponse.not_found("Excel aún no disponible")
        
        # Nombre descriptivo del archivo
        period_str = job.period_month.strftime("%Y-%m") if job.period_month else job.created_at.strftime("%Y%m%d")
        filename = f"PA_vs_SV_{period_str}.xlsx"
        
        # Proxy download: Django actúa como intermediario (más seguro)
        storage = get_storage_service()
        if storage.use_s3:
            try:
                # Obtener archivo desde MinIO y transmitirlo al usuario
                s3_response = storage.s3_client.get_object(
                    Bucket=storage.buckets.get("artifacts"),
                    Key=artifact.file.name
                )
                
                def file_iterator(body, chunk_size=8192):
                    """Generador que lee el archivo en chunks para no consumir memoria."""
                    for chunk in iter(lambda: body.read(chunk_size), b''):
                        yield chunk
                
                response = StreamingHttpResponse(
                    file_iterator(s3_response['Body']),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                # Log de auditoría
                logger.info(f"Excel downloaded: job={job_id}, user={request.user.username}, file={filename}")
                
                return response
            except Exception as e:
                logger.error(f"Error streaming from S3: {e}")
                # Fallback to FileResponse if S3 streaming fails
        
        # Descarga directa para storage local
        response = FileResponse(
            artifact.file.open("rb"), 
            as_attachment=True, 
            filename=filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return response


class JobLatestDownloadView(APIView):
    """
    Descarga el Excel del último job exitoso.
    
    GET /api/v1/jobs/latest/download/?tenant=<slug>
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrSessionAuth, CanExportDataOrSession]
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        
        if not tenant:
            return ErrorResponse.not_found("Tenant no encontrado")
        
        # Buscar último job exitoso
        job = AnalysisJob.objects.filter(
            tenant=tenant,
            status=JobStatus.SUCCEEDED
        ).order_by("-created_at").first()
        
        if not job:
            return ErrorResponse.not_found("No hay jobs exitosos disponibles")
        
        artifact = job.artifacts.filter(kind=ArtifactKind.EXCEL).first()
        if not artifact:
            return ErrorResponse.not_found("Excel no disponible para este job")
        
        # Nombre descriptivo del archivo
        period_str = job.period_month.strftime("%Y-%m") if job.period_month else job.created_at.strftime("%Y%m%d")
        filename = f"PA_vs_SV_{period_str}.xlsx"
        
        # Proxy download: Django actúa como intermediario (más seguro)
        storage = get_storage_service()
        if storage.use_s3:
            try:
                # Obtener archivo desde MinIO y transmitirlo al usuario
                s3_response = storage.s3_client.get_object(
                    Bucket=storage.buckets.get("artifacts"),
                    Key=artifact.file.name
                )
                
                def file_iterator(body, chunk_size=8192):
                    """Generador que lee el archivo en chunks para no consumir memoria."""
                    for chunk in iter(lambda: body.read(chunk_size), b''):
                        yield chunk
                
                response = StreamingHttpResponse(
                    file_iterator(s3_response['Body']),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                # Log de auditoría
                logger.info(f"Excel downloaded (latest): user={request.user.username}, file={filename}")
                
                return response
            except Exception as e:
                logger.error(f"Error streaming from S3: {e}")
                # Fallback to FileResponse if S3 streaming fails
        
        response = FileResponse(
            artifact.file.open("rb"), 
            as_attachment=True, 
            filename=filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return response


class JobListView(APIView):
    """
    Lista los jobs del tenant actual (GET) o crea un nuevo job (POST).
    
    GET /api/v1/jobs/?status=succeeded&limit=10
    POST /api/v1/jobs/
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticatedOrSessionAuth, CanViewAnalysisOrSession]
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        
        jobs = AnalysisJob.objects.filter(tenant=tenant)
        
        # Filtros opcionales
        status_filter = request.query_params.get("status")
        if status_filter:
            jobs = jobs.filter(status=status_filter)
        
        # Paginación simple
        try:
            limit = int(request.query_params.get("limit", 20))
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            return Response(
                {"error": {"code": "invalid_param", "message": "limit y offset deben ser enteros"}},
                status=status.HTTP_400_BAD_REQUEST
            )
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        
        total = jobs.count()
        jobs = jobs[offset:offset + limit]
        
        return Response({
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": AnalysisJobStatusSerializer(jobs, many=True).data
        })

    def get_permissions(self):
        """
        Usa permisos diferentes para GET y POST.
        """
        if self.request.method == 'POST':
            return [IsAuthenticatedOrSessionAuth(), CanManageFilesOrSession()]
        return [IsAuthenticatedOrSessionAuth(), CanViewAnalysisOrSession()]

    def post(self, request):
        """
        Crea un nuevo job de análisis.
        Delega a JobCreateView.post()
        """
        return JobCreateView().post(request)

