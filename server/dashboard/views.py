"""
Dashboard Views - Vistas para el dashboard de métricas PA vs SV.
"""
from django.db.models import Sum, Count, Avg
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin

from jobs.models import AnalysisJob, AnalysisSnapshot, JobStatus, Artifact, ArtifactKind
from tenants.models import Tenant, Membership, MembershipRole


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


class UploadView(LoginRequiredMixin, TemplateView):
    """Vista para subir archivos Excel con drag & drop."""
    template_name = "dashboard/upload.html"
    login_url = "/admin/login/"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = Tenant.objects.filter(slug="default").first()
        
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
    login_url = "/admin/login/"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener tenant (por ahora usa default)
        tenant = Tenant.objects.filter(slug="default").first()
        
        # Permisos del usuario
        permissions = get_user_permissions(self.request.user)
        
        # Obtener periodos disponibles
        snapshots = AnalysisSnapshot.objects.filter(
            tenant=tenant
        ).order_by("-period_month") if tenant else []
        
        periods = [
            {
                "value": s.period_month.strftime("%Y-%m"),
                "label": s.period_month.strftime("%B %Y")
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
                            "label": job.period_month.strftime("%B %Y")
                        })
        
        context["tenant"] = tenant
        context["periods"] = periods
        context["current_period"] = periods[0] if periods else None
        context["user"] = self.request.user
        context["permissions"] = permissions
        
        return context


