# 📡 Documentación de API

Este documento describe todos los endpoints disponibles en la API REST del sistema PA vs SV.

---

## 🌐 Base URL

```
Desarrollo: http://localhost:8001
Producción: https://api.liderman.com.pe
```

---

## 🔑 Autenticación

Actualmente la API usa autenticación basada en sesiones de Django. Para ambientes de producción, se recomienda implementar JWT o API Keys.

### Headers Requeridos

```http
Content-Type: application/json
X-CSRFToken: <token>  # Para métodos POST/PUT/DELETE
```

---

## 📋 Endpoints

### 1. Health Check

Verifica el estado del servidor.

```http
GET /api/v1/health/
```

**Response** `200 OK`
```json
{
    "status": "healthy",
    "timestamp": "2025-12-26T10:30:00Z"
}
```

---

### 2. Jobs API

#### 2.1 Crear Job de Análisis

Crea un nuevo job para procesar archivos PA y SV.

```http
POST /api/v1/jobs/
Content-Type: multipart/form-data
```

**Request Body (FormData)**

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `file_pa` | File | ✅ | Archivo Excel/CSV de Personal Asignado |
| `file_sv` | File | ✅ | Archivo Excel/CSV de Servicio Vivo |
| `period` | String | ✅ | Periodo en formato `YYYY-MM` |
| `tenant` | String | ❌ | Slug del tenant (default: "default") |

**Ejemplo cURL**
```bash
curl -X POST http://localhost:8001/api/v1/jobs/ \
  -F "file_pa=@personal_asignado.xlsx" \
  -F "file_sv=@servicio_vivo.xlsx" \
  -F "period=2025-11" \
  -F "tenant=default"
```

**Response** `201 Created`
```json
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "running",
    "message": "Job creado exitosamente"
}
```

**Errores Posibles**

| Código | Descripción |
|--------|-------------|
| `400` | Archivos faltantes o formato inválido |
| `404` | Tenant no encontrado |
| `500` | Error interno de procesamiento |

---

#### 2.2 Consultar Estado del Job

Obtiene el estado actual de un job de análisis.

```http
GET /api/v1/jobs/{job_id}/status/
```

**Parámetros de URL**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `job_id` | UUID | ID único del job |

**Response** `200 OK`
```json
{
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "succeeded",
    "created_at": "2025-12-26T10:30:00Z",
    "updated_at": "2025-12-26T10:30:45Z",
    "error_message": null,
    "artifact_url": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/excel/"
}
```

**Estados Posibles**

| Estado | Descripción |
|--------|-------------|
| `queued` | En cola, esperando procesamiento |
| `running` | Procesando archivos |
| `succeeded` | Completado exitosamente |
| `failed` | Error durante el procesamiento |

---

#### 2.3 Descargar Excel del Job

Descarga el archivo Excel resultado de un job específico.

```http
GET /api/v1/jobs/{job_id}/excel/
```

**Response** `200 OK`
```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="PA_vs_SV_2025-11.xlsx"
```

---

#### 2.4 Descargar Último Excel

Descarga el Excel del último job exitoso del tenant.

```http
GET /api/v1/jobs/latest/download/
```

**Query Parameters**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `tenant` | String | "default" | Slug del tenant |

**Ejemplo**
```http
GET /api/v1/jobs/latest/download/?tenant=default
```

**Response** `200 OK`
```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="PA_vs_SV_2025-11.xlsx"
```

**Errores Posibles**

| Código | Descripción |
|--------|-------------|
| `404` | No hay jobs exitosos para el tenant |

---

### 3. Dashboard API

#### 3.1 Obtener Métricas

Obtiene todas las métricas agregadas para un periodo específico.

```http
GET /dashboard/api/metrics/
```

**Query Parameters**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `tenant` | String | "default" | Slug del tenant |
| `period` | String | último | Periodo en formato `YYYY-MM` |

**Ejemplo**
```http
GET /dashboard/api/metrics/?tenant=default&period=2025-11
```

