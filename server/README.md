# PA vs SV — Server (Django)

Este folder contiene el backend web (Django + DRF + Celery).

## Levantar con Docker

1. Crear `server/.env` a partir de `server/.env.example`.
2. Ejecutar desde `server/`:

```bash
docker compose up --build
```

- API: http://localhost:8001/api/v1/health

## Notas
- El pipeline de análisis (Polars) vive en la raíz del repo. Django lo importa agregando el root al `sys.path`.
