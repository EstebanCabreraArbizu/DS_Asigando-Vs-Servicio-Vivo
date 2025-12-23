#!/bin/bash
# Script de instalación para VPS (Ubuntu/Debian)

set -e

echo "=========================================="
echo "🚀 Instalando API PA vs SV en VPS"
echo "=========================================="

# Actualizar sistema
echo "📦 Actualizando sistema..."
sudo apt update && sudo apt upgrade -y

# Instalar dependencias del sistema
echo "📦 Instalando dependencias..."
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Crear directorio de aplicación
APP_DIR="/opt/Project_PAvsSV"
echo "📁 Creando directorio en $APP_DIR..."
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Copiar archivos (asume que estás en el directorio del proyecto)
echo "📂 Copiando archivos..."
cp -r . $APP_DIR/
cd $APP_DIR

# Crear entorno virtual
echo "🐍 Creando entorno virtual..."
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias Python
echo "📚 Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Configurar archivo .env
if [ ! -f .env ]; then
    echo "⚙️  Configurando variables de entorno..."
    read -p "Ingresa MAX_UPLOAD_SIZE (default: 50000000): " max_size
    max_size=${max_size:-50000000}
    
    read -p "Ingresa ALLOW_ORIGINS (ej: https://dominio.com): " origins
    origins=${origins:-"*"}
    
    cat > .env << EOF
MAX_UPLOAD_SIZE=$max_size
ALLOW_ORIGINS=$origins
ENVIRONMENT=production
EOF
    echo "✅ Archivo .env creado"
else
    echo "⚠️  Archivo .env ya existe, no se modificó"
fi

# Crear servicio systemd
echo "🔧 Configurando servicio systemd..."
sudo tee /etc/systemd/system/pavssv-api.service > /dev/null << EOF
[Unit]
Description=API de Análisis PA vs SV
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker api:app --bind 0.0.0.0:8000 --timeout 300
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Habilitar y arrancar servicio
echo "🚀 Iniciando servicio..."
sudo systemctl daemon-reload
sudo systemctl enable pavssv-api
sudo systemctl start pavssv-api

# Verificar estado
sleep 2
sudo systemctl status pavssv-api --no-pager

# Configurar Nginx
read -p "¿Configurar Nginx ahora? (s/n): " config_nginx
if [ "$config_nginx" = "s" ]; then
    read -p "Ingresa el dominio (ej: api.tudominio.com): " domain
    
    echo "🌐 Configurando Nginx..."
    sudo tee /etc/nginx/sites-available/pavssv-api > /dev/null << EOF
server {
    listen 80;
    server_name $domain;

    client_max_body_size 60M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
EOF

    sudo ln -sf /etc/nginx/sites-available/pavssv-api /etc/nginx/sites-enabled/
    sudo nginx -t && sudo systemctl reload nginx
    
    echo "✅ Nginx configurado"
    
    # Configurar SSL
    read -p "¿Configurar SSL con Let's Encrypt? (s/n): " config_ssl
    if [ "$config_ssl" = "s" ]; then
        echo "🔒 Configurando SSL..."
        sudo certbot --nginx -d $domain
    fi
fi

echo ""
echo "=========================================="
echo "✅ Instalación completada"
echo "=========================================="
echo ""
echo "📡 API ejecutándose en http://localhost:8000"
echo "📚 Documentación: http://localhost:8000/docs"
echo "🔍 Health check: http://localhost:8000/api/v1/health"
echo ""
echo "🔧 Comandos útiles:"
echo "  - Ver logs: journalctl -u pavssv-api -f"
echo "  - Reiniciar: sudo systemctl restart pavssv-api"
echo "  - Estado: sudo systemctl status pavssv-api"
echo ""