@method_decorator(csrf_exempt, name="dispatch")
class MetricsAPIView(View):
    """API para obtener métricas del dashboard."""
    
    def get(self, request):
        tenant_slug = request.GET.get("tenant", "default")
        period = request.GET.get("period")  # Formato: YYYY-MM
        
        # Filtros opcionales recibidos desde frontend
        request_filters = {
            "macrozona": request.GET.get("macrozona", ""),
            "zona": request.GET.get("zona", ""),
            "compania": request.GET.get("compania", ""),
            "grupo": request.GET.get("grupo", ""),
            "sector": request.GET.get("sector", ""),
            "gerente": request.GET.get("gerente", ""),
        }
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            return JsonResponse({"error": "Tenant no encontrado"}, status=404)
        
        # Buscar snapshot del periodo (consulta de snapshots/jobs no incluye filtros de UI)
        snapshot_query = {"tenant": tenant}
        if period:
            from datetime import datetime
            period_date = datetime.strptime(f"{period}-01", "%Y-%m-%d").date()
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
        
        filters = filters or {}
        
        artifact = job.artifacts.filter(kind=ArtifactKind.PARQUET).first()
        if not artifact:
            return {}
        
        try:
            df = pl.read_parquet(artifact.file.path)
            
            # Aplicar filtros
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
                    "filtros_disponibles": {},
                }
            
            # KPIs básicos
            total_pa = int(df["Personal_Real"].sum() or 0)
            total_sv = float(df["Personal_Estimado"].sum() or 0)
            coincidencias = len(df.filter(
                (pl.col("Personal_Real") > 0) & (pl.col("Personal_Estimado") > 0)
            ))
            diferencia = total_pa - total_sv
            # Cobertura = PA/SV × 100 (qué tanto del SV está cubierto por PA)
            cobertura = round((total_pa / total_sv * 100) if total_sv > 0 else 0, 2)
            
            # Por estado
            by_estado = df.group_by("Estado").agg([
                pl.col("Personal_Real").sum().alias("pa"),
                pl.col("Personal_Estimado").sum().alias("sv"),
                pl.len().alias("count")
            ]).sort("count", descending=True).to_dicts()
            
            # Por zona - PREFERIR SV, SI NO HAY USAR PA
            by_zona = []
            zona_col = None
            if "Zona_SV" in df.columns:
                zona_col = "Zona_SV"
            elif "Zona_PA" in df.columns:
                zona_col = "Zona_PA"
            
            if zona_col:
                # Crear columna de zona combinada (preferir SV)
                df_zona = df.with_columns(
                    pl.coalesce([
                        pl.when(pl.col("Zona_SV").is_not_null() & (pl.col("Zona_SV") != ""))
                        .then(pl.col("Zona_SV"))
                        .otherwise(None) if "Zona_SV" in df.columns else pl.lit(None),
                        pl.when(pl.col("Zona_PA").is_not_null() & (pl.col("Zona_PA") != ""))
                        .then(pl.col("Zona_PA"))
                        .otherwise(None) if "Zona_PA" in df.columns else pl.lit(None),
                        pl.lit("Sin Zona")
                    ]).alias("Zona_Display")
                )
                by_zona = df_zona.group_by("Zona_Display").agg([
                    pl.col("Personal_Real").sum().alias("pa"),
                    pl.col("Personal_Estimado").sum().alias("sv"),
                    pl.len().alias("count")
                ]).filter(
                    pl.col("Zona_Display").is_not_null() & (pl.col("Zona_Display") != "")
                ).sort("pa", descending=True).head(10).to_dicts()
            
            # Por MacroZona
            by_macrozona = []
            if "Macrozona_SV" in df.columns:
                by_macrozona = df.group_by("Macrozona_SV").agg([
                    pl.col("Personal_Real").sum().alias("pa"),
                    pl.col("Personal_Estimado").sum().alias("sv"),
                    pl.len().alias("count")
                ]).filter(
                    pl.col("Macrozona_SV").is_not_null() & (pl.col("Macrozona_SV") != "")
                ).sort("pa", descending=True).to_dicts()
            
            # Top 10 clientes con nombre combinado (preferir SV > PA)
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
            ]).sort("pa", descending=True).head(10).to_dicts()
            
            # Por Unidad - Top 10
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
            ]).sort("pa", descending=True).head(10).to_dicts()
            
            # Por Servicio - Top 10
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
            ]).sort("pa", descending=True).head(10).to_dicts()
            
            # Por Grupo
            by_grupo = []
            grupo_col = "Nombre_Grupo_SV" if "Nombre_Grupo_SV" in df.columns else ("Nombre_Grupo_PA" if "Nombre_Grupo_PA" in df.columns else None)
            if grupo_col:
                by_grupo = df.group_by(grupo_col).agg([
                    pl.col("Personal_Real").sum().alias("pa"),
                    pl.col("Personal_Estimado").sum().alias("sv"),
                    pl.len().alias("count")
                ]).filter(
                    pl.col(grupo_col).is_not_null() & (pl.col(grupo_col) != "")
                ).sort("pa", descending=True).head(10).to_dicts()
            
            # Calcular cobertura diferencial
            cobertura_diff = round((diferencia / total_sv * 100) if total_sv > 0 else 0, 2)
            
            # Obtener lista de filtros disponibles
            filtros_disponibles = {
                "macrozona": self._get_unique_values(df, "Macrozona_SV"),
                "zona": self._get_unique_values(df, "Zona_SV", "Zona_PA"),
                "compania": self._get_unique_values(df, "Compañía_SV", "Compañía_PA"),
                "grupo": self._get_unique_values(df, "Nombre_Grupo_SV", "Nombre_Grupo_PA"),
                "sector": self._get_unique_values(df, "Sector_SV", "Sector_PA"),
                "gerente": self._get_unique_values(df, "Gerencia_SV", "Gerencia_PA"),
            }
            
            return {
                "total_personal_asignado": total_pa,
                "total_servicio_vivo": round(total_sv, 2),
                "coincidencias": coincidencias,
                "diferencia_total": round(diferencia, 2),
                "cobertura_porcentaje": cobertura,
                "cobertura_diferencial": cobertura_diff,
                "total_servicios": len(df),
                "by_estado": by_estado,
                "by_zona": by_zona,
                "by_macrozona": by_macrozona,
                "by_cliente_top10": by_cliente,
                "by_unidad_top10": by_unidad,
                "by_servicio_top10": by_servicio,
                "by_grupo": by_grupo,
                "filtros_disponibles": filtros_disponibles,
            }
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


@method_decorator(csrf_exempt, name="dispatch")
class PeriodsAPIView(View):
    """API para obtener periodos disponibles."""
    
    def get(self, request):
        tenant_slug = request.GET.get("tenant", "default")
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
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
                        "label": job.period_month.strftime("%B %Y") if job.period_month else job.created_at.strftime("%B %Y"),
                        "job_id": str(job.id)
                    })
        else:
            periods = [
                {
                    "value": s.period_month.strftime("%Y-%m"),
                    "label": s.period_month.strftime("%B %Y"),
                    "job_id": str(s.job_id)
                }
                for s in snapshots
            ]
        
        return JsonResponse({"periods": periods})


