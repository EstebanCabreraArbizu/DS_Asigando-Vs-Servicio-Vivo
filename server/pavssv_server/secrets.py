"""
Gestión segura de secretos para PA vs SV.

Soporta:
- AWS Secrets Manager (producción)
- Variables de entorno (desarrollo)
- Archivo .env (desarrollo local)

Uso:
    from pavssv_server.secrets import get_secret
    
    db_password = get_secret("POSTGRES_PASSWORD")
    jwt_key = get_secret("DJANGO_SECRET_KEY")
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


class SecretsManager:
    """
    Gestor de secretos con soporte para múltiples backends.
    
    En producción usa AWS Secrets Manager.
    En desarrollo usa variables de entorno.
    """
    
    def __init__(self):
        self.use_aws = os.getenv("USE_AWS_SECRETS", "false").lower() == "true"
        self._aws_client = None
        self._secrets_cache: dict[str, Any] = {}
    
    @property
    def aws_client(self):
        """Cliente boto3 para Secrets Manager (lazy loading)."""
        if self._aws_client is None and self.use_aws:
            try:
                import boto3
                self._aws_client = boto3.client(
                    "secretsmanager",
                    region_name=os.getenv("AWS_REGION", "us-east-1"),
                )
            except ImportError:
                logger.warning("boto3 no está instalado. Usando variables de entorno.")
                self.use_aws = False
            except Exception as e:
                logger.error(f"Error conectando a AWS Secrets Manager: {e}")
                self.use_aws = False
        return self._aws_client
    
    def get_secret(self, secret_name: str, default: Any = None) -> Any:
        """
        Obtiene un secreto del backend configurado.
        
        Args:
            secret_name: Nombre del secreto
            default: Valor por defecto si no se encuentra
            
        Returns:
            Valor del secreto
        """
        # Primero verificar caché
        if secret_name in self._secrets_cache:
            return self._secrets_cache[secret_name]
        
        value = None
        
        # Intentar AWS Secrets Manager en producción
        if self.use_aws:
            value = self._get_from_aws(secret_name)
        
        # Fallback a variables de entorno
        if value is None:
            value = os.getenv(secret_name, default)
        
        # Guardar en caché
        if value is not None:
            self._secrets_cache[secret_name] = value
        
        return value
    
    def _get_from_aws(self, secret_name: str) -> Any | None:
        """Obtiene un secreto desde AWS Secrets Manager."""
        try:
            # El prefijo de secretos en AWS
            aws_secret_name = os.getenv(
                "AWS_SECRET_PREFIX", "pavssv"
            ) + "/" + secret_name
            
            response = self.aws_client.get_secret_value(SecretId=aws_secret_name)
            
            # El secreto puede ser string o JSON
            if "SecretString" in response:
                secret = response["SecretString"]
                try:
                    # Intentar parsear como JSON
                    return json.loads(secret)
                except json.JSONDecodeError:
                    return secret
            else:
                # Secreto binario
                return response["SecretBinary"]
                
        except self.aws_client.exceptions.ResourceNotFoundException:
            logger.debug(f"Secreto no encontrado en AWS: {secret_name}")
            return None
        except Exception as e:
            logger.error(f"Error obteniendo secreto de AWS: {e}")
            return None
    
    def get_database_credentials(self) -> dict[str, str]:
        """
        Obtiene las credenciales de base de datos.
        
        Returns:
            Dict con NAME, USER, PASSWORD, HOST, PORT
        """
        if self.use_aws:
            # En AWS, las credenciales pueden estar en un solo secreto JSON
            creds = self._get_from_aws("database")
            if isinstance(creds, dict):
                return {
                    "NAME": creds.get("dbname", "pavssv"),
                    "USER": creds.get("username", "pavssv"),
                    "PASSWORD": creds.get("password", ""),
                    "HOST": creds.get("host", "localhost"),
                    "PORT": str(creds.get("port", 5432)),
                }
        
        # Fallback a variables de entorno individuales
        return {
            "NAME": os.getenv("POSTGRES_DB", "pavssv"),
            "USER": os.getenv("POSTGRES_USER", "pavssv"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    
    def get_s3_credentials(self) -> dict[str, str]:
        """
        Obtiene las credenciales de S3/MinIO.
        
        Returns:
            Dict con access_key, secret_key, region, endpoint
        """
        if self.use_aws:
            creds = self._get_from_aws("s3")
            if isinstance(creds, dict):
                return {
                    "access_key": creds.get("access_key", ""),
                    "secret_key": creds.get("secret_key", ""),
                    "region": creds.get("region", "us-east-1"),
                    "endpoint": creds.get("endpoint"),  # None para AWS real
                }
        
        return {
            "access_key": os.getenv("AWS_ACCESS_KEY_ID", ""),
            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            "region": os.getenv("AWS_S3_REGION_NAME", "us-east-1"),
            "endpoint": os.getenv("AWS_S3_ENDPOINT_URL"),
        }
    
    def clear_cache(self) -> None:
        """Limpia la caché de secretos."""
        self._secrets_cache.clear()


# Instancia singleton
_secrets_manager: SecretsManager | None = None


def get_secrets_manager() -> SecretsManager:
    """Obtiene la instancia singleton del gestor de secretos."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def get_secret(secret_name: str, default: Any = None) -> Any:
    """
    Función de conveniencia para obtener un secreto.
    
    Args:
        secret_name: Nombre del secreto
        default: Valor por defecto
        
    Returns:
        Valor del secreto
    """
    return get_secrets_manager().get_secret(secret_name, default)
