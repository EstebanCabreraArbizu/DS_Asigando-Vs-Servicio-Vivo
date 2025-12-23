"""
Test del flujo completo EPIC 1 + EPIC 2:
1. POST /api/v1/jobs/ con archivos PA y SV
2. GET /api/v1/jobs/{job_id}/status/
3. GET /api/v1/jobs/{job_id}/excel/ (cuando esté listo)
"""
import requests
import time
import os

BASE_URL = "http://127.0.0.1:8001/api/v1"

# Archivos de prueba (usar los más recientes)
PA_FILE = r"C:\Project_PAvsSV\data\11. Personal Asignado - Noviembre 2025 - (191125).xlsx"
SV_FILE = r"C:\Project_PAvsSV\data\SV Octubre 2025.xlsx"

def test_health():
    """Verificar que el servidor esté funcionando"""
    print("=" * 50)
    print("1. TEST: Health Check")
    print("=" * 50)
    resp = requests.get(f"{BASE_URL}/health/")
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    print("   [OK] Health check passed!")
    return True

def test_create_job():
    """Crear un job con archivos PA y SV"""
    print("\n" + "=" * 50)
    print("2. TEST: Crear Job (Upload PA + SV)")
    print("=" * 50)
    
    # Verificar que los archivos existen
    if not os.path.exists(PA_FILE):
        print(f"   [ERROR] Archivo PA no encontrado: {PA_FILE}")
        return None
    if not os.path.exists(SV_FILE):
        print(f"   [ERROR] Archivo SV no encontrado: {SV_FILE}")
        return None
    
    print(f"   PA: {os.path.basename(PA_FILE)}")
    print(f"   SV: {os.path.basename(SV_FILE)}")
    
    with open(PA_FILE, "rb") as pa, open(SV_FILE, "rb") as sv:
        files = {
            "input_personal_asignado": (os.path.basename(PA_FILE), pa, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            "input_servicio_vivo": (os.path.basename(SV_FILE), sv, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        }
        data = {
            "period_month": "2025-11"
        }
        
        resp = requests.post(f"{BASE_URL}/jobs/", files=files, data=data)
    
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.text}")
    
    if resp.status_code == 202:
        job_id = resp.json()["job_id"]
        print(f"   [OK] Job creado: {job_id}")
        return job_id
    else:
        print(f"   [ERROR] No se pudo crear el job")
        return None

def test_job_status(job_id: str):
    """Verificar el estado del job"""
    print("\n" + "=" * 50)
    print("3. TEST: Verificar Estado del Job")
    print("=" * 50)
    
    resp = requests.get(f"{BASE_URL}/jobs/{job_id}/status/")
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json()}")
    
    if resp.status_code == 200:
        status = resp.json()
        print(f"   [OK] Job status: {status.get('status', 'unknown')}")
        return status
    else:
        print(f"   [ERROR] No se pudo obtener el estado")
        return None

def test_download_excel(job_id: str):
    """Intentar descargar el Excel (si está listo)"""
    print("\n" + "=" * 50)
    print("4. TEST: Descargar Excel")
    print("=" * 50)
    
    resp = requests.get(f"{BASE_URL}/jobs/{job_id}/excel/")
    print(f"   Status: {resp.status_code}")
    
    if resp.status_code == 200:
        # Guardar el archivo
        output_path = f"C:\\Project_PAvsSV\\data\\test_output_{job_id[:8]}.xlsx"
        with open(output_path, "wb") as f:
            f.write(resp.content)
        print(f"   [OK] Excel descargado: {output_path}")
        print(f"   Tamano: {len(resp.content)} bytes")
        return output_path
    elif resp.status_code == 404:
        print(f"   [INFO] Excel aun no disponible (job en proceso)")
        print(f"   Response: {resp.json()}")
        return None
    else:
        print(f"   [ERROR] Error al descargar: {resp.text}")
        return None

def main():
    print("\n" + "#" * 60)
    print("# TEST FLUJO COMPLETO: EPIC 1 + EPIC 2")
    print("#" * 60)
    
    # 1. Health check
    if not test_health():
        return
    
    # 2. Crear job
    job_id = test_create_job()
    if not job_id:
        return
    
    # 3. Verificar estado
    status = test_job_status(job_id)
    
    # 4. Intentar descargar Excel
    # Nota: Sin Celery corriendo, el job quedará en "queued"
    # En producción, esperaríamos a que cambie a "succeeded"
    test_download_excel(job_id)
    
    print("\n" + "#" * 60)
    print("# RESUMEN")
    print("#" * 60)
    print(f"   Job ID: {job_id}")
    print(f"   Estado: {status.get('status') if status else 'unknown'}")
    print("\n   NOTA: Sin Celery worker, el job queda en 'queued'.")
    print("   Para ejecutar el análisis, inicia Celery:")
    print("   celery -A pavssv_server worker -l info")
    print("#" * 60)

if __name__ == "__main__":
    main()
