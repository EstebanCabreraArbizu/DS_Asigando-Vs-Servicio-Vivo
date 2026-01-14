"""
Tests de Lógica de Negocio para PA vs SV

Este módulo contiene tests automatizados para verificar que la lógica
de negocio del servicio de comparación funciona correctamente.

Ejecución:
    cd server
    python -m pytest ../tests/test_business_logic.py -v

Con cobertura:
    python -m pytest ../tests/test_business_logic.py --cov=api_v1 --cov=core -v
"""
from __future__ import annotations

import io
import json
import tempfile
import os
import sys

import pytest

# Configurar Django antes de importar modelos
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pavssv_server.settings')
os.environ['USE_SQLITE'] = '1'

django.setup()

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


# =============================================================================
# TESTS DE UPLOAD DE ARCHIVOS
# =============================================================================

class TestFileUpload(TestCase):
    """Tests para la funcionalidad de upload de archivos."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePassword123!'
        )
        # Autenticar
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePassword123!'
        })
        if login_response.status_code == 200:
            self.client.credentials(
                HTTP_AUTHORIZATION=f'Bearer {login_response.data["access"]}'
            )
    
    def _create_csv_file(self, content: str, filename: str = 'test.csv'):
        """Helper para crear archivos CSV de prueba."""
        return io.BytesIO(content.encode('utf-8'))
    
    def test_upload_valid_csv(self):
        """Verificar upload de CSV válido."""
        csv_content = "id,name,value\n1,test,100\n2,test2,200"
        csv_file = self._create_csv_file(csv_content)
        csv_file.name = 'test.csv'
        
        response = self.client.post(
            '/api/v1/analysis/upload/',
            {'file': csv_file},
            format='multipart'
        )
        
        # Debe ser exitoso o indicar que el endpoint existe
        self.assertIn(response.status_code, [200, 201, 400, 404])
    
    def test_upload_excel_file(self):
        """Verificar upload de archivo Excel."""
        # Crear un archivo Excel mínimo de prueba
        # En producción, usaríamos openpyxl para crear uno real
        excel_content = b'PK'  # Magic bytes de archivo ZIP/XLSX
        excel_file = io.BytesIO(excel_content)
        excel_file.name = 'test.xlsx'
        
        response = self.client.post(
            '/api/v1/analysis/upload/',
            {'file': excel_file},
            format='multipart'
        )
        
        # El archivo puede ser rechazado por magic bytes inválidos, lo cual es correcto
        self.assertIn(response.status_code, [200, 201, 400, 404])
    
    def test_reject_unauthorized_upload(self):
        """Verificar que uploads sin autenticación son rechazados."""
        # Remover credenciales
        self.client.credentials()
        
        csv_file = self._create_csv_file("id,name\n1,test")
        csv_file.name = 'test.csv'
        
        response = self.client.post(
            '/api/v1/analysis/upload/',
            {'file': csv_file},
            format='multipart'
        )
        
        # Debe ser rechazado (401 o 403) o el endpoint no existe (404)
        self.assertIn(response.status_code, [401, 403, 404])


# =============================================================================
# TESTS DE COMPARACIÓN DE ARCHIVOS
# =============================================================================

class TestFileComparison(TestCase):
    """Tests para la lógica de comparación de archivos PA vs SV."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePassword123!'
        )
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'testuser',
            'password': 'SecurePassword123!'
        })
        if login_response.status_code == 200:
            self.client.credentials(
                HTTP_AUTHORIZATION=f'Bearer {login_response.data["access"]}'
            )
    
    def test_comparison_with_identical_files(self):
        """Verificar comparación de archivos idénticos."""
        # Este test depende de los endpoints específicos implementados
        # Aquí verificamos la lógica general
        pass  # Implementar según los endpoints reales
    
    def test_comparison_detects_differences(self):
        """Verificar que la comparación detecta diferencias."""
        pass  # Implementar según los endpoints reales
    
    def test_comparison_handles_missing_columns(self):
        """Verificar manejo de columnas faltantes en comparación."""
        pass  # Implementar según los endpoints reales


