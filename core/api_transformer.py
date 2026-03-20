"""
api_transformer.py — Transforma respuestas de ServicioGeneral API en pl.DataFrame.

Convierte las listas de dicts retornadas por ServicioGeneralClient en DataFrames
de Polars con el mismo esquema (columnas y tipos) que produce DataLoader al leer
los archivos Excel de Servicio Vivo y Personal Asignado.

Funciones principales:
    programacion_to_sv_dataframe()  — reemplazar df_sv (Excel SV → API)
    tareo_to_dataframe()            — DataFrame de tareo real (diagnóstico)
    unidades_to_dataframe()         — catálogo de unidades como DataFrame
    zonas_to_dataframe()            — catálogo de zonas como DataFrame

Notas de mapeo (API → DataFrame):
    - 'unidad' (int)  → 'Unidad' (str, cero padding a 5 dígitos)
    - 'servicio' (str) → 'Servicio' (str)
    - sum dias 'D' en dia1..dia31 → 'Q° PER. FACTOR - REQUERIDO' (float)
    - 'tipoEmpleado' → 'Tipo_Empleado' (str, columna adicional diagnóstica)
    - UnidadesxCliente JOIN por 'unidad' enriquece con ZONA, GERENTE, JEFE, etc.
"""

import logging
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Nombres de los 31 campos de días en la respuesta de Programacion/Tareo
DIA_COLS = [f"dia{i}" for i in range(1, 32)]

# Valor que indica día trabajado en la API
DIA_TRABAJADO = "D"

