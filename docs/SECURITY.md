# 🔐 Guía de Seguridad y Autenticación

Este documento describe la configuración de seguridad, autenticación JWT y permisos del sistema PA vs SV.

## Índice

- [Autenticación JWT](#autenticación-jwt)
- [Roles y Permisos](#roles-y-permisos)
- [CORS](#cors)
- [Almacenamiento S3/MinIO](#almacenamiento-s3minio)
- [Migración a AWS S3](#migración-a-aws-s3)
- [Buenas Prácticas de Seguridad](#buenas-prácticas-de-seguridad)

---

## Autenticación JWT

El sistema utiliza **JWT (JSON Web Tokens)** para autenticación stateless.

### Endpoints de Autenticación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/login/` | Obtener tokens (access + refresh) |
| `POST` | `/api/v1/auth/refresh/` | Renovar access token |
| `POST` | `/api/v1/auth/verify/` | Verificar validez del token |
| `POST` | `/api/v1/auth/logout/` | Invalidar refresh token |

### Login

```bash
curl -X POST http://localhost:8001/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password123"}'
```

**Respuesta exitosa:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "is_superuser": false
  },
  "tenant": {
    "id": "uuid-del-tenant",
    "slug": "default",
    "name": "Default Tenant"
  },
  "role": "coordinator",
  "permissions": [
    "files.upload",
    "files.delete",
    "files.download",
    "analysis.view",
    "analysis.export"
  ]
}
```

### Usar el Token

Incluir el token en el header `Authorization`:

```bash
curl -X GET http://localhost:8001/api/v1/jobs/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

### Renovar Token

El access token expira en **30 minutos**. Usar el refresh token para obtener uno nuevo:

```bash
curl -X POST http://localhost:8001/api/v1/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."}'
```

### Configuración JWT

En `settings.py`:

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}
```

---

## Roles y Permisos

### Roles Disponibles

| Rol | Descripción | Permisos |
|-----|-------------|----------|
| **owner** | Dueño del tenant | Todo |
| **admin** | Administrador | Gestión de usuarios, archivos, configuración |
| **coordinator** | Coordinador | Subir, modificar, eliminar archivos Excel |
| **analyst** | Analista | Ver dashboard, exportar reportes |
| **viewer** | Visualizador | Solo lectura del dashboard |

### Matriz de Permisos

| Permiso | owner | admin | coordinator | analyst | viewer |
|---------|:-----:|:-----:|:-----------:|:-------:|:------:|
| `tenant.manage` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `users.manage` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `files.upload` | ✅ | ✅ | ✅ | ❌ | ❌ |
| `files.delete` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `files.download` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `analysis.view` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `analysis.export` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `audit.view` | ✅ | ✅ | ❌ | ❌ | ❌ |

### Crear Usuario con Rol

```python
from django.contrib.auth.models import User
from tenants.models import Tenant, Membership, MembershipRole

# Crear usuario
user = User.objects.create_user(
    username="coordinador1",
    email="coord@example.com",
    password="SecurePass123!"
)

# Asignar a tenant con rol
tenant = Tenant.objects.get(slug="default")
Membership.objects.create(
    user=user,
    tenant=tenant,
    role=MembershipRole.COORDINATOR,
    is_default=True
)
```

### Verificar Permisos en Código

```python
from api_v1.permissions import CanManageFiles, CanDeleteFiles

class MyView(APIView):
    permission_classes = [IsAuthenticated, CanManageFiles]
    
    def post(self, request):
        # Solo admin y coordinator pueden acceder
        ...
```

---

## CORS

### Configuración

En `.env`:

```env
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://app.ejemplo.com
```

### Headers Permitidos

- `authorization` - Para JWT tokens
- `x-tenant-id` - Para identificar el tenant
- `content-type` - Para requests JSON/multipart

### Desarrollo vs Producción

En desarrollo (`DEBUG=1`), CORS permite todos los orígenes.  
En producción, solo los orígenes en `CORS_ALLOWED_ORIGINS`.

---

## Almacenamiento S3/MinIO

### Arquitectura

```
┌─────────────────┐     ┌─────────────────┐
│   Django App    │────▶│  MinIO / S3     │
└─────────────────┘     │                 │
                        │  Buckets:       │
                        │  - pavssv-inputs│
                        │  - pavssv-artifacts
                        │  - pavssv-exports│
                        └─────────────────┘
```

### Buckets

| Bucket | Uso | Acceso |
|--------|-----|--------|
| `pavssv-inputs` | Archivos PA y SV subidos | Privado |
| `pavssv-artifacts` | Resultados procesados | Privado |
| `pavssv-exports` | Exportaciones para descarga | Público (solo lectura) |

### Acceder a MinIO Console

En desarrollo:
- URL: http://localhost:9001
- Usuario: `minioadmin`
- Password: `minioadmin123`

### URLs Prefirmadas

Para descargas seguras, el sistema genera URLs prefirmadas con expiración:

```python
from jobs.services import get_storage_service

storage = get_storage_service()
url = storage.get_presigned_url(
    "tenants/default/jobs/123/artifacts/result.xlsx",
    expires_in=3600  # 1 hora
)
```

---

## Migración a AWS S3

### 1. Crear Buckets en AWS

```bash
aws s3 mb s3://pavssv-inputs
aws s3 mb s3://pavssv-artifacts
aws s3 mb s3://pavssv-exports
```

### 2. Configurar IAM

Crear usuario IAM con política:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::pavssv-*",
        "arn:aws:s3:::pavssv-*/*"
      ]
    }
  ]
}
```

### 3. Actualizar Variables de Entorno

```env
USE_S3_STORAGE=true
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_S3_ENDPOINT_URL=
AWS_S3_REGION_NAME=us-east-1
AWS_STORAGE_BUCKET_NAME=pavssv-artifacts
```

> **Nota:** Dejar `AWS_S3_ENDPOINT_URL` vacío para usar AWS S3 real.

### 4. Migrar Datos Existentes

```bash
# Desde MinIO a S3
mc alias set minio http://localhost:9000 minioadmin minioadmin123
mc alias set aws https://s3.amazonaws.com ACCESS_KEY SECRET_KEY

# Copiar buckets
mc mirror minio/pavssv-inputs aws/pavssv-inputs
mc mirror minio/pavssv-artifacts aws/pavssv-artifacts
```

---

## Buenas Prácticas de Seguridad

### 1. Contraseñas

- Mínimo 10 caracteres
- Hasher: Argon2 (más seguro que bcrypt)
- Validación contra passwords comunes

### 2. Tokens

- Access token: 30 minutos
- Refresh token: 7 días
- Tokens invalidados se agregan a blacklist

### 3. HTTPS (Producción)

```env
SECURE_SSL_REDIRECT=true
```

Esto habilita:
- Redirección HTTP → HTTPS
- Cookies seguras
- HSTS headers

### 4. Headers de Seguridad

El sistema configura automáticamente:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security` (HSTS)

### 5. Rate Limiting

```python
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    }
}
```

### 6. Logs de Auditoría

Cada acción crítica se registra con:
- Usuario que realizó la acción
- Timestamp
- Tenant afectado
- Tipo de operación

---

## Troubleshooting

### Token Expirado

```json
{
  "error": {
    "code": "token_not_valid",
    "message": "Token is invalid or expired"
  }
}
```

**Solución:** Usar el refresh token para obtener uno nuevo.

### Acceso Denegado

```json
{
  "error": {
    "code": "permission_denied",
    "message": "No tienes permiso para esta acción"
  }
}
```

**Solución:** Verificar que el usuario tenga el rol adecuado en el tenant.

### Tenant No Encontrado

```json
{
  "error": {
    "code": "tenant_not_found",
    "message": "Tenant no encontrado"
  }
}
```

**Solución:** Verificar el header `X-Tenant-ID` o query param `?tenant=`.

---

## Componentes de Seguridad Implementados

### Middlewares de Seguridad (`pavssv_server/middleware.py`)

| Middleware | Función |
|------------|---------|
| `SecurityHeadersMiddleware` | Añade CSP, X-Frame-Options, Referrer-Policy |
| `IPRateLimitMiddleware` | Rate limiting por IP y endpoint |
| `AuditLoggingMiddleware` | Logging de acciones críticas |
| `RequestSanitizationMiddleware` | Sanitización de inputs |

### Validación de Archivos (`api_v1/validators.py`)

- Validación de extensiones permitidas (.csv, .xlsx, .xls)
- Verificación de magic bytes
- Sanitización de nombres de archivo
- Detección de contenido malicioso
- Límite de tamaño (50 MB)

### Gestión de Secretos (`pavssv_server/secrets.py`)

- Soporte para AWS Secrets Manager en producción
- Fallback a variables de entorno en desarrollo
- Caché de secretos para mejor rendimiento

### Infraestructura AWS (`aws-security-infrastructure.yaml`)

- VPC con subnets privadas
- WAF con reglas de protección
- S3 con encriptación
- Secrets Manager
- IAM roles con mínimos privilegios

---

## Documentación Adicional

- [Checklist de Despliegue Seguro](SECURITY_DEPLOYMENT_CHECKLIST.md)
- [Reporte de Costos AWS](AWS_COST_REPORT.md)
- [Manual de Usuario](USER_MANUAL.md)

---

## Soporte

Para reportar vulnerabilidades de seguridad, contactar a:
- Email: seguridad@liderman.com.pe

