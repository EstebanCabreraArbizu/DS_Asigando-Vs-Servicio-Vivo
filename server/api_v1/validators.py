"""
Validadores de seguridad para archivos subidos.

Implementa validación según OWASP File Upload Cheat Sheet:
- Validación de tipos MIME
- Verificación de extensiones permitidas
- Detección de contenido malicioso
- Límites de tamaño
- Sanitización de nombres de archivo
"""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
import re
import uuid
from typing import BinaryIO

from django.core.exceptions import ValidationError

logger = logging.getLogger("security")


# Tipos de archivo permitidos para el sistema PA vs SV
ALLOWED_EXTENSIONS = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}

# Firmas mágicas (magic bytes) para validar el contenido real del archivo
MAGIC_SIGNATURES = {
    # CSV no tiene firma específica, se valida por contenido
    # XLSX (es un ZIP con estructura específica)
    ".xlsx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],
    # XLS (formato binario antiguo de Excel)
    ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
}

# Patrones peligrosos en nombres de archivo
DANGEROUS_PATTERNS = [
    r"\.\.",           # Path traversal
    r"[<>:\"|?*]",     # Caracteres inválidos en Windows
    r"[\x00-\x1f]",    # Caracteres de control
    r"^\.+$",          # Solo puntos
    r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\.|$)",  # Nombres reservados en Windows
]

# Tamaño máximo de archivo (50 MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


