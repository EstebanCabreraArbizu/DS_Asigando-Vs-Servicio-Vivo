"""
Servicio de almacenamiento de archivos compatible con S3/MinIO.

Este módulo proporciona una abstracción sobre el almacenamiento de archivos
que funciona tanto con MinIO (desarrollo/staging) como con AWS S3 (producción).

Características:
- Upload/download de archivos
- URLs prefirmadas para descarga segura
- Eliminación de archivos
- Listado de objetos
- Soporte para múltiples buckets (inputs, artifacts, exports)
"""
from __future__ import annotations

import logging
import mimetypes
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


class StorageService:
    """
    Servicio de almacenamiento abstracto compatible con S3/MinIO.
    
    Uso:
        storage = StorageService()
        
        # Subir archivo
        url = storage.upload_file(
            file=request.FILES["file"],
            path="tenants/default/jobs/123/inputs/pa.xlsx",
            bucket_type="inputs"
        )
        
        # Obtener URL prefirmada
        url = storage.get_presigned_url("tenants/default/jobs/123/artifacts/result.xlsx")
        
        # Eliminar archivo
        storage.delete_file("tenants/default/jobs/123/inputs/pa.xlsx")
    """
    
    BUCKET_TYPES = {
        "inputs": "inputs",      # Archivos de entrada (PA, SV)
        "artifacts": "default",  # Resultados procesados
        "exports": "exports",    # Exportaciones para descarga
    }
    
    def __init__(self):
        self.use_s3 = getattr(settings, "USE_S3_STORAGE", False)
        
        if self.use_s3:
            import boto3
            from botocore.config import Config
            
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
                config=Config(signature_version=getattr(settings, "AWS_S3_SIGNATURE_VERSION", "s3v4"))
            )
            
            self.buckets = {
                "inputs": getattr(settings, "AWS_INPUTS_BUCKET", "pavssv-inputs"),
                "artifacts": getattr(settings, "AWS_STORAGE_BUCKET_NAME", "pavssv-artifacts"),
                "exports": getattr(settings, "AWS_EXPORTS_BUCKET", "pavssv-exports"),
                "default": getattr(settings, "AWS_STORAGE_BUCKET_NAME", "pavssv-artifacts"),
            }
    
    def _get_bucket(self, bucket_type: str = "default") -> str:
        """Obtiene el nombre del bucket según el tipo."""
        if not self.use_s3:
            return "local"
        return self.buckets.get(bucket_type, self.buckets["default"])
    
    def _get_storage(self, bucket_type: str = "default"):
        """Obtiene el storage backend apropiado."""
        from django.core.files.storage import storages
        
        if not self.use_s3:
            return default_storage
        
        storage_key = self.BUCKET_TYPES.get(bucket_type, "default")
        try:
            return storages[storage_key]
        except KeyError:
            return default_storage
    
    def upload_file(
        self,
        file: BinaryIO,
        path: str,
        bucket_type: str = "default",
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Sube un archivo al storage.
        
        Args:
            file: Archivo a subir (puede ser un file-like object o bytes)
            path: Ruta donde guardar el archivo (ej: tenants/default/jobs/123/inputs/pa.xlsx)
            bucket_type: Tipo de bucket (inputs, artifacts, exports, default)
            content_type: Tipo MIME del archivo
            metadata: Metadatos adicionales para el archivo
            
        Returns:
            URL o ruta del archivo subido
        """
        try:
            if self.use_s3:
                return self._upload_to_s3(file, path, bucket_type, content_type, metadata)
            else:
                return self._upload_to_local(file, path)
        except Exception as e:
            logger.error(f"Error uploading file to {path}: {e}")
            raise StorageException(f"Error al subir archivo: {e}")
    
    def _upload_to_s3(
        self,
        file: BinaryIO,
        path: str,
        bucket_type: str,
        content_type: str | None,
        metadata: dict | None,
    ) -> str:
        """Sube archivo a S3/MinIO."""
        bucket = self._get_bucket(bucket_type)
        
        # Detectar content type si no se proporciona
        if not content_type:
            content_type, _ = mimetypes.guess_type(path)
            content_type = content_type or "application/octet-stream"
        
        extra_args = {
            "ContentType": content_type,
        }
        
        if metadata:
            extra_args["Metadata"] = {str(k): str(v) for k, v in metadata.items()}
        
        # Si es un file-like object, leer bytes
        if hasattr(file, "read"):
            file_content = file.read()
            file.seek(0)  # Reset for potential reuse
        else:
            file_content = file
        
        self.s3_client.put_object(
            Bucket=bucket,
            Key=path,
            Body=file_content,
            **extra_args
        )
        
        logger.info(f"File uploaded to s3://{bucket}/{path}")
        return f"s3://{bucket}/{path}"
    
    def _upload_to_local(self, file: BinaryIO, path: str) -> str:
        """Sube archivo al sistema de archivos local."""
        if hasattr(file, "read"):
            content = ContentFile(file.read())
        else:
            content = ContentFile(file)
        
        saved_path = default_storage.save(path, content)
        logger.info(f"File uploaded to local: {saved_path}")
        return saved_path
    
    def download_file(self, path: str, bucket_type: str = "default") -> BytesIO:
        """
        Descarga un archivo del storage.
        
        Args:
            path: Ruta del archivo
            bucket_type: Tipo de bucket
            
        Returns:
            BytesIO con el contenido del archivo
        """
        try:
            if self.use_s3:
                return self._download_from_s3(path, bucket_type)
            else:
                return self._download_from_local(path)
        except Exception as e:
            logger.error(f"Error downloading file from {path}: {e}")
            raise StorageException(f"Error al descargar archivo: {e}")
    
    def _download_from_s3(self, path: str, bucket_type: str) -> BytesIO:
        """Descarga archivo de S3/MinIO."""
        bucket = self._get_bucket(bucket_type)
        
        response = self.s3_client.get_object(Bucket=bucket, Key=path)
        return BytesIO(response["Body"].read())
    
    def _download_from_local(self, path: str) -> BytesIO:
        """Descarga archivo del sistema local."""
        with default_storage.open(path, "rb") as f:
            return BytesIO(f.read())
    
    def get_presigned_url(
        self,
        path: str,
        bucket_type: str = "default",
        expires_in: int = 3600,
        response_content_type: str | None = None,
        response_filename: str | None = None,
    ) -> str:
        """
        Genera una URL prefirmada para descarga segura.
        
        Args:
            path: Ruta del archivo
            bucket_type: Tipo de bucket
            expires_in: Tiempo de expiración en segundos (default: 1 hora)
            response_content_type: Content-Type para la respuesta
            response_filename: Nombre del archivo en la descarga
            
        Returns:
            URL prefirmada
        """
        if not self.use_s3:
            # Para storage local, retornar URL relativa
            return f"{settings.MEDIA_URL}{path}"
        
        bucket = self._get_bucket(bucket_type)
        
        params = {
            "Bucket": bucket,
            "Key": path,
        }
        
        response_params = {}
        if response_content_type:
            response_params["ResponseContentType"] = response_content_type
        if response_filename:
            response_params["ResponseContentDisposition"] = f'attachment; filename="{response_filename}"'
        
        if response_params:
            params["ResponseContentType"] = response_params.get("ResponseContentType")
            params["ResponseContentDisposition"] = response_params.get("ResponseContentDisposition")
        
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={k: v for k, v in params.items() if v is not None},
                ExpiresIn=expires_in,
            )
            
            # Si se definió una URL pública diferente a la interna (ej: localhost vs minio en docker)
            # Reemplazar la base de la URL
            public_url = getattr(settings, "AWS_S3_PUBLIC_URL", None)
            internal_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
            
            if public_url and internal_url and public_url != internal_url:
                url = url.replace(internal_url, public_url)
                
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL for {path}: {e}")
            raise StorageException(f"Error al generar URL de descarga: {e}")
    
    def delete_file(self, path: str, bucket_type: str = "default") -> bool:
        """
        Elimina un archivo del storage.
        
        Args:
            path: Ruta del archivo
            bucket_type: Tipo de bucket
            
        Returns:
            True si se eliminó exitosamente
        """
        try:
            if self.use_s3:
                return self._delete_from_s3(path, bucket_type)
            else:
                return self._delete_from_local(path)
        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}")
            raise StorageException(f"Error al eliminar archivo: {e}")
    
    def _delete_from_s3(self, path: str, bucket_type: str) -> bool:
        """Elimina archivo de S3/MinIO."""
        bucket = self._get_bucket(bucket_type)
        self.s3_client.delete_object(Bucket=bucket, Key=path)
        logger.info(f"File deleted from s3://{bucket}/{path}")
        return True
    
    def _delete_from_local(self, path: str) -> bool:
        """Elimina archivo del sistema local."""
        if default_storage.exists(path):
            default_storage.delete(path)
            logger.info(f"File deleted from local: {path}")
            return True
        return False
    
    def delete_folder(self, prefix: str, bucket_type: str = "default") -> int:
        """
        Elimina todos los archivos con un prefijo dado (carpeta virtual).
        
        Args:
            prefix: Prefijo/carpeta a eliminar (ej: tenants/default/jobs/123/)
            bucket_type: Tipo de bucket
            
        Returns:
            Número de archivos eliminados
        """
        if not self.use_s3:
            # Para local, usar shutil
            import shutil
            full_path = Path(settings.MEDIA_ROOT) / prefix
            if full_path.exists():
                shutil.rmtree(full_path)
                logger.info(f"Folder deleted from local: {prefix}")
                return 1
            return 0
        
        bucket = self._get_bucket(bucket_type)
        
        # Listar objetos con el prefijo
        response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        
        if "Contents" not in response:
            return 0
        
        # Eliminar objetos
        objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]
        
        if objects_to_delete:
            self.s3_client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": objects_to_delete}
            )
            logger.info(f"Deleted {len(objects_to_delete)} files from s3://{bucket}/{prefix}")
        
        return len(objects_to_delete)
    
    def file_exists(self, path: str, bucket_type: str = "default") -> bool:
        """
        Verifica si un archivo existe.
        
        Args:
            path: Ruta del archivo
            bucket_type: Tipo de bucket
            
        Returns:
            True si el archivo existe
        """
        if not self.use_s3:
            return default_storage.exists(path)
        
        bucket = self._get_bucket(bucket_type)
        
        try:
            self.s3_client.head_object(Bucket=bucket, Key=path)
            return True
        except self.s3_client.exceptions.ClientError:
            return False
    
    def list_files(
        self,
        prefix: str = "",
        bucket_type: str = "default",
        max_keys: int = 1000,
    ) -> list[dict]:
        """
        Lista archivos en el storage.
        
        Args:
            prefix: Prefijo para filtrar (ej: tenants/default/)
            bucket_type: Tipo de bucket
            max_keys: Máximo número de resultados
            
        Returns:
            Lista de diccionarios con información de archivos
        """
        if not self.use_s3:
            # Para local, listar directorio
            files = []
            base_path = Path(settings.MEDIA_ROOT) / prefix
            if base_path.exists():
                for path in base_path.rglob("*"):
                    if path.is_file():
                        files.append({
                            "key": str(path.relative_to(settings.MEDIA_ROOT)),
                            "size": path.stat().st_size,
                            "last_modified": path.stat().st_mtime,
                        })
            return files[:max_keys]
        
        bucket = self._get_bucket(bucket_type)
        
        response = self.s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=max_keys,
        )
        
        if "Contents" not in response:
            return []
        
        return [
            {
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
                "etag": obj.get("ETag", "").strip('"'),
            }
            for obj in response["Contents"]
        ]
    
    def copy_file(
        self,
        source_path: str,
        dest_path: str,
        source_bucket_type: str = "default",
        dest_bucket_type: str = "default",
    ) -> str:
        """
        Copia un archivo dentro del storage.
        
        Args:
            source_path: Ruta origen
            dest_path: Ruta destino
            source_bucket_type: Bucket origen
            dest_bucket_type: Bucket destino
            
        Returns:
            Ruta del archivo copiado
        """
        if not self.use_s3:
            # Para local, copiar archivo
            import shutil
            source = Path(settings.MEDIA_ROOT) / source_path
            dest = Path(settings.MEDIA_ROOT) / dest_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            return str(dest_path)
        
        source_bucket = self._get_bucket(source_bucket_type)
        dest_bucket = self._get_bucket(dest_bucket_type)
        
        self.s3_client.copy_object(
            CopySource={"Bucket": source_bucket, "Key": source_path},
            Bucket=dest_bucket,
            Key=dest_path,
        )
        
        return f"s3://{dest_bucket}/{dest_path}"


class StorageException(Exception):
    """Excepción para errores de almacenamiento."""
    pass


# Instancia singleton del servicio
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Obtiene la instancia singleton del servicio de storage."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
