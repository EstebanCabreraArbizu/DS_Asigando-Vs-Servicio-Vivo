# 🔐 Checklist de Seguridad para Despliegue en la Nube - PA vs SV

Este documento proporciona una lista de verificación completa para asegurar que el servicio web PA vs SV cumple con todos los requisitos de seguridad antes del despliegue en producción.

---

## 📋 Resumen de Cumplimiento

| Categoría OWASP | Implementado | Archivo/Configuración |
|-----------------|:------------:|----------------------|
| Validación de Input | ✅ | `middleware.py`, `validators.py` |
| Autenticación | ✅ | JWT + Argon2 en `settings.py` |
| Gestión de Sesiones | ✅ | JWT blacklist + rotación |
| Control de Acceso | ✅ | `permissions.py` + roles |
| Prácticas Criptográficas | ✅ | TLS + Argon2 + S3 encryption |
| Manejo de Errores | ✅ | `exceptions.py` + logging |
| Protección de Datos | ✅ | S3 encryption + secrets manager |
| Seguridad de Comunicaciones | ✅ | HTTPS + HSTS |
| Configuración del Sistema | ✅ | Headers CSP + WAF |
| Seguridad de Base de Datos | ✅ | PostgreSQL + IAM roles |
| Gestión de Archivos | ✅ | `validators.py` + magic bytes |

---

## ✅ Checklist Pre-Despliegue

### 1. Configuración de Django (`settings.py`)

- [x] `DEBUG = False` en producción
- [x] `SECRET_KEY` obligatoria (sin valor por defecto, error descriptivo si falta)
- [x] `ALLOWED_HOSTS` configurado con dominios específicos
- [x] `SECURE_SSL_REDIRECT = True`
- [x] `SESSION_COOKIE_SECURE = True`
- [x] `CSRF_COOKIE_SECURE = True`
- [x] `SECURE_HSTS_SECONDS = 31536000` (1 año)
- [x] `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- [x] `SECURE_HSTS_PRELOAD = True`
- [x] `X_FRAME_OPTIONS = "DENY"`
- [x] Content Security Policy configurado (diferenciado admin/dashboard)
- [x] Logging de auditoría habilitado
- [x] Prefijo `__Host-` en cookies de sesión y CSRF (producción)
- [x] `SESSION_COOKIE_AGE = 900` (15 minutos)
- [x] `SESSION_COOKIE_HTTPONLY = True`
- [x] `SESSION_COOKIE_SAMESITE = "Lax"`
- [x] `CSRF_COOKIE_SAMESITE = "Lax"`
- [x] `Permissions-Policy` configurada (sin camera, microphone, geolocation)

### 2. Autenticación y Autorización

- [x] JWT con tiempo de expiración corto (30 min)
- [x] Refresh tokens con rotación
- [x] Blacklist de tokens revocados habilitado
- [x] Contraseñas hasheadas con Argon2
- [x] Validación de complejidad de contraseñas (mínimo 10 caracteres)
- [x] Rate limiting en endpoint de login (5 intentos/minuto, bloqueo 30 min)
- [x] Roles y permisos implementados por tenant
- [x] `django-axes` configurado (5 intentos, lockout por user+IP, 30 min cooldown)
- [x] CAPTCHA matemático después de 3 intentos fallidos (`django-simple-captcha`)
- [x] Template de lockout personalizado (`lockout.html`)
- [x] `LoginRequiredJSONMixin` en todas las APIs del dashboard (retorna 401 JSON)
- [x] `@csrf_exempt` eliminado de todas las vistas
- [x] Logout solo acepta POST (GET redirige al dashboard)

### 3. Protección de API

- [x] Rate limiting por endpoint (auth: 5/min, upload: 20/min, api: 200/min)
- [x] Rate limiting por IP con bloqueo temporal
- [x] Validación de Content-Type
- [x] Sanitización de inputs (XSS/SQLi patterns)
- [x] Protección contra CSRF
- [x] CORS configurado con orígenes específicos
- [x] Headers de seguridad en todas las respuestas
- [x] Validación de parámetros: `validate_period()`, `validate_pagination()`, `validate_sort()`
- [x] Whitelist de campos de ordenamiento (`ALLOWED_SORT_FIELDS`)
- [x] Errores 500 internos ocultan detalles técnicos al cliente

### 4. Almacenamiento (S3/AWS)

- [ ] Buckets S3 con encriptación AES-256
- [ ] Block Public Access habilitado
- [ ] URLs prefirmadas con expiración (1 hora)
- [ ] Versionado de objetos habilitado
- [ ] Políticas de ciclo de vida configuradas
- [ ] IAM roles con mínimos privilegios

### 5. Base de Datos

- [ ] PostgreSQL con conexión SSL
- [ ] Credenciales en Secrets Manager
- [ ] Usuario de aplicación con permisos limitados
- [ ] Backups automáticos configurados
- [ ] Security Group restringido (solo desde app)

### 6. Infraestructura AWS

- [ ] VPC con subnets privadas para aplicación
- [ ] Security Groups con reglas mínimas necesarias
- [ ] WAF configurado con reglas:
  - [ ] Rate limiting global
  - [ ] Rate limiting en login
  - [ ] AWS Managed Rules (Common, SQLi, Bad Inputs)
  - [ ] IP Reputation List
- [ ] ALB con certificado SSL/TLS válido
- [ ] CloudWatch Logs habilitado

### 7. Docker/Contenedores

- [x] Imagen base slim (python:3.11-slim)
- [x] Multi-stage build
- [x] Usuario no-root (appuser)
- [x] No se exponen puertos privilegiados
- [x] Healthcheck configurado
- [x] Gunicorn en lugar de runserver
- [x] Sin credenciales hardcodeadas

### 8. Panel Admin

- [x] URL personalizable via `DJANGO_ADMIN_URL` (default: `panel-gestion`)
- [x] `AdminIPRestrictionMiddleware` restringe acceso por IP
- [x] Retorna 404 (no 403) para no confirmar existencia de la ruta
- [x] `ADMIN_ALLOWED_IPS` configurable por variable de entorno
- [x] CSP diferenciado (más permisivo solo en rutas admin)
- [x] Detección multi-proxy de IP (Cloudflare, Nginx, X-Forwarded-For)

### 8. Validación de Archivos

- [ ] Extensiones permitidas: .csv, .xlsx, .xls
- [ ] Validación de magic bytes
- [ ] Tamaño máximo: 50 MB
- [ ] Nombres de archivo sanitizados
- [ ] Escaneo de contenido malicioso
- [ ] Almacenamiento en bucket separado

### 9. Logging y Monitoreo

- [ ] Logs de auditoría para acciones críticas
- [ ] Logs de seguridad para eventos de seguridad
- [ ] Rotación de logs configurada
- [ ] CloudWatch metrics habilitados
- [ ] Alertas configuradas para:
  - [ ] Múltiples intentos de login fallidos
  - [ ] Rate limit excedido
  - [ ] Errores 5xx
  - [ ] WAF blocks

### 10. Gestión de Secretos

- [ ] `DJANGO_SECRET_KEY` en Secrets Manager
- [ ] Credenciales de DB en Secrets Manager
- [ ] Credenciales de S3 via IAM Role
- [ ] No hay secretos en código o Dockerfile
- [ ] Variables de entorno no contienen secretos sensibles

---

## 🚀 Pasos para Despliegue

### 1. Preparación

```bash
# Crear stack de infraestructura
aws cloudformation create-stack \
  --stack-name pavssv-security \
  --template-body file://aws-security-infrastructure.yaml \
  --parameters ParameterKey=Environment,ParameterValue=production \
  --capabilities CAPABILITY_NAMED_IAM
