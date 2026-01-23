# =============================================================================
# PA vs SV - Dockerfile de Producción con Mejores Prácticas de Seguridad
# =============================================================================

FROM python:3.11-slim AS base

# Etiquetas de metadatos
LABEL maintainer="seguridad@liderman.com.pe"
LABEL version="1.0"
LABEL description="PA vs SV Web Service - Secure Production Image"

# Variables de entorno de seguridad
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Crear usuario no-root para la aplicación
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# =============================================================================
# Stage de construcción de Assets (Node.js)
# =============================================================================
FROM node:18-slim AS assets-builder
WORKDIR /app/server
COPY server/package*.json ./
COPY server/scripts/ ./scripts/
COPY server/dashboard/static/dashboard/src/ ./dashboard/static/dashboard/src/
# Si necesitas Tailwind, copia también el config y el input css
COPY server/tailwind.config.js ./
COPY server/dashboard/static/dashboard/tailwind.input.css ./dashboard/static/dashboard/tailwind.input.css

RUN npm install
RUN npm run build:js
# Si tienes un script de tailwind, ejecútalo aquí también
# RUN npm run build:css

# =============================================================================
# Stage de construcción de Python (instala dependencias)
# =============================================================================
FROM base AS builder

# Dependencias del sistema (solo las necesarias)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copiar requirements y instalar dependencias
COPY requirements.txt /app/requirements.txt
COPY server/requirements.txt /app/server/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir -r /app/server/requirements.txt

# =============================================================================
# Stage final (imagen de producción)
# =============================================================================
FROM base AS production

# Instalar solo dependencias de runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copiar paquetes de Python desde el builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar código de la aplicación
COPY --chown=appuser:appuser . /app
# Sobrescribir con los assets ofuscados y compilados
COPY --from=assets-builder --chown=appuser:appuser /app/server/dashboard/static/dashboard/main.js /app/server/dashboard/static/dashboard/main.js
COPY --from=assets-builder --chown=appuser:appuser /app/server/dashboard/static/dashboard/upload.js /app/server/dashboard/static/dashboard/upload.js

# Crear directorios necesarios con permisos correctos
RUN mkdir -p /app/server/logs /app/server/media /app/server/staticfiles && \
    chown -R appuser:appuser /app/server/logs /app/server/media /app/server/staticfiles && \
    chmod 750 /app/server/logs /app/server/media /app/server/staticfiles

WORKDIR /app/server

# Collect static files for WhiteNoise (run as root before switching user)
RUN python manage.py collectstatic --noinput

# Cambiar al usuario no-root
USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/dashboard/api/v1/health/ || exit 1

# Exponer puerto (no root puede usar puertos > 1024)
EXPOSE 8001

# Usar gunicorn en producción (no runserver de Django)
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "4", "--threads", "2", \
     "--worker-class", "gthread", "--timeout", "120", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "pavssv_server.wsgi:application"]

