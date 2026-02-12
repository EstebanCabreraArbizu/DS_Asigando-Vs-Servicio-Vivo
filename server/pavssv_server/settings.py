from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

# Cargar env (docker-compose usa server/.env)
load_dotenv(BASE_DIR / ".env", override=False)

# Permite importar los módulos del pipeline desde el root del repo
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "DJANGO_SECRET_KEY no está configurada. "
        "Genera una con: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# Upload Limits (50 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "storages",
    # Local apps
    "tenants",
    "jobs",
    "api_v1",
    "dashboard",
    # Security & Admin protection
    "axes",
    "captcha",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static files in production
    "corsheaders.middleware.CorsMiddleware",  # CORS - debe ir antes de CommonMiddleware
    # Middlewares de seguridad personalizados
    "pavssv_server.middleware.RequestSanitizationMiddleware",  # Sanitización de inputs
    "pavssv_server.middleware.IPRateLimitMiddleware",  # Rate limiting por IP
    "pavssv_server.middleware.SecurityHeadersMiddleware",  # Headers CSP y seguridad
    "pavssv_server.middleware.AuditLoggingMiddleware",  # Logging de auditoría
    # Middlewares estándar de Django
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Brute force protection (django-axes) - debe ir después de AuthenticationMiddleware
    "axes.middleware.AxesMiddleware",
    # Restricción de IP para panel admin
    "pavssv_server.middleware.AdminIPRestrictionMiddleware",
]

ROOT_URLCONF = "pavssv_server.urls"

# =============================================================================
# AUTHENTICATION BACKENDS (django-axes para brute-force protection)
# =============================================================================
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "pavssv_server.wsgi.application"

# Base de datos: PostgreSQL en Docker, SQLite en desarrollo local
if os.getenv("USE_SQLITE", "0") == "1":
    # Desarrollo local con SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    # Producción/Docker con PostgreSQL
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "pavssv"),
            "USER": os.getenv("POSTGRES_USER", "pavssv"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "pavssv"),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }

# Password validation con Argon2
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Usar Argon2 como hasher de contraseñas (más seguro que PBKDF2)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise: Compress and cache static files
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# =============================================================================
# STORAGE CONFIGURATION - MinIO / S3
# =============================================================================
USE_S3_STORAGE = os.getenv("USE_S3_STORAGE", "false").lower() == "true"

if USE_S3_STORAGE:
    # Configuración S3/MinIO
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "pavssv-artifacts")
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")  # None para AWS S3 real
    AWS_S3_PUBLIC_URL = os.getenv("AWS_S3_PUBLIC_URL", AWS_S3_ENDPOINT_URL)
    AWS_S3_ADDRESSING_STYLE = "path"  # Requerido para MinIO
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_SIGNATURE_VERSION = os.getenv("AWS_S3_SIGNATURE_VERSION", "s3v4")
    # Cambiado a True para evitar que Django chequee si el archivo existe (lo cual causa 403 en MinIO seguro)
    AWS_S3_FILE_OVERWRITE = True 
    # MinIO no soporta bien ACLs de AWS, mejor desactivarlas si se usa MinIO
    AWS_DEFAULT_ACL = None if AWS_S3_ENDPOINT_URL else os.getenv("AWS_DEFAULT_ACL", "private")
    AWS_QUERYSTRING_AUTH = True  # URLs firmadas con expiración
    AWS_QUERYSTRING_EXPIRE = 3600  # 1 hora de validez para URLs firmadas
    AWS_S3_VERIFY = os.getenv("AWS_S3_VERIFY", "true").lower() == "true"

    # Buckets separados por tipo de archivo
    AWS_INPUTS_BUCKET = os.getenv("AWS_INPUTS_BUCKET", "pavssv-inputs")
    AWS_ARTIFACTS_BUCKET = os.getenv("AWS_ARTIFACTS_BUCKET", "pavssv-artifacts")
    AWS_EXPORTS_BUCKET = os.getenv("AWS_EXPORTS_BUCKET", "pavssv-exports")
    
    # Storage backends personalizados
    # Opciones comunes para todos los backends S3
    S3_COMMON_OPTIONS = {
        "access_key": AWS_ACCESS_KEY_ID,
        "secret_key": AWS_SECRET_ACCESS_KEY,
        "endpoint_url": AWS_S3_ENDPOINT_URL,
        "region_name": AWS_S3_REGION_NAME,
        "signature_version": AWS_S3_SIGNATURE_VERSION,
        "default_acl": AWS_DEFAULT_ACL,
        "addressing_style": AWS_S3_ADDRESSING_STYLE,
        "querystring_auth": AWS_QUERYSTRING_AUTH,
        "querystring_expire": AWS_QUERYSTRING_EXPIRE,
        "use_ssl": AWS_S3_ENDPOINT_URL.startswith("https") if AWS_S3_ENDPOINT_URL else True,
        "verify": AWS_S3_VERIFY,
    }
    
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                **S3_COMMON_OPTIONS,
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
        "inputs": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                **S3_COMMON_OPTIONS,
                "bucket_name": AWS_INPUTS_BUCKET,
            },
        },
        "artifacts": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                **S3_COMMON_OPTIONS,
                "bucket_name": AWS_ARTIFACTS_BUCKET,
            },
        },
        "exports": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                **S3_COMMON_OPTIONS,
                "bucket_name": AWS_EXPORTS_BUCKET,
            },
        },
    }
    
    MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/" if AWS_S3_ENDPOINT_URL else f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"