# Esquema esperado de df_sv (debe coincidir con EXCEL_SCHEMAS["servicio_vivo"] en config.py)
SV_SCHEMA: dict[str, pl.DataType] = {
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
    "GERENTE": pl.String,
    "JEFE": pl.String,
    # Columna diagnóstica extra (no estaba en Excel, útil para análisis)
    "Tipo_Empleado": pl.String,
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _count_dias_trabajados(row: dict[str, Any]) -> float:
    """
    Cuenta cuántos días tiene valor 'D' (trabajado) en los campos dia1..dia31.

    Este valor es el equivalente al campo 'Q° PER. FACTOR - REQUERIDO' del Excel SV,
    que representa la cantidad de personal requerido/programado.

    Nota: La equivalencia exacta debe confirmarse con el equipo de negocio.
    La presente implementación asume 1 persona por día 'D'.
    """
    return float(sum(1 for col in DIA_COLS if row.get(col, " ").strip() == DIA_TRABAJADO))


def _build_unidades_lookup(
    unidades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Construye un índice unidad_id → dict con todos los campos de UnidadesxCliente.

    Permite hacer un JOIN eficiente en Python entre programacion y unidades.
    La clave es str(unidad) para alinear tipos con el campo 'unidad' de programacion.
    """
    return {str(u["unidad"]): u for u in unidades}


def _estado_from_unidad(unidad_row: dict[str, Any] | None) -> str:
    """
    Mapea el campo 'estado' de la unidad al valor 'Aprobado'/'Inactivo'
    que usa el filtro estado_filter de AnalysisEngine.

    La API devuelve 'A' (activo) o 'I' (inactivo) — inferido del ejemplo
    donde estado="I".
    """
    if unidad_row is None:
        return "Desconocido"
    raw = str(unidad_row.get("estado", "")).strip().upper()
    if raw == "A":
        return "Aprobado"
    if raw == "I":
        return "Inactivo"
    return raw or "Desconocido"


# ---------------------------------------------------------------------------
# Función principal: Programacion → df_sv
# ---------------------------------------------------------------------------

def programacion_to_sv_dataframe(
    programacion: list[dict[str, Any]],
    unidades: list[dict[str, Any]],
) -> pl.DataFrame:
    """
    Convierte la respuesta de ProgramacionxCliente + UnidadesxCliente en un
    pl.DataFrame compatible con el esquema de load_servicio_vivo() (Excel SV).

    Cada registro de programacion corresponde a un empleado en un puesto,
    agrupado por unidad + servicio. La función agrega los días trabajados ('D')
    y enriquece con datos de catálogo de Unidades.

    Args:
        programacion: Lista de dicts de ProgramacionxCliente (ya normalizada).
        unidades: Lista de dicts de UnidadesxCliente (ya normalizada).

    Returns:
        pl.DataFrame con columnas según SV_SCHEMA, compatible con analysis_engine.py.

    Raises:
        ValueError: Si 'programacion' está vacía o le faltan campos requeridos.
    """
    if not programacion:
        logger.warning("programacion_to_sv_dataframe: lista de programación vacía. Retornando DataFrame vacío.")
        return pl.DataFrame(schema=SV_SCHEMA)

    unidades_lookup = _build_unidades_lookup(unidades)

    rows: list[dict[str, Any]] = []

    for rec in programacion:
        unidad_key = str(rec.get("unidad", ""))
        unidad_info = unidades_lookup.get(unidad_key)

        # Días trabajados → equivalente a Q° PER. FACTOR - REQUERIDO
        q_requerido = _count_dias_trabajados(rec)

        # Determinar estado desde la unidad (filtro Aprobado/Inactivo)
        estado = _estado_from_unidad(unidad_info)

        row: dict[str, Any] = {
            # --- Identificación ---
            "Estado": estado,
            "Cliente": str(rec.get("unidad", "")),          # API no expone código de cliente directo
            "Unidad": str(rec.get("unidad", "")),
            "Servicio": str(rec.get("servicio", "")),
            "Nombre Servicio": str(rec.get("descripcion", "")),

            # --- Clasificación (API no expone Grupo directamente en Programacion) ---
            "Grupo": "",                                      # No disponible en este endpoint
            "Nombre Grupo": "",                               # No disponible en este endpoint

            # --- Métricas ---
            "HRS": None,                                      # No disponible en Programacion
            "Q° PER. FACTOR - REQUERIDO": q_requerido,

            # --- Entidad corporativa ---
            "Compañía": "",                                   # No disponible en Programacion

            # --- Catálogo de Unidad (enriquecimiento) ---
            "Nombre Cliente": (
                unidad_info.get("descripcionCliente") or ""
                if unidad_info else ""
            ),
            "Nombre Unidad": (
                unidad_info.get("descripcion") or ""
                if unidad_info else ""
            ),
            "ZONA": (
                str(unidad_info.get("zona") or "")
                if unidad_info else ""
            ),
            "MACROZONA": (
                str(unidad_info.get("tsZonaDescripcion") or "")
                if unidad_info else ""
            ),
            "LÍDERZONAL": "",                                 # No disponible directamente

            # --- Personal Responsable ---
            "GERENTE": (
                str(unidad_info.get("gerenteNombre") or "")
                if unidad_info else ""
            ),
            "JEFE": (
                str(unidad_info.get("jefeNombre") or "")
                if unidad_info else ""
            ),

            # --- Columna diagnóstica adicional (no estaba en Excel) ---
            "Tipo_Empleado": str(rec.get("tipoEmpleado", "")),
        }

        rows.append(row)

    df = pl.DataFrame(rows, schema=SV_SCHEMA)

    logger.info(
        "programacion_to_sv_dataframe: %d registros transformados (%d únicos unidad+servicio).",
        len(df),
        df.select(["Unidad", "Servicio"]).unique().height,
    )
    return df


# ---------------------------------------------------------------------------
# Función alternativa: Tareo → DataFrame (diagnóstico de desvíos)
# ---------------------------------------------------------------------------

def tareo_to_dataframe(tareo: list[dict[str, Any]]) -> pl.DataFrame:
    """
    Convierte la respuesta de TareoxCliente en un pl.DataFrame simple
    con el conteo de días realmente trabajados ('D') por empleado.

    Útil para comparar programación vs. tareo real:
        df_prog = programacion_to_sv_dataframe(...)
        df_tareo = tareo_to_dataframe(...)
        desvios = df_prog.join(df_tareo, on=["empleado", "Servicio"], how="left")

    Returns:
        pl.DataFrame con columnas:
            empleado (int), nombreEmpleado (str), documento (str),
            unidad (str), servicio (str), dias_reales (float),
            tipoEmpleado (str)
    """
    if not tareo:
        logger.warning("tareo_to_dataframe: lista de tareo vacía.")
        return pl.DataFrame(
            schema={
                "empleado": pl.Int64,
                "nombreEmpleado": pl.String,
                "documento": pl.String,
                "unidad": pl.String,
                "servicio": pl.String,
                "dias_reales": pl.Float64,
                "tipoEmpleado": pl.String,
            }
        )

    rows = [
        {
            "empleado": int(rec.get("empleado", 0)),
            "nombreEmpleado": str(rec.get("nombreEmpleado", "")),
            "documento": str(rec.get("documento", "")),
            "unidad": str(rec.get("unidad", "")),
            "servicio": str(rec.get("servicio", "")),
            "dias_reales": _count_dias_trabajados(rec),
            "tipoEmpleado": str(rec.get("tipoEmpleado", "")),
        }
        for rec in tareo
    ]
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# Catálogos como DataFrames
# ---------------------------------------------------------------------------

def unidades_to_dataframe(unidades: list[dict[str, Any]]) -> pl.DataFrame:
    """
    Convierte la respuesta de UnidadesxCliente en un pl.DataFrame de catálogo.

    Útil para joins y búsquedas de metadatos de unidades.
    """
    if not unidades:
        return pl.DataFrame()

    return pl.DataFrame(
        [
            {
                "unidad": str(u.get("unidad", "")),
                "nombre_unidad": str(u.get("descripcion", "")),
                "zona": str(u.get("zona") or ""),
                "ts_zona": str(u.get("tsZonaDescripcion") or ""),
                "estado": str(u.get("estado") or ""),
                "departamento": str(u.get("departamentoDescripcion") or ""),
                "provincia": str(u.get("provinciaDescripcion") or ""),
                "distrito": str(u.get("distritoDescripcion") or ""),    # typo corregido
                "gerente": str(u.get("gerenteNombre") or ""),
                "jefe": str(u.get("jefeNombre") or ""),
                "responsable": str(u.get("responsableNombre") or ""),
                "es_grupo_empresarial": str(u.get("esGrupoEmpresarial") or ""),
                "des_grupo_empresarial": str(u.get("desGrupoEmpresarial") or ""),
            }
            for u in unidades
        ]
    )


def zonas_to_dataframe(zonas: list[dict[str, Any]]) -> pl.DataFrame:
    """
    Convierte la respuesta de Zonas en un pl.DataFrame del catálogo de zonas.

    Nota: tS_ZonaDesc ya fue normalizado a 'tsZonaDescripcion' por api_client.py.
    """
    if not zonas:
        return pl.DataFrame()

    return pl.DataFrame(
        [
            {
                "codigo_zona": str(z.get("codigo", "")),
                "descripcion": str(z.get("descripcion", "")),
                "ts_zona_desc": str(z.get("tsZonaDescripcion") or ""),
                "codigo_gerente": z.get("codigoGerente"),
                "gerente": str(z.get("gerenteNombre") or ""),
                "codigo_jefe": z.get("codigoJefe"),
                "jefe": str(z.get("jefeNombre") or ""),
                "codigo_responsable": z.get("codigoResponsable"),
                "responsable": str(z.get("responsableNombre") or ""),
            }
            for z in zonas
        ]
    )


# ---------------------------------------------------------------------------
# Esquema PA y función: Tareo → df_pa (Personal Asignado real)
# ---------------------------------------------------------------------------

# Esquema esperado de df_pa (coincide con EXCEL_SCHEMAS["personal_asignado"] en config.py)
# TareoxCliente representa el tareo real = lo que hay efectivamente asignado.
PA_SCHEMA: dict[str, pl.DataType] = {
    "ESTADO": pl.String,           # Estado del empleado/puesto ('Activo'/'Inactivo')
    "COD CLIENTE": pl.String,      # Código de cliente (de UnidadesxCliente)
    "COD UNID": pl.String,         # Código de unidad (unidad de tareo)
    "COD SERVICIO": pl.String,     # Código de servicio
    "COD GRUPO": pl.String,        # Código de grupo (no disponible en API — vacío)
    "TIPO DE COMPAÑÍA": pl.String, # Tipo de compañía (no disponible en API — vacío)
    "CLIENTE": pl.String,          # Nombre del cliente (de UnidadesxCliente)
    "UNIDAD": pl.String,           # Nombre de la unidad (de UnidadesxCliente)
    "TIPO DE SERVCIO": pl.String,  # Tipo de servicio = descripcion del servicio
    "GRUPO": pl.String,            # Nombre del grupo (no disponible en API — vacío)
    "LIDER ZONAL / COORDINADOR": pl.String,  # Responsable de la unidad
    "JEFE DE OPERACIONES": pl.String,        # Jefe de la unidad
    "GERENTE REGIONAL": pl.String,           # Gerente de la unidad
    "SECTOR": pl.String,           # Sector (departamento de la unidad)
    "DEPARTAMENTO": pl.String,     # Departamento geográfico

    # Columnas diagnósticas extra provenientes de TareoxCliente
    # (no estaban en Excel, facilitan joins y análisis de brechas)
    "COD EMPLEADO": pl.Int64,      # ID numérico del empleado
    "NOMBRE EMPLEADO": pl.String,  # Nombre completo del empleado
    "DOCUMENTO": pl.String,        # DNI u documento de identidad
    "TIPO EMPLEADO": pl.String,    # 'Titular' o 'Descansero'
    "DIAS_TAREO": pl.Float64,      # Días realmente trabajados ('D') en el periodo
}


def tareo_to_pa_dataframe(
    tareo: list[dict[str, Any]],
    unidades: list[dict[str, Any]],
) -> pl.DataFrame:
    """
    Convierte la respuesta de TareoxCliente + UnidadesxCliente en un
    pl.DataFrame compatible con el esquema de load_personal_asignado() (Excel PA).

    Conceptualmente:
        - TareoxCliente = "lo que hay efectivamente" = Personal Asignado real
        - ProgramacionxCliente = "lo que debería haber" = Servicio Vivo (planificado)

    Cada registro del tareo = un empleado asignado en el periodo, con sus días
    realmente trabajados y datos de la unidad enriquecidos desde UnidadesxCliente.

    Campos del Excel PA que NO están en la API (quedan como string vacío):
        - COD GRUPO, TIPO DE COMPAÑÍA, GRUPO (catálogos internos del ERP)

    Campos extra que SÍ podemos obtener de la API (columnas diagnósticas):
        - COD EMPLEADO, NOMBRE EMPLEADO, DOCUMENTO, TIPO EMPLEADO, DIAS_TAREO

    Args:
        tareo: Lista de dicts de TareoxCliente (ya normalizada por api_client.py).
        unidades: Lista de dicts de UnidadesxCliente (ya normalizada).

    Returns:
        pl.DataFrame con columnas según PA_SCHEMA, compatible con analysis_engine.py.

    Example:
        >>> tareo = client.get_tareo("17", "1")
        >>> unidades = client.get_unidades("7006", "0099")
        >>> df_pa = tareo_to_pa_dataframe(tareo, unidades)
        >>> # Mismas columnas core que load_personal_asignado()
    """
    if not tareo:
        logger.warning("tareo_to_pa_dataframe: lista de tareo vacía. Retornando DataFrame vacío.")
        return pl.DataFrame(schema=PA_SCHEMA)

    unidades_lookup = _build_unidades_lookup(unidades)

    rows: list[dict[str, Any]] = []

    for rec in tareo:
        unidad_key = str(rec.get("unidad", ""))
        u = unidades_lookup.get(unidad_key)

        # ------------------------------------------------------------------------
        # Estado del puesto: derivado del estado de la unidad
        # 'A' (activo en unidad) → 'ACTIVO'  |  'I' → 'INACTIVO'
        # El Excel PA usa valores como "ACTIVO - PARA BAJA", "ALTA NUEVA - PARA BAJA"
        # Aquí usamos 'ACTIVO' como valor base; puede refinarse con datos del ERP.
        # ------------------------------------------------------------------------
        raw_estado = str(u.get("estado", "") if u else "").strip().upper()
        estado = "ACTIVO" if raw_estado == "A" else ("INACTIVO" if raw_estado == "I" else "DESCONOCIDO")

        row: dict[str, Any] = {
            # ---- Identificadores ----
            "ESTADO": estado,
            "COD CLIENTE": str(u.get("cliente", "") if u else ""),
            "COD UNID": unidad_key,
            "COD SERVICIO": str(rec.get("servicio", "")),
            "COD GRUPO": "",                          # No disponible en tareo/unidades

            # ---- Clasificación corporativa ----
            "TIPO DE COMPAÑÍA": "",                   # No disponible en API
            "CLIENTE": (
                str(u.get("descripcionCliente") or u.get("desGrupoEmpresarial") or "")
                if u else ""
            ),
            "UNIDAD": str(u.get("descripcion") or "" if u else ""),
            "TIPO DE SERVCIO": str(rec.get("descripcion", "")),
            "GRUPO": "",                               # No disponible en API

            # ---- Jerarquía operativa (desde UnidadesxCliente) ----
            "LIDER ZONAL / COORDINADOR": (
                str(u.get("responsableNombre") or "")
                if u else ""
            ),
            "JEFE DE OPERACIONES": (
                str(u.get("jefeNombre") or "")
                if u else ""
            ),
            "GERENTE REGIONAL": (
                str(u.get("gerenteNombre") or "")
                if u else ""
            ),

            # ---- Geografía ----
            "SECTOR": (
                str(u.get("tsZonaDescripcion") or "")
                if u else ""
            ),
            "DEPARTAMENTO": (
                str(u.get("departamentoDescripcion") or "")
                if u else ""
            ),

            # ---- Columnas diagnósticas del empleado (extra vs Excel) ----
            "COD EMPLEADO": int(rec.get("empleado", 0)),
            "NOMBRE EMPLEADO": str(rec.get("nombreEmpleado", "")),
            "DOCUMENTO": str(rec.get("documento", "")),
            "TIPO EMPLEADO": str(rec.get("tipoEmpleado", "")),
            "DIAS_TAREO": _count_dias_trabajados(rec),
        }

        rows.append(row)

    df = pl.DataFrame(rows, schema=PA_SCHEMA)

    logger.info(
        "tareo_to_pa_dataframe: %d registros → %d empleados únicos en %d unidades.",
        len(df),
        df["COD EMPLEADO"].n_unique(),
        df["COD UNID"].n_unique(),
    )
    return df

