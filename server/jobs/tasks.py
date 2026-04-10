from __future__ import annotations

import io
import logging
import os
import tempfile
import unicodedata
from pathlib import Path

import polars as pl
from celery import shared_task
from django.core.files.base import ContentFile

from jobs.models import AnalysisJob, JobStatus, Artifact, ArtifactKind, AnalysisSnapshot
from jobs.utils import generate_analysis_metrics

# Pipeline (root del repo) — se habilita por sys.path en settings/manage.py
from core.data_processor import DataProcessor
from core.analysis_engine import AnalysisEngine
from core.excel_exporter import ExcelExporter
from core.config import SHEET_NAMES, HEADER_ROWS, EXCEL_SCHEMAS


logger = logging.getLogger(__name__)


SERVICIO_VIVO_HEADER_ALIASES = {
    "Q° PER. FACTOR - REQUERIDO": [
        "Q° PER FACTOR REQUERIDO",
        "Q° PER. FACTOR REQUERIDO",
        "Q PER FACTOR REQUERIDO",
    ],
    "TIPO DE PLANILLA": [
        "Compañía",
        "COMPAÑIA",
        "COMPANIA",
        "TIPO PLANILLA",
        "TIPO_DE_PLANILLA",
    ],
    "ZONA": ["Zona", "zona"],
    "LÍDER ZONAL": ["LIDER ZONAL", "LÍDERZONAL", "LIDERZONAL", "Lider Zonal"],
    "GERENTE": ["GERENCIA", "Gerencia"],
    "JEFE": ["JEFATURA", "Jefatura"],
    "MACROZONA": ["Macrozona", "macrozona"],
}

SERVICIO_VIVO_REQUIRED_COLUMNS = [
    "Cliente",
    "Unidad",
    "Servicio",
    "Grupo",
    "Q° PER. FACTOR - REQUERIDO",
    "TIPO DE PLANILLA",
    "Nombre Cliente",
    "Nombre Unidad",
    "Nombre Servicio",
    "Nombre Grupo",
    "ZONA",
    "MACROZONA",
    "LÍDER ZONAL",
    "JEFE",
    "GERENTE",
    "SECTOR",
]


def _make_unique_columns(header_values):
    """Convierte nombres de columna a strings únicos, manejando duplicados y valores vacíos."""
    seen = {}
    result = []
    for i, v in enumerate(header_values):
        name = str(v).strip() if v is not None else ""
        # Si está vacío o es "(en blanco)", generar nombre único
        if not name or name == "(en blanco)" or name.lower() == "none":
            name = f"_col_{i}"
        
        # Manejar duplicados
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        
        result.append(name)
    return result


def _normalize_header_name(name: str) -> str:
    """Normaliza nombres de columnas para matching tolerante."""
    normalized = unicodedata.normalize("NFKD", str(name).strip()).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.replace("_", " ").replace("-", " ").replace(".", " ")
    normalized = " ".join(normalized.upper().split())
    return normalized


def _apply_column_aliases(df: pl.DataFrame, aliases: dict[str, list[str]] | None) -> pl.DataFrame:
    """Renombra columnas usando un mapa de alias tolerante a mayúsculas/espacios/acentos."""
    if not aliases:
        return df

    normalized_to_actual = {
        _normalize_header_name(column): column
        for column in df.columns
    }

    rename_map = {}
    for canonical_name, alias_list in aliases.items():
        if canonical_name in df.columns:
            continue

        candidates = [canonical_name, *alias_list]
        for candidate in candidates:
            matched_column = normalized_to_actual.get(_normalize_header_name(candidate))
            if matched_column and matched_column != canonical_name:
                rename_map[matched_column] = canonical_name
                break

    if rename_map:
        df = df.rename(rename_map)

    return df


def _validate_required_columns(df: pl.DataFrame, required_columns: list[str] | None) -> None:
    """Valida presencia de columnas obligatorias y falla temprano con mensaje claro."""
    if not required_columns:
        return

    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(
            "Faltan columnas obligatorias: "
            + ", ".join(missing_columns)
            + ". Columnas detectadas: "
            + ", ".join(df.columns)
        )


