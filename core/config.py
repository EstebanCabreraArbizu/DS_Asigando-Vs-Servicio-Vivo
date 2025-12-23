"""
Configuration module for Personal Asignado vs Servicio Vivo analysis.
Contains externalized paths, schemas, and parameters.
"""

from typing import Dict, Any

import polars as pl

# File paths for datasets and outputs
FILE_PATHS: Dict[str, str] = {
    "personal_asignado": "11. Personal Asignado - Noviembre 2025 - (191125).xlsx",
    "servicio_vivo": "SV Octubre 2025.xlsx",
    "output_template": "Mezclado_PA_vs_SV_{timestamp}.xlsx"
}

# Sheet names for Excel files
SHEET_NAMES: Dict[str, str] = {
    "personal_asignado": "ASIGNADO",
    "servicio_vivo": "DATA"
}

# Header row indices (0-based, indica la fila que contiene los encabezados)
HEADER_ROWS: Dict[str, int] = {
    "personal_asignado": 1,  # Fila 1 tiene encabezados (ITEM, TIPO DE COMPAÑÍA, etc.)
    "servicio_vivo": 2       # Fila 2 tiene encabezados (ITEM, TIPO DE PLANILLA, etc.)
}

# Excel schemas (column types as strings for polars compatibility)
EXCEL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "personal_asignado": {
        "ESTADO": pl.String,
        "COD CLIENTE": pl.String,
        "COD UNID": pl.String,
        "COD SERVICIO": pl.String,
        "COD GRUPO": pl.String,
        "TIPO DE COMPAÑÍA": pl.String,
        "CLIENTE": pl.String,
        "UNIDAD": pl.String,
        "TIPO DE SERVCIO": pl.String,
        "GRUPO": pl.String,
        "LIDER ZONAL / COORDINADOR": pl.String,
        "JEFE DE OPERACIONES": pl.String,
        "GERENTE REGIONAL": pl.String,
        "SECTOR": pl.String,
        "DEPARTAMENTO": pl.String
    },
    "servicio_vivo": {
        "Estado": pl.String,
        "Cliente": pl.String,
        "Unidad": pl.String,
        "Servicio": pl.String,
        "Nombre Servicio": pl.String,
        "Grupo": pl.String,
        "HRS": pl.Float64,
        "Q° PER. FACTOR - REQUERIDO": pl.Float64,
        "Compañía": pl.String,
        "Nombre Cliente": pl.String,
        "Nombre Unidad": pl.String,
        "ZONA": pl.String,
        "MACROZONA": pl.String,
        "Nombre Grupo": pl.String,
        "LÍDERZONAL": pl.String,
        #"JEFATURA": pl.String,
        "GERENTE": pl.String,
        "JEFE": pl.String,
        #"Descripcion Departamento": pl.String
    }
}

# Processing parameters
PARAMETERS: Dict[str, Any] = {
    "estado_filter": "Aprobado",  # Filter for Servicio Vivo (can be None to disable)
    "estado_pa_filter": [
        "ACTIVO - PARA BAJA 2",
        "ACTIVO - PARA BAJA",
        "ACTIVO - ALTA NUEVA - PARA BAJA",
        "ACTIVO - ALTA NUEVA - PARA BAJA 2",
        "ALTA NUEVA - PARA BAJA",
        "ALTA NUEVA - PARA BAJA 2"
    ],  # Filter for Personal Asignado (can be None to disable)
    "discrepancy_threshold": 50,  # Threshold for major discrepancies (|difference| > threshold)
    "fill_null_value": 0,  # Value to fill nulls in numeric columns
    "round_decimals": 2  # Decimal places for rounding calculations
}

# Output sheet names for Excel export
OUTPUT_SHEETS: Dict[str, str] = {
    "resultado_completo": "Resultado_Completo",
    "analisis_antapaccay": "Analisis_ANTAPACCAY",
    "discrepancias_mayores": "Discrepancias_Mayores",
    "resumen_por_cliente": "Resumen_por_Cliente",
    "top_diferencias": "Top_Diferencias",
    "resultado_final": "Resultado_Final",
    "estadisticas": "Estadisticas",
    "investigacion": "Investigacion"
}