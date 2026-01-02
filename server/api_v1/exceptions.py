"""
Custom exception handler para respuestas de error consistentes.
"""
from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class StorageError(APIException):
    """Error relacionado con el almacenamiento de archivos."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Error en el servicio de almacenamiento."
    default_code = "storage_error"


class TenantNotFoundError(APIException):
    """Tenant no encontrado."""
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Tenant no encontrado."
    default_code = "tenant_not_found"


class TenantAccessDenied(APIException):
    """Usuario no tiene acceso al tenant."""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "No tienes acceso a este tenant."
    default_code = "tenant_access_denied"


class FileUploadError(APIException):
    """Error al subir archivo."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Error al subir el archivo."
    default_code = "file_upload_error"


class AnalysisJobError(APIException):
    """Error en el job de análisis."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Error al procesar el análisis."
    default_code = "analysis_error"


def custom_exception_handler(exc, context):
    """
    Handler personalizado que formatea todas las excepciones de manera consistente.
    
    Formato de respuesta:
    {
        "error": {
            "code": "error_code",
            "message": "Mensaje descriptivo",
            "details": {...}  # Opcional
        }
    }
    """
    # Primero, usar el handler por defecto de DRF
    response = exception_handler(exc, context)
    
    if response is not None:
        # Reformatear la respuesta
        error_data = {
            "error": {
                "code": getattr(exc, "default_code", "error"),
                "message": str(exc.detail) if hasattr(exc, "detail") else str(exc),
            }
        }
        
        # Si hay múltiples errores (validación), incluirlos en details
        if hasattr(exc, "detail") and isinstance(exc.detail, dict):
            error_data["error"]["details"] = exc.detail
            error_data["error"]["message"] = "Error de validación"
        
        response.data = error_data
        
        # Logging
        if response.status_code >= 500:
            logger.error(
                f"Server Error: {exc}",
                exc_info=True,
                extra={"request": context.get("request")}
            )
        elif response.status_code >= 400:
            logger.warning(
                f"Client Error: {exc}",
                extra={"request": context.get("request")}
            )
    
    return response


class ErrorResponse:
    """Helper para crear respuestas de error consistentes."""
    
    @staticmethod
    def not_found(message: str = "Recurso no encontrado", code: str = "not_found"):
        return Response(
            {"error": {"code": code, "message": message}},
            status=status.HTTP_404_NOT_FOUND
        )
    
    @staticmethod
    def forbidden(message: str = "Acceso denegado", code: str = "forbidden"):
        return Response(
            {"error": {"code": code, "message": message}},
            status=status.HTTP_403_FORBIDDEN
        )
    
    @staticmethod
    def bad_request(message: str = "Solicitud inválida", code: str = "bad_request", details: dict = None):
        error = {"code": code, "message": message}
        if details:
            error["details"] = details
        return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
    
    @staticmethod
    def server_error(message: str = "Error interno del servidor", code: str = "server_error"):
        return Response(
            {"error": {"code": code, "message": message}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
