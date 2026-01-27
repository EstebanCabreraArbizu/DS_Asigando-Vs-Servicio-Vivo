
import polars as pl
from io import BytesIO

def generate_analysis_metrics(df: pl.DataFrame) -> dict:
    """
    Genera métricas agregadas para el dashboard a partir de un DataFrame de polars.
    Esta lógica es la misma que usa el MetricsAPIView.
    """
    if len(df) == 0:
        return {
            "total_personal_asignado": 0,
            "total_servicio_vivo": 0,
            "coincidencias": 0,
            "diferencia_total": 0,
            "cobertura_porcentaje": 0,
            "cobertura_diferencial": 0,
            "total_servicios": 0,
            "by_estado": [],
            "by_zona": [],
            "by_macrozona": [],
            "by_cliente_top10": [],
            "by_unidad_top10": [],
            "by_servicio_top10": [],
            "by_grupo": [],
            "filtros_disponibles": {},
        }
    
    # KPIs básicos
    total_pa = int(df["Personal_Real"].sum() or 0)
    total_sv = float(df["Personal_Estimado"].sum() or 0)
    coincidencias = len(df.filter(
        (pl.col("Personal_Real") > 0) & (pl.col("Personal_Estimado") > 0)
    ))
    diferencia = total_pa - total_sv
    cobertura = round((total_pa / total_sv * 100) if total_sv > 0 else 0, 2)
    cobertura_diff = round((diferencia / total_sv * 100) if total_sv > 0 else 0, 2)
    
    # Por estado
    by_estado = df.group_by("Estado").agg([
        pl.col("Personal_Real").sum().alias("pa"),
        pl.col("Personal_Estimado").sum().alias("sv"),
        pl.len().alias("count")
    ]).sort("count", descending=True).to_dicts()
    
    # Helper para valores únicos (para filtros)
    def get_unique_values(df_in, *columns):
        for col in columns:
            if col in df_in.columns:
                values = df_in.select(pl.col(col)).filter(
                    pl.col(col).is_not_null() & (pl.col(col) != "")
                ).unique().sort(col).to_series().to_list()
                if values:
                    return values
        return []

    # Por zona
    df_zona = df.with_columns(
        pl.coalesce([
            pl.when(pl.col("Zona_SV").is_not_null() & (pl.col("Zona_SV") != ""))
            .then(pl.col("Zona_SV"))
            .otherwise(None) if "Zona_SV" in df.columns else pl.lit(None),
            pl.when(pl.col("Zona_PA").is_not_null() & (pl.col("Zona_PA") != ""))
            .then(pl.col("Zona_PA"))
            .otherwise(None) if "Zona_PA" in df.columns else pl.lit(None),
            pl.lit("Sin Zona")
        ]).alias("Zona_Display")
    )
    by_zona = df_zona.group_by("Zona_Display").agg([
        pl.col("Personal_Real").sum().alias("pa"),
        pl.col("Personal_Estimado").sum().alias("sv"),
        pl.len().alias("count")
    ]).filter(
        pl.col("Zona_Display").is_not_null() & (pl.col("Zona_Display") != "")
    ).sort("pa", descending=True).head(10).to_dicts()
    
    # Por MacroZona
    by_macrozona = []
    if "Macrozona_SV" in df.columns:
        by_macrozona = df.group_by("Macrozona_SV").agg([
            pl.col("Personal_Real").sum().alias("pa"),
            pl.col("Personal_Estimado").sum().alias("sv"),
            pl.len().alias("count")
        ]).filter(
            pl.col("Macrozona_SV").is_not_null() & (pl.col("Macrozona_SV") != "")
        ).sort("pa", descending=True).to_dicts()
    
    # Top 10 clientes
    df_cliente = df.with_columns(
        pl.coalesce([
            pl.col("Nombre_Cliente_SV") if "Nombre_Cliente_SV" in df.columns else pl.lit(None),
            pl.col("Nombre_Cliente_PA") if "Nombre_Cliente_PA" in df.columns else pl.lit(None),
            pl.col("Cliente_Final")
        ]).alias("Nombre_Cliente_Display")
    )
    by_cliente = df_cliente.group_by("Cliente_Final").agg([
        pl.col("Personal_Real").sum().alias("pa"),
        pl.col("Personal_Estimado").sum().alias("sv"),
        (pl.col("Personal_Real").sum() - pl.col("Personal_Estimado").sum()).alias("diferencia"),
        pl.col("Nombre_Cliente_Display").first().alias("nombre"),
        pl.len().alias("servicios")
    ]).sort("pa", descending=True).head(10).to_dicts()
    
    # Por Unidad
    df_unidad = df.with_columns(
        pl.coalesce([
            pl.col("Nombre_Unidad_SV") if "Nombre_Unidad_SV" in df.columns else pl.lit(None),
            pl.col("Nombre_Unidad_PA") if "Nombre_Unidad_PA" in df.columns else pl.lit(None),
            pl.col("Unidad_Str")
        ]).alias("Nombre_Unidad_Display")
    )
    by_unidad = df_unidad.group_by("Unidad_Str").agg([
        pl.col("Personal_Real").sum().alias("pa"),
        pl.col("Personal_Estimado").sum().alias("sv"),
        (pl.col("Personal_Real").sum() - pl.col("Personal_Estimado").sum()).alias("diferencia"),
        pl.col("Nombre_Unidad_Display").first().alias("nombre"),
        pl.len().alias("servicios")
    ]).sort("pa", descending=True).head(10).to_dicts()
    
    # Por Servicio
    df_servicio = df.with_columns(
        pl.coalesce([
            pl.col("Nombre_Servicio_SV") if "Nombre_Servicio_SV" in df.columns else pl.lit(None),
            pl.col("Nombre_Servicio_PA") if "Nombre_Servicio_PA" in df.columns else pl.lit(None),
            pl.col("Servicio_Limpio")
        ]).alias("Nombre_Servicio_Display")
    )
    by_servicio = df_servicio.group_by("Servicio_Limpio").agg([
        pl.col("Personal_Real").sum().alias("pa"),
        pl.col("Personal_Estimado").sum().alias("sv"),
        (pl.col("Personal_Real").sum() - pl.col("Personal_Estimado").sum()).alias("diferencia"),
        pl.col("Nombre_Servicio_Display").first().alias("nombre"),
        pl.len().alias("registros")
    ]).sort("pa", descending=True).head(10).to_dicts()
    
    # Por Grupo
    by_grupo = []
    grupo_col = "Nombre_Grupo_SV" if "Nombre_Grupo_SV" in df.columns else ("Nombre_Grupo_PA" if "Nombre_Grupo_PA" in df.columns else None)
    if grupo_col:
        by_grupo = df.group_by(grupo_col).agg([
            pl.col("Personal_Real").sum().alias("pa"),
            pl.col("Personal_Estimado").sum().alias("sv"),
            pl.len().alias("count")
        ]).filter(
            pl.col(grupo_col).is_not_null() & (pl.col(grupo_col) != "")
        ).sort("pa", descending=True).head(10).to_dicts()
    
    # Filtros disponibles
    filtros_disponibles = {
        "macrozona": get_unique_values(df, "Macrozona_SV"),
        "zona": get_unique_values(df, "Zona_SV", "Zona_PA"),
        "compania": get_unique_values(df, "Compañía_SV", "Compañía_PA"),
        "grupo": get_unique_values(df, "Nombre_Grupo_SV", "Nombre_Grupo_PA"),
        "sector": get_unique_values(df, "Sector_SV", "Sector_PA"),
        "gerente": get_unique_values(df, "Gerencia_SV", "Gerencia_PA"),
    }
    
    return {
        "total_personal_asignado": total_pa,
        "total_servicio_vivo": round(total_sv, 2),
        "coincidencias": coincidencias,
        "diferencia_total": round(diferencia, 2),
        "cobertura_porcentaje": cobertura,
        "cobertura_diferencial": cobertura_diff,
        "total_servicios": len(df),
        "by_estado": by_estado,
        "by_zona": by_zona,
        "by_macrozona": by_macrozona,
        "by_cliente_top10": by_cliente,
        "by_unidad_top10": by_unidad,
        "by_servicio_top10": by_servicio,
        "by_grupo": by_grupo,
        "filtros_disponibles": filtros_disponibles,
    }
