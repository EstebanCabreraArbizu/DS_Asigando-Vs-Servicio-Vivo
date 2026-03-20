"""
demo_api.py — Script de demostración local de integración ServicioGeneral API + Polars.

Ejecutar desde la carpeta core/:
    cd core
    python demo_api.py

O desde la raíz:
    python core/demo_api.py

Requiere acceso a la red interna donde está la API (192.168.1.44).
Si no hay acceso, usar los tests con mocks:
    python -m pytest tests/test_api_integration.py -v

Variables de entorno opcionales:
    SERVICIO_GENERAL_URL    (default: http://192.168.1.44/ServicioGeneral)
    SERVICIO_GENERAL_USER   (default: USUWEB)
    SERVICIO_GENERAL_CLAVE  (default: 160821)
"""

import sys
import os
import logging

# Asegurar que core/ está en el path (para ejecutar desde raíz del proyecto)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("demo_api")


def run_demo():
    """Ejecuta la demo completa de integración API → Polars DataFrame."""
    import polars as pl
    from core.api_client import ServicioGeneralClient
    from core.api_transformer import (
        programacion_to_sv_dataframe,
        tareo_to_dataframe,
        unidades_to_dataframe,
        zonas_to_dataframe,
    )
    from core.data_loader import DataLoader
    from core.config import API_CONFIG

    # --------------------------------------------------------------------------
    # 1. Crear cliente y autenticar
    # --------------------------------------------------------------------------
    print("\n" + "="*60)
    print("DEMO: Integración ServicioGeneral API + Polars")
    print("="*60)

    print(f"\n[1] Conectando a: {API_CONFIG['base_url']}")
    client = ServicioGeneralClient.from_config(API_CONFIG)

    try:
        client._login()
        print(f"    ✅ Autenticado. Token expira: {client._token_expires_at}")
    except Exception as e:
        print(f"    ❌ Error de autenticación: {e}")
        print("      → Verifica que estás en la red interna y que la API está activa.")
        return

    # --------------------------------------------------------------------------
    # 2. Catálogo de Zonas → DataFrame
    # --------------------------------------------------------------------------
    print("\n[2] Cargando catálogo de Zonas...")
    try:
        zonas_raw = client.get_zonas()
        df_zonas = zonas_to_dataframe(zonas_raw)
        print(f"    ✅ {len(df_zonas)} zonas obtenidas")
        print(df_zonas.head(3))
    except Exception as e:
        print(f"    ⚠️  Error en Zonas: {e}")

    # --------------------------------------------------------------------------
    # 3. Unidades por Cliente → DataFrame
    # --------------------------------------------------------------------------
    print("\n[3] Cargando Unidades (cliente=7006, grupo=0099)...")
    try:
        unidades_raw = client.get_unidades(cliente="7006", grupo_empresarial="0099")
        df_unidades = unidades_to_dataframe(unidades_raw)
        print(f"    ✅ {len(df_unidades)} unidades obtenidas")
        print(df_unidades.select(["unidad", "nombre_unidad", "zona", "estado"]).head(3))
    except Exception as e:
        print(f"    ⚠️  Error en Unidades: {e}")
        unidades_raw = []

    # --------------------------------------------------------------------------
    # 4. Programación → df_sv (reemplazo del Excel)
    # --------------------------------------------------------------------------
    print("\n[4] Cargando ProgramacionxCliente (periodo=17, servicio=1)...")
    try:
        programacion_raw = client.get_programacion(
            secuencia_periodo="17", servicio_tareo="1"
        )
        df_sv_api = programacion_to_sv_dataframe(programacion_raw, unidades_raw)
        print(f"    ✅ df_sv desde API: {len(df_sv_api)} filas, {len(df_sv_api.columns)} columnas")
        print("\n    Columnas del DataFrame:")
        for col, dtype in df_sv_api.schema.items():
            print(f"      {col}: {dtype}")
        print("\n    Primeras 3 filas:")
        print(df_sv_api.select([
            "Estado", "Unidad", "Servicio", "Nombre Servicio",
            "Q° PER. FACTOR - REQUERIDO", "ZONA", "GERENTE", "Tipo_Empleado"
        ]).head(3))
    except Exception as e:
        print(f"    ⚠️  Error en Programación: {e}")

    # --------------------------------------------------------------------------
    # 5. Tareo → DataFrame (diagnóstico)
    # --------------------------------------------------------------------------
    print("\n[5] Cargando TareoxCliente (periodo=17, servicio=1)...")
    try:
        tareo_raw = client.get_tareo(
            secuencia_periodo="17", servicio_tareo="1"
        )
        df_tareo = tareo_to_dataframe(tareo_raw)
        print(f"    ✅ df_tareo: {len(df_tareo)} filas")
        print(df_tareo.select(["empleado", "nombreEmpleado", "dias_reales", "tipoEmpleado"]).head(3))
    except Exception as e:
        print(f"    ⚠️  Error en Tareo: {e}")

    # --------------------------------------------------------------------------
    # 6. Usar DataLoader con el nuevo método (drop-in del Excel)
    # --------------------------------------------------------------------------
    print("\n[6] Probando DataLoader.load_servicio_vivo_from_api()...")
    try:
        loader = DataLoader()
        df_sv_loader = loader.load_servicio_vivo_from_api(
            client=client,
            secuencia_periodo="17",
            servicio_tareo="1",
            cliente="7006",
            grupo_empresarial="0099",
        )
        print(f"    ✅ DataLoader via API: {len(df_sv_loader)} filas")

        # Verificar que el esquema es compatible con el Excel
        from core.config import EXCEL_SCHEMAS
        expected_cols = set(EXCEL_SCHEMAS["servicio_vivo"].keys()) | {"Tipo_Empleado"}
        actual_cols = set(df_sv_loader.columns)
        sv_cols = set(EXCEL_SCHEMAS["servicio_vivo"].keys())
        missing = sv_cols - actual_cols
        if missing:
            print(f"    ⚠️  Columnas faltantes vs Excel SV: {missing}")
        else:
            print("    ✅ Todas las columnas del Excel SV están presentes")
    except Exception as e:
        print(f"    ⚠️  Error en DataLoader.load_servicio_vivo_from_api: {e}")

    # --------------------------------------------------------------------------
    # 7. Información de una Hoja de Costo
    # --------------------------------------------------------------------------
    print("\n[7] Consultando InformacionHoja (HC000013)...")
    try:
        hoja = client.get_informacion_hoja("01000000", "HC000013")
        df_hoja = pl.DataFrame(hoja)
        print(f"    ✅ Hoja de costo: {len(df_hoja)} registro(s)")
        print(df_hoja.select(["hojaCosto", "estado", "empresa", "tipo"]))
    except Exception as e:
        print(f"    ⚠️  Error en InformacionHoja: {e}")

    print("\n" + "="*60)
    print("DEMO completa.")
    print("="*60 + "\n")


if __name__ == "__main__":
    run_demo()
