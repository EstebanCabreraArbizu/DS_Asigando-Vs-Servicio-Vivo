from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import polars as pl
from celery import shared_task
from django.core.files.base import ContentFile

from jobs.models import AnalysisJob, JobStatus, Artifact, ArtifactKind

# Pipeline (root del repo) — se habilita por sys.path en settings/manage.py
from core.data_processor import DataProcessor
from core.analysis_engine import AnalysisEngine
from core.excel_exporter import ExcelExporter
from core.config import SHEET_NAMES, HEADER_ROWS, EXCEL_SCHEMAS


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


def _read_excel_bytes_to_df(content: bytes, sheet_name: str, header_row: int, schema: dict) -> pl.DataFrame:
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
        
        if header_row > 0:
            # La fila header_row contiene los nombres de columnas reales
            # Extraer nombres de columna de esa fila
            header_values = df.row(header_row)
            new_columns = _make_unique_columns(header_values)
            
            # Renombrar columnas y saltar filas hasta los datos
            df = df.slice(header_row + 1)  # Datos comienzan después del encabezado
            df.columns = new_columns
        else:
            # Primera fila es el encabezado, ya está bien
            header_values = df.row(0)
            new_columns = _make_unique_columns(header_values)
            df = df.slice(1)
            df.columns = new_columns
        
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

    # --- DEBUGGING START ---
    import logging
    logger = logging.getLogger(__name__)
    try:
        logger.info(f" Job ID: {job_id}")
        logger.info(f" Field PA name: {job.input_personal_asignado.name}")
        logger.info(f" Field PA storage: {job.input_personal_asignado.storage}")
        # Intenta ver opciones del storage
        if hasattr(job.input_personal_asignado.storage, "connection"):
             client_meta = job.input_personal_asignado.storage.connection.meta
             logger.info(f" Boto3 Endpoint: {client_meta.endpoint_url}")
             logger.info(f" addressing_style (from storage options): {job.input_personal_asignado.storage.addressing_style}")
    except Exception as e:
        logger.error(f"Debug log error: {e}")
    # --- DEBUGGING END ---

    try:
        pa_bytes = job.input_personal_asignado.read()
        sv_bytes = job.input_servicio_vivo.read()

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

        job.status = JobStatus.SUCCEEDED
        job.save(update_fields=["status", "updated_at"])

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=["status", "error_message", "updated_at"])
        raise
