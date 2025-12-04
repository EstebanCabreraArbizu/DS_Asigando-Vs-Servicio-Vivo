"""
DataLoader module for loading and validating Excel datasets using Polars.

This module provides a DataLoader class that encapsulates the logic for loading
Personal Asignado and Servicio Vivo datasets with proper schema validation,
error handling, and logging.
"""

import logging
from typing import Any

import polars as pl
from config import FILE_PATHS, SHEET_NAMES, HEADER_ROWS, EXCEL_SCHEMAS


class DataLoaderError(Exception):
    """
    Base exception for DataLoader errors.

    This is the parent class for all custom exceptions raised by the DataLoader class.
    """
    pass


class FileLoadError(DataLoaderError):
    """
    Exception raised when file loading fails.

    This exception is raised when there is an issue reading the Excel file,
    such as file not found or corrupted file.
    """
    pass


class SchemaValidationError(DataLoaderError):
    """
    Exception raised when schema validation fails.

    This exception is raised when the loaded DataFrame does not match the expected schema.
    """
    pass


class DataLoader:
    """
    DataLoader class for loading and validating Excel datasets using Polars.

    This class encapsulates the logic for loading Personal Asignado and Servicio Vivo
    datasets with proper schema validation, error handling, and logging. It uses
    configuration from config.py for file paths, sheet names, header rows, and schemas.

    Attributes:
        logger (logging.Logger): Logger instance for logging operations and errors.
    """

    def __init__(self):
        """
        Initialize the DataLoader instance.

        Sets up the logger with INFO level and a stream handler for console output.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)

    def _load_excel(self, file_path: str, sheet_name: str, header_row: int, schema: dict[str, Any]) -> pl.DataFrame:
        """
        Private method to load an Excel file using Polars with schema validation.

        This method handles the loading of Excel files, skipping the specified header rows,
        and applying the expected schema for type casting and validation.

        Args:
            file_path (str): Path to the Excel file.
            sheet_name (str): Name of the sheet to load.
            header_row (int): Number of rows to skip before the header (0-based).
            schema (dict[str, str]): Expected schema mapping column names to data types.

        Returns:
            pl.DataFrame: Loaded and validated Polars DataFrame.

        Raises:
            FileLoadError: If the file cannot be loaded (e.g., file not found, corrupted).
            SchemaValidationError: If the schema does not match the expected structure.
        """
        try:
            self.logger.info(f"Loading Excel file: {file_path}, sheet: {sheet_name}")
            df = pl.read_excel(
                file_path,
                sheet_name=sheet_name,
                engine='xlsx2csv',
                read_options={
                    "skip_rows": header_row,
                    "null_values": ["--------","-", "", "#N/A"],
                    "infer_schema_length": 10000,
                },
                schema_overrides=schema,
            )
            self.logger.info(f"Successfully loaded {len(df)} rows from {file_path}")
            return df
        except FileNotFoundError as e:
            self.logger.error(f"File not found: {file_path}")
            raise FileLoadError(f"File not found: {file_path}") from e
        except pl.exceptions.SchemaError as e:
            self.logger.error(f"Schema validation failed for {file_path}: {str(e)}")
            raise SchemaValidationError(f"Schema validation failed: {str(e)}") from e
        except Exception as e:
            self.logger.error(f"Error loading Excel file {file_path}: {str(e)}")
            raise FileLoadError(f"Error loading Excel file: {str(e)}") from e

    def load_personal_asignado(self) -> pl.DataFrame:
        """
        Load the Personal Asignado dataset.

        This method loads the Personal Asignado Excel file using the configuration
        from config.py, performs schema validation, and returns a validated Polars DataFrame.

        Returns:
            pl.DataFrame: Validated DataFrame containing Personal Asignado data.

        Raises:
            DataLoaderError: If loading or validation fails.
        """
        file_path = FILE_PATHS["personal_asignado"]
        sheet_name = SHEET_NAMES["personal_asignado"]
        header_row = HEADER_ROWS["personal_asignado"]
        schema = EXCEL_SCHEMAS["personal_asignado"]
        return self._load_excel(file_path, sheet_name, header_row, schema)

    def load_servicio_vivo(self) -> pl.DataFrame:
        """
        Load the Servicio Vivo dataset.

        This method loads the Servicio Vivo Excel file using the configuration
        from config.py, performs schema validation, and returns a validated Polars DataFrame.

        Returns:
            pl.DataFrame: Validated DataFrame containing Servicio Vivo data.

        Raises:
            DataLoaderError: If loading or validation fails.
        """
        file_path = FILE_PATHS["servicio_vivo"]
        sheet_name = SHEET_NAMES["servicio_vivo"]
        header_row = HEADER_ROWS["servicio_vivo"]
        schema = EXCEL_SCHEMAS["servicio_vivo"]
        return self._load_excel(file_path, sheet_name, header_row, schema)