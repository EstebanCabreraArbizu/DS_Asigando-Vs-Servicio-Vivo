# PA vs SV — Server (Django)

Este folder contiene el backend web (Django + DRF + Celery) con infraestructura Docker completa.

---

## 🏗️ Arquitectura de Servicios

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| **Django Web** | 8000 | API REST + Dashboard |
| **PostgreSQL 16** | 5433 | Base de datos de producción |
| **MinIO API** | 9000 | Storage S3-compatible |
| **MinIO Console** | 9001 | Interfaz de administración |
| **Redis 7** | 6379 | Broker para Celery |
| **Celery Worker** | - | Procesamiento asíncrono |

---

## 🚀 Levantar con Docker

1. Crear `server/.env` a partir de `server/.env.example`:

```bash
cp .env.example .env
```

2. Ejecutar desde `server/`:

```bash
docker-compose up --build -d
```

3. Crear superusuario:

```bash
docker exec -it server-web-1 python manage.py createsuperuser
```

---

## 📊 URLs de Acceso

| URL | Descripción |
|-----|-------------|
| http://localhost:8000/dashboard/ | Dashboard principal |
| http://localhost:8000/dashboard/upload/ | Subir archivos |
| http://localhost:8000/admin/ | Panel de administración |
| http://localhost:9001 | MinIO Console (minioadmin/minioadmin123) |
| http://localhost:8000/api/v1/health/ | Health check API |

---

## 🔐 Sistema de Seguridad

### Autenticación
- **JWT**: Para APIs externas (REST clients, móvil)
- **Session**: Para dashboard interno (navegador)

### Roles y Permisos

| Rol | Ver | Subir | Eliminar | Exportar |
|-----|-----|-------|----------|----------|
| Owner | ✅ | ✅ | ✅ | ✅ |
| Admin | ✅ | ✅ | ✅ | ✅ |
| Coordinator | ✅ | ✅ | ✅ | ✅ |
| Analyst | ✅ | ❌ | ❌ | ✅ |
| Viewer | ✅ | ❌ | ❌ | ❌ |

---

## 📦 Buckets de MinIO (S3-compatible)

| Bucket | Propósito |
|--------|-----------|
| `pavssv-inputs` | Archivos de entrada (PA, SV) |
| `pavssv-artifacts` | Resultados procesados (Parquet, Excel) |
| `pavssv-exports` | Archivos para descarga |

---

## 🔧 Variables de Entorno

```env
# PostgreSQL
POSTGRES_DB=pavssv
POSTGRES_USER=pavssv
POSTGRES_PASSWORD=pavssv

# MinIO/S3 Storage
USE_S3_STORAGE=true
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123
AWS_S3_ENDPOINT_URL=http://minio:9000

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

---

## 🛠️ Comandos Útiles

```bash
# Ver logs del servidor
docker logs server-web-1 -f

# Ver logs del worker
docker logs server-worker-1 -f

# Ejecutar migraciones
docker exec server-web-1 python manage.py migrate

# Verificar estado de servicios
docker-compose ps

# Reiniciar servicios
docker-compose restart web worker
```

---

## 📝 Notas

- El pipeline de análisis (Polars) vive en la raíz del repo. Django lo importa agregando el root al `sys.path`.
- Los archivos se almacenan en MinIO (compatible con AWS S3) para facilitar migración a producción.
- El sistema es multi-tenant con aislamiento de datos por organización.