class FileValidator:
    """
    Validador integral de archivos subidos.
    
    Uso:
        validator = FileValidator(file)
        validator.validate()  # Lanza ValidationError si hay problemas
        safe_name = validator.get_safe_filename()
    """
    
    def __init__(
        self,
        file: BinaryIO,
        allowed_extensions: dict[str, str] | None = None,
        max_size: int = MAX_FILE_SIZE,
    ):
        self.file = file
        self.allowed_extensions = allowed_extensions or ALLOWED_EXTENSIONS
        self.max_size = max_size
        self.original_name = getattr(file, "name", "unknown")
        self._file_hash: str | None = None
    
    def validate(self) -> None:
        """
        Ejecuta todas las validaciones de seguridad.
        
        Raises:
            ValidationError: Si el archivo no pasa alguna validación.
        """
        self._validate_filename()
        self._validate_extension()
        self._validate_size()
        self._validate_content_type()
        self._validate_magic_bytes()
        self._scan_for_malicious_content()
        
        logger.info(
            f"Archivo validado exitosamente: {self.original_name}, "
            f"hash: {self.get_file_hash()}"
        )
    
    def _validate_filename(self) -> None:
        """Valida que el nombre del archivo no contenga patrones peligrosos."""
        filename = self.original_name
        
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                logger.warning(f"Nombre de archivo peligroso detectado: {filename}")
                raise ValidationError(
                    "El nombre del archivo contiene caracteres no permitidos."
                )
        
        # Verificar longitud del nombre
        if len(filename) > 255:
            raise ValidationError(
                "El nombre del archivo es demasiado largo (máximo 255 caracteres)."
            )
    
    def _validate_extension(self) -> None:
        """Valida que la extensión del archivo esté en la lista permitida."""
        _, ext = os.path.splitext(self.original_name.lower())
        
        if ext not in self.allowed_extensions:
            logger.warning(
                f"Extensión de archivo no permitida: {ext}, "
                f"archivo: {self.original_name}"
            )
            raise ValidationError(
                f"Tipo de archivo no permitido. Extensiones válidas: "
                f"{', '.join(self.allowed_extensions.keys())}"
            )
    
    def _validate_size(self) -> None:
        """Valida que el archivo no exceda el tamaño máximo."""
        # Intentar obtener el tamaño del archivo
        try:
            self.file.seek(0, 2)  # Ir al final
            size = self.file.tell()
            self.file.seek(0)  # Volver al inicio
        except (AttributeError, OSError):
            size = len(self.file.read())
            self.file.seek(0)
        
        if size > self.max_size:
            logger.warning(
                f"Archivo demasiado grande: {size} bytes, "
                f"máximo: {self.max_size} bytes"
            )
            raise ValidationError(
                f"El archivo excede el tamaño máximo permitido "
                f"({self.max_size // (1024 * 1024)} MB)."
            )
        
        if size == 0:
            raise ValidationError("El archivo está vacío.")
    
    def _validate_content_type(self) -> None:
        """Valida el Content-Type del archivo."""
        _, ext = os.path.splitext(self.original_name.lower())
        expected_mime = self.allowed_extensions.get(ext)
        
        # Obtener el content type del archivo si está disponible
        content_type = getattr(self.file, "content_type", None)
        
        if content_type and expected_mime:
            # Permitir variaciones comunes de MIME types
            if not self._mime_matches(content_type, expected_mime):
                logger.warning(
                    f"Content-Type no coincide: recibido={content_type}, "
                    f"esperado={expected_mime}"
                )
                # No fallar automáticamente, ya que el navegador puede enviar
                # tipos MIME incorrectos. La validación de magic bytes es más confiable.
    
    def _validate_magic_bytes(self) -> None:
        """
        Valida que los primeros bytes del archivo coincidan con el tipo esperado.
        Esta es la validación más confiable del tipo real de archivo.
        """
        _, ext = os.path.splitext(self.original_name.lower())
        
        # CSV no tiene firma mágica, se valida de otra forma
        if ext == ".csv":
            self._validate_csv_content()
            return
        
        signatures = MAGIC_SIGNATURES.get(ext, [])
        if not signatures:
            return
        
        # Leer los primeros bytes
        self.file.seek(0)
        header = self.file.read(8)
        self.file.seek(0)
        
        # Verificar si coincide con alguna firma válida
        is_valid = any(header.startswith(sig) for sig in signatures)
        
        if not is_valid:
            logger.warning(
                f"Magic bytes no coinciden para {ext}: {header[:16].hex()}"
            )
            raise ValidationError(
                "El contenido del archivo no coincide con su extensión. "
                "Por favor, suba un archivo válido."
            )
    
    def _validate_csv_content(self) -> None:
        """Validación específica para archivos CSV."""
        self.file.seek(0)
        
        try:
            # Leer las primeras líneas para verificar estructura CSV
            sample = self.file.read(4096)
            self.file.seek(0)
            
            # Intentar decodificar como texto
            try:
                text = sample.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = sample.decode("latin-1")
                except UnicodeDecodeError:
                    raise ValidationError(
                        "El archivo CSV no tiene una codificación de texto válida."
                    )
            
            # Verificar que tenga estructura de CSV (al menos una coma o punto y coma)
            if "," not in text and ";" not in text and "\t" not in text:
                raise ValidationError(
                    "El archivo no parece ser un CSV válido."
                )
            
            # Verificar que no contenga código ejecutable
            dangerous_patterns = [
                "<?php", "<%", "<script", "javascript:", "eval(", "exec(",
            ]
            text_lower = text.lower()
            for pattern in dangerous_patterns:
                if pattern in text_lower:
                    logger.warning(f"Patrón peligroso en CSV: {pattern}")
                    raise ValidationError(
                        "El archivo contiene contenido no permitido."
                    )
                    
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validando CSV: {e}")
            raise ValidationError("Error al validar el archivo CSV.")
    
    def _scan_for_malicious_content(self) -> None:
        """
        Escanea el archivo en busca de contenido potencialmente malicioso.
        
        Esto es una primera línea de defensa; en producción se recomienda
        integrar con un antivirus como ClamAV.
        """
        self.file.seek(0)
        content = self.file.read()
        self.file.seek(0)
        
        # Patrones de contenido malicioso
        malicious_patterns = [
            b"<?php",           # PHP code
            b"<%",              # ASP code
            b"<script",         # JavaScript
            b"javascript:",     # JavaScript URL
            b"vbscript:",       # VBScript URL
            b"data:text/html",  # Data URL con HTML
            b"eval(",           # JavaScript eval
            b"exec(",           # Ejecución de comandos
            b"system(",         # Ejecución de comandos
            b"powershell",      # PowerShell commands
            b"cmd.exe",         # Windows command
            b"/bin/sh",         # Unix shell
            b"/bin/bash",       # Bash shell
        ]
        
        content_lower = content.lower()
        for pattern in malicious_patterns:
            if pattern in content_lower:
                logger.warning(
                    f"Contenido malicioso detectado en {self.original_name}: {pattern}"
                )
                raise ValidationError(
                    "El archivo contiene contenido potencialmente peligroso."
                )
    
    def _mime_matches(self, received: str, expected: str) -> bool:
        """Verifica si los MIME types coinciden (con tolerancia)."""
        # Normalizar
        received = received.lower().split(";")[0].strip()
        expected = expected.lower()
        
        if received == expected:
            return True
        
        # Variaciones comunes
        variations = {
            "application/vnd.ms-excel": [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/octet-stream",
            ],
            "text/csv": [
                "text/plain",
                "application/csv",
                "application/vnd.ms-excel",
            ],
        }
        
        return received in variations.get(expected, [])
    
    def get_file_hash(self) -> str:
        """Calcula y retorna el hash SHA-256 del archivo."""
        if self._file_hash is None:
            self.file.seek(0)
            hasher = hashlib.sha256()
            for chunk in iter(lambda: self.file.read(8192), b""):
                hasher.update(chunk)
            self.file.seek(0)
            self._file_hash = hasher.hexdigest()
        return self._file_hash
    
    def get_safe_filename(self) -> str:
        """
        Genera un nombre de archivo seguro.
        
        Formato: {uuid}_{sanitized_original_name}.{extension}
        """
        # Obtener extensión original
        _, ext = os.path.splitext(self.original_name)
        ext = ext.lower()
        
        # Sanitizar nombre original (solo alfanuméricos y guiones)
        base_name = os.path.splitext(self.original_name)[0]
        safe_base = re.sub(r"[^a-zA-Z0-9_-]", "_", base_name)
        safe_base = safe_base[:50]  # Limitar longitud
        
        # Generar nombre único
        unique_id = uuid.uuid4().hex[:12]
        
        return f"{unique_id}_{safe_base}{ext}"


def validate_uploaded_file(file: BinaryIO) -> str:
    """
    Función de conveniencia para validar un archivo subido.
    
    Args:
        file: Archivo a validar
        
    Returns:
        Nombre de archivo seguro
        
    Raises:
        ValidationError: Si el archivo no es válido
    """
    validator = FileValidator(file)
    validator.validate()
    return validator.get_safe_filename()