def _detect_header_row(
    df: pl.DataFrame,
    required_columns: list[str],
    aliases: dict[str, list[str]] | None,
    max_scan_rows: int = 15,
) -> int:
    """Detecta automáticamente la fila de cabeceras comparando matches contra columnas requeridas."""
    if df.height == 0:
        raise ValueError("El archivo está vacío; no se puede detectar la fila de cabeceras.")

    alias_map = {}
    for canonical in required_columns:
        candidates = [canonical]
        if aliases and canonical in aliases:
            candidates.extend(aliases[canonical])
        alias_map[canonical] = {_normalize_header_name(candidate) for candidate in candidates}

    rows_to_scan = min(max_scan_rows, df.height)
    best_row_index = -1
    best_score = -1
    best_matched_names: list[str] = []
    scan_summary: list[str] = []

    for row_index in range(rows_to_scan):
        row_values = df.row(row_index)
        normalized_row = {
            _normalize_header_name(value)
            for value in row_values
            if str(value).strip() and str(value).strip().lower() != "none"
        }

        matched_names = [
            canonical
            for canonical in required_columns
            if normalized_row.intersection(alias_map[canonical])
        ]
        score = len(matched_names)
        scan_summary.append(f"fila {row_index}: {score}/{len(required_columns)}")

        if score > best_score:
            best_score = score
            best_row_index = row_index
            best_matched_names = matched_names

    minimum_matches = max(5, min(len(required_columns), int(len(required_columns) * 0.4)))
    if best_score < minimum_matches:
        logger.error(
            "No se pudo detectar header row automáticamente (mejor fila=%s, score=%s/%s, mínimo=%s). Escaneo: %s",
            best_row_index,
            best_score,
            len(required_columns),
            minimum_matches,
            " | ".join(scan_summary),
        )
        raise ValueError(
            "No se pudo detectar la fila de cabeceras automáticamente. "
            f"Mejor coincidencia: fila {best_row_index} con {best_score} columnas; "
            f"mínimo requerido: {minimum_matches}."
        )

    logger.info(
        "Header row detectado automáticamente en fila %s (%s/%s). Coincidencias: %s",
        best_row_index,
        best_score,
        len(required_columns),
        ", ".join(best_matched_names) if best_matched_names else "sin coincidencias",
    )

    return best_row_index


def _read_excel_bytes_to_df(
    content: bytes,
    sheet_name: str,
    header_row: int,
    schema: dict,
    header_aliases: dict[str, list[str]] | None = None,
    required_columns: list[str] | None = None,
    auto_detect_header: bool = False,
) -> pl.DataFrame:
    """Lee un Excel desde bytes, saltando las filas de encabezado indicadas."""
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(content)

        # Leer sin encabezados para poder manejar filas de título
        df = pl.read_excel(
            tmp_path,
            sheet_name=sheet_name,
            engine="calamine",
            has_header=False,
            infer_schema_length=10000,
        )

        resolved_header_row = header_row
        if auto_detect_header and required_columns:
            resolved_header_row = _detect_header_row(
                df,
                required_columns=required_columns,
                aliases=header_aliases,
            )

        if resolved_header_row < 0 or resolved_header_row >= df.height:
            raise ValueError(
                f"Fila de cabecera inválida ({resolved_header_row}) para hoja '{sheet_name}'. "
                f"Total de filas detectadas: {df.height}."
            )
        
        if resolved_header_row > 0:
            # La fila resolved_header_row contiene los nombres de columnas reales
            # Extraer nombres de columna de esa fila
            header_values = df.row(resolved_header_row)
            new_columns = _make_unique_columns(header_values)
            
            # Renombrar columnas y saltar filas hasta los datos
            df = df.slice(resolved_header_row + 1)  # Datos comienzan después del encabezado
            df.columns = new_columns
        else:
            # Primera fila es el encabezado, ya está bien
            header_values = df.row(0)
            new_columns = _make_unique_columns(header_values)
            df = df.slice(1)
            df.columns = new_columns

        # Resolver alias y validar columnas críticas antes de procesar
        df = _apply_column_aliases(df, header_aliases)
        _validate_required_columns(df, required_columns)
        
        # Aplicar schema si se especificó
        if schema:
            for col, dtype in schema.items():
                if col in df.columns:
                    try:
                        df = df.with_columns(pl.col(col).cast(dtype))
                    except Exception:
                        pass  # Ignorar errores de cast
        
        return df
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