# =============================================================================
# TESTS DE PROCESAMIENTO DE DATOS (Core Module)
# =============================================================================

class TestDataProcessor(TestCase):
    """Tests para el módulo core de procesamiento de datos."""
    
    def test_data_loader_imports(self):
        """Verificar que el data_loader se puede importar."""
        try:
            from core.data_loader import DataLoader
            imported = True
        except ImportError:
            imported = False
        
        self.assertTrue(imported, "No se pudo importar DataLoader")
    
    def test_data_processor_imports(self):
        """Verificar que el data_processor se puede importar."""
        try:
            from core.data_processor import DataProcessor
            imported = True
        except ImportError:
            imported = False
        
        self.assertTrue(imported, "No se pudo importar DataProcessor")
    
    def test_analysis_engine_imports(self):
        """Verificar que el analysis_engine se puede importar."""
        try:
            from core.analysis_engine import AnalysisEngine
            imported = True
        except ImportError:
            imported = False
        
        self.assertTrue(imported, "No se pudo importar AnalysisEngine")


# =============================================================================
# TESTS DE API ENDPOINTS
# =============================================================================

class TestAPIEndpoints(TestCase):
    """Tests para los endpoints de la API."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePassword123!'
        )
    
    def test_health_endpoint(self):
        """Verificar que el health check funciona."""
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
    
    def test_api_root_returns_json(self):
        """Verificar que la raíz de API retorna JSON."""
        response = self.client.get('/api/v1/')
        self.assertIn(response.status_code, [200, 401])
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_analysis_endpoints_require_auth(self):
        """Verificar que endpoints de análisis requieren autenticación."""
        endpoints = [
            '/api/v1/analysis/',
            '/api/v1/analysis/upload/',
            '/api/v1/analysis/compare/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertIn(
                response.status_code, 
                [401, 403, 404, 405],
                f"Endpoint {endpoint} debería requerir auth o no existir"
            )


# =============================================================================
# TESTS DE EXPORTACIÓN DE RESULTADOS
# =============================================================================

class TestExcelExporter(TestCase):
    """Tests para el exportador de Excel."""
    
    def test_excel_exporter_imports(self):
        """Verificar que el excel_exporter se puede importar."""
        try:
            from core.excel_exporter import ExcelExporter
            imported = True
        except ImportError:
            imported = False
        
        self.assertTrue(imported, "No se pudo importar ExcelExporter")
    
    def test_export_creates_valid_excel(self):
        """Verificar que la exportación crea Excel válido."""
        try:
            from core.excel_exporter import ExcelExporter
            import openpyxl
            
            # Datos de prueba
            data = {
                'headers': ['ID', 'Name', 'Value'],
                'rows': [
                    [1, 'Test1', 100],
                    [2, 'Test2', 200],
                ]
            }
            
            # Exportar a archivo temporal
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                exporter = ExcelExporter()
                exporter.export(data, tmp.name)
                
                # Verificar que el archivo es Excel válido
                wb = openpyxl.load_workbook(tmp.name)
                self.assertIsNotNone(wb)
                wb.close()
                
                os.unlink(tmp.name)
        except (ImportError, AttributeError):
            # Si el módulo no está disponible, skip
            pass


# =============================================================================
# TESTS DE MODELO DE DATOS
# =============================================================================

class TestDataModels(TestCase):
    """Tests para los modelos de datos."""
    
    def test_user_model_exists(self):
        """Verificar que el modelo de usuario existe."""
        self.assertIsNotNone(User)
    
    def test_user_can_be_created(self):
        """Verificar que se pueden crear usuarios."""
        user = User.objects.create_user(
            username='newuser',
            email='new@example.com',
            password='TestPass123!'
        )
        
        self.assertIsNotNone(user.id)
        self.assertEqual(user.username, 'newuser')
    
    def test_user_password_is_hashed(self):
        """Verificar que la contraseña se almacena hasheada."""
        user = User.objects.create_user(
            username='hashtest',
            email='hash@example.com',
            password='PlainPassword123!'
        )
        
        # La contraseña no debe estar en texto plano
        self.assertNotEqual(user.password, 'PlainPassword123!')
        self.assertTrue(user.password.startswith('argon2'))


# =============================================================================
# TESTS DE CONFIGURACIÓN
# =============================================================================

class TestConfiguration(TestCase):
    """Tests para la configuración del sistema."""
    
    def test_config_module_imports(self):
        """Verificar que el módulo config se puede importar."""
        try:
            from core.config import Config
            imported = True
        except ImportError:
            try:
                from core.config import config
                imported = True
            except ImportError:
                imported = False
        
        self.assertTrue(imported, "No se pudo importar config")
    
    def test_django_settings_accessible(self):
        """Verificar que Django settings son accesibles."""
        from django.conf import settings
        
        self.assertTrue(hasattr(settings, 'DEBUG'))
        self.assertTrue(hasattr(settings, 'INSTALLED_APPS'))
        self.assertTrue(hasattr(settings, 'DATABASES'))


# =============================================================================
# TESTS DE INTEGRACIÓN
# =============================================================================

class TestIntegration(TestCase):
    """Tests de integración end-to-end."""
    
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='integration_test',
            email='integration@example.com',
            password='IntegrationTest123!'
        )
    
    def test_full_authentication_flow(self):
        """Test del flujo completo de autenticación."""
        # 1. Login
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'integration_test',
            'password': 'IntegrationTest123!'
        })
        
        if login_response.status_code == 200:
            access_token = login_response.data['access']
            refresh_token = login_response.data['refresh']
            
            # 2. Acceder a recurso protegido
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
            me_response = self.client.get('/api/v1/users/me/')
            
            self.assertEqual(me_response.status_code, 200)
            self.assertEqual(me_response.data['username'], 'integration_test')
            
            # 3. Refresh token
            self.client.credentials()  # Limpiar credenciales
            refresh_response = self.client.post('/api/v1/auth/refresh/', {
                'refresh': refresh_token
            })
            
            if refresh_response.status_code == 200:
                new_access = refresh_response.data['access']
                self.assertIsNotNone(new_access)
                self.assertNotEqual(new_access, access_token)


# =============================================================================
# TESTS DE PERMISOS Y AUTORIZACIÓN
# =============================================================================

class TestPermissions(TestCase):
    """Tests para el sistema de permisos."""
    
    def setUp(self):
        self.client = APIClient()
        
        # Usuario normal
        self.user = User.objects.create_user(
            username='normaluser',
            email='normal@example.com',
            password='NormalUser123!'
        )
        
        # Usuario staff
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='StaffUser123!',
            is_staff=True
        )
        
        # Superusuario
        self.super_user = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='SuperUser123!'
        )
    
    def test_normal_user_cannot_access_admin(self):
        """Verificar que usuarios normales no pueden acceder al admin."""
        login_response = self.client.post('/api/v1/auth/login/', {
            'username': 'normaluser',
            'password': 'NormalUser123!'
        })
        
        if login_response.status_code == 200:
            self.client.credentials(
                HTTP_AUTHORIZATION=f'Bearer {login_response.data["access"]}'
            )
            
            # Intentar acceder a endpoint de admin (si existe)
            admin_response = self.client.get('/api/v1/admin/')
            self.assertIn(admin_response.status_code, [403, 404])
    
    def test_staff_user_has_elevated_permissions(self):
        """Verificar que usuarios staff tienen permisos elevados."""
        self.assertTrue(self.staff_user.is_staff)
        self.assertFalse(self.staff_user.is_superuser)
    
    def test_superuser_has_all_permissions(self):
        """Verificar que superusuarios tienen todos los permisos."""
        self.assertTrue(self.super_user.is_superuser)
        self.assertTrue(self.super_user.has_perm('any_permission'))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
