# 📊 PA vs SV - Sistema de Análisis de Personal

Sistema web para el análisis comparativo entre **Personal Asignado (PA)** y **Servicio Vivo (SV)** de Liderman. Permite cargar archivos Excel, procesarlos automáticamente y visualizar métricas en un dashboard interactivo.

![Dashboard Preview](docs/images/dashboard_preview.png)

---

## 📋 Índice

- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Tecnologías](#-tecnologías)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [API Endpoints](#-api-endpoints)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Diagramas](#-diagramas)

---

## ✨ Características

### 🎯 Funcionalidades Principales

| Característica | Descripción |
|----------------|-------------|
| **Upload de archivos** | Drag & drop para cargar archivos PA y SV en formato Excel/CSV |
| **Procesamiento automático** | Análisis y cruce de datos usando Polars |
| **Dashboard interactivo** | 6 pestañas con KPIs, gráficos y tablas |
| **Multi-tenant** | Soporte para múltiples organizaciones aisladas |
| **Filtros avanzados** | Macro Zona, Zona, Compañía, Grupo, Sector, Gerente |
| **Exportación Excel** | Descarga de resultados procesados |
| **Comparación histórica** | Comparar métricas entre períodos |

### 📈 Métricas Calculadas

- **Personal Asignado (PA)**: Total de personal asignado
- **Servicio Vivo (SV)**: Personal estimado según planificación
- **Diferencia**: PA - SV
- **Cobertura**: (SV/PA) × 100%
- **% Diferencial**: (Diferencia/SV) × 100%
- **Estados**: SOBRECARGA, FALTA, EXACTO, NO_PLANIFICADO, SIN_PERSONAL, SIN_DATOS

---

## 🏗️ Arquitectura

### Diagrama de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  Dashboard  │  │   Upload    │  │   Gráficos  │  │   Tablas    │    │
│  │   (HTML)    │  │ (Drag&Drop) │  │  (ECharts)  │  │ (Tailwind)  │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │                │            │
│         └────────────────┴────────────────┴────────────────┘            │
│                                   │                                      │
│                          JavaScript (Fetch API)                          │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           API LAYER (Django)                             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      Django REST Framework                       │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │    │
│  │  │ /api/v1/jobs │  │  /dashboard  │  │ /dashboard/api/*     │  │    │
│  │  │  - POST      │  │  - GET views │  │ - /metrics           │  │    │
│  │  │  - GET status│  │  - Templates │  │ - /periods           │  │    │
│  │  │  - GET excel │  │              │  │ - /compare           │  │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │    │
│  │         │                 │                      │              │    │
│  │         └─────────────────┼──────────────────────┘              │    │
│  │                           │                                      │    │
│  │                   ┌───────▼───────┐                             │    │
│  │                   │    Views &    │                             │    │
│  │                   │  Serializers  │                             │    │
│  │                   └───────┬───────┘                             │    │
│  └───────────────────────────┼─────────────────────────────────────┘    │
│                              │                                           │
│  ┌───────────────────────────▼─────────────────────────────────────┐    │
│  │                     BUSINESS LOGIC                               │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │    │
│  │  │DataProcessor │  │AnalysisEngine│  │   ExcelExporter      │  │    │
│  │  │  (Polars)    │  │   (Polars)   │  │     (Polars)         │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                                       │
│  ┌─────────────────────┐    ┌─────────────────────────────────────┐    │
│  │   SQLite/PostgreSQL │    │         File System (Media)         │    │
│  │  ┌───────────────┐  │    │  ┌─────────────────────────────┐   │    │
│  │  │   Tenant      │  │    │  │ /media/tenants/{slug}/      │   │    │
│  │  │   AnalysisJob │  │    │  │   └─ jobs/{job_id}/         │   │    │
│  │  │   Artifact    │  │    │  │       ├─ inputs/            │   │    │
│  │  │   Snapshot    │  │    │  │       │   ├─ pa.xlsx        │   │    │
│  │  │   Membership  │  │    │  │       │   └─ sv.xlsx        │   │    │
│  │  └───────────────┘  │    │  │       └─ artifacts/         │   │    │
│  └─────────────────────┘    │  │           └─ resultado.xlsx │   │    │
│                             │  └─────────────────────────────────┘   │    │
│                             └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tecnologías

### Backend
| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | 3.11+ | Lenguaje principal |
| Django | 5.2 | Framework web |
| Django REST Framework | 3.15 | API REST |
| Polars | 1.x | Procesamiento de datos |
| SQLite/PostgreSQL | - | Base de datos |

### Frontend
| Tecnología | Versión | Uso |
|------------|---------|-----|
| HTML5/CSS3 | - | Estructura y estilos |
| Tailwind CSS | CDN | Framework CSS |
| ECharts | 5.4.3 | Gráficos interactivos |
| JavaScript ES6 | - | Interactividad |

### Infraestructura
| Tecnología | Uso |
|------------|-----|
| Docker | Contenedorización |
| Celery | Tareas asíncronas (opcional) |
| Redis | Message broker (opcional) |

---

## 🚀 Instalación

### Prerrequisitos

- Python 3.11 o superior
- pip (gestor de paquetes Python)
- Git

### Pasos de Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/pavssv.git
cd pavssv

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Instalar dependencias
cd server
pip install -r requirements.txt
pip install polars openpyxl xlsxwriter

# 5. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# 6. Ejecutar migraciones
python manage.py migrate

# 7. Crear superusuario (opcional)
python manage.py createsuperuser

# 8. Iniciar servidor de desarrollo
python manage.py runserver 8001
```

### Acceso

- **Dashboard**: http://localhost:8001/dashboard/
- **Admin**: http://localhost:8001/admin/
- **API**: http://localhost:8001/api/v1/

---

## 📖 Uso

### 1. Subir Archivos

1. Navegar a `/dashboard/upload/`
2. Arrastrar archivo de **Personal Asignado** (PA)
3. Arrastrar archivo de **Servicio Vivo** (SV)
4. Seleccionar el período (mes/año)
5. Click en "Procesar Archivos"

### 2. Ver Dashboard

1. Navegar a `/dashboard/`
2. Seleccionar período en el dropdown
3. Usar filtros para segmentar datos
4. Navegar entre pestañas:
   - **Resumen**: KPIs y gráficos principales
   - **Por Cliente**: Tabla detallada por cliente
   - **Por Unidad**: Análisis por unidad de negocio
   - **Por Servicio**: Desglose por servicio
   - **Gráficos**: Visualizaciones adicionales
   - **Detalle Completo**: Datos granulares

### 3. Exportar Resultados

- Click en botón "📥 Excel" para descargar el análisis completo

---

## 🔌 API Endpoints

### Jobs API (`/api/v1/jobs/`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/v1/jobs/` | Crear nuevo job de análisis |
| `GET` | `/api/v1/jobs/<id>/status/` | Consultar estado del job |
| `GET` | `/api/v1/jobs/<id>/excel/` | Descargar Excel del job |
| `GET` | `/api/v1/jobs/latest/download/` | Descargar último Excel |

### Dashboard API (`/dashboard/api/`)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/dashboard/api/metrics/` | Métricas del período seleccionado |
| `GET` | `/dashboard/api/periods/` | Períodos disponibles |
| `GET` | `/dashboard/api/compare/` | Comparar dos períodos |
| `GET` | `/dashboard/api/details/` | Datos detallados paginados |

### Parámetros Comunes

```
?tenant=<slug>        # Identificador del tenant
?period=<YYYY-MM>     # Período a consultar
```

---

## 📁 Estructura del Proyecto

```
Project_PAvsSV/
├── server/                     # Backend Django
│   ├── pavssv_server/          # Configuración principal
│   │   ├── settings.py         # Configuraciones Django
│   │   ├── urls.py             # URLs raíz
│   │   └── wsgi.py             # WSGI config
│   │
│   ├── tenants/                # App de multi-tenancy
│   │   ├── models.py           # Tenant, Membership
│   │   └── views.py
│   │
│   ├── jobs/                   # App de procesamiento
│   │   ├── models.py           # AnalysisJob, Artifact, Snapshot
│   │   ├── views.py            # JobCreateView, JobStatusView
│   │   ├── urls.py
│   │   └── services/
│   │       └── analysis_service.py
│   │
│   ├── dashboard/              # App de visualización
│   │   ├── views.py            # DashboardView, MetricsAPIView
│   │   ├── urls.py
│   │   └── templates/
│   │       └── dashboard/
│   │           ├── main.html   # Dashboard principal
│   │           └── upload.html # Página de upload
│   │
│   ├── api_v1/                 # API REST
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── media/                  # Archivos subidos
│   │   └── tenants/
│   │       └── {slug}/
│   │           └── jobs/
│   │
│   ├── manage.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── docs/                       # Documentación
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── images/
│
├── venv/                       # Entorno virtual
└── README.md                   # Este archivo
```

---

## 📊 Diagramas

Ver documentación detallada en:
- [Arquitectura y Flujos](docs/ARCHITECTURE.md)
- [Documentación API](docs/API.md)

---

## � Infraestructura Docker (Producción)

### Servicios Desplegados

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| **Django Web** | 8000 | API REST + Dashboard |
| **PostgreSQL 16** | 5433 | Base de datos de producción |
| **MinIO API** | 9000 | Storage S3-compatible |
| **MinIO Console** | 9001 | Interfaz de administración |
| **Redis 7** | 6379 | Broker para Celery |
| **Celery Worker** | - | Procesamiento asíncrono |

### Buckets de MinIO (S3-compatible)

| Bucket | Propósito |
|--------|-----------|
| `pavssv-inputs` | Archivos de entrada (PA, SV) |
| `pavssv-artifacts` | Resultados procesados (Parquet, Excel) |
| `pavssv-exports` | Archivos para descarga |

### Comandos Rápidos

```bash
# Levantar toda la infraestructura
cd server
docker-compose up --build -d

# Ver logs
docker logs server-web-1 -f

# Crear superusuario
docker exec -it server-web-1 python manage.py createsuperuser
```

### URLs de Acceso

- **Dashboard**: http://localhost:8000/dashboard/
- **Admin**: http://localhost:8000/admin/
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin123)
- **API Health**: http://localhost:8000/api/v1/health/

---

## 🔐 Seguridad

### Autenticación
- **JWT**: Para APIs externas (REST clients, móvil)
- **Session**: Para dashboard interno (navegador)
- CORS configurado para dominios permitidos

### Roles y Permisos

| Rol | Ver | Subir | Eliminar | Exportar |
|-----|-----|-------|----------|----------|
| Owner | ✅ | ✅ | ✅ | ✅ |
| Admin | ✅ | ✅ | ✅ | ✅ |
| Coordinator | ✅ | ✅ | ✅ | ✅ |
| Analyst | ✅ | ❌ | ❌ | ✅ |
| Viewer | ✅ | ❌ | ❌ | ❌ |

### Otras medidas
- Aislamiento de datos por tenant
- Validación de archivos en upload
- CSRF protection habilitado

---

## 🤝 Contribución

1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

---

## 📄 Licencia

Este proyecto es propietario de Liderman. Todos los derechos reservados.

---

## 📞 Soporte

Para soporte técnico, contactar a:
- Email: soporte@liderman.com.pe
- Documentación interna: [Wiki Liderman]

---

*Desarrollado con ❤️ para Liderman*
