# API de Análisis Personal Asignado vs Servicio Vivo

API REST para consolidar y analizar datos de Personal Asignado y Servicio Vivo generando reportes Excel automatizados.

## 🚀 Despliegue en VPS

### Requisitos Previos

- Python 3.12+
- 2 GB RAM mínimo
- 5 GB espacio en disco

### 1. Clonar el repositorio

```bash
git clone <tu-repositorio>
cd Project_PAvsSV
```

### 2. Crear entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\Activate.ps1  # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crear archivo `.env` en la raíz:

```env
# Límites
MAX_UPLOAD_SIZE=50000000

# CORS - Reemplazar con tus dominios
ALLOW_ORIGINS=https://tu-dominio.com,https://api.tu-dominio.com

# Entorno
ENVIRONMENT=production
```

### 5. Ejecutar la API

#### Desarrollo:
```bash
python main.py --reload
```

#### Producción con Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app --bind 0.0.0.0:8000
```

#### Con systemd (recomendado):

Crear `/etc/systemd/system/pavssv-api.service`:

```ini
[Unit]
Description=API PA vs SV
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/Project_PAvsSV
Environment="PATH=/opt/Project_PAvsSV/venv/bin"
ExecStart=/opt/Project_PAvsSV/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Activar:
```bash
sudo systemctl enable pavssv-api
sudo systemctl start pavssv-api
```

### 6. Configurar Nginx (Reverse Proxy)

```nginx
server {
    listen 80;
    server_name api.tu-dominio.com;

    client_max_body_size 60M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
```

### 7. SSL con Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.tu-dominio.com
```

## 📡 Endpoints

- **POST** `/api/v1/analyze` - Analizar archivos Excel
- **GET** `/api/v1/health` - Health check
- **GET** `/api/v1/config` - Configuración actual
- **GET** `/docs` - Documentación Swagger

## 🧪 Pruebas

```bash
# Con curl
curl -X POST "http://localhost:8000/api/v1/analyze?return_json=true" \
  -F "personal_asignado=@archivo_pa.xlsx" \
  -F "servicio_vivo=@archivo_sv.xlsx"

# Health check
curl http://localhost:8000/api/v1/health
```

## 🔧 Comandos útiles

```bash
# Ver logs
journalctl -u pavssv-api -f

# Reiniciar servicio
sudo systemctl restart pavssv-api

# Ver estado
sudo systemctl status pavssv-api
```

## 📊 Monitoreo

Se recomienda configurar:
- **Logs**: `/var/log/pavssv/`
- **Métricas**: Prometheus + Grafana
- **Alertas**: Para errores 5xx y tiempos de respuesta

## 🔐 Seguridad

- ✅ CORS configurado por dominio
- ✅ Validación de tamaño de archivos
- ✅ Variables de entorno para configuración
- ⚠️ Configurar firewall (solo puerto 80/443)
- ⚠️ Configurar rate limiting en Nginx

## 📝 Mantenimiento

```bash
# Actualizar dependencias
pip install --upgrade -r requirements.txt

# Backup de configuración
cp .env .env.backup
```