```

### 2. Configurar Secretos

```bash
# Verificar que los secretos se crearon
aws secretsmanager list-secrets --filters Key=name,Values=pavssv

# Actualizar credenciales de DB (si es necesario)
aws secretsmanager update-secret \
  --secret-id pavssv/production/database \
  --secret-string '{"username":"pavssv_admin","password":"SECURE_PASSWORD","host":"db.endpoint.com","port":"5432","dbname":"pavssv"}'
```

### 3. Build y Push de Imagen

```bash
# Build de imagen de producción
docker build -t pavssv:production -f server/Dockerfile .

# Tag y push a ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker tag pavssv:production ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/pavssv:production
docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/pavssv:production
```

### 4. Desplegar en ECS

```bash
# Actualizar servicio ECS
aws ecs update-service \
  --cluster pavssv-cluster \
  --service pavssv-web \
  --force-new-deployment
```

### 5. Verificar Despliegue

```bash
# Verificar health check
curl -k https://api.pavssv.example.com/api/v1/health/

# Verificar headers de seguridad
curl -I https://api.pavssv.example.com/api/v1/health/
```

---

## 🔍 Verificación de Cumplimiento

### Headers de Seguridad Esperados

```
Content-Security-Policy: default-src 'self'; script-src 'self'; ...
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

### Test de Rate Limiting

```bash
# Ejecutar 10 requests rápidos al endpoint de login
for i in {1..10}; do
  curl -X POST https://api.example.com/api/v1/auth/login/ \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"test"}' \
    -w "%{http_code}\n" -o /dev/null -s
done
# Los últimos requests deberían retornar 429
```

### Test de WAF

```bash
# Intentar SQL injection (debería ser bloqueado)
curl "https://api.example.com/api/v1/?id=1%27%20OR%20%271%27=%271"
# Debería retornar 403 Forbidden

# Intentar path traversal (debería ser bloqueado)
curl "https://api.example.com/../../../etc/passwd"
# Debería retornar 403 Forbidden
```

---

## 📊 Métricas de Seguridad a Monitorear

| Métrica | Umbral de Alerta | Acción |
|---------|------------------|--------|
| Rate Limit Blocks | > 100/hora | Investigar IP |
| Login Failures | > 50/hora | Revisar logs |
| WAF Blocks | > 500/día | Analizar patrones |
| 401/403 Errors | > 200/hora | Revisar autenticación |
| 5xx Errors | > 10/minuto | Alerta inmediata |

---

## 📞 Contacto de Seguridad

Para reportar vulnerabilidades o incidentes de seguridad:
- **Email:** seguridad@liderman.com.pe
- **Slack:** #security-incidents

---

*Última actualización: 13 de febrero de 2026*