else:
    # Almacenamiento local (desarrollo sin Docker)
    MEDIA_ROOT = os.getenv("MEDIA_ROOT", str(BASE_DIR / "media"))
    MEDIA_URL = "/media/"
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# CACHE CONFIGURATION - Redis
# =============================================================================
# Usar Redis para el cache (rate limiting, sessions, etc.)
# Formato con auth: redis://:password@host:port/db o redis://user:password@host:port/db
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")

# Construir URL con o sin autenticación (formato Redis 6+ ACL con username 'default')
if REDIS_PASSWORD:
    REDIS_URL = os.getenv("REDIS_URL", f"redis://default:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
else:
    REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "pavssv",
        "TIMEOUT": 300,  # 5 minutos por defecto
    }
}

# Fallback a cache local si Redis no está disponible (desarrollo)
if os.getenv("USE_SQLITE") == "1":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }

# =============================================================================
# REST FRAMEWORK & JWT AUTHENTICATION
# =============================================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",  # Para el admin y desarrollo
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
    },
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ] if not DEBUG else [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "EXCEPTION_HANDLER": "api_v1.exceptions.custom_exception_handler",
}

# JWT Configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    
    # Custom claims para incluir tenant y rol
    "TOKEN_OBTAIN_SERIALIZER": "api_v1.serializers.CustomTokenObtainPairSerializer",
}

# =============================================================================
# CORS CONFIGURATION
# =============================================================================
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-tenant-id",  # Header custom para identificar tenant
]

# En desarrollo, permitir todos los orígenes (NO usar en producción)
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True

# =============================================================================
# SECURITY SETTINGS
# =============================================================================
# Expiración de sesiones y CSRF
SESSION_COOKIE_AGE = 900  # 15 minutos en segundos
CSRF_COOKIE_AGE = 900     # 15 minutos en segundos

# Cookies seguras (siempre activas, independiente de DEBUG)
SESSION_COOKIE_HTTPONLY = True       # Impide acceso a la cookie de sesión desde JS
CSRF_COOKIE_HTTPONLY = True          # Impide acceso a la cookie CSRF desde JS
SESSION_COOKIE_SAMESITE = "Lax"      # Previene envío cross-site
CSRF_COOKIE_SAMESITE = "Lax"         # Previene envío cross-site
SESSION_COOKIE_NAME = "__Host-sessionid"  # Prefijo __Host requiere Secure + path=/
CSRF_COOKIE_NAME = "__Host-csrftoken"     # Prefijo __Host requiere Secure + path=/