**Response** `200 OK`
```json
{
    "success": true,
    "period": "November 2025",
    "period_raw": "2025-11",
    
    "total_pa": 14708,
    "total_sv": 13237.94,
    "diferencia": 1470.06,
    "cobertura": 90.01,
    "pct_diferencial": 11.1,
    "total_registros": 5576,
    
    "by_estado": [
        {
            "estado": "SOBRECARGA",
            "count": 2500,
            "pa": 8234,
            "sv": 5890
        },
        {
            "estado": "FALTA",
            "count": 1800,
            "pa": 4500,
            "sv": 5200
        },
        {
            "estado": "EXACTO",
            "count": 500,
            "pa": 1000,
            "sv": 1000
        },
        {
            "estado": "NO_PLANIFICADO",
            "count": 450,
            "pa": 800,
            "sv": 0
        },
        {
            "estado": "SIN_PERSONAL",
            "count": 200,
            "pa": 0,
            "sv": 900
        },
        {
            "estado": "SIN_DATOS",
            "count": 126,
            "pa": 174,
            "sv": 247.94
        }
    ],
    
    "by_cliente": [
        {
            "nombre": "SOUTHERN PERU COPPER CORPORATION",
            "grupo": "GRUPO MINERO",
            "pa": 484,
            "sv": 366.69,
            "diferencia": 117.31,
            "cobertura": 131.99,
            "pct_diferencial": 31.99,
            "estado": "SOBRECARGA"
        }
        // ... más clientes
    ],
    
    "by_zona": [
        {
            "zona": "REGION AREQUIPA",
            "pa": 1100,
            "sv": 950
        },
        {
            "zona": "ZONA C1",
            "pa": 800,
            "sv": 750
        }
        // ... más zonas
    ],
    
    "by_macrozona": [
        {
            "macrozona": "ZONA CENTRO",
            "total": 3500
        },
        {
            "macrozona": "REGION SUR",
            "total": 2800
        }
        // ... más macrozonas
    ],
    
    "by_grupo": [
        {
            "grupo": "GRUPO GLORIA",
            "pa": 1500,
            "sv": 1400
        }
        // ... más grupos
    ],
    
    "by_unidad_top10": [
        {
            "unidad": "SEDE PRINCIPAL",
            "pa": 500,
            "sv": 480
        }
        // ... top 10 unidades
    ],
    
    "by_servicio_top10": [
        {
            "servicio": "VIGILANCIA 24H",
            "pa": 800,
            "sv": 750
        }
        // ... top 10 servicios
    ],
    
    "filtros_disponibles": {
        "macrozona": [
            "REGION CENTRO",
            "REGION NORTE",
            "REGION SUR",
            "ZONA CENTRO",
            "ZONA FACILITIES"
        ],
        "zona": [
            "ZONA C1",
            "ZONA C2",
            "REGION AREQUIPA",
            "REGION CHICLAYO"
        ],
        "compania": [
            "J & V Resguardo S.A.C.",
            "Liderman Servicios S.A.C.",
            "Liderman Facilities S.A.C."
        ],
        "grupo": [
            "GRUPO GLORIA",
            "GRUPO BRECA",
            "GRUPO ROMERO"
        ],
        "sector": [
            "CIUDAD",
            "MINAS"
        ],
        "gerente": [
            "JOSE PAZOS",
            "MIGUEL LOYOLA",
            "OMAR BABILONIA"
        ]
    }
}
```

---

#### 3.2 Obtener Periodos Disponibles

Lista todos los periodos con datos procesados.

```http
GET /dashboard/api/periods/
```

**Query Parameters**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `tenant` | String | "default" | Slug del tenant |

**Response** `200 OK`
```json
{
    "success": true,
    "periods": [
        {
            "value": "2025-11",
            "label": "November 2025",
            "is_latest": true
        },
        {
            "value": "2025-10",
            "label": "October 2025",
            "is_latest": false
        },
        {
            "value": "2025-09",
            "label": "September 2025",
            "is_latest": false
        }
    ]
}
```

---

#### 3.3 Comparar Periodos

Compara métricas entre dos periodos diferentes.

```http
GET /dashboard/api/compare/
```

**Query Parameters**

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `tenant` | String | ❌ | Slug del tenant |
| `period_a` | String | ✅ | Primer periodo `YYYY-MM` |
| `period_b` | String | ✅ | Segundo periodo `YYYY-MM` |

**Ejemplo**
```http
GET /dashboard/api/compare/?period_a=2025-11&period_b=2025-10
```

**Response** `200 OK`
```json
{
    "success": true,
    "period_a": {
        "period": "November 2025",
        "total_pa": 14708,
        "total_sv": 13237.94,
        "diferencia": 1470.06,
        "cobertura": 90.01
    },
    "period_b": {
        "period": "October 2025",
        "total_pa": 14200,
        "total_sv": 12800,
        "diferencia": 1400,
        "cobertura": 90.14
    },
    "variation": {
        "pa_delta": 508,
        "pa_pct": 3.58,
        "sv_delta": 437.94,
        "sv_pct": 3.42,
        "diff_delta": 70.06,
        "cob_delta": -0.13
    }
}
```

