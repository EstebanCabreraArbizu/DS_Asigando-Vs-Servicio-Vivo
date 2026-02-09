"""
Middleware de seguridad personalizado para PA vs SV.

Implementa:
- Content Security Policy (CSP)
- Headers de seguridad adicionales
- Rate limiting por IP
- Logging de auditoría de seguridad
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("security")
audit_logger = logging.getLogger("audit")


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware que añade headers de seguridad a todas las respuestas.
    
    Headers implementados:
    - Content-Security-Policy (CSP)
    - X-Content-Type-Options
    - X-Frame-Options
    - Referrer-Policy
    - Permissions-Policy
    - Cache-Control para datos sensibles
    """
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        # Content Security Policy
        csp_directives = self._build_csp_header()
        if csp_directives:
            response["Content-Security-Policy"] = csp_directives
        
        # X-Content-Type-Options - Previene MIME type sniffing
        response["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options - Previene clickjacking (complementa CSP frame-ancestors)
        response["X-Frame-Options"] = "DENY"
        
        # Referrer-Policy - Controla información enviada en referer
        response["Referrer-Policy"] = getattr(
            settings, "SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin"
        )
        
        # Permissions-Policy (antes Feature-Policy)
        permissions = getattr(settings, "PERMISSIONS_POLICY", {})
        if permissions:
            policy_parts = []
            for feature, allowlist in permissions.items():
                if not allowlist:
                    policy_parts.append(f"{feature}=()")
                else:
                    allowed = " ".join(f'"{item}"' for item in allowlist)
                    policy_parts.append(f"{feature}=({allowed})")
            response["Permissions-Policy"] = ", ".join(policy_parts)
        
        # Cache-Control para endpoints sensibles (auth, perfil, etc.)
        sensitive_paths = ["/api/v1/auth/", "/api/v1/users/me/"]
        if any(request.path.startswith(path) for path in sensitive_paths):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        
        # Eliminar headers que revelan información del servidor
        for header in ["Server", "X-Powered-By"]:
            if header in response:
                del response[header]
        
        return response
    
    def _build_csp_header(self) -> str:
        """Construye el header CSP desde la configuración."""
        directives = []
        
        csp_settings = {
            "default-src": getattr(settings, "CSP_DEFAULT_SRC", ("'self'",)),
            "script-src": getattr(settings, "CSP_SCRIPT_SRC", ("'self'",)),
            "style-src": getattr(settings, "CSP_STYLE_SRC", ("'self'",)),
            "img-src": getattr(settings, "CSP_IMG_SRC", ("'self'",)),
            "font-src": getattr(settings, "CSP_FONT_SRC", ("'self'",)),
            "connect-src": getattr(settings, "CSP_CONNECT_SRC", ("'self'",)),
            "frame-ancestors": getattr(settings, "CSP_FRAME_ANCESTORS", ("'none'",)),
            "form-action": getattr(settings, "CSP_FORM_ACTION", ("'self'",)),
            "base-uri": getattr(settings, "CSP_BASE_URI", ("'self'",)),
            "object-src": getattr(settings, "CSP_OBJECT_SRC", ("'none'",)),
        }
        
        for directive, values in csp_settings.items():
            if values:
                directives.append(f"{directive} {' '.join(values)}")
        
        return "; ".join(directives)


class IPRateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting basado en IP para prevenir ataques de fuerza bruta.
    
    Configuración:
    - Endpoints de autenticación: 5 intentos por minuto
    - API general: 100 requests por minuto
    - Bloqueo temporal después de exceder límites
    
    Variables de entorno:
    - RATE_LIMIT_WHITELIST_IPS: IPs separadas por coma que omiten rate limiting
    - RATE_LIMIT_DISABLED: "1" para deshabilitar rate limiting (solo desarrollo)
    """
    
    # Configuración de límites por tipo de endpoint
    RATE_LIMITS = {
        "auth": {"requests": 10, "window": 60, "block_time": 300},     # 10 req/min, bloqueo 5 min
        "upload": {"requests": 20, "window": 60, "block_time": 180},   # 20 req/min, bloqueo 3 min
        "api": {"requests": 200, "window": 60, "block_time": 60},      # 200 req/min, bloqueo 1 min
    }
    
    # Patrones de endpoints sensibles
    AUTH_PATTERNS = ["/api/v1/auth/login/", "/api/v1/auth/refresh/"]
    UPLOAD_PATTERNS = ["/api/v1/jobs/", "/api/v1/upload/", "/dashboard/upload/"]
    
    # IPs que omiten rate limiting (configurables por env var)
    WHITELIST_IPS = set()
    
    @classmethod
    def _load_whitelist(cls):
        """Carga la whitelist de IPs desde variable de entorno."""
        import os
        whitelist_str = os.getenv("RATE_LIMIT_WHITELIST_IPS", "")
        if whitelist_str:
            cls.WHITELIST_IPS = {ip.strip() for ip in whitelist_str.split(",") if ip.strip()}
        # Siempre permitir localhost en desarrollo
        if os.getenv("DJANGO_DEBUG", "0") == "1":
            cls.WHITELIST_IPS.update(["127.0.0.1", "localhost", "::1"])
    
    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        import os
        
        # Deshabilitar rate limiting si está configurado (solo desarrollo)
        if os.getenv("RATE_LIMIT_DISABLED", "0") == "1":
            return None
        
        # Cargar whitelist si no está cargada
        if not self.WHITELIST_IPS:
            self._load_whitelist()
        
        # Obtener IP del cliente (considerando proxies)
        client_ip = self._get_client_ip(request)
        
        # Omitir rate limiting para IPs en whitelist
        if client_ip in self.WHITELIST_IPS:
            return None
        
        # Determinar tipo de endpoint
        endpoint_type = self._get_endpoint_type(request.path)
        
        # Verificar si la IP está bloqueada
        block_key = f"rate_limit_block:{endpoint_type}:{client_ip}"
        if cache.get(block_key):
            logger.warning(
                f"IP bloqueada intentando acceder: {client_ip} -> {request.path}"
            )
            return JsonResponse(
                {
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "Demasiadas solicitudes. Por favor, espere antes de intentar nuevamente.",
                    }
                },
                status=429,
            )
        
        # Verificar rate limit
        if not self._check_rate_limit(client_ip, endpoint_type):
            # Bloquear IP temporalmente
            limits = self.RATE_LIMITS.get(endpoint_type, self.RATE_LIMITS["api"])
            cache.set(block_key, True, limits["block_time"])
            
            logger.warning(
                f"Rate limit excedido - IP: {client_ip}, Endpoint: {request.path}, Tipo: {endpoint_type}"
            )
            
            return JsonResponse(
                {
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": f"Límite de solicitudes excedido. Bloqueado por {limits['block_time']} segundos.",
                    }
                },
                status=429,
            )
        
        return None
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Obtiene la IP real del cliente, considerando proxies."""
        # Cloudflare inyecta la IP real del cliente en este header
        cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
        if cf_ip:
            return cf_ip.strip()
        # Fallback para proxies confiables (Nginx Proxy Manager)
        x_real_ip = request.META.get("HTTP_X_REAL_IP")
        if x_real_ip:
            return x_real_ip.strip()
        return request.META.get("REMOTE_ADDR", "unknown")
    
    def _get_endpoint_type(self, path: str) -> str:
        """Determina el tipo de endpoint para aplicar límites apropiados."""
        if any(path.startswith(p) for p in self.AUTH_PATTERNS):
            return "auth"
        if any(path.startswith(p) for p in self.UPLOAD_PATTERNS):
            return "upload"
        return "api"
    
    def _check_rate_limit(self, client_ip: str, endpoint_type: str) -> bool:
        """Verifica si la IP está dentro del límite de requests permitidos."""
        limits = self.RATE_LIMITS.get(endpoint_type, self.RATE_LIMITS["api"])
        cache_key = f"rate_limit:{endpoint_type}:{client_ip}"
        
        # Obtener contador actual
        current = cache.get(cache_key, {"count": 0, "start": time.time()})
        
        # Si la ventana de tiempo expiró, reiniciar
        if time.time() - current["start"] > limits["window"]:
            current = {"count": 0, "start": time.time()}
        
        # Incrementar contador
        current["count"] += 1
        
        # Guardar en cache
        cache.set(cache_key, current, limits["window"])
        
        return current["count"] <= limits["requests"]


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware de auditoría que registra todas las acciones importantes.
    
    Registra:
    - Intentos de autenticación (éxitos y fallos)
    - Accesos a recursos sensibles
    - Modificaciones de datos
    - Errores de permisos
    """
    
    # Endpoints que requieren auditoría detallada
    AUDIT_ENDPOINTS = {
        "/api/v1/auth/login/": "AUTH_LOGIN",
        "/api/v1/auth/logout/": "AUTH_LOGOUT",
        "/api/v1/auth/refresh/": "AUTH_REFRESH",
        "/api/v1/users/me/password/": "PASSWORD_CHANGE",
        "/api/v1/users/me/switch-tenant/": "TENANT_SWITCH",
        "/api/v1/jobs/": "JOB_ACCESS",
    }
    
    def process_request(self, request: HttpRequest) -> None:
        """Registra el inicio de la request."""
        request._audit_start_time = time.time()
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Registra la finalización de la request con resultado."""
        # Solo auditar endpoints específicos
        action = None
        for pattern, action_type in self.AUDIT_ENDPOINTS.items():
            if request.path.startswith(pattern):
                action = action_type
                break
        
        if not action:
            # Auditar también errores 4xx y 5xx en cualquier endpoint
            if response.status_code >= 400:
                action = "ERROR_RESPONSE"
            else:
                return response
        
        # Construir registro de auditoría
        duration = time.time() - getattr(request, "_audit_start_time", time.time())
        
        audit_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "ip": self._get_client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", "unknown")[:200],
            "user_id": getattr(request.user, "id", None) if hasattr(request, "user") else None,
            "username": getattr(request.user, "username", "anonymous") if hasattr(request, "user") else "anonymous",
            "tenant_id": request.META.get("HTTP_X_TENANT_ID"),
        }
        
        # Log según el tipo de evento
        if response.status_code >= 500:
            audit_logger.error(f"AUDIT: {audit_record}")
        elif response.status_code >= 400:
            audit_logger.warning(f"AUDIT: {audit_record}")
        elif action in ["AUTH_LOGIN", "PASSWORD_CHANGE", "TENANT_SWITCH"]:
            audit_logger.info(f"AUDIT: {audit_record}")
        else:
            audit_logger.debug(f"AUDIT: {audit_record}")
        
        return response
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """Obtiene la IP real del cliente."""
        cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
        if cf_ip:
            return cf_ip.strip()
        x_real_ip = request.META.get("HTTP_X_REAL_IP")
        if x_real_ip:
            return x_real_ip.strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class RequestSanitizationMiddleware(MiddlewareMixin):
    """
    Middleware que sanitiza y valida las requests entrantes.
    
    Protege contra:
    - Path traversal attacks
    - SQL injection básico en query params
    - Headers maliciosos
    - Payloads excesivamente grandes
    """
    
    # Patrones sospechosos (potenciales ataques)
    SUSPICIOUS_PATTERNS = [
        "../",           # Path traversal
        "..\\",          # Path traversal Windows
        "<script",       # XSS básico
        "javascript:",   # XSS en URLs
        "data:text/html", # XSS en data URLs
        "UNION SELECT",  # SQL injection
        "OR 1=1",        # SQL injection
        "' OR '",        # SQL injection
        "; DROP ",       # SQL injection
    ]
    
    # Tamaño máximo de request body (Default Django + Fallback 50MB)
    MAX_BODY_SIZE = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 50 * 1024 * 1024)
    
    def process_request(self, request: HttpRequest) -> HttpResponse | None:
        # Verificar tamaño del body
        content_length = request.META.get("CONTENT_LENGTH")
        if content_length:
            try:
                if int(content_length) > self.MAX_BODY_SIZE:
                    logger.warning(f"Request demasiado grande: {content_length} bytes")
                    return JsonResponse(
                        {"error": {"code": "payload_too_large", "message": "El contenido excede el límite permitido"}},
                        status=413,
                    )
            except ValueError:
                pass
        
        # Verificar path por patrones sospechosos
        if self._has_suspicious_content(request.path):
            logger.warning(f"Path sospechoso detectado: {request.path}")
            return JsonResponse(
                {"error": {"code": "invalid_request", "message": "Solicitud inválida"}},
                status=400,
            )
        
        # Verificar query params
        for key, values in request.GET.lists():
            for value in values:
                if self._has_suspicious_content(value):
                    logger.warning(f"Query param sospechoso: {key}={value}")
                    return JsonResponse(
                        {"error": {"code": "invalid_request", "message": "Parámetro inválido"}},
                        status=400,
                    )
        
        return None
    
    def _has_suspicious_content(self, content: str) -> bool:
        """Verifica si el contenido tiene patrones sospechosos."""
        content_lower = content.lower()
        return any(pattern.lower() in content_lower for pattern in self.SUSPICIOUS_PATTERNS)
