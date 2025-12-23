"""
ExcelExporter module for exporting analysis results to Excel with multiple sheets.

This module provides an ExcelExporter class that handles exporting the final merged
DataFrame and additional analysis results to Excel format with multiple sheets,
including proper data formatting, error handling, and logging.
"""

import polars as pl
import pandas as pd
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import pyarrow as pa

try:
    from .config import FILE_PATHS, OUTPUT_SHEETS
except ImportError:
    from config import FILE_PATHS, OUTPUT_SHEETS

class ExcelExporterError(Exception):
    """
    Base exception for ExcelExporter errors.

    This is the parent class for all custom exceptions raised by the ExcelExporter class.
    """
    pass


class ExportError(ExcelExporterError):
    """
    Exception raised when Excel export operations fail.

    This exception is raised when there is an issue writing to Excel files,
    creating sheets, or formatting data.
    """
    pass


class ExcelExporter:
    """
    ExcelExporter class for exporting analysis results to Excel with multiple sheets.

    This class handles the export of the final merged DataFrame and additional analysis
    results to Excel format using Polars' native Excel writing capabilities. It creates
    multiple sheets with appropriate data formatting, includes comprehensive error
    handling and logging, and integrates with config.py for output paths and sheet names.

    Attributes:
        logger (logging.Logger): Logger instance for logging operations and errors.
        file_paths (Dict[str, str]): File paths configuration from config.py.
        output_sheets (Dict[str, str]): Output sheet names configuration from config.py.
    """

    def __init__(self):
        """
        Initialize the ExcelExporter instance.

        Sets up the logger with INFO level and a stream handler for console output,
        and loads file paths and sheet names from config.py.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)

        self.file_paths = FILE_PATHS
        self.output_sheets = OUTPUT_SHEETS
        self.logger.info("ExcelExporter initialized with file paths and sheet configurations")

    def _create_estadisticas_dataframe(self, investigation_results: Dict[str, Any]) -> pl.DataFrame:
        """
        Create a DataFrame for the Estadisticas sheet from investigation results.

        This method extracts summary statistics and analysis metadata from the
        investigation results and formats them into a structured DataFrame for export.

        Args:
            investigation_results (Dict[str, Any]): Dictionary containing investigation results
                and analysis metadata from the analysis engine.

        Returns:
            pl.DataFrame: Formatted DataFrame containing statistics and metadata.

        Raises:
            ExportError: If data extraction or formatting fails.
        """
        try:
            self.logger.debug("Creating Estadisticas DataFrame")

            # Extract summary statistics
            summary_stats = investigation_results.get('summary_stats', {})
            analysis_metadata = investigation_results.get('analysis_metadata', {})

            # Create statistics rows
            stats_data = [
                {"Metrica": "Total de Registros", "Valor": summary_stats.get('total_records', 0)},
                {"Metrica": "Registros Completos", "Valor": summary_stats.get('complete_records', 0)},
                {"Metrica": "Faltantes en PA", "Valor": summary_stats.get('missing_in_pa_count', 0)},
                {"Metrica": "Faltantes en SV", "Valor": summary_stats.get('missing_in_sv_count', 0)},
                {"Metrica": "Completamente Faltantes", "Valor": summary_stats.get('completely_missing', 0)},
                {"Metrica": "Porcentaje de Completitud", "Valor": f"{summary_stats.get('completeness_percentage', 0)}%"},
                {"Metrica": "Total Personal Real", "Valor": analysis_metadata.get('total_personal_real', 0)},
                {"Metrica": "Total Personal Estimado", "Valor": analysis_metadata.get('total_personal_estimado', 0)},
                {"Metrica": "Total Diferencia", "Valor": analysis_metadata.get('total_diferencia', 0)},
                {"Metrica": "Servicios Analizados", "Valor": analysis_metadata.get('total_services_analyzed', 0)},
                {"Metrica": "Timestamp de Procesamiento", "Valor": analysis_metadata.get('processing_timestamp', '')}
            ]

            # Create DataFrame
            stats_df = pl.DataFrame(stats_data)

            self.logger.debug(f"Created Estadisticas DataFrame with {len(stats_df)} metrics")
            return stats_df

        except Exception as e:
            self.logger.error(f"Error creating Estadisticas DataFrame: {str(e)}")
            raise ExportError(f"Failed to create Estadisticas DataFrame: {str(e)}") from e

    def _create_investigacion_dataframe(self, investigation_results: Dict[str, Any]) -> pl.DataFrame:
        """
        Create a DataFrame for the Investigacion sheet from investigation results.

        This method extracts investigation details including ANTAPACCAY analysis,
        missing records, and other investigation data, formatting them into a
        structured DataFrame for export.

        Args:
            investigation_results (Dict[str, Any]): Dictionary containing investigation results
                from the analysis engine.

        Returns:
            pl.DataFrame: Formatted DataFrame containing investigation details.

        Raises:
            ExportError: If data extraction or formatting fails.
        """
        try:
            self.logger.debug("Creating Investigacion DataFrame")

            investigation_data = []

            # ANTAPACCAY analysis
            antapaccay = investigation_results.get('antapaccay_analysis', {})
            investigation_data.extend([
                {"Seccion": "ANTAPACCAY Analysis", "Campo": "Total de Registros", "Valor": antapaccay.get('total_records', 0)},
                {"Seccion": "ANTAPACCAY Analysis", "Campo": "Registros con Personal Real", "Valor": antapaccay.get('records_with_personal_real', 0)},
                {"Seccion": "ANTAPACCAY Analysis", "Campo": "Registros con Personal Estimado", "Valor": antapaccay.get('records_with_personal_estimado', 0)},
                {"Seccion": "ANTAPACCAY Analysis", "Campo": "Registros Faltantes", "Valor": antapaccay.get('missing_records', 0)},
                {"Seccion": "ANTAPACCAY Analysis", "Campo": "Unidad 22799 Encontrada", "Valor": antapaccay.get('unit_22799_found', False)}
            ])

            # Summary statistics
            summary = investigation_results.get('summary_stats', {})
            investigation_data.extend([
                {"Seccion": "Resumen General", "Campo": "Total de Registros", "Valor": summary.get('total_records', 0)},
                {"Seccion": "Resumen General", "Campo": "Registros Completos", "Valor": summary.get('complete_records', 0)},
                {"Seccion": "Resumen General", "Campo": "Faltantes en PA", "Valor": summary.get('missing_in_pa_count', 0)},
                {"Seccion": "Resumen General", "Campo": "Faltantes en SV", "Valor": summary.get('missing_in_sv_count', 0)},
                {"Seccion": "Resumen General", "Campo": "Porcentaje de Completitud", "Valor": f"{summary.get('completeness_percentage', 0)}%"}
            ])

            # Create DataFrame
            inv_df = pl.DataFrame(investigation_data)

            self.logger.debug(f"Created Investigacion DataFrame with {len(inv_df)} entries")
            return inv_df

        except Exception as e:
            self.logger.error(f"Error creating Investigacion DataFrame: {str(e)}")
            raise ExportError(f"Failed to create Investigacion DataFrame: {str(e)}") from e

    def export_to_excel(self, final_dataframe: pl.DataFrame, investigation_results: Dict[str, Any],
                       output_path: Optional[str] = None) -> str:
        """
        Export the final DataFrame and investigation results to Excel with multiple sheets.

        This method creates an Excel file with three sheets:
        - 'Resultado_Final': The main merged DataFrame with all calculated metrics
        - 'Estadisticas': Summary statistics and analysis metadata
        - 'Investigacion': Detailed investigation results and findings

        Args:
            final_dataframe (pl.DataFrame): The final merged DataFrame with calculated metrics.
            investigation_results (Dict[str, Any]): Dictionary containing investigation results
                and analysis metadata from the analysis engine.
            output_path (str, optional): Custom output path for the Excel file. If not provided,
                uses the template from config.py with current timestamp.

        Returns:
            str: Path to the exported Excel file.

        Raises:
            ExportError: If the export operation fails.
        """
        try:
            self.logger.info("Starting Excel export process")

            # Generate output path if not provided
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = self.file_paths["output_template"].replace("{timestamp}", timestamp)

            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"Exporting to: {output_path}")

            # Estadisticas sheet
            self.logger.debug("Preparing Estadisticas sheet")
            stats_df = self._create_estadisticas_dataframe(investigation_results)

            # Investigacion sheet
            self.logger.debug("Preparing Investigacion sheet")
            inv_df = self._create_investigacion_dataframe(investigation_results)

            # Export to Excel using pandas with xlsxwriter
            self.logger.debug("Writing sheets to Excel file")
            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                final_dataframe.to_pandas().to_excel(writer, sheet_name=self.output_sheets["resultado_final"], index=False)
                stats_df.to_pandas().to_excel(writer, sheet_name=self.output_sheets["estadisticas"], index=False)
                inv_df.to_pandas().to_excel(writer, sheet_name=self.output_sheets["investigacion"], index=False)

            self.logger.info(f"Excel export completed successfully: {output_path}")
            self.logger.info(f"Exported 3 sheets: {[self.output_sheets[k] for k in ['resultado_final', 'estadisticas', 'investigacion']]}")

            return output_path

        except Exception as e:
            self.logger.error(f"Error during Excel export: {str(e)}")
            raise ExportError(f"Failed to export to Excel: {str(e)}") from e