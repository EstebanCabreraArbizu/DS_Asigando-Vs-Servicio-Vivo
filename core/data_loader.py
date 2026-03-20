"""
DataLoader module for loading and validating Excel datasets using Polars.

This module provides a DataLoader class that encapsulates the logic for loading
Personal Asignado and Servicio Vivo datasets with proper schema validation,
error handling, and logging.
"""

import logging
from typing import Any, TYPE_CHECKING

import polars as pl
from config import FILE_PATHS, SHEET_NAMES, HEADER_ROWS, EXCEL_SCHEMAS

if TYPE_CHECKING:
    # Solo para type hints — evita importación circular en runtime si fuera necesario
    from api_client import ServicioGeneralClient



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

    def load_servicio_vivo_from_api(
        self,
        client: "ServicioGeneralClient",
        secuencia_periodo: str,
        servicio_tareo: str,
        cliente: str,
        grupo_empresarial: str,
    ) -> pl.DataFrame:
        """
        Carga el dataset de Servicio Vivo desde la API REST ServicioGeneral
        en lugar de un archivo Excel.

        Es un reemplazo drop-in de load_servicio_vivo(): devuelve un DataFrame
        con el mismo esquema de columnas que espera AnalysisEngine.

        El DataFrame resultante combina:
          - ProgramacionxCliente (empleados + días programados por servicio)
          - UnidadesxCliente (catálogo de unidades con zona, gerente, jefe)

        El campo 'Q° PER. FACTOR - REQUERIDO' se calcula como el conteo de días
        marcados como 'D' (trabajado) en los campos dia1..dia31.
        Confirmar esta equivalencia con el equipo de negocio.

        Args:
            client: Instancia autenticada de ServicioGeneralClient.
            secuencia_periodo: ID del periodo de nómina (ej. '17').
            servicio_tareo: ID del servicio de tareo (ej. '1').
            cliente: Código de cliente para UnidadesxCliente (ej. '7006').
            grupo_empresarial: Código de grupo (ej. '0099').

        Returns:
            pl.DataFrame con el mismo esquema que load_servicio_vivo().

        Raises:
            DataLoaderError: Si la llamada a la API falla.

        Example:
            >>> from core.api_client import ServicioGeneralClient
            >>> from core.config import API_CONFIG
            >>> client = ServicioGeneralClient.from_config(API_CONFIG)
            >>> loader = DataLoader()
            >>> df_sv = loader.load_servicio_vivo_from_api(
            ...     client, secuencia_periodo="17", servicio_tareo="1",
            ...     cliente="7006", grupo_empresarial="0099"
            ... )
            >>> print(df_sv.schema)
        """
        # Importamos aquí para evitar dependencia circular en el módulo-nivel
        from api_transformer import programacion_to_sv_dataframe

        try:
            self.logger.info(
                "Cargando Servicio Vivo desde API — periodo=%s, servicio=%s",
                secuencia_periodo, servicio_tareo,
            )

            programacion = client.get_programacion(secuencia_periodo, servicio_tareo)
            self.logger.info("Programación obtenida: %d registros", len(programacion))

            unidades = client.get_unidades(cliente, grupo_empresarial)
            self.logger.info("Unidades obtenidas: %d registros", len(unidades))

            df = programacion_to_sv_dataframe(programacion, unidades)
            self.logger.info(
                "DataFrame SV (API) creado: %d filas, %d columnas",
                len(df), len(df.columns),
            )
            return df

        except Exception as exc:
            self.logger.error("Error cargando Servicio Vivo desde API: %s", exc)
            raise DataLoaderError(
                f"Error cargando Servicio Vivo desde API: {exc}"
            ) from exc

    def load_personal_asignado_from_api(
        self,
        client: "ServicioGeneralClient",
        secuencia_periodo: str,
        servicio_tareo: str,
        cliente: str,
        grupo_empresarial: str,
    ) -> pl.DataFrame:
        """
        Carga el dataset de Personal Asignado desde la API REST ServicioGeneral
        usando TareoxCliente como fuente, en lugar de un archivo Excel.

        Concepto clave:
            TareoxCliente = tareo real del periodo = "lo que hay efectivamente"
                          = equivalente al Excel de Personal Asignado (PA)

            ProgramacionxCliente = planificación = "lo que debería haber"
                                 = equivalente al Excel de Servicio Vivo (SV)

        El DataFrame resultante combina:
          - TareoxCliente  → empleados con días realmente trabajados por servicio
          - UnidadesxCliente → catálogo con nombre de unidad, zona, gerente, jefe

        Columnas del Excel PA no disponibles en la API (quedan vacías):
          - COD GRUPO, TIPO DE COMPAÑÍA, GRUPO
          (son catálogos internos del ERP, no expuestos por ServicioGeneral)

        Columnas adicionales que la API sí provee (diagnósticas):
          - COD EMPLEADO, NOMBRE EMPLEADO, DOCUMENTO, TIPO EMPLEADO, DIAS_TAREO

        Args:
            client: Instancia autenticada de ServicioGeneralClient.
            secuencia_periodo: ID del periodo de nómina (ej. '17').
            servicio_tareo: ID del servicio de tareo (ej. '1').
            cliente: Código de cliente para UnidadesxCliente (ej. '7006').
            grupo_empresarial: Código de grupo (ej. '0099').

        Returns:
            pl.DataFrame con columnas del PA_SCHEMA de api_transformer.py,
            compatible con las columnas core que espera analysis_engine.py.

        Raises:
            DataLoaderError: Si la llamada a la API falla.

        Example:
            >>> from core.api_client import ServicioGeneralClient
            >>> from core.config import API_CONFIG
            >>> client = ServicioGeneralClient.from_config(API_CONFIG)
            >>> loader = DataLoader()
            >>> df_pa = loader.load_personal_asignado_from_api(
            ...     client, secuencia_periodo="17", servicio_tareo="1",
            ...     cliente="7006", grupo_empresarial="0099"
            ... )
            >>> # Uso drop-in en lugar de load_personal_asignado():
            >>> # engine = AnalysisEngine()
            >>> # result = engine.perform_full_outer_join(df_pa, df_sv)
        """
        from api_transformer import tareo_to_pa_dataframe

        try:
            self.logger.info(
                "Cargando Personal Asignado desde API (TareoxCliente) — periodo=%s, servicio=%s",
                secuencia_periodo, servicio_tareo,
            )

            tareo = client.get_tareo(secuencia_periodo, servicio_tareo)
            self.logger.info("Tareo obtenido: %d registros", len(tareo))

            unidades = client.get_unidades(cliente, grupo_empresarial)
            self.logger.info("Unidades obtenidas: %d registros", len(unidades))

            df = tareo_to_pa_dataframe(tareo, unidades)
            self.logger.info(
                "DataFrame PA (API) creado: %d filas, %d columnas (%d empleados únicos)",
                len(df), len(df.columns), df["COD EMPLEADO"].n_unique(),
            )
            return df

        except Exception as exc:
            self.logger.error("Error cargando Personal Asignado desde API: %s", exc)
            raise DataLoaderError(
                f"Error cargando Personal Asignado desde API: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Métodos empresa-completa (toda la empresa, no solo un cliente)
    # ------------------------------------------------------------------

    def load_sv_empresa(
        self,
        client: "ServicioGeneralClient",
        secuencia_periodo: str,
        servicio_tareo: str,
    ) -> pl.DataFrame:
        """
        Carga Servicio Vivo (planificado) de TODA la empresa para un periodo dado.

        Combina:
          - ProgramacionxCliente  → empleados planificados del periodo (empresa completa)
          - get_all_unidades()    → catálogo completo de unidades via iteración por zonas

        El parámetro `secuencia_periodo` controla QUÉ MES/PERIODO se analiza.
        Para cambiar el periodo basta con pasar un valor diferente a este método
        (el frontend o la capa de negocio puede parametrizarlo libremente).

        Args:
            client: Instancia autenticada de ServicioGeneralClient.
            secuencia_periodo: ID del periodo (ej. '17' = Nov 2025, '16' = Oct 2025).
                              Este es el parámetro que cambia según el mes analizado.
            servicio_tareo: Tipo de servicio de tareo (ej. '1' = seguridad).

        Returns:
            pl.DataFrame con columnas según SV_SCHEMA, para toda la empresa.

        Example:
            >>> df_sv = loader.load_sv_empresa(client, secuencia_periodo="17", servicio_tareo="1")
            >>> df_sv_prev = loader.load_sv_empresa(client, secuencia_periodo="16", servicio_tareo="1")
        """
        from api_transformer import programacion_to_sv_dataframe

        try:
            self.logger.info(
                "Cargando SV empresa completa — periodo=%s, servicio=%s",
                secuencia_periodo, servicio_tareo,
            )

            # Paso 1: todas las unidades de la empresa (Zonas como pivot)
            todas_unidades = client.get_all_unidades()
            self.logger.info("Unidades totales empresa: %d", len(todas_unidades))

            # Paso 2: programación del periodo (ya devuelve toda la empresa)
            programacion = client.get_programacion(secuencia_periodo, servicio_tareo)
            self.logger.info("Programación obtenida: %d registros", len(programacion))

            # Paso 3: transformar a DataFrame con join por unidad
            df = programacion_to_sv_dataframe(programacion, todas_unidades)
            self.logger.info(
                "df_sv (empresa completa): %d filas | %d unidades únicas | periodo=%s",
                len(df), df["Unidad"].n_unique(), secuencia_periodo,
            )
            return df

        except Exception as exc:
            self.logger.error("Error en load_sv_empresa: %s", exc)
            raise DataLoaderError(f"Error en load_sv_empresa: {exc}") from exc

    def load_pa_empresa(
        self,
        client: "ServicioGeneralClient",
        secuencia_periodo: str,
        servicio_tareo: str,
    ) -> pl.DataFrame:
        """
        Carga Personal Asignado (tareo real) de TODA la empresa para un periodo dado.

        Combina:
          - TareoxCliente      → empleados con asistencia real del periodo (empresa completa)
          - get_all_unidades() → catálogo completo de unidades via iteración por zonas

        El parámetro `secuencia_periodo` controla QUÉ MES/PERIODO se analiza.
        Para cambiar la "fecha" del personal asignado, simplemente cambia este valor.

        Mapeo de periodos (referencial — confirmar con el equipo de nómina):
            '17' = Noviembre 2025
            '16' = Octubre 2025
            '15' = Setiembre 2025
            (la secuencia es mensual, incrementa por periodo de pago)

        Args:
            client: Instancia autenticada de ServicioGeneralClient.
            secuencia_periodo: ID del periodo (ej. '17').
            servicio_tareo: Tipo de servicio de tareo (ej. '1').

        Returns:
            pl.DataFrame con columnas según PA_SCHEMA, para toda la empresa.

        Example:
            >>> # Análisis actual (periodo 17)
            >>> df_pa = loader.load_pa_empresa(client, secuencia_periodo="17", servicio_tareo="1")
            >>>
            >>> # Análisis histórico (periodo 16 = mes anterior)
            >>> df_pa_anterior = loader.load_pa_empresa(client, secuencia_periodo="16", servicio_tareo="1")
        """
        from api_transformer import tareo_to_pa_dataframe

        try:
            self.logger.info(
                "Cargando PA empresa completa (TareoxCliente) — periodo=%s, servicio=%s",
                secuencia_periodo, servicio_tareo,
            )

            # Paso 1: todas las unidades de la empresa (reutilizable entre PA y SV))
            todas_unidades = client.get_all_unidades()
            self.logger.info("Unidades totales empresa: %d", len(todas_unidades))

            # Paso 2: tareo del periodo (ya devuelve toda la empresa)
            tareo = client.get_tareo(secuencia_periodo, servicio_tareo)
            self.logger.info("Tareo obtenido: %d registros", len(tareo))

            # Paso 3: transformar a DataFrame compatible PA
            df = tareo_to_pa_dataframe(tareo, todas_unidades)
            self.logger.info(
                "df_pa (empresa completa): %d filas | %d empleados únicos | %d unidades | periodo=%s",
                len(df), df["COD EMPLEADO"].n_unique(), df["COD UNID"].n_unique(), secuencia_periodo,
            )
            return df

        except Exception as exc:
            self.logger.error("Error en load_pa_empresa: %s", exc)
            raise DataLoaderError(f"Error en load_pa_empresa: {exc}") from exc

    def load_empresa_completa(
        self,
        client: "ServicioGeneralClient",
        secuencia_periodo: str,
        servicio_tareo: str = "1",
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
        """
        Carga PA y SV de toda la empresa en una sola llamada, reutilizando las unidades.

        Optimización: get_all_unidades() se llama UNA SOLA VEZ y se reutiliza
        para construir tanto df_pa (tareo real) como df_sv (programación).
        Esto reduce el número de requests a la API significativamente.

        Args:
            client: Instancia autenticada de ServicioGeneralClient.
            secuencia_periodo: ID del periodo a analizar (ej. '17').
            servicio_tareo: Tipo de servicio (default '1').

        Returns:
            Tuple (df_pa, df_sv) — ambos DataFrames para el periodo dado.

        Example:
            >>> df_pa, df_sv = loader.load_empresa_completa(client, secuencia_periodo="17")
            >>> engine = AnalysisEngine()
            >>> resultado = engine.perform_full_outer_join(df_pa, df_sv)
        """
        from api_transformer import tareo_to_pa_dataframe, programacion_to_sv_dataframe

        try:
            self.logger.info(
                "load_empresa_completa — periodo=%s, servicio=%s",
                secuencia_periodo, servicio_tareo,
            )

            # Una sola llamada compuesta para todas las unidades
            todas_unidades = client.get_all_unidades()
            self.logger.info("Unidades empresa: %d", len(todas_unidades))

            # Tareo y programación en el mismo periodo
            tareo = client.get_tareo(secuencia_periodo, servicio_tareo)
            programacion = client.get_programacion(secuencia_periodo, servicio_tareo)
            self.logger.info(
                "Tareo: %d registros | Programación: %d registros",
                len(tareo), len(programacion),
            )

            df_pa = tareo_to_pa_dataframe(tareo, todas_unidades)
            df_sv = programacion_to_sv_dataframe(programacion, todas_unidades)

            self.logger.info(
                "Empresa completa — df_pa: %d filas / df_sv: %d filas | periodo=%s",
                len(df_pa), len(df_sv), secuencia_periodo,
            )
            return df_pa, df_sv

        except Exception as exc:
            self.logger.error("Error en load_empresa_completa: %s", exc)
            raise DataLoaderError(f"Error en load_empresa_completa: {exc}") from exc