---

#### 3.4 Obtener Detalles (Paginado)

Obtiene datos detallados con paginación para tablas grandes.

```http
GET /dashboard/api/details/
```

**Query Parameters**

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `tenant` | String | "default" | Slug del tenant |
| `period` | String | último | Periodo `YYYY-MM` |
| `page` | Integer | 1 | Número de página |
| `page_size` | Integer | 50 | Registros por página |
| `search` | String | - | Búsqueda por cliente/unidad |
| `estado` | String | - | Filtrar por estado |
| `zona` | String | - | Filtrar por zona |

**Ejemplo**
```http
GET /dashboard/api/details/?period=2025-11&page=1&page_size=20&estado=SOBRECARGA
```

**Response** `200 OK`
```json
{
    "success": true,
    "data": [
        {
            "cliente": "SOUTHERN PERU COPPER",
            "unidad": "SEDE LIMA",
            "servicio": "VIGILANCIA 24H",
            "zona": "ZONA C1",
            "macrozona": "ZONA CENTRO",
            "compania": "J & V Resguardo S.A.C.",
            "grupo": "GRUPO MINERO",
            "pa": 45,
            "sv": 32.5,
            "diferencia": 12.5,
            "cobertura": 138.46,
            "estado": "SOBRECARGA"
        }
        // ... más registros
    ],
    "pagination": {
        "page": 1,
        "page_size": 20,
        "total_pages": 15,
        "total_records": 289,
        "has_next": true,
        "has_prev": false
    }
}
```

---

## 📊 Códigos de Estado HTTP

| Código | Significado | Descripción |
|--------|-------------|-------------|
| `200` | OK | Solicitud exitosa |
| `201` | Created | Recurso creado exitosamente |
| `400` | Bad Request | Parámetros inválidos o faltantes |
| `401` | Unauthorized | No autenticado |
| `403` | Forbidden | Sin permisos suficientes |
| `404` | Not Found | Recurso no encontrado |
| `500` | Server Error | Error interno del servidor |

---

## 🔄 Flujo Típico de Uso

```
1. POST /api/v1/jobs/           → Crear job con archivos
                                   ↓
2. GET /api/v1/jobs/{id}/status/ → Polling hasta succeeded
                                   ↓
3. GET /dashboard/              → Ver dashboard
                                   ↓
4. GET /dashboard/api/metrics/  → Cargar métricas (JS)
                                   ↓
5. GET /api/v1/jobs/latest/download/ → Descargar Excel
```

---

## 📝 Ejemplos con JavaScript

### Crear Job

```javascript
async function createJob(filePa, fileSv, period) {
    const formData = new FormData();
    formData.append('file_pa', filePa);
    formData.append('file_sv', fileSv);
    formData.append('period', period);
    formData.append('tenant', 'default');
    
    const response = await fetch('/api/v1/jobs/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    });
    
    return await response.json();
}
```

### Polling de Estado

```javascript
async function pollJobStatus(jobId) {
    const response = await fetch(`/api/v1/jobs/${jobId}/status/`);
    const data = await response.json();
    
    if (data.status === 'succeeded') {
        return data;
    } else if (data.status === 'failed') {
        throw new Error(data.error_message);
    } else {
        // Esperar y reintentar
        await new Promise(r => setTimeout(r, 1000));
        return pollJobStatus(jobId);
    }
}
```

### Obtener Métricas

```javascript
async function fetchMetrics(period) {
    const params = new URLSearchParams({
        tenant: 'default',
        period: period
    });
    
    const response = await fetch(`/dashboard/api/metrics/?${params}`);
    return await response.json();
}
```

---

## 🚨 Manejo de Errores

Todas las respuestas de error siguen el formato:

```json
{
    "success": false,
    "error": "Descripción del error",
    "code": "ERROR_CODE",
    "details": {}
}
```

### Códigos de Error Comunes

| Código | Descripción |
|--------|-------------|
| `INVALID_FILE_FORMAT` | Formato de archivo no soportado |
| `MISSING_REQUIRED_FIELD` | Campo requerido faltante |
| `TENANT_NOT_FOUND` | Tenant no existe |
| `JOB_NOT_FOUND` | Job no encontrado |
| `NO_DATA_FOR_PERIOD` | Sin datos para el periodo |
| `PROCESSING_ERROR` | Error durante procesamiento |

---

*Documentación actualizada: 5 de Enero de 2026*
