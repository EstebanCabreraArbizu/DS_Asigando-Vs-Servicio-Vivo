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
from data_processor import DataProcessor
from analysis_engine import AnalysisEngine
from excel_exporter import ExcelExporter
from config import SHEET_NAMES, HEADER_ROWS, EXCEL_SCHEMAS


def _read_excel_bytes_to_df(content: bytes, sheet_name: str, header_row: int, schema: dict) -> pl.DataFrame:
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(content)

        df = pl.read_excel(
            tmp_path,
            sheet_name=sheet_name,
            engine="calamine",
            schema_overrides=schema,
            infer_schema_length=10000,
        )
        if header_row > 0:
            df = df.slice(header_row)
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