if not DEBUG:
    # HTTPS/SSL
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "true").lower() == "true"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    
    # Cookies seguras solo transmitidas por HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Prevención de ataques
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"
else:
    # En desarrollo sin HTTPS, no usar prefijo __Host ni Secure
    SESSION_COOKIE_NAME = "sessionid"
    CSRF_COOKIE_NAME = "csrftoken"

# CSP (Content Security Policy) - Configurar según necesidades del frontend
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:8001,http://127.0.0.1:8001").split(",")
    if origin.strip()
]

# =============================================================================
# CONTENT SECURITY POLICY (CSP)
# =============================================================================
# Configuración de CSP para prevenir XSS, clickjacking y otros ataques
# Todas las librerías (Bootstrap, ECharts) se sirven localmente via WhiteNoise
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",  # Necesario para estilos inline del dashboard
    "https://fonts.googleapis.com",  # Google Fonts
)
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com", "https://fonts.googleapis.com")
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_ANCESTORS = ("'none'",)
CSP_FORM_ACTION = ("'self'",)
CSP_BASE_URI = ("'self'",)
CSP_OBJECT_SRC = ("'none'",)

# Referrer Policy - No enviar información sensible en referer
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Permissions Policy (anteriormente Feature Policy)
PERMISSIONS_POLICY = {
    "geolocation": [],
    "microphone": [],
    "camera": [],
    "payment": [],
    "usb": [],
}

# =============================================================================
# DJANGO-AXES: Brute Force Protection (Obs 7)
# =============================================================================
from datetime import timedelta

AXES_FAILURE_LIMIT = 5                                    # Max 5 intentos fallidos
AXES_COOLOFF_TIME = timedelta(minutes=30)                 # Lockout de 30 minutos
AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True           # Lockout por user+IP
AXES_RESET_ON_SUCCESS = True                              # Reset contador en login exitoso
AXES_LOCKOUT_TEMPLATE = "dashboard/lockout.html"          # Template custom de lockout
AXES_META_PRECEDENCE_ORDER = [                            # Consistente con Cloudflare
    "HTTP_CF_CONNECTING_IP",
    "HTTP_X_REAL_IP",
    "REMOTE_ADDR",
]
AXES_VERBOSE = not DEBUG                                  # Logs detallados solo en prod
AXES_ENABLE_ACCESS_FAILURE_LOG = True                      # Registrar fallos en DB

# =============================================================================
# DJANGO-SIMPLE-CAPTCHA
# =============================================================================
CAPTCHA_LENGTH = 5
CAPTCHA_FONT_SIZE = 28
CAPTCHA_NOISE_FUNCTIONS = ("captcha.helpers.noise_dots",)
CAPTCHA_CHALLENGE_FUNCT = "captcha.helpers.math_challenge"  # Desafío matemático (más accesible)
CAPTCHA_TIMEOUT = 5  # 5 minutos para resolver

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_TRACK_STARTED = True
# En desarrollo (DEBUG=True), ejecutar tasks sincrónicamente sin Redis
CELERY_TASK_ALWAYS_EAGER = DEBUG
CELERY_TASK_EAGER_PROPAGATES = DEBUG

# =============================================================================
# LOGGING - Configuración de logs de seguridad y auditoría
# =============================================================================
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "audit": {
            "format": "{asctime} | {levelname} | {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "security": {
            "format": "[SECURITY] {asctime} | {levelname} | {name} | {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "audit_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "audit.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 10,
            "formatter": "audit",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "security.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 10,
            "formatter": "security",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "error.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "level": "ERROR",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "error_file"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console", "security_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "jobs": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        # Logger de auditoría para acciones críticas
        "audit": {
            "handlers": ["console", "audit_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Logger de seguridad para eventos de seguridad
        "security": {
            "handlers": ["console", "security_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