@shared_task(bind=True)
def run_analysis_job(self, job_id: str) -> None:
    job = AnalysisJob.objects.get(id=job_id)
    job.status = JobStatus.RUNNING
    job.error_message = ""
    job.save(update_fields=["status", "error_message", "updated_at"])

    # --- DEBUGGING / ROBUST COMPATIBILITY ---
    import boto3
    import logging
    from botocore.config import Config
    from django.conf import settings
    
    logger = logging.getLogger(__name__)

    def read_file_content(file_field, field_name):
        """Intenta leer usando el storage de Django, y si falla (403/404), usa boto3 directo."""
        try:
            logger.info(f"Probando leer {field_name} con storage default...")
            return file_field.read()
        except Exception as e:
            logger.warning(f"Fallo lectura estándar de {field_name}: {e}. Intentando fallback manual con Boto3...")
            
            # Fallback manual para MinIO cuando django-storages falla
            try:
                session = boto3.session.Session()
                s3_config = Config(signature_version='s3v4', s3={'addressing_style': 'path'})
                
                s3 = session.client(
                    's3',
                    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION_NAME,
                    config=s3_config,
                    verify=settings.AWS_S3_VERIFY
                )
                
                bucket_name = file_field.storage.bucket_name
                # El "name" del archivo suele ser la ruta relativa (key)
                file_key = file_field.name
                
                logger.info(f"Boto3 Fallback: Descargando objeto s3://{bucket_name}/{file_key}")
                response = s3.get_object(Bucket=bucket_name, Key=file_key)
                return response['Body'].read()
                
            except Exception as e2:
                logger.error(f"FATAL: Falló también el fallback manual para {field_name}: {e2}")
                raise e  # Lanzar la excepción original para no ocultar la raíz

    try:
        pa_bytes = read_file_content(job.input_personal_asignado, "Personal Asignado")
        sv_bytes = read_file_content(job.input_servicio_vivo, "Servicio Vivo")

        df_pa_raw = _read_excel_bytes_to_df(
            pa_bytes,
            SHEET_NAMES["personal_asignado"],
            HEADER_ROWS["personal_asignado"],
            EXCEL_SCHEMAS["personal_asignado"],
        )
        df_sv_raw = _read_excel_bytes_to_df(
            sv_bytes,
            SHEET_NAMES["servicio_vivo"],
            HEADER_ROWS["servicio_vivo"],
            EXCEL_SCHEMAS["servicio_vivo"],
            header_aliases=SERVICIO_VIVO_HEADER_ALIASES,
            required_columns=SERVICIO_VIVO_REQUIRED_COLUMNS,
            auto_detect_header=True,
        )

        processor = DataProcessor()
        engine = AnalysisEngine()

        df_pa = processor.process_personal_asignado(df_pa_raw)
        df_sv = processor.process_servicio_vivo(df_sv_raw)

        final_df, investigation = engine.run_analysis(df_pa, df_sv, df_pa_raw=df_pa_raw, df_sv_raw=df_sv_raw)

        # Parquet (Opción A)
        parquet_buffer = io.BytesIO()
        final_df.write_parquet(parquet_buffer)
        parquet_bytes = parquet_buffer.getvalue()
        Artifact.objects.create(
            job=job,
            kind=ArtifactKind.PARQUET,
            file=ContentFile(parquet_bytes, name="resultado_final.parquet"),
        )

        # Excel artifact
        exporter = ExcelExporter()
        # Exporter escribe a path; usamos temp file y luego guardamos bytes
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            exporter.export_to_excel(final_df, investigation, output_path=tmp_path)
            excel_bytes = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        Artifact.objects.create(
            job=job,
            kind=ArtifactKind.EXCEL,
            file=ContentFile(excel_bytes, name="mezclado_pa_vs_sv.xlsx"),
        )

        # Snapshot (Métricas para Dashboard)
        metrics = generate_analysis_metrics(final_df)
        AnalysisSnapshot.objects.update_or_create(
            tenant=job.tenant,
            period_month=job.period_month or job.created_at.date().replace(day=1),
            defaults={
                "job": job,
                "metrics": metrics
            }
        )

        job.status = JobStatus.SUCCEEDED
        job.save(update_fields=["status", "updated_at"])

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        raise