@method_decorator(csrf_exempt, name="dispatch")
class CompareAPIView(View):
    """API para comparar dos periodos."""
    
    def get(self, request):
        tenant_slug = request.GET.get("tenant", "default")
        period1 = request.GET.get("period1")
        period2 = request.GET.get("period2")
        
        if not period1 or not period2:
            return JsonResponse({"error": "Se requieren period1 y period2"}, status=400)
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            return JsonResponse({"error": "Tenant no encontrado"}, status=404)
        
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
            return JsonResponse({"error": f"No hay datos para {period1}"}, status=404)
        if not metrics2:
            return JsonResponse({"error": f"No hay datos para {period2}"}, status=404)
        
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


@method_decorator(csrf_exempt, name="dispatch")
class DetailsAPIView(View):
    """API para obtener detalles del análisis (tabla paginada)."""
    
    def get(self, request):
        tenant_slug = request.GET.get("tenant", "default")
        period = request.GET.get("period")
        page = int(request.GET.get("page", 1))
        per_page = int(request.GET.get("per_page", 25))
        search = request.GET.get("search", "")
        sort_by = request.GET.get("sort_by", "Personal_Real")
        sort_order = request.GET.get("sort_order", "desc")
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            return JsonResponse({"error": "Tenant no encontrado"}, status=404)
        
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
            return JsonResponse({"error": "No hay datos de análisis"}, status=404)
        
        try:
            df = pl.read_parquet(artifact.file.path)
            
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
            return JsonResponse({"error": str(e)}, status=500)
    
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


@method_decorator(csrf_exempt, name="dispatch")
class ClientsAPIView(View):
    """API para obtener datos de clientes con paginación."""
    
    def get(self, request):
        tenant_slug = request.GET.get("tenant", "default")
        period = request.GET.get("period")
        page = int(request.GET.get("page", 1))
        per_page = int(request.GET.get("per_page", 25))
        search = request.GET.get("search", "")
        sort_by = request.GET.get("sort_by", "pa")
        sort_order = request.GET.get("sort_order", "desc")
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            return JsonResponse({"error": "Tenant no encontrado"}, status=404)
        
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
            return JsonResponse({"error": "No hay datos de análisis"}, status=404)
        
        try:
            df = pl.read_parquet(artifact.file.path)
            
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
            return JsonResponse({"error": str(e)}, status=500)
    
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


@method_decorator(csrf_exempt, name="dispatch")
class UnitsAPIView(View):
    """API para obtener datos de unidades con paginación."""
    
    def get(self, request):
        tenant_slug = request.GET.get("tenant", "default")
        period = request.GET.get("period")
        page = int(request.GET.get("page", 1))
        per_page = int(request.GET.get("per_page", 25))
        search = request.GET.get("search", "")
        sort_by = request.GET.get("sort_by", "pa")
        sort_order = request.GET.get("sort_order", "desc")
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            return JsonResponse({"error": "Tenant no encontrado"}, status=404)
        
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
            return JsonResponse({"error": "No hay datos de análisis"}, status=404)
        
        try:
            df = pl.read_parquet(artifact.file.path)
            
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
            return JsonResponse({"error": str(e)}, status=500)
    
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


@method_decorator(csrf_exempt, name="dispatch")
class ServicesAPIView(View):
    """API para obtener datos de servicios con paginación."""
    
    def get(self, request):
        tenant_slug = request.GET.get("tenant", "default")
        period = request.GET.get("period")
        page = int(request.GET.get("page", 1))
        per_page = int(request.GET.get("per_page", 25))
        search = request.GET.get("search", "")
        sort_by = request.GET.get("sort_by", "pa")
        sort_order = request.GET.get("sort_order", "desc")
        
        try:
            tenant = Tenant.objects.get(slug=tenant_slug)
        except Tenant.DoesNotExist:
            return JsonResponse({"error": "Tenant no encontrado"}, status=404)
        
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
            return JsonResponse({"error": "No hay datos de análisis"}, status=404)
        
        try:
            df = pl.read_parquet(artifact.file.path)
            
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
            return JsonResponse({"error": str(e)}, status=500)
    
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
