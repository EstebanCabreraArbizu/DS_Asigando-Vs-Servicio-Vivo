# -*- coding: utf-8 -*-
"""
Test script to verify deterministic ordering in API responses.
Executes the same analysis twice and compares Excel outputs.
"""

import requests
import time
from pathlib import Path
import polars as pl

BASE_URL = "http://localhost:8000"

def analyze_files():
    """Execute analysis endpoint and return response."""
    files = {
        'personal_asignado': open('11. Personal Asignado - Noviembre 2025 - (191125).xlsx', 'rb'),
        'servicio_vivo': open('SV Octubre 2025.xlsx', 'rb')
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/analyze", files=files)
    
    # Close files
    for f in files.values():
        f.close()
    
    return response

def save_excel_from_response(response, filename):
    """Save Excel content from response to file."""
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"[OK] Excel guardado: {filename}")
        return True
    else:
        print(f"[ERROR] Error en analisis: {response.status_code}")
        return False

def compare_excel_files(file1, file2):
    """Compare two Excel files and check for deterministic ordering."""
    print("\n[INFO] Comparando archivos Excel...")
    
    # Read first sheet from both files
    df1 = pl.read_excel(file1, sheet_name="Resultado_Final")
    df2 = pl.read_excel(file2, sheet_name="Resultado_Final")
    
    # Check if schemas match
    if df1.columns != df2.columns:
        print("[ERROR] Las columnas no coinciden")
        return False
    
    # Check if row count matches
    if len(df1) != len(df2):
        print(f"[ERROR] Diferente numero de filas: {len(df1)} vs {len(df2)}")
        return False
    
    # Check if Clave_Mezclado values are identical
    if "Clave_Mezclado" in df1.columns:
        claves1 = df1.select("Clave_Mezclado").to_series().to_list()
        claves2 = df2.select("Clave_Mezclado").to_series().to_list()
        
        if claves1 == claves2:
            print("[OK] Las claves Clave_Mezclado son IDENTICAS en orden")
        else:
            print("[WARNING] Las claves Clave_Mezclado tienen orden DIFERENTE")
            print(f"  Claves comunes: {len(set(claves1) & set(claves2))}")
            print(f"  Solo en 1: {len(set(claves1) - set(claves2))}")
            print(f"  Solo en 2: {len(set(claves2) - set(claves1))}")
    
    # Check if data is identical (including order)
    if df1.equals(df2):
        print("[OK] Los archivos son IDENTICOS (orden y valores exactos)")
        return True
    
    # If not identical, check if data is the same but different order
    df1_sorted = df1.sort(df1.columns)
    df2_sorted = df2.sort(df2.columns)
    
    if df1_sorted.equals(df2_sorted):
        print("[WARNING] Los datos son iguales pero el ORDEN es diferente")
        print("          Esto indica un problema de orden no deterministico")
        
        # Show summary stats instead of raw data
        print("\n[INFO] Numero de filas:", len(df1))
        print("[INFO] Numero de columnas:", len(df1.columns))
        print("[INFO] Primeras columnas para clave:", df1.columns[:5])
        
        # Compare first rows by key columns
        key_cols = ["Clave_Mezclado"] if "Clave_Mezclado" in df1.columns else df1.columns[:3]
        print(f"\n[INFO] Primeros 3 valores de {key_cols[0]}:")
        print("  Archivo 1:", df1.select(key_cols[0]).head(3).to_series().to_list())
        print("  Archivo 2:", df2.select(key_cols[0]).head(3).to_series().to_list())
        
        return False
    else:
        print("[ERROR] Los datos son DIFERENTES")
        
        # Show differences
        print("\n[INFO] Estadisticas Archivo 1:")
        print(df1.describe())
        print("\n[INFO] Estadisticas Archivo 2:")
        print(df2.describe())
        
        return False

def main():
    """Main test function."""
    print("=" * 60)
    print("TEST DE ORDEN DETERMINISTICO")
    print("=" * 60)
    
    # Check if API is running
    try:
        health = requests.get(f"{BASE_URL}/api/v1/health")
        if health.status_code != 200:
            print("[ERROR] API no esta funcionando")
            return
        print("[OK] API esta activa\n")
    except Exception as e:
        print(f"[ERROR] No se puede conectar a la API: {e}")
        print("        Asegurate de ejecutar: python main.py")
        return
    
    # Execute first analysis
    print("[INFO] Ejecutando primera analisis...")
    response1 = analyze_files()
    if not save_excel_from_response(response1, "test_output_1.xlsx"):
        return
    
    # Wait a bit
    time.sleep(2)
    
    # Execute second analysis
    print("\n[INFO] Ejecutando segunda analisis...")
    response2 = analyze_files()
    if not save_excel_from_response(response2, "test_output_2.xlsx"):
        return
    
    # Compare files
    success = compare_excel_files("test_output_1.xlsx", "test_output_2.xlsx")
    
    print("\n" + "=" * 60)
    if success:
        print("[OK] RESULTADO: El orden es DETERMINISTICO")
        print("     Las ejecuciones multiples producen resultados identicos")
    else:
        print("[ERROR] RESULTADO: El orden NO es deterministico")
        print("        Las ejecuciones multiples producen resultados diferentes")
    print("=" * 60)
    
    # Cleanup
    Path("test_output_1.xlsx").unlink(missing_ok=True)
    Path("test_output_2.xlsx").unlink(missing_ok=True)

if __name__ == "__main__":
    main()
