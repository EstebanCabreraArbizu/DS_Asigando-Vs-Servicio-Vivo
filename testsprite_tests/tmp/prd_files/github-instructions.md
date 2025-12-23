# Instrucciones (PA vs SV Web — Django)

## Contexto
- El pipeline actual (Polars) vive en `core/`: `data_loader.py`, `data_processor.py`, `analysis_engine.py`, `excel_exporter.py`.
- El backend web nuevo vive en `server/` (Django + DRF + Celery).
- Los archivos de datos y resultados locales están en `data/` (ignorados por Git).
- Decisión de almacenamiento: **Opción A**
  - Excel final como artefacto descargable.
  - `Resultado_Final` como Parquet por Job.
  - Agregados/snapshots en Postgres para dashboard.

---

## Estado de las EPICs

### ✅ EPIC 1 — Fundaciones (COMPLETADA)
- Django + DRF funcionando
- Endpoints: health, jobs (create/status/excel)
- Celery task para ejecutar pipeline
- Docker Compose configurado

### ✅ EPIC 2 — Multi-tenant + Seguridad (COMPLETADA)
- Modelo `Tenant` con slug único
- Modelo `Membership` (User ↔ Tenant con roles: owner/admin/analyst/viewer)
- `AnalysisJob` con FK a `Tenant` (aislamiento de datos)
- `AnalysisSnapshot` para agregados por tenant/periodo
- Archivos organizados por tenant: `tenants/{slug}/jobs/{id}/...`
- Índices optimizados para queries por tenant + periodo
- **Pendiente para producción**: Activar RLS en PostgreSQL

### 🔲 EPIC 3 — Dashboard Embebido (PENDIENTE)
**IMPORTANTE**: NO usar Power BI. Crear dashboard propio con:
- **Frontend**: Gráficos interactivos estilo Power BI usando Plotly.js o Apache ECharts
- **Backend**: API de métricas desde `AnalysisSnapshot`
- **Características**:
  - Filtros por periodo, tenant, tipo de servicio
  - Comparativo mensual (periodo actual vs anterior)
  - KPIs: total PA, total SV, coincidencias, diferencias
  - Gráficos: barras, líneas temporales, treemaps por categoría
  - Exportar gráficos como imagen/PDF

---

## Prompt para EPIC 3 — Dashboard (copiar/pegar)

"""
Objetivo: Implementar EPIC 3 (Dashboard interactivo propio, SIN Power BI).

Contexto:
- Los datos vienen de `AnalysisSnapshot.metrics` (JSON con métricas agregadas)
- El dashboard debe ser responsive y profesional (estilo Power BI pero propio)
- Stack recomendado: Django templates + Plotly.js o ECharts

Tareas:
1) Crear app `dashboard/` en Django con:
   - Vista principal con filtros (tenant, periodo)
   - API endpoints para métricas: `/api/v1/dashboard/metrics/`, `/api/v1/dashboard/compare/`
2) Implementar frontend con:
   - Selector de periodo (dropdown meses disponibles)
   - KPIs en cards: Total PA, Total SV, Coincidencias, Diferencias
   - Gráfico de barras: PA vs SV por categoría
   - Gráfico de líneas: tendencia mensual
   - Tabla resumen con paginación
3) Comparativo mensual:
   - Endpoint que recibe 2 periodos y devuelve diferencias
   - Visualización side-by-side o delta

Restricciones:
- NO usar Power BI ni embeds externos
- Usar Plotly.js o Apache ECharts para gráficos
- Los datos vienen de AnalysisSnapshot, no del Parquet directamente
- Responsive design (mobile-friendly)

Aceptación:
- Dashboard carga en < 2 segundos
- Filtros actualizan gráficos en tiempo real
- Comparativo mensual funciona correctamente
"""

---

## Estructura de Modelos (EPIC 2)

```python
# tenants/models.py
Tenant(id, name, slug, is_active, created_at, updated_at)
Membership(id, user, tenant, role, is_default, created_at)

# jobs/models.py
AnalysisJob(id, tenant, period_month, status, inputs..., error_message, timestamps)
Artifact(id, job, kind, file, created_at)
AnalysisSnapshot(id, tenant, job, period_month, metrics, timestamps)
```

## Notas
- Para imports del pipeline desde Django, el proyecto agrega el root al `sys.path` (ver `server/manage.py` y `server/pavssv_server/settings.py`).
- RLS en PostgreSQL: Se implementará al migrar de SQLite a Postgres en producción.
