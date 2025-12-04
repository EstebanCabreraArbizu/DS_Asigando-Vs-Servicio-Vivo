"""
DataProcessor module for cleaning, transforming, and aggregating datasets.

This module provides a DataProcessor class that handles data processing logic
for Personal Asignado and Servicio Vivo datasets using vectorized Polars operations.
"""

import polars as pl
import logging
from typing import Optional, Dict, Any
from config import PARAMETERS


class DataProcessorError(Exception):
    """
    Base exception for DataProcessor errors.

    This is the parent class for all custom exceptions raised by the DataProcessor class.
    """
    pass


class DataProcessor:
    """
    DataProcessor class for cleaning, transforming, and aggregating datasets.

    This class provides methods to process Personal Asignado and Servicio Vivo datasets,
    including data cleaning, transformation, and aggregation using vectorized Polars operations.
    It uses configuration from config.py for processing parameters and includes proper
    error handling and logging.

    Attributes:
        logger (logging.Logger): Logger instance for logging operations and errors.
        parameters (Dict[str, Any]): Processing parameters from config.py.
    """

    def __init__(self):
        """
        Initialize the DataProcessor instance.

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
        self.logger.info("DataProcessor initialized with parameters: %s", self.parameters)

    def _clean_string_column(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """
        Clean string values in a specified column using vectorized operations.

        Performs string cleaning operations: strip whitespace, convert to uppercase,
        remove extra spaces, and handle null values.

        Args:
            df (pl.DataFrame): Input DataFrame.
            column (str): Name of the column to clean.

        Returns:
            pl.DataFrame: DataFrame with cleaned string column.

        Raises:
            DataProcessorError: If column does not exist or cleaning fails.
        """
        try:
            if column not in df.columns:
                raise DataProcessorError(f"Column '{column}' not found in DataFrame")

            self.logger.debug(f"Cleaning string column: {column}")
            df = df.with_columns(
                pl.col(column)
                .str.strip_chars()
                .str.to_uppercase()
                .str.replace_all(r'\s+', ' ', literal=False)
                .alias(column)
            )
            return df
        except Exception as e:
            self.logger.error(f"Error cleaning string column '{column}': {str(e)}")
            raise DataProcessorError(f"Failed to clean string column '{column}': {str(e)}") from e

    def _create_fallback_client(self, df: pl.DataFrame, client_col: str, unit_col: str) -> pl.DataFrame:
        """
        Create fallback client entries for missing client data.

        When client information is missing, creates a fallback using unit information
        or a default placeholder.

        Args:
            df (pl.DataFrame): Input DataFrame.
            client_col (str): Name of the client column.
            unit_col (str): Name of the unit column to use as fallback.

        Returns:
            pl.DataFrame: DataFrame with fallback client entries filled.

        Raises:
            DataProcessorError: If fallback creation fails.
        """
        try:
            self.logger.debug(f"Creating fallback clients using column: {unit_col}")
            df = df.with_columns(
                pl.when(pl.col(client_col).is_null() | (pl.col(client_col) == ""))
                .then(pl.col(unit_col))
                .otherwise(pl.col(client_col))
                .alias(client_col)
            )
            # Fill any remaining nulls with a default
            df = df.with_columns(
                pl.col(client_col).fill_null("SIN CLIENTE").alias(client_col)
            )
            return df
        except Exception as e:
            self.logger.error(f"Error creating fallback clients: {str(e)}")
            raise DataProcessorError(f"Failed to create fallback clients: {str(e)}") from e

    def _filter_by_estado(self, df: pl.DataFrame, estado_col: str, filter_value: Optional[str] = None) -> pl.DataFrame:
        """
        Filter DataFrame by estado column if filter_value is provided.

        Args:
            df (pl.DataFrame): Input DataFrame.
            estado_col (str): Name of the estado column.
            filter_value (Optional[str]): Value to filter by. If None, no filtering is applied.

        Returns:
            pl.DataFrame: Filtered DataFrame.

        Raises:
            DataProcessorError: If filtering fails.
        """
        try:
            if filter_value is not None:
                self.logger.debug(f"Filtering by {estado_col} = '{filter_value}'")
                df = df.filter(pl.col(estado_col) == filter_value)
                self.logger.info(f"Filtered to {len(df)} rows where {estado_col} = '{filter_value}'")
            else:
                self.logger.debug("No estado filtering applied")
            return df
        except Exception as e:
            self.logger.error(f"Error filtering by estado: {str(e)}")
            raise DataProcessorError(f"Failed to filter by estado: {str(e)}") from e
    def _filter_without_estados(self, df: pl.DataFrame, estado_col: str, filter_values: Optional[list[str]] = None) -> pl.DataFrame:
        """
        Filter DataFrame by estado column if filter_values is provided.

        Args:
            df (pl.DataFrame): Input DataFrame.
            estado_col (str): Name of the estado column.
            filter_values (Optional[list[str]]): Values to filter out. If None, no filtering is applied.
        Returns:
            pl.DataFrame: Filtered DataFrame.

        Raises:
            DataProcessorError: If filtering fails.
        """
        try:
            if filter_values is not None:
                self.logger.debug(f"Filtering by {estado_col} not in '{filter_values}'")
                df = df.filter(~pl.col(estado_col).is_in(filter_values))
                self.logger.info(f"Filtered to {len(df)} rows where {estado_col} != '{filter_values}'")
            else:
                self.logger.debug("No estado filtering applied")
            return df
        except Exception as e:
            self.logger.error(f"Error filtering by estado: {str(e)}")
            raise DataProcessorError(f"Failed to filter by estado: {str(e)}") from e

    def _fill_nulls_numeric(self, df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
        """
        Fill null values in numeric columns with configured fill value.

        Args:
            df (pl.DataFrame): Input DataFrame.
            columns (list[str]): List of numeric column names to fill.

        Returns:
            pl.DataFrame: DataFrame with nulls filled in numeric columns.

        Raises:
            DataProcessorError: If filling nulls fails.
        """
        try:
            fill_value = self.parameters.get("fill_null_value", 0)
            self.logger.debug(f"Filling nulls in numeric columns with value: {fill_value}")
            for col in columns:
                if col in df.columns:
                    df = df.with_columns(pl.col(col).fill_null(fill_value).alias(col))
            return df
        except Exception as e:
            self.logger.error(f"Error filling nulls in numeric columns: {str(e)}")
            raise DataProcessorError(f"Failed to fill nulls in numeric columns: {str(e)}") from e

    def _round_numeric_columns(self, df: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
        """
        Round numeric columns to configured decimal places.

        Args:
            df (pl.DataFrame): Input DataFrame.
            columns (list[str]): List of numeric column names to round.

        Returns:
            pl.DataFrame: DataFrame with rounded numeric columns.

        Raises:
            DataProcessorError: If rounding fails.
        """
        try:
            decimals = self.parameters.get("round_decimals", 2)
            self.logger.debug(f"Rounding numeric columns to {decimals} decimal places")
            for col in columns:
                if col in df.columns:
                    df = df.with_columns(pl.col(col).round(decimals).alias(col))
            return df
        except Exception as e:
            self.logger.error(f"Error rounding numeric columns: {str(e)}")
            raise DataProcessorError(f"Failed to round numeric columns: {str(e)}") from e

    def process_personal_asignado(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Process Personal Asignado dataset with cleaning, transformation, and aggregation.

        Performs the following operations:
        - Clean string columns
        - Create fallback clients
        - Filter invalid records
        - Aggregate by Cliente_Final, COD UNID, Servicio_Limpio
        - Fill nulls in numeric columns
        - Round numeric values
        - Standardize column names for merging

        Args:
            df (pl.DataFrame): Raw Personal Asignado DataFrame.

        Returns:
            pl.DataFrame: Processed and aggregated DataFrame ready for merging.

        Raises:
            DataProcessorError: If processing fails.
        """
        try:
            self.logger.info("Starting processing of Personal Asignado dataset")
            initial_rows = len(df)
            # Clean string columns
            string_columns = ["ESTADO", "COD CLIENTE", "COD UNID", "COD SERVICIO", "COD GRUPO",
                            "TIPO DE COMPAÑÍA", "CLIENTE", "UNIDAD", "TIPO DE SERVCIO", "GRUPO",
                            "LIDER ZONAL / COORDINADOR", "JEFE DE OPERACIONES", "GERENTE REGIONAL",
                            "SECTOR", "DEPARTAMENTO"]
            for col in string_columns:
                if col in df.columns:
                    df = self._clean_string_column(df, col)

            # Filter by estado if configured
            estado_filters = self.parameters.get("estado_pa_filter")
            df = self._filter_without_estados(df, "ESTADO", estado_filters)
            # Create Servicio_Limpio
            df = df.with_columns(
                pl.col("COD SERVICIO").str.strip_chars(" ").alias("Servicio_Limpio")
            )

            # Create fallback clients
            df = df.with_columns(
                pl.when(
                    pl.col("COD CLIENTE").is_not_null() & (pl.col("COD CLIENTE") != "")
                )
                .then(pl.col("COD CLIENTE"))
                .otherwise(pl.col("COD GRUPO"))
                .alias("Cliente_Final")
            )

            # Filter invalid records
            df = df.filter(
                pl.col("Cliente_Final").is_not_null() &
                (pl.col("Cliente_Final") != "-") &
                (pl.col("Cliente_Final") != "") &
                pl.col("COD UNID").is_not_null() &
                (pl.col("COD UNID") != "-") &
                (pl.col("COD UNID") != "") &
                pl.col("Servicio_Limpio").is_not_null() &
                (pl.col("Servicio_Limpio") != "") &
                (pl.col("Servicio_Limpio") != "-")
            )

            # Aggregate by group
            df = df.group_by(["Cliente_Final", "COD UNID", "Servicio_Limpio"]).agg([
                pl.len().alias("Personal_Real"),
                pl.col("TIPO DE COMPAÑÍA").first().alias("Compañía_PA"),
                pl.col("CLIENTE").first().alias("Nombre_Cliente_PA"),
                pl.col("UNIDAD").first().alias("Nombre_Unidad_PA"),
                pl.col("TIPO DE SERVCIO").first().alias("Nombre_Servicio_PA"),
                pl.col("COD GRUPO").first().alias("Codigo_Grupo_PA"),
                pl.col("GRUPO").first().alias("Nombre_Grupo_PA"),
                pl.col("LIDER ZONAL / COORDINADOR").first().alias("Lider_Zonal_PA"),
                pl.col("JEFE DE OPERACIONES").first().alias("Jefatura_PA"),
                pl.col("GERENTE REGIONAL").first().alias("Gerencia_PA"),
                pl.col("SECTOR").first().alias("Sector_PA"),
                pl.col("DEPARTAMENTO").first().alias("Departamento_PA"),
            ])

            # Fill nulls in numeric columns
            numeric_columns = ["Personal_Real"]
            df = self._fill_nulls_numeric(df, numeric_columns)

            # Round numeric columns
            df = self._round_numeric_columns(df, numeric_columns)

            final_rows = len(df)
            self.logger.info(f"Personal Asignado processing completed: {initial_rows} -> {final_rows} rows")
            return df

        except Exception as e:
            self.logger.error(f"Error processing Personal Asignado dataset: {str(e)}")
            raise DataProcessorError(f"Failed to process Personal Asignado dataset: {str(e)}") from e

    def process_servicio_vivo(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Process Servicio Vivo dataset with cleaning, transformation, and aggregation.

        Performs the following operations:
        - Filter by estado if configured
        - Clean string columns
        - Create fallback clients
        - Convert Unidad to string
        - Filter invalid records
        - Aggregate by Cliente_Final, Unidad_Str, Servicio_Limpio
        - Fill nulls in numeric columns
        - Round numeric values
        - Standardize column names for merging

        Args:
            df (pl.DataFrame): Raw Servicio Vivo DataFrame.

        Returns:
            pl.DataFrame: Processed and aggregated DataFrame ready for merging.

        Raises:
            DataProcessorError: If processing fails.
        """
        try:
            self.logger.info("Starting processing of Servicio Vivo dataset")
            initial_rows = len(df)

            # Filter by estado if configured
            estado_filter = self.parameters.get("estado_filter")
            df = self._filter_by_estado(df, "Estado", estado_filter)

            # Clean string columns
            string_columns = ["Estado", "Cliente", "Unidad", "Servicio", "Nombre Servicio", "Grupo",
                            "Compañía", "Nombre Cliente", "Nombre Unidad", "ZONA", "MACROZONA",
                            "Nombre Grupo", "LIDERZONAL", "JEFATURA", "GERENCIA", "SECTOR",
                            "Descripcion Departamento"]
            for col in string_columns:
                if col in df.columns:
                    df = self._clean_string_column(df, col)

            # Create Servicio_Limpio
            df = df.with_columns(
                pl.col("Servicio").str.strip_chars(" ").alias("Servicio_Limpio")
            )

            # Create fallback clients
            df = df.with_columns(
                pl.when(
                    pl.col("Cliente").is_not_null() & (pl.col("Cliente") != "")
                )
                .then(pl.col("Cliente"))
                .otherwise(pl.col("Grupo"))
                .alias("Cliente_Final")
            )

            # Convert Unidad to string
            df = df.with_columns(
                pl.col("Unidad").cast(pl.Utf8).alias("Unidad_Str")
            )

            # Filter invalid records
            df = df.filter(
                pl.col("Cliente_Final").is_not_null() &
                (pl.col("Cliente_Final") != "") &
                (pl.col("Cliente_Final") != "-") &
                pl.col("Unidad_Str").is_not_null() &
                (pl.col("Unidad_Str") != "") &
                (pl.col("Unidad_Str") != "-") &
                pl.col("Servicio_Limpio").is_not_null() &
                (pl.col("Servicio_Limpio") != "") &
                (pl.col("Servicio_Limpio") != "-")
            )

            # Aggregate by group
            df = df.group_by(["Cliente_Final", "Unidad_Str", "Servicio_Limpio"]).agg([
                pl.col("Q° PER. FACTOR - REQUERIDO").sum().alias("Personal_Estimado"),
                pl.col("TIPO DE PLANILLA").first().alias("Compañía_SV"),
                pl.col("Nombre Cliente").first().alias("Nombre_Cliente_SV"),
                pl.col("Nombre Unidad").first().alias("Nombre_Unidad_SV"),
                pl.col("Nombre Servicio").first().alias("Nombre_Servicio_SV"),
                pl.col("ZONA").first().alias("Zona_SV"),
                pl.col("MACROZONA").first().alias("Macrozona_SV"),
                pl.col("Grupo").first().alias("Codigo_Grupo_SV"),
                pl.col("Nombre Grupo").first().alias("Nombre_Grupo_SV"),
                pl.col("LÍDER ZONAL").first().alias("Lider_Zonal_SV"),
                pl.col("JEFE").first().alias("Jefatura_SV"),
                pl.col("GERENTE").first().alias("Gerencia_SV"),
                pl.col("SECTOR").first().alias("Sector_SV"),
                #pl.col("Descripcion Departamento").first().alias("Departamento_SV"),
            ])

            # Fill nulls in numeric columns
            numeric_columns = ["Personal_Estimado"]
            df = self._fill_nulls_numeric(df, numeric_columns)

            # Round numeric columns
            df = self._round_numeric_columns(df, numeric_columns)

            final_rows = len(df)
            self.logger.info(f"Servicio Vivo processing completed: {initial_rows} -> {final_rows} rows")
            return df

        except Exception as e:
            self.logger.error(f"Error processing Servicio Vivo dataset: {str(e)}")
            raise DataProcessorError(f"Failed to process Servicio Vivo dataset: {str(e)}") from e