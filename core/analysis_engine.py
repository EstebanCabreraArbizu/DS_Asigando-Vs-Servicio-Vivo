"""
AnalysisEngine module for performing data merging, metric calculations, and analytical operations.

This module provides an AnalysisEngine class that handles the core analytical operations
for Personal Asignado vs Servicio Vivo analysis, including full outer joins, metric calculations,
and investigation of missing records using vectorized Polars operations.
"""

import polars as pl
import logging
import datetime as dt
from typing import Optional, Dict, Any, Tuple
from config import PARAMETERS


class AnalysisEngineError(Exception):
    """
    Base exception for AnalysisEngine errors.

    This is the parent class for all custom exceptions raised by the AnalysisEngine class.
    """
    pass


class JoinError(AnalysisEngineError):
    """
    Exception raised when join operations fail.

    This exception is raised when there is an issue performing the full outer join
    between Personal Asignado and Servicio Vivo datasets.
    """
    pass


class MetricCalculationError(AnalysisEngineError):
    """
    Exception raised when metric calculations fail.

    This exception is raised when there is an issue calculating metrics like
    differences, coverage percentages, or status classifications.
    """
    pass


class InvestigationError(AnalysisEngineError):
    """
    Exception raised when record investigation fails.

    This exception is raised when there is an issue investigating missing or
    specific records like the ANTAPACCAY case.
    """
    pass


