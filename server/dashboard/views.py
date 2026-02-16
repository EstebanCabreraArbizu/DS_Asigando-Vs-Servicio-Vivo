"""
Dashboard Views - Vistas para el dashboard de métricas PA vs SV.
"""
from io import BytesIO
import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum, Count, Avg
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from axes.helpers import get_client_ip_address, get_failure_limit
from axes.utils import reset as axes_reset
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url

from jobs.models import AnalysisJob, AnalysisSnapshot, JobStatus, Artifact, ArtifactKind
from jobs.utils import generate_analysis_metrics
from tenants.models import Tenant, Membership, MembershipRole


# Diccionario de meses en español para formateo de fechas
MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

logger = logging.getLogger(__name__)

# ─── Constantes de validación ────────────────────────────────────────────────
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
ALLOWED_SORT_FIELDS = {"pa", "sv", "diferencia", "nombre", "Cliente_Final",
                       "Unidad_Str", "Servicio_Limpio", "Personal_Real",
                       "Personal_Estimado", "Diferencia", "Estado"}
ALLOWED_SORT_ORDERS = {"asc", "desc"}


# ─── Mixin de autenticación para APIs JSON ───────────────────────────────────
class LoginRequiredJSONMixin:
    """
    Mixin que retorna 401 JSON en lugar de redirigir al login.
    Esto es necesario para APIs llamadas via AJAX desde el dashboard.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": {"code": "unauthorized", "message": "Autenticación requerida"}},
                status=401
            )
        return super().dispatch(request, *args, **kwargs)


# ─── Funciones de validación ─────────────────────────────────────────────────
def validate_pagination(request):
    """
    Valida y sanitiza parámetros de paginación.
    Returns: (page, per_page, error_response_or_None)
    """
    try:
        page = int(request.GET.get("page", 1))
        per_page = int(request.GET.get("per_page", 20))
    except (ValueError, TypeError):
        return None, None, JsonResponse(
            {"error": {"code": "invalid_param", "message": "page y per_page deben ser enteros"}},
            status=400
        )
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    return page, per_page, None


def validate_period(period_str):
    """
    Valida formato de periodo YYYY-MM.
    Returns: (date_or_None, error_response_or_None)
    """
    if not period_str:
        return None, None
    if not PERIOD_RE.match(period_str):
        return None, JsonResponse(
            {"error": {"code": "invalid_param", "message": "Formato de periodo inválido. Use YYYY-MM"}},
            status=400
        )
    from datetime import datetime
    return datetime.strptime(f"{period_str}-01", "%Y-%m-%d").date(), None


def validate_sort(sort_by, sort_order):
    """
    Valida campos de ordenamiento contra whitelist.
    Returns: (safe_sort_by, safe_sort_order, error_response_or_None)
    """
    if sort_by and sort_by not in ALLOWED_SORT_FIELDS:
        sort_by = None
    if sort_order not in ALLOWED_SORT_ORDERS:
        sort_order = "desc"
    return sort_by, sort_order, None


def format_period_spanish(date):
    """
    Formatea una fecha como 'Enero 2026' en español.
    
    Args:
        date: objeto date o datetime con month y year
        
    Returns:
        str: fecha formateada en español, ej: 'Enero 2026'
    """
    return f"{MESES_ES[date.month]} {date.year}"


def read_file_to_buffer(file_field) -> BytesIO:
    """
    Lee un FileField a un buffer BytesIO, compatible con S3 y almacenamiento local.
    
    Cuando se usa S3 storage, los archivos no tienen .path disponible.
    Esta función lee el contenido del archivo desde cualquier backend.
    
    Args:
        file_field: Django FileField (ej: artifact.file)
        
    Returns:
        BytesIO con el contenido del archivo
    """
    buffer = BytesIO()
    try:
        # Intentar abrir y leer el archivo
        with file_field.open('rb') as f:
            buffer.write(f.read())
        buffer.seek(0)
    except Exception as e:
        raise IOError(f"Error al leer archivo: {e}")
    return buffer


def get_user_permissions(user):
    """
    Obtiene los permisos del usuario basado en su rol.
    
    Returns:
        dict con los permisos del usuario
    """
    if not user or not user.is_authenticated:
        return {
            "can_view": False,
            "can_upload": False,
            "can_delete": False,
            "can_export": False,
            "role": None,
            "role_display": "No autenticado",
        }
    
    # Superuser y staff tienen todos los permisos
    if user.is_superuser or user.is_staff:
        return {
            "can_view": True,
            "can_upload": True,
            "can_delete": True,
            "can_export": True,
            "role": "admin",
            "role_display": "Administrador",
        }
    
    # Buscar membership del usuario
    membership = Membership.objects.filter(user=user, is_default=True).first()
    if not membership:
        membership = Membership.objects.filter(user=user).first()
    
    if not membership:
        return {
            "can_view": True,
            "can_upload": False,
            "can_delete": False,
            "can_export": False,
            "role": "viewer",
            "role_display": "Visor",
        }
    
    role = membership.role
    
    # Definir permisos por rol
    permissions = {
        MembershipRole.OWNER: {
            "can_view": True,
            "can_upload": True,
            "can_delete": True,
            "can_export": True,
            "role": "owner",
            "role_display": "Propietario",
        },
        MembershipRole.ADMIN: {
            "can_view": True,
            "can_upload": True,
            "can_delete": True,
            "can_export": True,
            "role": "admin",
            "role_display": "Administrador",
        },
        MembershipRole.COORDINATOR: {
            "can_view": True,
            "can_upload": True,
            "can_delete": True,
            "can_export": True,
            "role": "coordinator",
            "role_display": "Coordinador",
        },
        MembershipRole.ANALYST: {
            "can_view": True,
            "can_upload": False,
            "can_delete": False,
            "can_export": True,
            "role": "analyst",
            "role_display": "Analista",
        },
        MembershipRole.VIEWER: {
            "can_view": True,
            "can_upload": False,
            "can_delete": False,
            "can_export": False,
            "role": "viewer",
            "role_display": "Visor",
        },
    }
    
    return permissions.get(role, permissions[MembershipRole.VIEWER])


def get_tenant_for_user(user, request=None):
    """
    Obtiene el tenant activo del usuario para el dashboard.
    
    Prioridad:
    1. Query param ?tenant=<slug>
    2. Header X-Tenant-ID
    3. Tenant por defecto del usuario
    4. Primer tenant del usuario
    5. Fallback: tenant "default" (solo para usuarios autenticados)
    
    Retorna None si el usuario no está autenticado.
    """
    if not user or not user.is_authenticated:
        return None
    
    if request:
        # 1. Query param (usado en links del dashboard)
        tenant_slug = request.GET.get("tenant")
        if tenant_slug:
            tenant = Tenant.objects.filter(slug=tenant_slug).first()
            if tenant:
                return tenant
        
        # 2. Header (usado en llamadas API/AJAX)
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        if tenant_id:
            try:
                tenant = Tenant.objects.filter(id=tenant_id).first()
                if tenant:
                    return tenant
            except:
                pass
    
    # 3. Default membership
    membership = Membership.objects.filter(user=user, is_default=True).first()
    if not membership:
        # 4. First membership
        membership = Membership.objects.filter(user=user).first()
    
    if membership:
        return membership.tenant
    
    # 5. Fallback a default
    return Tenant.objects.filter(slug="default").first()


class UploadView(LoginRequiredMixin, TemplateView):
    """Vista para subir archivos Excel con drag & drop."""
    template_name = "dashboard/upload.html"
    login_url = "/dashboard/login/"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = get_tenant_for_user(self.request.user, self.request)
        
        # Permisos del usuario
        permissions = get_user_permissions(self.request.user)
        
        # Últimos 10 jobs para mostrar historial
        recent_jobs = AnalysisJob.objects.filter(
            tenant=tenant
        ).order_by("-created_at")[:10] if tenant else []
        
        context["tenant"] = tenant
        context["recent_jobs"] = recent_jobs
        context["user"] = self.request.user
        context["permissions"] = permissions
        return context


class DashboardView(LoginRequiredMixin, TemplateView):
    """Vista principal del dashboard con gráficos y KPIs."""
    template_name = "dashboard/main.html"
    login_url = "/dashboard/login/"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener tenant dinámicamente
        tenant = get_tenant_for_user(self.request.user, self.request)
        
        # Permisos del usuario
        permissions = get_user_permissions(self.request.user)
        
        # Obtener periodos disponibles
        snapshots = AnalysisSnapshot.objects.filter(
            tenant=tenant
        ).order_by("-period_month") if tenant else []
        
        periods = [
            {
                "value": s.period_month.strftime("%Y-%m"),
                "label": format_period_spanish(s.period_month)
            }
            for s in snapshots
        ]
        
        # Si no hay snapshots, obtener de jobs
        if not periods and tenant:
            jobs = AnalysisJob.objects.filter(
                tenant=tenant,
                status=JobStatus.SUCCEEDED
            ).order_by("-created_at")[:12]
            
            seen = set()
            for job in jobs:
                if job.period_month:
                    period_str = job.period_month.strftime("%Y-%m")
                    if period_str not in seen:
                        seen.add(period_str)
                        periods.append({
                            "value": period_str,
                            "label": format_period_spanish(job.period_month)
                        })
        
        context["tenant"] = tenant
        context["periods"] = periods
        context["current_period"] = periods[0] if periods else None
        context["user"] = self.request.user
        context["permissions"] = permissions
        
        return context


class MetricsAPIView(LoginRequiredJSONMixin, View):
    """API para obtener métricas del dashboard."""
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        period = request.GET.get("period")  # Formato: YYYY-MM
        
        # Validar periodo
        period_date, period_err = validate_period(period)
        if period_err:
            return period_err
        
        # Filtros opcionales recibidos desde frontend
        request_filters = {
            "macrozona": request.GET.get("macrozona", ""),
            "zona": request.GET.get("zona", ""),
            "compania": request.GET.get("compania", ""),
            "grupo": request.GET.get("grupo", ""),
            "sector": request.GET.get("sector", ""),
            "gerente": request.GET.get("gerente", ""),
        }
        
        if not tenant:
            return JsonResponse({"error": "Tenant no encontrado"}, status=404)
        
        # Buscar snapshot del periodo (consulta de snapshots/jobs no incluye filtros de UI)
        snapshot_query = {"tenant": tenant}
        if period and period_date:
            snapshot_query["period_month"] = period_date

        snapshot = AnalysisSnapshot.objects.filter(**snapshot_query).order_by("-period_month").first()
        
        if not snapshot:
            # Si no hay snapshot, intentar obtener del último job exitoso
            job_filters = {"tenant": tenant, "status": JobStatus.SUCCEEDED}
            if period:
                job_filters["period_month"] = period_date
            
            job = AnalysisJob.objects.filter(**job_filters).order_by("-created_at").first()
            
            if not job:
                return JsonResponse({
                    "error": "No hay datos disponibles",
                    "kpis": {
                        "total_personal_asignado": 0,
                        "total_servicio_vivo": 0,
                        "coincidencias": 0,
                        "diferencia_total": 0,
                        "cobertura_porcentaje": 0
                    },
                    "charts": {},
                    "filtros_disponibles": {}
                })
            
            # Generar métricas desde el parquet del job (aplicar filtros recibidos)
            metrics = self._generate_metrics_from_job(job, request_filters)
        else:
            # Si hay snapshot pero también filtros, regenerar desde job
            if any(request_filters.values()):
                job = AnalysisJob.objects.filter(
                    tenant=tenant,
                    status=JobStatus.SUCCEEDED,
                    period_month=snapshot.period_month
                ).first()
                if job:
                    metrics = self._generate_metrics_from_job(job, request_filters)
                else:
                    metrics = snapshot.metrics
            else:
                metrics = snapshot.metrics
        
        return JsonResponse({
            "period": period or (snapshot.period_month.strftime("%Y-%m") if snapshot else "N/A"),
            "kpis": {
                "total_personal_asignado": metrics.get("total_personal_asignado", 0),
                "total_servicio_vivo": metrics.get("total_servicio_vivo", 0),
                "coincidencias": metrics.get("coincidencias", 0),
                "diferencia_total": metrics.get("diferencia_total", 0),
                "cobertura_porcentaje": metrics.get("cobertura_porcentaje", 0),
                "cobertura_diferencial": metrics.get("cobertura_diferencial", 0),
                "total_servicios": metrics.get("total_servicios", 0),
            },
            "charts": {
                "by_estado": metrics.get("by_estado", []),
                "by_zona": metrics.get("by_zona", []),
                "by_macrozona": metrics.get("by_macrozona", []),
                "by_cliente_top10": metrics.get("by_cliente_top10", []),
                "by_unidad_top10": metrics.get("by_unidad_top10", []),
                "by_servicio_top10": metrics.get("by_servicio_top10", []),
                "by_grupo": metrics.get("by_grupo", []),
            },
            "filtros_disponibles": metrics.get("filtros_disponibles", {})
        })
    
    def _generate_metrics_from_job(self, job, filters=None):
        """Genera métricas desde el parquet de un job."""
        import polars as pl
        from jobs.models import Artifact, ArtifactKind
        from jobs.utils import get_unique_values, generate_analysis_metrics
        
        filters = filters or {}
        
        artifact = job.artifacts.filter(kind=ArtifactKind.PARQUET).first()
        if not artifact:
            return {}
        
        try:
            # Leer desde buffer para compatibilidad con S3
            file_buffer = read_file_to_buffer(artifact.file)
            df_original = pl.read_parquet(file_buffer)
            
            # --- Lógica de filtros independientes ---
            # Para cada filtro, queremos ver todas las opciones posibles dado el RESTO de filtros,
            # pero IGNORANDO la selección del filtro actual.
            # Esto permite cambiar de opción sin tener que "deseleccionar" primero.
            
            filter_configs = {
                "macrozona": ["Macrozona_SV"],
                "zona": ["Zona_SV", "Zona_PA"],
                "compania": ["Compañía_SV", "Compañía_PA"],
                "grupo": ["Nombre_Grupo_SV", "Nombre_Grupo_PA"],
                "sector": ["Sector_SV", "Sector_PA"],
                "gerente": ["Gerencia_SV", "Gerencia_PA"],
            }
            
            filtros_disponibles = {}
            
            for key, columns in filter_configs.items():
                # Empezamos con el dataset original para cada cálculo de opciones
                df_temp = df_original
                
                # Aplicamos TODOS los filtros EXCEPTO el filtro actual (key)
                # Ejemplo: Si calculamos opciones para 'zona', aplicamos filtros de macrozona, compania, etc.
                # pero NO aplicamos el filtro de 'zona' que pueda venir en la request.
                
                current_temp_filters = {k: v for k, v in filters.items() if k != key and v}
                
                # Aplicar los filtros restantes a df_temp
                if current_temp_filters.get("macrozona"):
                    df_temp = df_temp.filter(pl.col("Macrozona_SV") == current_temp_filters["macrozona"])
                
                if current_temp_filters.get("zona"):
                    zona_filter = pl.lit(False)
                    if "Zona_SV" in df_temp.columns:
                        zona_filter = zona_filter | (pl.col("Zona_SV") == current_temp_filters["zona"])
                    if "Zona_PA" in df_temp.columns:
                        zona_filter = zona_filter | (pl.col("Zona_PA") == current_temp_filters["zona"])
                    df_temp = df_temp.filter(zona_filter)
                
                if current_temp_filters.get("compania"):
                    compania_filter = pl.lit(False)
                    if "Compañía_SV" in df_temp.columns:
                        compania_filter = compania_filter | (pl.col("Compañía_SV") == current_temp_filters["compania"])
                    if "Compañía_PA" in df_temp.columns:
                        compania_filter = compania_filter | (pl.col("Compañía_PA") == current_temp_filters["compania"])
                    df_temp = df_temp.filter(compania_filter)
                
                if current_temp_filters.get("grupo"):
                    grupo_filter = pl.lit(False)
                    if "Nombre_Grupo_SV" in df_temp.columns:
                        grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_SV") == current_temp_filters["grupo"])
                    if "Nombre_Grupo_PA" in df_temp.columns:
                        grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_PA") == current_temp_filters["grupo"])
                    df_temp = df_temp.filter(grupo_filter)
                
                if current_temp_filters.get("sector"):
                    sector_filter = pl.lit(False)
                    if "Sector_SV" in df_temp.columns:
                        sector_filter = sector_filter | (pl.col("Sector_SV") == current_temp_filters["sector"])
                    if "Sector_PA" in df_temp.columns:
                        sector_filter = sector_filter | (pl.col("Sector_PA") == current_temp_filters["sector"])
                    df_temp = df_temp.filter(sector_filter)
                
                if current_temp_filters.get("gerente"):
                    gerente_filter = pl.lit(False)
                    if "Gerencia_SV" in df_temp.columns:
                        gerente_filter = gerente_filter | (pl.col("Gerencia_SV") == current_temp_filters["gerente"])
                    if "Gerencia_PA" in df_temp.columns:
                        gerente_filter = gerente_filter | (pl.col("Gerencia_PA") == current_temp_filters["gerente"])
                    df_temp = df_temp.filter(gerente_filter)
                
                # Obtener valores únicos para este filtro
                # (usando las columnas definidas en filter_configs)
                filtros_disponibles[key] = get_unique_values(df_temp, *columns)

            # --- Fin lógica de filtros independientes ---

            # Ahora aplicamos TODOS los filtros para los datos de los gráficos/KPIs
            df = df_original
            
            if filters.get("macrozona"):
                df = df.filter(pl.col("Macrozona_SV") == filters["macrozona"])
            
            if filters.get("zona"):
                # Filtrar por zona SV o PA
                zona_filter = pl.lit(False)
                if "Zona_SV" in df.columns:
                    zona_filter = zona_filter | (pl.col("Zona_SV") == filters["zona"])
                if "Zona_PA" in df.columns:
                    zona_filter = zona_filter | (pl.col("Zona_PA") == filters["zona"])
                df = df.filter(zona_filter)
            
            if filters.get("compania"):
                compania_filter = pl.lit(False)
                if "Compañía_SV" in df.columns:
                    compania_filter = compania_filter | (pl.col("Compañía_SV") == filters["compania"])
                if "Compañía_PA" in df.columns:
                    compania_filter = compania_filter | (pl.col("Compañía_PA") == filters["compania"])
                df = df.filter(compania_filter)
            
            if filters.get("grupo"):
                grupo_filter = pl.lit(False)
                if "Nombre_Grupo_SV" in df.columns:
                    grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_SV") == filters["grupo"])
                if "Nombre_Grupo_PA" in df.columns:
                    grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_PA") == filters["grupo"])
                df = df.filter(grupo_filter)
            
            if filters.get("sector"):
                sector_filter = pl.lit(False)
                if "Sector_SV" in df.columns:
                    sector_filter = sector_filter | (pl.col("Sector_SV") == filters["sector"])
                if "Sector_PA" in df.columns:
                    sector_filter = sector_filter | (pl.col("Sector_PA") == filters["sector"])
                df = df.filter(sector_filter)
            
            if filters.get("gerente"):
                gerente_filter = pl.lit(False)
                if "Gerencia_SV" in df.columns:
                    gerente_filter = gerente_filter | (pl.col("Gerencia_SV") == filters["gerente"])
                if "Gerencia_PA" in df.columns:
                    gerente_filter = gerente_filter | (pl.col("Gerencia_PA") == filters["gerente"])
                df = df.filter(gerente_filter)
            
            # Si el DataFrame quedó vacío después de filtrar
            if len(df) == 0:
                return {
                    "total_personal_asignado": 0,
                    "total_servicio_vivo": 0,
                    "coincidencias": 0,
                    "diferencia_total": 0,
                    "cobertura_porcentaje": 0,
                    "cobertura_diferencial": 0,
                    "total_servicios": 0,
                    "by_estado": [],
                    "by_zona": [],
                    "by_macrozona": [],
                    "by_cliente_top10": [],
                    "by_unidad_top10": [],
                    "by_servicio_top10": [],
                    "by_grupo": [],
                    "filtros_disponibles": filtros_disponibles, # Usamos los calculados independientemente
                }
            
            # Usar utilidad compartida para generar métricas
            metrics = generate_analysis_metrics(df)
            
            # Sobrescribir filtros_disponibles con nuestra versión "inteligente"
            metrics["filtros_disponibles"] = filtros_disponibles
            
            return metrics
        except Exception as e:
            print(f"Error generando métricas: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _get_unique_values(self, df, *columns):
        """Obtiene valores únicos de columnas, priorizando en orden."""
        import polars as pl
        for col in columns:
            if col in df.columns:
                values = df.select(pl.col(col)).filter(
                    pl.col(col).is_not_null() & (pl.col(col) != "")
                ).unique().sort(col).to_series().to_list()
                if values:
                    return values
        return []


class PeriodsAPIView(LoginRequiredJSONMixin, View):
    """API para obtener periodos disponibles."""
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        
        if not tenant:
            return JsonResponse({"error": "Tenant no encontrado"}, status=404)
        
        # Obtener periodos de snapshots
        snapshots = AnalysisSnapshot.objects.filter(tenant=tenant).order_by("-period_month")
        
        # Si no hay snapshots, obtener de jobs exitosos
        if not snapshots.exists():
            jobs = AnalysisJob.objects.filter(
                tenant=tenant,
                status=JobStatus.SUCCEEDED
            ).order_by("-created_at")
            
            periods = []
            seen = set()
            for job in jobs:
                period_str = job.period_month.strftime("%Y-%m") if job.period_month else job.created_at.strftime("%Y-%m")
                if period_str not in seen:
                    seen.add(period_str)
                    periods.append({
                        "value": period_str,
                        "label": format_period_spanish(job.period_month) if job.period_month else format_period_spanish(job.created_at),
                        "job_id": str(job.id)
                    })
        else:
            periods = [
                {
                    "value": s.period_month.strftime("%Y-%m"),
                    "label": format_period_spanish(s.period_month),
                    "job_id": str(s.job_id)
                }
                for s in snapshots
            ]
        
        return JsonResponse({"periods": periods})


class CompareAPIView(LoginRequiredJSONMixin, View):
    """API para comparar dos periodos."""
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        period1 = request.GET.get("period1")
        period2 = request.GET.get("period2")
        
        if not period1 or not period2:
            return JsonResponse({"error": {"code": "invalid_param", "message": "Se requieren period1 y period2"}}, status=400)
        
        # Validar formato de periodos
        _, err1 = validate_period(period1)
        if err1:
            return err1
        _, err2 = validate_period(period2)
        if err2:
            return err2
        
        if not tenant:
            return JsonResponse({"error": {"code": "not_found", "message": "Tenant no encontrado"}}, status=404)
        
        from datetime import datetime
        
        def get_metrics_for_period(period_str):
            period_date = datetime.strptime(f"{period_str}-01", "%Y-%m-%d").date()
            snapshot = AnalysisSnapshot.objects.filter(
                tenant=tenant,
                period_month=period_date
            ).first()
            
            if snapshot:
                return snapshot.metrics
            
            job = AnalysisJob.objects.filter(
                tenant=tenant,
                period_month=period_date,
                status=JobStatus.SUCCEEDED
            ).first()
            
            if job:
                return MetricsAPIView()._generate_metrics_from_job(job)
            
            return None
        
        metrics1 = get_metrics_for_period(period1)
        metrics2 = get_metrics_for_period(period2)
        
        if not metrics1:
            return JsonResponse({"error": {"code": "not_found", "message": f"No hay datos para {period1}"}}, status=404)
        if not metrics2:
            return JsonResponse({"error": {"code": "not_found", "message": f"No hay datos para {period2}"}}, status=404)
        
        def calc_delta(m1, m2, key):
            v1 = m1.get(key, 0) or 0
            v2 = m2.get(key, 0) or 0
            diff = v1 - v2
            pct = round((diff / v2 * 100) if v2 != 0 else 0, 2)
            return {"current": v1, "previous": v2, "diff": round(diff, 2), "pct_change": pct}
        
        return JsonResponse({
            "period1": period1,
            "period2": period2,
            "comparison": {
                "total_personal_asignado": calc_delta(metrics1, metrics2, "total_personal_asignado"),
                "total_servicio_vivo": calc_delta(metrics1, metrics2, "total_servicio_vivo"),
                "coincidencias": calc_delta(metrics1, metrics2, "coincidencias"),
                "diferencia_total": calc_delta(metrics1, metrics2, "diferencia_total"),
                "cobertura_porcentaje": calc_delta(metrics1, metrics2, "cobertura_porcentaje"),
            }
        })


class DetailsAPIView(LoginRequiredJSONMixin, View):
    """API para obtener detalles del análisis (tabla paginada)."""
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        period = request.GET.get("period")
        
        # Validar paginación
        page, per_page, err = validate_pagination(request)
        if err:
            return err
        
        # Validar periodo
        period_date, err = validate_period(period)
        if err:
            return err
        
        search = request.GET.get("search", "")
        sort_by = request.GET.get("sort_by", "Personal_Real")
        sort_order = request.GET.get("sort_order", "desc")
        sort_by, sort_order, _ = validate_sort(sort_by, sort_order)
        if not sort_by:
            sort_by = "Personal_Real"
        
        if not tenant:
            return JsonResponse({"error": {"code": "not_found", "message": "Tenant no encontrado"}}, status=404)
        
        filters = {"tenant": tenant, "status": JobStatus.SUCCEEDED}
        if period:
            from datetime import datetime
            period_date = datetime.strptime(f"{period}-01", "%Y-%m-%d").date()
            filters["period_month"] = period_date
        
        job = AnalysisJob.objects.filter(**filters).order_by("-created_at").first()
        
        if not job:
            return JsonResponse({
                "data": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            })
        
        import polars as pl
        from jobs.models import Artifact, ArtifactKind
        
        artifact = job.artifacts.filter(kind=ArtifactKind.PARQUET).first()
        if not artifact:
            return JsonResponse({"error": {"code": "not_found", "message": "No hay datos de análisis"}}, status=404)
        
        try:
            # Leer desde buffer para compatibilidad con S3
            file_buffer = read_file_to_buffer(artifact.file)
            df = pl.read_parquet(file_buffer)
            
            # Agregar filtros globales desde request
            global_filters = {
                "macrozona": request.GET.get("macrozona", ""),
                "zona": request.GET.get("zona", ""),
                "compania": request.GET.get("compania", ""),
                "grupo": request.GET.get("grupo", ""),
                "sector": request.GET.get("sector", ""),
                "gerente": request.GET.get("gerente", ""),
            }
            
            # Aplicar filtros globales
            df = self._apply_global_filters(df, global_filters)
            
            if search:
                search_lower = search.lower()
                df = df.filter(
                    pl.col("Cliente_Final").cast(pl.String).str.to_lowercase().str.contains(search_lower) |
                    pl.col("Nombre_Cliente_PA").fill_null("").str.to_lowercase().str.contains(search_lower) |
                    pl.col("Unidad_Str").cast(pl.String).str.to_lowercase().str.contains(search_lower)
                )
            
            total = len(df)
            
            if sort_by in df.columns:
                df = df.sort(sort_by, descending=(sort_order == "desc"))
            
            offset = (page - 1) * per_page
            df_page = df.slice(offset, per_page)
            
            columns = [
                "Cliente_Final", "Nombre_Cliente_PA", "Unidad_Str", "Servicio_Limpio",
                "Personal_Real", "Personal_Estimado", "Diferencia", "Estado"
            ]
            columns = [c for c in columns if c in df_page.columns]
            
            data = df_page.select(columns).to_dicts()
            
            return JsonResponse({
                "data": data,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            })
            
        except Exception as e:
            logger.error(f"Error en DetailsAPIView: {e}", exc_info=True)
            return JsonResponse({"error": {"code": "server_error", "message": "Error al procesar los datos"}}, status=500)
    
    def _apply_global_filters(self, df, filters):
        """Aplica filtros globales al DataFrame."""
        import polars as pl
        
        if filters.get("macrozona"):
            df = df.filter(pl.col("Macrozona_SV") == filters["macrozona"])
        
        if filters.get("zona"):
            zona_filter = pl.lit(False)
            if "Zona_SV" in df.columns:
                zona_filter = zona_filter | (pl.col("Zona_SV") == filters["zona"])
            if "Zona_PA" in df.columns:
                zona_filter = zona_filter | (pl.col("Zona_PA") == filters["zona"])
            df = df.filter(zona_filter)
        
        if filters.get("compania"):
            compania_filter = pl.lit(False)
            if "Compañía_SV" in df.columns:
                compania_filter = compania_filter | (pl.col("Compañía_SV") == filters["compania"])
            if "Compañía_PA" in df.columns:
                compania_filter = compania_filter | (pl.col("Compañía_PA") == filters["compania"])
            df = df.filter(compania_filter)
        
        if filters.get("grupo"):
            grupo_filter = pl.lit(False)
            if "Nombre_Grupo_SV" in df.columns:
                grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_SV") == filters["grupo"])
            if "Nombre_Grupo_PA" in df.columns:
                grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_PA") == filters["grupo"])
            df = df.filter(grupo_filter)
        
        if filters.get("sector"):
            sector_filter = pl.lit(False)
            if "Sector_SV" in df.columns:
                sector_filter = sector_filter | (pl.col("Sector_SV") == filters["sector"])
            if "Sector_PA" in df.columns:
                sector_filter = sector_filter | (pl.col("Sector_PA") == filters["sector"])
            df = df.filter(sector_filter)
        
        if filters.get("gerente"):
            gerente_filter = pl.lit(False)
            if "Gerencia_SV" in df.columns:
                gerente_filter = gerente_filter | (pl.col("Gerencia_SV") == filters["gerente"])
            if "Gerencia_PA" in df.columns:
                gerente_filter = gerente_filter | (pl.col("Gerencia_PA") == filters["gerente"])
            df = df.filter(gerente_filter)
        
        return df


class ClientsAPIView(LoginRequiredJSONMixin, View):
    """API para obtener datos de clientes con paginación."""
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        period = request.GET.get("period")
        
        # Validar paginación
        page, per_page, err = validate_pagination(request)
        if err:
            return err
        
        # Validar periodo
        period_date, err = validate_period(period)
        if err:
            return err
        
        search = request.GET.get("search", "")
        sort_by = request.GET.get("sort_by", "pa")
        sort_order = request.GET.get("sort_order", "desc")
        sort_by, sort_order, _ = validate_sort(sort_by, sort_order)
        if not sort_by:
            sort_by = "pa"
        
        if not tenant:
            return JsonResponse({"error": {"code": "not_found", "message": "Tenant no encontrado"}}, status=404)
        
        filters = {"tenant": tenant, "status": JobStatus.SUCCEEDED}
        if period:
            from datetime import datetime
            period_date = datetime.strptime(f"{period}-01", "%Y-%m-%d").date()
            filters["period_month"] = period_date
        
        job = AnalysisJob.objects.filter(**filters).order_by("-created_at").first()
        
        if not job:
            return JsonResponse({
                "data": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            })
        
        import polars as pl
        from jobs.models import Artifact, ArtifactKind
        
        artifact = job.artifacts.filter(kind=ArtifactKind.PARQUET).first()
        if not artifact:
            return JsonResponse({"error": {"code": "not_found", "message": "No hay datos de análisis"}}, status=404)
        
        try:
            # Leer desde buffer para compatibilidad con S3
            file_buffer = read_file_to_buffer(artifact.file)
            df = pl.read_parquet(file_buffer)
            
            # Agregar filtros globales desde request
            global_filters = {
                "macrozona": request.GET.get("macrozona", ""),
                "zona": request.GET.get("zona", ""),
                "compania": request.GET.get("compania", ""),
                "grupo": request.GET.get("grupo", ""),
                "sector": request.GET.get("sector", ""),
                "gerente": request.GET.get("gerente", ""),
            }
            
            # Aplicar filtros globales
            df = self._apply_global_filters(df, global_filters)
            
            # Agrupar por cliente
            df_cliente = df.with_columns(
                pl.coalesce([
                    pl.col("Nombre_Cliente_SV") if "Nombre_Cliente_SV" in df.columns else pl.lit(None),
                    pl.col("Nombre_Cliente_PA") if "Nombre_Cliente_PA" in df.columns else pl.lit(None),
                    pl.col("Cliente_Final")
                ]).alias("Nombre_Cliente_Display")
            )
            
            by_cliente = df_cliente.group_by("Cliente_Final").agg([
                pl.col("Personal_Real").sum().alias("pa"),
                pl.col("Personal_Estimado").sum().alias("sv"),
                (pl.col("Personal_Real").sum() - pl.col("Personal_Estimado").sum()).alias("diferencia"),
                pl.col("Nombre_Cliente_Display").first().alias("nombre"),
                pl.len().alias("servicios")
            ])
            
            # Aplicar búsqueda
            if search:
                search_lower = search.lower()
                by_cliente = by_cliente.filter(
                    pl.col("Cliente_Final").cast(pl.String).str.to_lowercase().str.contains(search_lower) |
                    pl.col("nombre").cast(pl.String).str.to_lowercase().str.contains(search_lower)
                )
            
            total = len(by_cliente)
            
            # Aplicar ordenamiento
            if sort_by == "pa":
                by_cliente = by_cliente.sort("pa", descending=(sort_order == "desc"))
            elif sort_by == "sv":
                by_cliente = by_cliente.sort("sv", descending=(sort_order == "desc"))
            elif sort_by == "diferencia":
                by_cliente = by_cliente.sort("diferencia", descending=(sort_order == "desc"))
            elif sort_by == "nombre":
                by_cliente = by_cliente.sort("nombre", descending=(sort_order == "desc"))
            else:
                by_cliente = by_cliente.sort("pa", descending=True)
            
            # Paginación
            offset = (page - 1) * per_page
            df_page = by_cliente.slice(offset, per_page)
            
            data = df_page.to_dicts()
            
            return JsonResponse({
                "data": data,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            })
            
        except Exception as e:
            logger.error(f"Error en ClientsAPIView: {e}", exc_info=True)
            return JsonResponse({"error": {"code": "server_error", "message": "Error al procesar los datos"}}, status=500)
    
    def _apply_global_filters(self, df, filters):
        """Aplica filtros globales al DataFrame."""
        import polars as pl
        
        if filters.get("macrozona"):
            df = df.filter(pl.col("Macrozona_SV") == filters["macrozona"])
        
        if filters.get("zona"):
            zona_filter = pl.lit(False)
            if "Zona_SV" in df.columns:
                zona_filter = zona_filter | (pl.col("Zona_SV") == filters["zona"])
            if "Zona_PA" in df.columns:
                zona_filter = zona_filter | (pl.col("Zona_PA") == filters["zona"])
            df = df.filter(zona_filter)
        
        if filters.get("compania"):
            compania_filter = pl.lit(False)
            if "Compañía_SV" in df.columns:
                compania_filter = compania_filter | (pl.col("Compañía_SV") == filters["compania"])
            if "Compañía_PA" in df.columns:
                compania_filter = compania_filter | (pl.col("Compañía_PA") == filters["compania"])
            df = df.filter(compania_filter)
        
        if filters.get("grupo"):
            grupo_filter = pl.lit(False)
            if "Nombre_Grupo_SV" in df.columns:
                grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_SV") == filters["grupo"])
            if "Nombre_Grupo_PA" in df.columns:
                grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_PA") == filters["grupo"])
            df = df.filter(grupo_filter)
        
        if filters.get("sector"):
            sector_filter = pl.lit(False)
            if "Sector_SV" in df.columns:
                sector_filter = sector_filter | (pl.col("Sector_SV") == filters["sector"])
            if "Sector_PA" in df.columns:
                sector_filter = sector_filter | (pl.col("Sector_PA") == filters["sector"])
            df = df.filter(sector_filter)
        
        if filters.get("gerente"):
            gerente_filter = pl.lit(False)
            if "Gerencia_SV" in df.columns:
                gerente_filter = gerente_filter | (pl.col("Gerencia_SV") == filters["gerente"])
            if "Gerencia_PA" in df.columns:
                gerente_filter = gerente_filter | (pl.col("Gerencia_PA") == filters["gerente"])
            df = df.filter(gerente_filter)
        
        return df


class UnitsAPIView(LoginRequiredJSONMixin, View):
    """API para obtener datos de unidades con paginación."""
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        period = request.GET.get("period")
        
        # Validar paginación
        page, per_page, err = validate_pagination(request)
        if err:
            return err
        
        # Validar periodo
        period_date, err = validate_period(period)
        if err:
            return err
        
        search = request.GET.get("search", "")
        sort_by = request.GET.get("sort_by", "pa")
        sort_order = request.GET.get("sort_order", "desc")
        sort_by, sort_order, _ = validate_sort(sort_by, sort_order)
        if not sort_by:
            sort_by = "pa"
        
        if not tenant:
            return JsonResponse({"error": {"code": "not_found", "message": "Tenant no encontrado"}}, status=404)
        
        filters = {"tenant": tenant, "status": JobStatus.SUCCEEDED}
        if period:
            from datetime import datetime
            period_date = datetime.strptime(f"{period}-01", "%Y-%m-%d").date()
            filters["period_month"] = period_date
        
        job = AnalysisJob.objects.filter(**filters).order_by("-created_at").first()
        
        if not job:
            return JsonResponse({
                "data": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            })
        
        import polars as pl
        from jobs.models import Artifact, ArtifactKind
        
        artifact = job.artifacts.filter(kind=ArtifactKind.PARQUET).first()
        if not artifact:
            return JsonResponse({"error": {"code": "not_found", "message": "No hay datos de análisis"}}, status=404)
        
        try:
            # Leer desde buffer para compatibilidad con S3
            file_buffer = read_file_to_buffer(artifact.file)
            df = pl.read_parquet(file_buffer)
            
            # Agregar filtros globales desde request
            global_filters = {
                "macrozona": request.GET.get("macrozona", ""),
                "zona": request.GET.get("zona", ""),
                "compania": request.GET.get("compania", ""),
                "grupo": request.GET.get("grupo", ""),
                "sector": request.GET.get("sector", ""),
                "gerente": request.GET.get("gerente", ""),
            }
            
            # Aplicar filtros globales
            df = self._apply_global_filters(df, global_filters)
            
            # Agrupar por unidad
            df_unidad = df.with_columns(
                pl.coalesce([
                    pl.col("Nombre_Unidad_SV") if "Nombre_Unidad_SV" in df.columns else pl.lit(None),
                    pl.col("Nombre_Unidad_PA") if "Nombre_Unidad_PA" in df.columns else pl.lit(None),
                    pl.col("Unidad_Str")
                ]).alias("Nombre_Unidad_Display")
            )
            
            by_unidad = df_unidad.group_by("Unidad_Str").agg([
                pl.col("Personal_Real").sum().alias("pa"),
                pl.col("Personal_Estimado").sum().alias("sv"),
                (pl.col("Personal_Real").sum() - pl.col("Personal_Estimado").sum()).alias("diferencia"),
                pl.col("Nombre_Unidad_Display").first().alias("nombre"),
                pl.len().alias("servicios")
            ])
            
            # Aplicar búsqueda
            if search:
                search_lower = search.lower()
                by_unidad = by_unidad.filter(
                    pl.col("Unidad_Str").cast(pl.String).str.to_lowercase().str.contains(search_lower) |
                    pl.col("nombre").cast(pl.String).str.to_lowercase().str.contains(search_lower)
                )
            
            total = len(by_unidad)
            
            # Aplicar ordenamiento
            if sort_by == "pa":
                by_unidad = by_unidad.sort("pa", descending=(sort_order == "desc"))
            elif sort_by == "sv":
                by_unidad = by_unidad.sort("sv", descending=(sort_order == "desc"))
            elif sort_by == "diferencia":
                by_unidad = by_unidad.sort("diferencia", descending=(sort_order == "desc"))
            elif sort_by == "nombre":
                by_unidad = by_unidad.sort("nombre", descending=(sort_order == "desc"))
            else:
                by_unidad = by_unidad.sort("pa", descending=True)
            
            # Paginación
            offset = (page - 1) * per_page
            df_page = by_unidad.slice(offset, per_page)
            
            data = df_page.to_dicts()
            
            return JsonResponse({
                "data": data,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            })
            
        except Exception as e:
            logger.error(f"Error en UnitsAPIView: {e}", exc_info=True)
            return JsonResponse({"error": {"code": "server_error", "message": "Error al procesar los datos"}}, status=500)
    
    def _apply_global_filters(self, df, filters):
        """Aplica filtros globales al DataFrame."""
        import polars as pl
        
        if filters.get("macrozona"):
            df = df.filter(pl.col("Macrozona_SV") == filters["macrozona"])
        if filters.get("zona"):
            zona_filter = pl.lit(False)
            if "Zona_SV" in df.columns:
                zona_filter = zona_filter | (pl.col("Zona_SV") == filters["zona"])
            if "Zona_PA" in df.columns:
                zona_filter = zona_filter | (pl.col("Zona_PA") == filters["zona"])
            df = df.filter(zona_filter)
        if filters.get("compania"):
            compania_filter = pl.lit(False)
            if "Compañía_SV" in df.columns:
                compania_filter = compania_filter | (pl.col("Compañía_SV") == filters["compania"])
            if "Compañía_PA" in df.columns:
                compania_filter = compania_filter | (pl.col("Compañía_PA") == filters["compania"])
            df = df.filter(compania_filter)
        if filters.get("grupo"):
            grupo_filter = pl.lit(False)
            if "Nombre_Grupo_SV" in df.columns:
                grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_SV") == filters["grupo"])
            if "Nombre_Grupo_PA" in df.columns:
                grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_PA") == filters["grupo"])
            df = df.filter(grupo_filter)
        if filters.get("sector"):
            sector_filter = pl.lit(False)
            if "Sector_SV" in df.columns:
                sector_filter = sector_filter | (pl.col("Sector_SV") == filters["sector"])
            if "Sector_PA" in df.columns:
                sector_filter = sector_filter | (pl.col("Sector_PA") == filters["sector"])
            df = df.filter(sector_filter)
        if filters.get("gerente"):
            gerente_filter = pl.lit(False)
            if "Gerencia_SV" in df.columns:
                gerente_filter = gerente_filter | (pl.col("Gerencia_SV") == filters["gerente"])
            if "Gerencia_PA" in df.columns:
                gerente_filter = gerente_filter | (pl.col("Gerencia_PA") == filters["gerente"])
            df = df.filter(gerente_filter)
        return df


class ServicesAPIView(LoginRequiredJSONMixin, View):
    """API para obtener datos de servicios con paginación."""
    
    def get(self, request):
        tenant = get_tenant_for_user(request.user, request)
        period = request.GET.get("period")
        
        # Validar paginación
        page, per_page, err = validate_pagination(request)
        if err:
            return err
        
        # Validar periodo
        period_date, err = validate_period(period)
        if err:
            return err
        
        search = request.GET.get("search", "")
        sort_by = request.GET.get("sort_by", "pa")
        sort_order = request.GET.get("sort_order", "desc")
        sort_by, sort_order, _ = validate_sort(sort_by, sort_order)
        if not sort_by:
            sort_by = "pa"
        
        if not tenant:
            return JsonResponse({"error": {"code": "not_found", "message": "Tenant no encontrado"}}, status=404)
        
        filters = {"tenant": tenant, "status": JobStatus.SUCCEEDED}
        if period:
            from datetime import datetime
            period_date = datetime.strptime(f"{period}-01", "%Y-%m-%d").date()
            filters["period_month"] = period_date
        
        job = AnalysisJob.objects.filter(**filters).order_by("-created_at").first()
        
        if not job:
            return JsonResponse({
                "data": [],
                "total": 0,
                "page": page,
                "per_page": per_page,
                "total_pages": 0
            })
        
        import polars as pl
        from jobs.models import Artifact, ArtifactKind
        
        artifact = job.artifacts.filter(kind=ArtifactKind.PARQUET).first()
        if not artifact:
            return JsonResponse({"error": {"code": "not_found", "message": "No hay datos de análisis"}}, status=404)
        
        try:
            # Leer desde buffer para compatibilidad con S3
            file_buffer = read_file_to_buffer(artifact.file)
            df = pl.read_parquet(file_buffer)
            
            # Agregar filtros globales desde request
            global_filters = {
                "macrozona": request.GET.get("macrozona", ""),
                "zona": request.GET.get("zona", ""),
                "compania": request.GET.get("compania", ""),
                "grupo": request.GET.get("grupo", ""),
                "sector": request.GET.get("sector", ""),
                "gerente": request.GET.get("gerente", ""),
            }
            
            # Aplicar filtros globales
            df = self._apply_global_filters(df, global_filters)
            
            # Agrupar por servicio
            df_servicio = df.with_columns(
                pl.coalesce([
                    pl.col("Nombre_Servicio_SV") if "Nombre_Servicio_SV" in df.columns else pl.lit(None),
                    pl.col("Nombre_Servicio_PA") if "Nombre_Servicio_PA" in df.columns else pl.lit(None),
                    pl.col("Servicio_Limpio")
                ]).alias("Nombre_Servicio_Display")
            )
            
            by_servicio = df_servicio.group_by("Servicio_Limpio").agg([
                pl.col("Personal_Real").sum().alias("pa"),
                pl.col("Personal_Estimado").sum().alias("sv"),
                (pl.col("Personal_Real").sum() - pl.col("Personal_Estimado").sum()).alias("diferencia"),
                pl.col("Nombre_Servicio_Display").first().alias("nombre"),
                pl.len().alias("registros")
            ])
            
            # Aplicar búsqueda
            if search:
                search_lower = search.lower()
                by_servicio = by_servicio.filter(
                    pl.col("Servicio_Limpio").cast(pl.String).str.to_lowercase().str.contains(search_lower) |
                    pl.col("nombre").cast(pl.String).str.to_lowercase().str.contains(search_lower)
                )
            
            total = len(by_servicio)
            
            # Aplicar ordenamiento
            if sort_by == "pa":
                by_servicio = by_servicio.sort("pa", descending=(sort_order == "desc"))
            elif sort_by == "sv":
                by_servicio = by_servicio.sort("sv", descending=(sort_order == "desc"))
            elif sort_by == "diferencia":
                by_servicio = by_servicio.sort("diferencia", descending=(sort_order == "desc"))
            elif sort_by == "nombre":
                by_servicio = by_servicio.sort("nombre", descending=(sort_order == "desc"))
            else:
                by_servicio = by_servicio.sort("pa", descending=True)
            
            # Paginación
            offset = (page - 1) * per_page
            df_page = by_servicio.slice(offset, per_page)
            
            data = df_page.to_dicts()
            
            return JsonResponse({
                "data": data,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            })
            
        except Exception as e:
            logger.error(f"Error en ServicesAPIView: {e}", exc_info=True)
            return JsonResponse({"error": {"code": "server_error", "message": "Error al procesar los datos"}}, status=500)
    
    def _apply_global_filters(self, df, filters):
        """Aplica filtros globales al DataFrame."""
        import polars as pl
        
        if filters.get("macrozona"):
            df = df.filter(pl.col("Macrozona_SV") == filters["macrozona"])
        
        if filters.get("zona"):
            zona_filter = pl.lit(False)
            if "Zona_SV" in df.columns:
                zona_filter = zona_filter | (pl.col("Zona_SV") == filters["zona"])
            if "Zona_PA" in df.columns:
                zona_filter = zona_filter | (pl.col("Zona_PA") == filters["zona"])
            df = df.filter(zona_filter)
        
        if filters.get("compania"):
            compania_filter = pl.lit(False)
            if "Compañía_SV" in df.columns:
                compania_filter = compania_filter | (pl.col("Compañía_SV") == filters["compania"])
            if "Compañía_PA" in df.columns:
                compania_filter = compania_filter | (pl.col("Compañía_PA") == filters["compania"])
            df = df.filter(compania_filter)
        
        if filters.get("grupo"):
            grupo_filter = pl.lit(False)
            if "Nombre_Grupo_SV" in df.columns:
                grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_SV") == filters["grupo"])
            if "Nombre_Grupo_PA" in df.columns:
                grupo_filter = grupo_filter | (pl.col("Nombre_Grupo_PA") == filters["grupo"])
            df = df.filter(grupo_filter)
        
        if filters.get("sector"):
            sector_filter = pl.lit(False)
            if "Sector_SV" in df.columns:
                sector_filter = sector_filter | (pl.col("Sector_SV") == filters["sector"])
            if "Sector_PA" in df.columns:
                sector_filter = sector_filter | (pl.col("Sector_PA") == filters["sector"])
            df = df.filter(sector_filter)
        
        if filters.get("gerente"):
            gerente_filter = pl.lit(False)
            if "Gerencia_SV" in df.columns:
                gerente_filter = gerente_filter | (pl.col("Gerencia_SV") == filters["gerente"])
            if "Gerencia_PA" in df.columns:
                gerente_filter = gerente_filter | (pl.col("Gerencia_PA") == filters["gerente"])
            df = df.filter(gerente_filter)
        
        return df


class CustomLoginView(View):
    """Vista de login personalizada con protección contra brute force.
    
    Integra:
    - django-axes para lockout tras 5 intentos fallidos (30 min)
    - CAPTCHA después de 3 intentos fallidos
    - Rate limiting vía IPRateLimitMiddleware
    """
    template_name = "dashboard/login.html"
    CAPTCHA_THRESHOLD = 3  # Mostrar CAPTCHA después de N intentos fallidos
    
    def _get_failed_attempts(self, request):
        """Obtiene el número de intentos fallidos para la IP actual."""
        client_ip = get_client_ip_address(request)
        cache_key = f"login_attempts:{client_ip}"
        return cache.get(cache_key, 0)
    
    def _increment_failed_attempts(self, request):
        """Incrementa y retorna el contador de intentos fallidos."""
        client_ip = get_client_ip_address(request)
        cache_key = f"login_attempts:{client_ip}"
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, 1800)  # 30 min TTL, consistente con AXES_COOLOFF_TIME
        return attempts
    
    def _reset_failed_attempts(self, request):
        """Resetea el contador de intentos fallidos tras login exitoso."""
        client_ip = get_client_ip_address(request)
        cache_key = f"login_attempts:{client_ip}"
        cache.delete(cache_key)
    
    def _needs_captcha(self, request):
        """Determina si debe mostrar CAPTCHA."""
        return self._get_failed_attempts(request) >= self.CAPTCHA_THRESHOLD
    
    def _generate_captcha(self):
        """Genera un nuevo CAPTCHA y retorna key + image_url."""
        captcha_key = CaptchaStore.generate_key()
        captcha_url = captcha_image_url(captcha_key)
        return captcha_key, captcha_url
    
    def _build_context(self, request, error=None):
        """Construye el contexto del template con estado de CAPTCHA."""
        ctx = {}
        if error:
            ctx["error"] = error
        attempts = self._get_failed_attempts(request)
        ctx["failed_attempts"] = attempts
        if attempts >= self.CAPTCHA_THRESHOLD:
            captcha_key, captcha_url = self._generate_captcha()
            ctx["captcha_key"] = captcha_key
            ctx["captcha_image_url"] = captcha_url
            ctx["show_captcha"] = True
        return ctx
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard:main')
        return render(request, self.template_name, self._build_context(request))
    
    def post(self, request):
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        # Verificar CAPTCHA si es requerido
        if self._needs_captcha(request):
            captcha_key = request.POST.get('captcha_key', '')
            captcha_value = request.POST.get('captcha_value', '').strip()
            
            try:
                captcha_obj = CaptchaStore.objects.get(hashkey=captcha_key)
                if captcha_obj.response != captcha_value.lower():
                    return render(request, self.template_name, self._build_context(
                        request, error='Código de verificación incorrecto'
                    ))
            except CaptchaStore.DoesNotExist:
                return render(request, self.template_name, self._build_context(
                    request, error='Código de verificación expirado. Intente de nuevo.'
                ))
        
        # authenticate() pasa por AxesStandaloneBackend que maneja el lockout
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            self._reset_failed_attempts(request)
            return redirect('dashboard:main')
        else:
            attempts = self._increment_failed_attempts(request)
            remaining = max(0, get_failure_limit(request, None) - attempts)
            
            if remaining == 0:
                error = 'Cuenta bloqueada temporalmente. Intente de nuevo en 30 minutos.'
            else:
                error = f'Usuario o contraseña incorrectos. {remaining} intento(s) restante(s).'
            
            return render(request, self.template_name, self._build_context(request, error=error))


class CustomLogoutView(LoginRequiredMixin, View):
    """Vista de logout personalizada - solo POST."""
    login_url = "/dashboard/login/"
    
    def post(self, request):
        logout(request)
        return redirect('dashboard:login')
    
    def get(self, request):
        """GET no permitido para logout - redirigir al dashboard."""
        return redirect('dashboard:main')
