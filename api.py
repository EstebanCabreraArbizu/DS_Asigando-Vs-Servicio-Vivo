"""
API REST para el análisis de Personal Asignado vs Servicio Vivo.

Esta API proporciona un endpoint para recibir dos archivos Excel (Personal Asignado y Servicio Vivo)
y retorna un archivo Excel consolidado con el análisis completo.

Uso:
    uvicorn api:app --reload --host 0.0.0.0 --port 8000

Endpoints:
    POST /api/v1/analyze - Recibe dos archivos Excel y retorna el consolidado
    GET /api/v1/health - Verifica el estado de la API
    GET /docs - Documentación Swagger UI
"""

import io
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import polars as pl
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Importar módulos existentes
from data_processor import DataProcessor, DataProcessorError
from analysis_engine import AnalysisEngine, AnalysisEngineError
from excel_exporter import ExcelExporter, ExportError
from config import SHEET_NAMES, HEADER_ROWS, EXCEL_SCHEMAS

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear aplicación FastAPI
app = FastAPI(
    title="API de Análisis Personal Asignado vs Servicio Vivo",
    description="""
    API REST para consolidar y analizar datos de Personal Asignado y Servicio Vivo.
    
    ## Funcionalidades
    
    * **Carga de archivos**: Recibe dos archivos Excel con datos de personal
    * **Procesamiento**: Limpia, transforma y agrega los datos
    * **Análisis**: Realiza joins, calcula métricas y detecta discrepancias
    * **Exportación**: Genera un archivo Excel consolidado con múltiples hojas
    
    ## Uso
    
    Envía una solicitud POST a `/api/v1/analyze` con dos archivos Excel:
    - `personal_asignado`: Archivo Excel con datos del personal asignado
    - `servicio_vivo`: Archivo Excel con datos del servicio vivo
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS para permitir acceso desde cualquier origen (ajustar en producción)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class APIDataLoader:
    """
    Cargador de datos adaptado para la API que recibe archivos en memoria.
    
    A diferencia del DataLoader original que lee desde rutas de archivo,
    este carga datos desde objetos UploadFile de FastAPI.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.APIDataLoader")

    def load_from_bytes(
        self,
        file_content: bytes,
        sheet_name: str,
        header_row: int,
        schema: Dict[str, Any]
    ) -> pl.DataFrame:
        """
        Carga un DataFrame desde bytes de un archivo Excel.
        
        Args:
            file_content: Contenido del archivo Excel en bytes
            sheet_name: Nombre de la hoja a cargar
            header_row: Fila donde inicia el header (0-based)
            schema: Esquema de tipos de columnas
            
        Returns:
            DataFrame de Polars con los datos cargados
        """
        try:
            self.logger.info(f"Cargando archivo Excel, hoja: {sheet_name}")
            
            # Crear archivo temporal para procesar
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                df = pl.read_excel(
                    tmp_path,
                    sheet_name=sheet_name,
                    engine='xlsx2csv',
                    read_options={
                        "skip_rows": header_row,
                        "null_values": ["--------", "-", "", "#N/A"],
                        "infer_schema_length": 10000,
                    },
                    schema_overrides=schema,
                )
                self.logger.info(f"Cargados {len(df)} registros exitosamente")
                return df
            finally:
                # Limpiar archivo temporal
                Path(tmp_path).unlink(missing_ok=True)
                
        except Exception as e:
            self.logger.error(f"Error cargando archivo Excel: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Error al cargar archivo Excel: {str(e)}"
            )

    def load_personal_asignado(self, file_content: bytes) -> pl.DataFrame:
        """Carga el dataset de Personal Asignado desde bytes."""
        return self.load_from_bytes(
            file_content,
            SHEET_NAMES["personal_asignado"],
            HEADER_ROWS["personal_asignado"],
            EXCEL_SCHEMAS["personal_asignado"]
        )

    def load_servicio_vivo(self, file_content: bytes) -> pl.DataFrame:
        """Carga el dataset de Servicio Vivo desde bytes."""
        return self.load_from_bytes(
            file_content,
            SHEET_NAMES["servicio_vivo"],
            HEADER_ROWS["servicio_vivo"],
            EXCEL_SCHEMAS["servicio_vivo"]
        )


class APIExcelExporter:
    """
    Exportador adaptado para la API que genera Excel en memoria.
    
    A diferencia del ExcelExporter original que escribe a disco,
    este genera el archivo Excel en un buffer de memoria para streaming.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.APIExcelExporter")
        self.exporter = ExcelExporter()

    def export_to_bytes(
        self,
        final_dataframe: pl.DataFrame,
        investigation_results: Dict[str, Any]
    ) -> bytes:
        """
        Exporta los resultados a un archivo Excel en memoria.
        
        Args:
            final_dataframe: DataFrame con los resultados del análisis
            investigation_results: Diccionario con resultados de investigación
            
        Returns:
            Bytes del archivo Excel generado
        """
        try:
            self.logger.info("Generando archivo Excel en memoria")
            
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
                tmp_path = tmp_file.name
            
            try:
                # Usar el exportador existente
                self.exporter.export_to_excel(
                    final_dataframe,
                    investigation_results,
                    output_path=tmp_path
                )
                
                # Leer bytes del archivo
                with open(tmp_path, 'rb') as f:
                    excel_bytes = f.read()
                
                self.logger.info(f"Archivo Excel generado: {len(excel_bytes)} bytes")
                return excel_bytes
                
            finally:
                # Limpiar archivo temporal
                Path(tmp_path).unlink(missing_ok=True)
                
        except Exception as e:
            self.logger.error(f"Error generando archivo Excel: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error al generar archivo Excel: {str(e)}"
            )


# Instanciar componentes
api_data_loader = APIDataLoader()
data_processor = DataProcessor()
analysis_engine = AnalysisEngine()
api_excel_exporter = APIExcelExporter()


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Verifica el estado de la API.
    
    Returns:
        Estado de la API con timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "components": {
            "data_loader": "ready",
            "data_processor": "ready",
            "analysis_engine": "ready",
            "excel_exporter": "ready"
        }
    }


@app.post("/api/v1/analyze", tags=["Analysis"], response_model=None)
async def analyze_files(
    personal_asignado: UploadFile = File(..., description="Archivo Excel con Personal Asignado"),
    servicio_vivo: UploadFile = File(..., description="Archivo Excel con Servicio Vivo"),
    return_json: bool = Query(False, description="Si es True, retorna JSON en lugar de Excel")
):
    """
    Analiza los archivos de Personal Asignado y Servicio Vivo.
    
    Recibe dos archivos Excel, los procesa, realiza el análisis comparativo
    y retorna un archivo Excel consolidado con múltiples hojas:
    - Resultado_Final: Dataset completo con métricas calculadas
    - Estadisticas: Resumen estadístico del análisis
    - Investigacion: Análisis de casos especiales y registros faltantes
    
    Args:
        personal_asignado: Archivo Excel con datos del personal asignado
        servicio_vivo: Archivo Excel con datos del servicio vivo
        return_json: Si es True, retorna resumen en JSON en lugar de Excel
        
    Returns:
        Archivo Excel consolidado o JSON con resumen del análisis
        
    Raises:
        HTTPException: Si hay errores en el procesamiento
    """
    logger.info("Iniciando análisis de archivos")
    
    # Validar tipos de archivo
    for file, name in [(personal_asignado, "personal_asignado"), (servicio_vivo, "servicio_vivo")]:
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=400,
                detail=f"El archivo {name} debe ser un archivo Excel (.xlsx o .xls)"
            )
    
    try:
        # Leer contenido de los archivos
        logger.info(f"Leyendo archivo Personal Asignado: {personal_asignado.filename}")
        pa_content = await personal_asignado.read()
        
        logger.info(f"Leyendo archivo Servicio Vivo: {servicio_vivo.filename}")
        sv_content = await servicio_vivo.read()
        
        # Cargar datasets
        logger.info("Cargando datasets...")
        df_pa = api_data_loader.load_personal_asignado(pa_content)
        df_sv = api_data_loader.load_servicio_vivo(sv_content)
        
        logger.info(f"Personal Asignado: {len(df_pa)} registros")
        logger.info(f"Servicio Vivo: {len(df_sv)} registros")
        
        # Procesar datasets
        logger.info("Procesando datasets...")
        try:
            pa_processed = data_processor.process_personal_asignado(df_pa)
            sv_processed = data_processor.process_servicio_vivo(df_sv)
        except DataProcessorError as e:
            raise HTTPException(status_code=400, detail=f"Error en procesamiento: {str(e)}")
        
        logger.info(f"Personal procesado: {len(pa_processed)} registros agrupados")
        logger.info(f"Servicio procesado: {len(sv_processed)} registros agrupados")
        
        # Ejecutar análisis
        logger.info("Ejecutando análisis...")
        try:
            resultado_final, investigation_results = analysis_engine.run_analysis(
                pa_processed, sv_processed, df_pa, df_sv
            )
        except AnalysisEngineError as e:
            raise HTTPException(status_code=500, detail=f"Error en análisis: {str(e)}")
        
        logger.info(f"Análisis completado: {len(resultado_final)} servicios analizados")
        
        # Retornar JSON si se solicita
        if return_json:
            metadata = investigation_results.get('analysis_metadata', {})
            summary = investigation_results.get('summary_stats', {})
            
            return JSONResponse(content={
                "status": "success",
                "message": "Análisis completado exitosamente",
                "resumen": {
                    "total_servicios": metadata.get('total_services_analyzed', 0),
                    "personal_real_total": metadata.get('total_personal_real', 0),
                    "personal_estimado_total": metadata.get('total_personal_estimado', 0),
                    "diferencia_total": metadata.get('total_diferencia', 0),
                    "registros_completos": summary.get('complete_records', 0),
                    "completitud_porcentaje": summary.get('completeness_percentage', 0),
                    "faltantes_en_pa": summary.get('missing_in_pa_count', 0),
                    "faltantes_en_sv": summary.get('missing_in_sv_count', 0)
                },
                "distribucion_estados": resultado_final.group_by("Estado").agg(
                    pl.len().alias("cantidad")
                ).sort("cantidad", descending=True).to_dicts(),
                "timestamp": datetime.now().isoformat()
            })
        
        # Generar Excel
        logger.info("Generando archivo Excel consolidado...")
        try:
            excel_bytes = api_excel_exporter.export_to_bytes(resultado_final, investigation_results)
        except ExportError as e:
            raise HTTPException(status_code=500, detail=f"Error en exportación: {str(e)}")
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Analisis_PA_vs_SV_{timestamp}.xlsx"
        
        logger.info(f"Análisis completado exitosamente, retornando: {filename}")
        
        # Retornar archivo como streaming response
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(excel_bytes))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error inesperado durante el análisis: {str(e)}"
        )


@app.get("/api/v1/config", tags=["Configuration"])
async def get_configuration() -> Dict[str, Any]:
    """
    Retorna la configuración actual del sistema.
    
    Returns:
        Configuración de hojas Excel, headers y parámetros
    """
    from config import PARAMETERS, OUTPUT_SHEETS
    
    return {
        "sheet_names": SHEET_NAMES,
        "header_rows": HEADER_ROWS,
        "parameters": PARAMETERS,
        "output_sheets": OUTPUT_SHEETS
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
