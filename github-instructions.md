# Instrucciones (PA vs SV Web — Django)

## Contexto
- El pipeline actual (Polars) vive en `core/`: `data_loader.py`, `data_processor.py`, `analysis_engine.py`, `excel_exporter.py`.
- El backend web nuevo vive en `server/` (Django + DRF + Celery).
- Los archivos de datos y resultados locales están en `data/` (ignorados por Git).
- Decisión de almacenamiento: **Opción A**
  - Excel final como artefacto descargable.
  - `Resultado_Final` como Parquet por Job.
  - Agregados/snapshots en Postgres para dashboard.

## Prompt recomendado para continuar (copiar/pegar)

"""
Objetivo: Implementar EPIC 1 (Fundaciones) y dejar listo el esqueleto para EPIC 2 (Multi-tenant + RLS).

Restricciones:
- El pipeline de negocio está en `core/`.
- Todo el código Django debe vivir en `server/`.
- Mantener el pipeline existente como librería interna (no reescribir lógica de negocio).

Tareas (orden sugerido):
1) Validar que `server/` levante con Docker: web + worker + db + redis.
2) Correr migraciones y crear superuser.
3) Implementar modelos base: Tenant, Membership (User↔Tenant), AnalysisJob, Artifact.
4) Implementar endpoints DRF mínimos:
   - POST `/api/v1/jobs/` (upload PA+SV, retorna job_id)
   - GET  `/api/v1/jobs/{job_id}/status`
   - GET  `/api/v1/jobs/{job_id}/excel`
5) Celery task `run_analysis_job(job_id)`:
   - leer inputs
   - ejecutar pipeline (DataProcessor + AnalysisEngine desde `core`)
   - guardar Parquet y Excel como artifacts
6) Dejar preparado EPIC 2:
   - agregar `tenant_id` real (FK) a tablas
   - diseñar políticas RLS (Postgres)

Aceptación:
- `GET /api/v1/health` responde `{status: ok}`
- Un upload dispara un job async y luego permite descargar Excel.
"""

## Notas
- Para imports del pipeline desde Django, el proyecto agrega el root al `sys.path` (ver `server/manage.py` y `server/pavssv_server/settings.py`).
- Próximo paso (EPIC 2): convertir `tenant_id` a FK y activar RLS.
