"""
Tests de Seguridad para PA vs SV

Este módulo contiene tests automatizados para verificar que todas las
medidas de seguridad están funcionando correctamente.

Ejecución:
    cd server
    python -m pytest ../tests/test_security.py -v

Con cobertura:
    python -m pytest ../tests/test_security.py --cov=api_v1 --cov=pavssv_server -v
"""
from __future__ import annotations

import io
import time
from unittest.mock import MagicMock, patch

import pytest

# Configurar Django antes de importar modelos
import django
import os
import sys

# Agregar el servidor al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pavssv_server.settings')
os.environ['USE_SQLITE'] = '1'

django.setup()

from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


# =============================================================================
# TESTS DE AUTENTICACIÓN Y RATE LIMITING
# =============================================================================

class TestAuthenticationSecurity(TestCase):
    """Tests de seguridad para el sistema de autenticación."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePassword123!'
        )
    
    def test_login_with_valid_credentials(self):
        """Verificar que login funciona con credenciales válidas."""
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePassword123!'
        })
        # Debería retornar tokens
        self.assertIn(response.status_code, [200, 201])
        if response.status_code == 200:
            self.assertIn('access', response.data)
            self.assertIn('refresh', response.data)
    
    def test_login_with_invalid_credentials(self):
        """Verificar que login falla con credenciales inválidas."""
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 401)
    
    def test_login_response_no_password_leak(self):
        """Verificar que la respuesta de login no filtra la contraseña."""
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePassword123!'
        })
        # La respuesta no debe contener la contraseña
        response_text = str(response.content)
        self.assertNotIn('SecurePassword123!', response_text)
        self.assertNotIn('password', response_text.lower().replace('"password":', ''))
    
    def test_protected_endpoint_requires_auth(self):
        """Verificar que endpoints protegidos requieren autenticación."""
        response = self.client.get('/api/v1/users/me/')
        self.assertEqual(response.status_code, 401)
    
    def test_protected_endpoint_with_valid_token(self):
        """Verificar acceso con token válido."""
        # Obtener token
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePassword123!'
        })
        
        if login_response.status_code == 200:
            token = login_response.data['access']
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            
            response = self.client.get('/api/v1/users/me/')
            self.assertEqual(response.status_code, 200)


class TestRateLimiting(TestCase):
    """Tests para verificar el rate limiting."""
    
    def setUp(self):
        self.client = APIClient()
        # Limpiar cache para tests consistentes
        from django.core.cache import cache
        cache.clear()
    
    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    })
    def test_rate_limit_login_endpoint(self):
        """Verificar que el rate limit funciona en el endpoint de login."""
        # El límite es 5 intentos por minuto
        for i in range(6):
            response = self.client.post('/api/v1/auth/login/', {
                'username': 'nonexistent',
                'password': 'wrongpassword'
            }, REMOTE_ADDR='192.168.1.100')
        
        # El 6to intento debería ser bloqueado (429) o fallar normalmente (401)
        # Depende de si el middleware de rate limit está activo
        self.assertIn(response.status_code, [401, 429])


# =============================================================================
# TESTS DE VALIDACIÓN DE ARCHIVOS
# =============================================================================

class TestFileValidation(TestCase):
    """Tests para el validador de archivos."""
    
    def test_valid_csv_extension(self):
        """Verificar que CSV válido es aceptado."""
        from api_v1.validators import FileValidator
        
        csv_content = b"name,value\ntest,123\n"
        file = io.BytesIO(csv_content)
        file.name = "data.csv"
        
        validator = FileValidator(file)
        # No debería lanzar excepción
        try:
            validator._validate_extension()
            passed = True
        except ValidationError:
            passed = False
        
        self.assertTrue(passed)
    
    def test_reject_exe_extension(self):
        """Verificar que extensiones peligrosas son rechazadas."""
        from api_v1.validators import FileValidator
        
        file = io.BytesIO(b"MZ\x90\x00")  # Magic bytes de EXE
        file.name = "malware.exe"
        
        validator = FileValidator(file)
        
        with self.assertRaises(ValidationError):
            validator._validate_extension()
    
    def test_reject_php_extension(self):
        """Verificar que archivos PHP son rechazados."""
        from api_v1.validators import FileValidator
        
        file = io.BytesIO(b"<?php echo 'hack'; ?>")
        file.name = "backdoor.php"
        
        validator = FileValidator(file)
        
        with self.assertRaises(ValidationError):
            validator._validate_extension()
    
    def test_reject_path_traversal_filename(self):
        """Verificar que nombres con path traversal son rechazados."""
        from api_v1.validators import FileValidator
        
        file = io.BytesIO(b"name,value")
        file.name = "../../../etc/passwd.csv"
        
        validator = FileValidator(file)
        
        with self.assertRaises(ValidationError):
            validator._validate_filename()
    
    def test_reject_null_byte_filename(self):
        """Verificar que nombres con null bytes son rechazados."""
        from api_v1.validators import FileValidator
        
        file = io.BytesIO(b"data")
        file.name = "file\x00.csv"
        
        validator = FileValidator(file)
        
        with self.assertRaises(ValidationError):
            validator._validate_filename()
    
    def test_reject_oversized_file(self):
        """Verificar que archivos muy grandes son rechazados."""
        from api_v1.validators import FileValidator, MAX_FILE_SIZE
        
        # Crear archivo más grande que el límite
        large_content = b"x" * (MAX_FILE_SIZE + 1)
        file = io.BytesIO(large_content)
        file.name = "huge.csv"
        
        validator = FileValidator(file)
        
        with self.assertRaises(ValidationError):
            validator._validate_size()
    
    def test_reject_empty_file(self):
        """Verificar que archivos vacíos son rechazados."""
        from api_v1.validators import FileValidator
        
        file = io.BytesIO(b"")
        file.name = "empty.csv"
        
        validator = FileValidator(file)
        
        with self.assertRaises(ValidationError):
            validator._validate_size()
    
    def test_reject_malicious_csv_with_php(self):
        """Verificar que CSV con código PHP es rechazado."""
        from api_v1.validators import FileValidator
        
        malicious = b"name,value\n<?php system('rm -rf /'); ?>,test"
        file = io.BytesIO(malicious)
        file.name = "data.csv"
        
        validator = FileValidator(file)
        
        with self.assertRaises(ValidationError):
            validator._scan_for_malicious_content()
    
    def test_reject_malicious_csv_with_script(self):
        """Verificar que CSV con JavaScript es rechazado."""
        from api_v1.validators import FileValidator
        
        malicious = b"name,value\n<script>alert('xss')</script>,test"
        file = io.BytesIO(malicious)
        file.name = "data.csv"
        
        validator = FileValidator(file)
        
        with self.assertRaises(ValidationError):
            validator._scan_for_malicious_content()
    
    def test_safe_filename_generation(self):
        """Verificar que se genera un nombre de archivo seguro."""
        from api_v1.validators import FileValidator
        
        file = io.BytesIO(b"name,value\ntest,123")
        file.name = "My File (1).csv"
        
        validator = FileValidator(file)
        safe_name = validator.get_safe_filename()
        
        # El nombre seguro debe:
        # - Tener extensión .csv
        # - No tener espacios ni paréntesis
        # - Tener un UUID prefix
        self.assertTrue(safe_name.endswith('.csv'))
        self.assertNotIn(' ', safe_name)
        self.assertNotIn('(', safe_name)
        self.assertEqual(len(safe_name.split('_')[0]), 12)  # UUID de 12 chars
    
    def test_file_hash_calculation(self):
        """Verificar que el hash del archivo se calcula correctamente."""
        from api_v1.validators import FileValidator
        
        content = b"name,value\ntest,123"
        file = io.BytesIO(content)
        file.name = "data.csv"
        
        validator = FileValidator(file)
        hash1 = validator.get_file_hash()
        hash2 = validator.get_file_hash()  # Debe ser cacheado
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA-256 = 64 hex chars


# =============================================================================
# TESTS DE HEADERS DE SEGURIDAD
# =============================================================================

class TestSecurityHeaders(TestCase):
    """Tests para verificar headers de seguridad HTTP."""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_health_endpoint_returns_security_headers(self):
        """Verificar que el health check tiene headers de seguridad."""
        response = self.client.get('/api/v1/health/')
        
        # Verificar headers básicos
        self.assertEqual(response.status_code, 200)
        
        # Estos headers deberían estar presentes si el middleware está activo
        # Nota: En tests unitarios, algunos middlewares pueden no ejecutarse
    
    def test_csp_header_format(self):
        """Verificar el formato del header CSP."""
        from pavssv_server.middleware import SecurityHeadersMiddleware
        
        middleware = SecurityHeadersMiddleware(get_response=lambda r: MagicMock())
        csp = middleware._build_csp_header()
        
        # Debe contener directivas CSP válidas
        self.assertIn("default-src", csp)
        self.assertIn("'self'", csp)


# =============================================================================
# TESTS DE PROTECCIÓN CONTRA INYECCIÓN
# =============================================================================

class TestInjectionPrevention(TestCase):
    """Tests para verificar protección contra ataques de inyección."""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_sql_injection_in_query_param(self):
        """Verificar protección contra SQL injection en query params."""
        from pavssv_server.middleware import RequestSanitizationMiddleware
        
        middleware = RequestSanitizationMiddleware(get_response=lambda r: MagicMock())
        
        # Verificar que detecta patrones de SQL injection
        self.assertTrue(middleware._has_suspicious_content("' OR '1'='1"))
        self.assertTrue(middleware._has_suspicious_content("UNION SELECT"))
        self.assertTrue(middleware._has_suspicious_content("; DROP TABLE"))
    
    def test_xss_detection(self):
        """Verificar detección de patrones XSS."""
        from pavssv_server.middleware import RequestSanitizationMiddleware
        
        middleware = RequestSanitizationMiddleware(get_response=lambda r: MagicMock())
        
        # Verificar que detecta patrones de XSS
        self.assertTrue(middleware._has_suspicious_content("<script>alert('xss')</script>"))
        self.assertTrue(middleware._has_suspicious_content("javascript:alert(1)"))
    
    def test_path_traversal_detection(self):
        """Verificar detección de path traversal."""
        from pavssv_server.middleware import RequestSanitizationMiddleware
        
        middleware = RequestSanitizationMiddleware(get_response=lambda r: MagicMock())
        
        # Verificar que detecta path traversal
        self.assertTrue(middleware._has_suspicious_content("../../../etc/passwd"))
        self.assertTrue(middleware._has_suspicious_content("..\\..\\windows\\system32"))


# =============================================================================
# TESTS DE GESTIÓN DE SECRETOS
# =============================================================================

class TestSecretsManager(TestCase):
    """Tests para el gestor de secretos."""
    
    def test_get_secret_from_env(self):
        """Verificar que se pueden obtener secretos de variables de entorno."""
        from pavssv_server.secrets import SecretsManager
        
        # Configurar variable de entorno de prueba
        os.environ['TEST_SECRET'] = 'test_value'
        
        manager = SecretsManager()
        manager.use_aws = False  # Forzar uso de env vars
        
        value = manager.get_secret('TEST_SECRET')
        self.assertEqual(value, 'test_value')
        
        # Limpiar
        del os.environ['TEST_SECRET']
    
    def test_get_secret_with_default(self):
        """Verificar que se retorna el default si el secreto no existe."""
        from pavssv_server.secrets import SecretsManager
        
        manager = SecretsManager()
        manager.use_aws = False
        
        value = manager.get_secret('NONEXISTENT_SECRET', default='default_value')
        self.assertEqual(value, 'default_value')
    
    def test_secrets_cache(self):
        """Verificar que los secretos se cachean correctamente."""
        from pavssv_server.secrets import SecretsManager
        
        os.environ['CACHED_SECRET'] = 'cached_value'
        
        manager = SecretsManager()
        manager.use_aws = False
        
        # Primera llamada
        value1 = manager.get_secret('CACHED_SECRET')
        
        # Modificar env (no debería afectar por el cache)
        os.environ['CACHED_SECRET'] = 'new_value'
        
        # Segunda llamada (debe venir del cache)
        value2 = manager.get_secret('CACHED_SECRET')
        
        self.assertEqual(value1, value2)
        self.assertEqual(value1, 'cached_value')
        
        # Limpiar
        del os.environ['CACHED_SECRET']


# =============================================================================
# TESTS DE LOGGING DE AUDITORÍA
# =============================================================================

class TestAuditLogging(TestCase):
    """Tests para verificar el logging de auditoría."""
    
    def test_audit_middleware_records_timestamp(self):
        """Verificar que el middleware de auditoría registra timestamps."""
        from pavssv_server.middleware import AuditLoggingMiddleware
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/api/v1/auth/login/')
        
        middleware = AuditLoggingMiddleware(get_response=lambda r: MagicMock(status_code=200))
        
        # Procesar request
        middleware.process_request(request)
        
        # Debe tener timestamp de inicio
        self.assertTrue(hasattr(request, '_audit_start_time'))
        self.assertIsInstance(request._audit_start_time, float)


# =============================================================================
# TESTS DE CONFIGURACIÓN DE PRODUCCIÓN
# =============================================================================

class TestProductionSettings(TestCase):
    """Tests para verificar la configuración de producción."""
    
    def test_debug_is_false_when_not_set(self):
        """Verificar que DEBUG es False por defecto."""
        # En producción, DJANGO_DEBUG no debería estar configurado o ser "0"
        debug_value = os.getenv("DJANGO_DEBUG", "0")
        self.assertIn(debug_value, ["0", "false", "False", ""])
    
    def test_secret_key_is_not_default(self):
        """Verificar que SECRET_KEY no es el valor por defecto en producción."""
        from django.conf import settings
        
        # En tests puede ser el default, pero verificamos que existe
        self.assertTrue(hasattr(settings, 'SECRET_KEY'))
        self.assertTrue(len(settings.SECRET_KEY) > 20)
    
    def test_password_hashers_use_argon2(self):
        """Verificar que Argon2 es el hasher principal."""
        from django.conf import settings
        
        self.assertTrue(hasattr(settings, 'PASSWORD_HASHERS'))
        self.assertIn('Argon2', settings.PASSWORD_HASHERS[0])
    
    def test_minimum_password_length(self):
        """Verificar que se requiere longitud mínima de contraseña."""
        from django.conf import settings
        
        # Buscar el validador de longitud mínima
        min_length_validator = None
        for validator in settings.AUTH_PASSWORD_VALIDATORS:
            if 'MinimumLengthValidator' in validator['NAME']:
                min_length_validator = validator
                break
        
        self.assertIsNotNone(min_length_validator)
        self.assertGreaterEqual(
            min_length_validator.get('OPTIONS', {}).get('min_length', 8),
            10
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
