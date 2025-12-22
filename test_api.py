"""
Script de prueba para la API de análisis Personal Asignado vs Servicio Vivo.

Este script prueba el endpoint /api/v1/analyze enviando los archivos Excel
del proyecto y verificando la respuesta.

Uso:
    1. Primero iniciar la API: uvicorn api:app --reload
    2. Luego ejecutar este script: python test_api.py
"""

import requests
import sys
from pathlib import Path
from config import FILE_PATHS


def test_health_endpoint(base_url: str) -> bool:
    """Prueba el endpoint de health check."""
    print("\n🔍 Probando endpoint /api/v1/health...")
    try:
        response = requests.get(f"{base_url}/api/v1/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check exitoso:")
            print(f"   - Status: {data.get('status')}")
            print(f"   - Version: {data.get('version')}")
            print(f"   - Timestamp: {data.get('timestamp')}")
            return True
        else:
            print(f"❌ Health check falló: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar a la API. ¿Está ejecutándose?")
        return False


def test_config_endpoint(base_url: str) -> bool:
    """Prueba el endpoint de configuración."""
    print("\n🔍 Probando endpoint /api/v1/config...")
    try:
        response = requests.get(f"{base_url}/api/v1/config")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Configuración obtenida:")
            print(f"   - Hojas Excel: {list(data.get('sheet_names', {}).keys())}")
            print(f"   - Parámetros: {list(data.get('parameters', {}).keys())}")
            return True
        else:
            print(f"❌ Config falló: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar a la API")
        return False


def test_analyze_endpoint_json(base_url: str, pa_file: str, sv_file: str) -> bool:
    """Prueba el endpoint de análisis con respuesta JSON."""
    print("\n🔍 Probando endpoint /api/v1/analyze (JSON)...")
    
    # Verificar que los archivos existan
    if not Path(pa_file).exists():
        print(f"❌ Archivo no encontrado: {pa_file}")
        return False
    if not Path(sv_file).exists():
        print(f"❌ Archivo no encontrado: {sv_file}")
        return False
    
    print(f"   📁 Personal Asignado: {pa_file}")
    print(f"   📁 Servicio Vivo: {sv_file}")
    
    try:
        with open(pa_file, 'rb') as pa, open(sv_file, 'rb') as sv:
            files = {
                'personal_asignado': (Path(pa_file).name, pa, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                'servicio_vivo': (Path(sv_file).name, sv, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            response = requests.post(
                f"{base_url}/api/v1/analyze",
                files=files,
                params={"return_json": True}
            )
        
        if response.status_code == 200:
            data = response.json()
            resumen = data.get('resumen', {})
            print(f"✅ Análisis completado (JSON):")
            print(f"   - Total servicios: {resumen.get('total_servicios', 0):,}")
            print(f"   - Personal real: {resumen.get('personal_real_total', 0):,}")
            print(f"   - Personal estimado: {resumen.get('personal_estimado_total', 0):,.2f}")
            print(f"   - Diferencia: {resumen.get('diferencia_total', 0):,.2f}")
            print(f"   - Completitud: {resumen.get('completitud_porcentaje', 0):.1f}%")
            
            print("\n   📊 Distribución por estado:")
            for estado in data.get('distribucion_estados', [])[:5]:
                print(f"      - {estado.get('Estado')}: {estado.get('cantidad'):,}")
            return True
        else:
            print(f"❌ Análisis falló: {response.status_code}")
            print(f"   Detalle: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar a la API")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_analyze_endpoint_excel(base_url: str, pa_file: str, sv_file: str, output_dir: str = ".") -> bool:
    """Prueba el endpoint de análisis con respuesta Excel."""
    print("\n🔍 Probando endpoint /api/v1/analyze (Excel)...")
    
    # Verificar que los archivos existan
    if not Path(pa_file).exists():
        print(f"❌ Archivo no encontrado: {pa_file}")
        return False
    if not Path(sv_file).exists():
        print(f"❌ Archivo no encontrado: {sv_file}")
        return False
    
    print(f"   📁 Personal Asignado: {pa_file}")
    print(f"   📁 Servicio Vivo: {sv_file}")
    
    try:
        with open(pa_file, 'rb') as pa, open(sv_file, 'rb') as sv:
            files = {
                'personal_asignado': (Path(pa_file).name, pa, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                'servicio_vivo': (Path(sv_file).name, sv, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            response = requests.post(
                f"{base_url}/api/v1/analyze",
                files=files,
                params={"return_json": False}
            )
        
        if response.status_code == 200:
            # Obtener nombre del archivo del header
            content_disposition = response.headers.get('Content-Disposition', '')
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"')
            else:
                filename = "Analisis_API_Test.xlsx"
            
            # Guardar archivo
            output_path = Path(output_dir) / filename
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            print(f"✅ Análisis completado (Excel):")
            print(f"   - Archivo guardado: {output_path}")
            print(f"   - Tamaño: {file_size:,} bytes ({file_size/1024:.1f} KB)")
            return True
        else:
            print(f"❌ Análisis falló: {response.status_code}")
            print(f"   Detalle: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar a la API")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def main():
    """Ejecuta todas las pruebas."""
    print("=" * 60)
    print("🧪 PRUEBAS DE LA API DE ANÁLISIS PA vs SV")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Archivos de prueba desde config.py
    pa_file = FILE_PATHS.get("personal_asignado", "")
    sv_file = FILE_PATHS.get("servicio_vivo", "")
    
    # Verificar archivos
    print(f"\n📁 Archivos configurados:")
    print(f"   - Personal Asignado: {pa_file}")
    print(f"   - Servicio Vivo: {sv_file}")
    
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health_endpoint(base_url)))
    
    if not results[0][1]:
        print("\n" + "=" * 60)
        print("⚠️  La API no está disponible.")
        print("   Ejecuta primero: uvicorn api:app --reload --port 8000")
        print("=" * 60)
        return 1
    
    # Test 2: Config
    results.append(("Config", test_config_endpoint(base_url)))
    
    # Test 3: Analyze (JSON)
    results.append(("Analyze (JSON)", test_analyze_endpoint_json(base_url, pa_file, sv_file)))
    
    # Test 4: Analyze (Excel)
    results.append(("Analyze (Excel)", test_analyze_endpoint_excel(base_url, pa_file, sv_file)))
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS")
    print("=" * 60)
    
    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")
        if result:
            passed += 1
    
    print(f"\n   Total: {passed}/{len(results)} pruebas exitosas")
    print("=" * 60)
    
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