class AnalysisEngine:
    """
    AnalysisEngine class for performing data merging, metric calculations, and analytical operations.

    This class encapsulates the core analytical logic for comparing Personal Asignado
    (actual personnel) and Servicio Vivo (estimated personnel) datasets. It performs
    full outer joins, calculates key metrics, and investigates missing records using
    vectorized Polars operations. The class integrates with config.py for parameters
    and includes comprehensive error handling and logging.

    Attributes:
        logger (logging.Logger): Logger instance for logging operations and errors.
        parameters (Dict[str, Any]): Processing parameters from config.py.
    """

    def __init__(self):
        """
        Initialize the AnalysisEngine instance.

        Sets up the logger with INFO level and a stream handler for console output,
        and loads processing parameters from config.py.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)

        self.parameters = PARAMETERS
        self.logger.info("AnalysisEngine initialized with parameters: %s", self.parameters)

    def perform_full_outer_join(self, df_pa: pl.DataFrame, df_sv: pl.DataFrame) -> pl.DataFrame:
        """
        Perform full outer join between Personal Asignado and Servicio Vivo datasets.

        This method creates composite join keys for both datasets using Cliente_Final,
        Unidad, and Servicio_Limpio columns, then performs a full outer join to combine
        the data. The join key format is: Cliente_Final + "_" + Unidad + "_" + Servicio_Limpio.

        Args:
            df_pa (pl.DataFrame): Processed Personal Asignado DataFrame.
            df_sv (pl.DataFrame): Processed Servicio Vivo DataFrame.

        Returns:
            pl.DataFrame: Merged DataFrame with all records from both datasets.

        Raises:
            JoinError: If the join operation fails or required columns are missing.
        """
        try:
            self.logger.info("Starting full outer join between Personal Asignado and Servicio Vivo datasets")

            # Validate required columns exist
            required_pa_cols = ["Cliente_Final", "COD UNID", "Servicio_Limpio"]
            required_sv_cols = ["Cliente_Final", "Unidad_Str", "Servicio_Limpio"]

            for col in required_pa_cols:
                if col not in df_pa.columns:
                    raise JoinError(f"Required column '{col}' not found in Personal Asignado DataFrame")

            for col in required_sv_cols:
                if col not in df_sv.columns:
                    raise JoinError(f"Required column '{col}' not found in Servicio Vivo DataFrame")

            # Create join keys
            self.logger.debug("Creating join keys for Personal Asignado")
            pa_with_key = df_pa.with_columns([
                pl.concat_str([
                    pl.col("Cliente_Final"),
                    pl.lit("_"),
                    pl.col("COD UNID").cast(pl.Utf8),
                    pl.lit("_"),
                    pl.col("Servicio_Limpio")
                ]).alias("Clave_Mezclado")
            ])

            self.logger.debug("Creating join keys for Servicio Vivo")
            sv_with_key = df_sv.with_columns([
                pl.concat_str([
                    pl.col("Cliente_Final"),
                    pl.lit("_"),
                    pl.col("Unidad_Str"),
                    pl.lit("_"),
                    pl.col("Servicio_Limpio")
                ]).alias("Clave_Mezclado")
            ])

            # Perform full outer join
            self.logger.debug("Performing full outer join")
            merged_df = pa_with_key.join(
                sv_with_key,
                on="Clave_Mezclado",
                how="full",
                coalesce=True
            )
            
            # Sort by Clave_Mezclado to ensure deterministic order (always has value after join)
            merged_df = merged_df.sort("Clave_Mezclado")

            self.logger.info(f"Full outer join completed: {len(merged_df)} records in merged dataset")
            return merged_df

        except Exception as e:
            self.logger.error(f"Error performing full outer join: {str(e)}")
    def calculate_metrics(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Calculate key metrics for the merged dataset.

        This method computes various metrics including differences, coverage percentages,
        and status classifications using vectorized Polars operations. It fills null values,
        rounds numeric columns, and determines operational status based on personnel data.

        Args:
            df (pl.DataFrame): Merged DataFrame from the full outer join.

        Returns:
            pl.DataFrame: DataFrame with calculated metrics and status columns.

        Raises:
            MetricCalculationError: If metric calculations fail or required columns are missing.
        """
        try:
            self.logger.info("Starting metric calculations")

            # Validate required columns exist
            required_cols = ["Personal_Real", "Personal_Estimado"]
            for col in required_cols:
                if col not in df.columns:
                    raise MetricCalculationError(f"Required column '{col}' not found in DataFrame")

            # Get parameters
            fill_value = self.parameters.get("fill_null_value", 0)
            round_decimals = self.parameters.get("round_decimals", 2)

            self.logger.debug(f"Using fill_value: {fill_value}, round_decimals: {round_decimals}")

            # Fill nulls and calculate metrics
            df_with_metrics = df.with_columns([
                # Fill nulls in numeric columns
                pl.col("Personal_Real").fill_null(fill_value).alias("Personal_Real"),
                pl.col("Personal_Estimado").fill_null(fill_value).alias("Personal_Estimado"),

                # Calculate difference
                (pl.col("Personal_Real").fill_null(fill_value) -
                 pl.col("Personal_Estimado").fill_null(fill_value))
                .round(round_decimals)
                .alias("Diferencia"),

                # Calculate coverage percentage
                pl.when(pl.col("Personal_Estimado").fill_null(fill_value) > 0)
                .then((pl.col("Personal_Real").fill_null(fill_value) /
                       pl.col("Personal_Estimado").fill_null(fill_value) * 100)
                      .round(round_decimals))
                .otherwise(fill_value)
                .alias("Cobertura_Pct"),

                # Determine status
                pl.when(
                    (pl.col("Personal_Real").fill_null(fill_value) == 0) &
                    (pl.col("Personal_Estimado").fill_null(fill_value) == 0)
                ).then(pl.lit("SIN_DATOS"))
                .when(pl.col("Personal_Real").fill_null(fill_value) == 0)
                .then(pl.lit("SIN_PERSONAL"))
                .when(pl.col("Personal_Estimado").fill_null(fill_value) == 0)
                .then(pl.lit("NO_PLANIFICADO"))
                .when(pl.col("Personal_Real").fill_null(fill_value) ==
                      pl.col("Personal_Estimado").fill_null(fill_value))
                .then(pl.lit("EXACTO"))
                .when(pl.col("Personal_Real").fill_null(fill_value) >
                      pl.col("Personal_Estimado").fill_null(fill_value))
                .then(pl.lit("SOBRECARGA"))
                .when(pl.col("Personal_Estimado").fill_null(fill_value) >
                      pl.col("Personal_Real").fill_null(fill_value))
                .then(pl.lit("FALTA"))
                .otherwise(pl.lit("INDETERMINADO"))
                .alias("Estado")
            ])
            
            # Sort by Clave_Mezclado to ensure deterministic order
            df_with_metrics = df_with_metrics.sort("Clave_Mezclado")

            self.logger.info(f"Metric calculations completed: {len(df_with_metrics)} records processed")
            return df_with_metrics

        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            raise MetricCalculationError(f"Failed to calculate metrics: {str(e)}") from e

    def investigate_missing_records(self, df: pl.DataFrame, df_pa_raw: pl.DataFrame = None,
                                   df_sv_raw: pl.DataFrame = None) -> Dict[str, Any]:
        """
        Investigate missing records and specific cases like ANTAPACCAY.

        This method performs detailed investigation of missing records in the merged dataset,
        with special focus on the ANTAPACCAY case. It analyzes records that appear in only
        one dataset or are missing from the final merge.

        Args:
            df (pl.DataFrame): Final merged DataFrame with metrics.
            df_pa_raw (pl.DataFrame, optional): Raw Personal Asignado DataFrame for comparison.
            df_sv_raw (pl.DataFrame, optional): Raw Servicio Vivo DataFrame for comparison.

        Returns:
            Dict[str, Any]: Dictionary containing investigation results with keys:
                - 'antapaccay_analysis': Analysis of ANTAPACCAY records
                - 'missing_in_pa': Records present in SV but missing in PA
                - 'missing_in_sv': Records present in PA but missing in SV
                - 'summary_stats': Summary statistics of missing records

        Raises:
            InvestigationError: If investigation fails.
        """
        try:
            self.logger.info("Starting investigation of missing records")

            investigation_results = {
                'antapaccay_analysis': {},
                'missing_in_pa': None,
                'missing_in_sv': None,
                'summary_stats': {}
            }

            # ANTAPACCAY specific investigation
            self.logger.debug("Investigating ANTAPACCAY records")
            antapaccay_records = df.filter(pl.col("Cliente_Final") == "117232")

            investigation_results['antapaccay_analysis'] = {
                'total_records': len(antapaccay_records),
                'records_with_personal_real': len(antapaccay_records.filter(pl.col("Personal_Real") > 0)),
                'records_with_personal_estimado': len(antapaccay_records.filter(pl.col("Personal_Estimado") > 0)),
                'missing_records': len(antapaccay_records.filter(
                    (pl.col("Personal_Real") == 0) & (pl.col("Personal_Estimado") == 0)
                )),
                'sample_records': antapaccay_records.select([
                    "Cliente_Final", "COD UNID", "Unidad_Str", "Servicio_Limpio",
                    "Personal_Real", "Personal_Estimado", "Estado"
                ]).head(10).to_dicts() if len(antapaccay_records) > 0 else []
            }

            # Check for specific ANTAPACCAY unit 22799
            antapaccay_22799 = df.filter(
                (pl.col("Cliente_Final") == "117232") &
                ((pl.col("COD UNID") == "22799") | (pl.col("Unidad_Str") == "22799"))
            )
            investigation_results['antapaccay_analysis']['unit_22799_found'] = len(antapaccay_22799) > 0
            investigation_results['antapaccay_analysis']['unit_22799_details'] = antapaccay_22799.select([
                "Cliente_Final", "COD UNID", "Unidad_Str", "Servicio_Limpio",
                "Personal_Real", "Personal_Estimado", "Estado"
            ]).to_dicts() if len(antapaccay_22799) > 0 else []

            # General missing records analysis
            self.logger.debug("Analyzing general missing records")

            # Records with only PA data (missing in SV)
            missing_in_sv = df.filter(
                (pl.col("Personal_Real") > 0) & (pl.col("Personal_Estimado") == 0)
            )
            investigation_results['missing_in_sv'] = missing_in_sv.select([
                "Cliente_Final", "COD UNID", "Servicio_Limpio", "Personal_Real", "Estado"
            ])

            # Records with only SV data (missing in PA)
            missing_in_pa = df.filter(
                (pl.col("Personal_Real") == 0) & (pl.col("Personal_Estimado") > 0)
            )
            investigation_results['missing_in_pa'] = missing_in_pa.select([
                "Cliente_Final", "Unidad_Str", "Servicio_Limpio", "Personal_Estimado", "Estado"
            ])

            # Summary statistics
            total_records = len(df)
            complete_records = len(df.filter(
                (pl.col("Personal_Real") > 0) & (pl.col("Personal_Estimado") > 0)
            ))

            investigation_results['summary_stats'] = {
                'total_records': total_records,
                'complete_records': complete_records,
                'missing_in_sv_count': len(missing_in_sv),
                'missing_in_pa_count': len(missing_in_pa),
                'completely_missing': len(df.filter(
                    (pl.col("Personal_Real") == 0) & (pl.col("Personal_Estimado") == 0)
                )),
                'completeness_percentage': round((complete_records / total_records * 100), 2) if total_records > 0 else 0
            }

            self.logger.info("Investigation completed successfully")
            return investigation_results

        except Exception as e:
            self.logger.error(f"Error during investigation: {str(e)}")
    def run_analysis(self, df_pa: pl.DataFrame, df_sv: pl.DataFrame,
                    df_pa_raw: pl.DataFrame = None, df_sv_raw: pl.DataFrame = None) -> Tuple[pl.DataFrame, Dict[str, Any]]:
        """
        Run the complete analysis pipeline.

        This is the main method that orchestrates the entire analysis process:
        1. Performs full outer join between processed datasets
        2. Calculates key metrics (differences, coverage, status)
        3. Investigates missing records and ANTAPACCAY case
        4. Returns the final merged DataFrame with all calculated fields

        Args:
            df_pa (pl.DataFrame): Processed Personal Asignado DataFrame.
            df_sv (pl.DataFrame): Processed Servicio Vivo DataFrame.
            df_pa_raw (pl.DataFrame, optional): Raw Personal Asignado DataFrame for investigation.
            df_sv_raw (pl.DataFrame, optional): Raw Servicio Vivo DataFrame for investigation.

        Returns:
            Tuple[pl.DataFrame, Dict[str, Any]]: A tuple containing:
                - Final merged DataFrame with all calculated metrics and fields
                - Dictionary with investigation results and analysis metadata

        Raises:
            AnalysisEngineError: If any step in the analysis pipeline fails.
        """
        try:
            self.logger.info("Starting complete analysis pipeline")

            # Step 1: Perform full outer join
            self.logger.info("Step 1: Performing full outer join")
            merged_df = self.perform_full_outer_join(df_pa, df_sv)

            # Step 2: Calculate metrics
            self.logger.info("Step 2: Calculating metrics")
            final_df = self.calculate_metrics(merged_df)

            # Step 3: Investigate missing records
            self.logger.info("Step 3: Investigating missing records")
            investigation_results = self.investigate_missing_records(
                final_df, df_pa_raw, df_sv_raw
            )

            # Add analysis metadata
            investigation_results['analysis_metadata'] = {
                'total_services_analyzed': len(final_df),
                'total_personal_real': final_df.select(pl.col("Personal_Real").sum()).item(),
                'total_personal_estimado': final_df.select(pl.col("Personal_Estimado").sum()).item(),
                'total_diferencia': final_df.select(pl.col("Diferencia").sum()).item(),
                'processing_timestamp': dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'parameters_used': self.parameters
            }

            # Final sort to ensure deterministic output
            final_df = final_df.sort("Clave_Mezclado")
            
            self.logger.info("Analysis pipeline completed successfully")
            self.logger.info(f"Final dataset contains {len(final_df)} records")

            return final_df, investigation_results

        except Exception as e:
            self.logger.error(f"Error in analysis pipeline: {str(e)}")
            raise AnalysisEngineError(f"Analysis pipeline failed: {str(e)}") from e