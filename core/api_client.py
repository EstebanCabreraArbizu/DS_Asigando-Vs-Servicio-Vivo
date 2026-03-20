"""
ServicioGeneralClient — cliente HTTP para la API REST interna ServicioGeneral.

Maneja:
  - Autenticación JWT con /Autorizacion/Login
  - Renovación automática del token antes de que expire
  - Normalización de nombres de campos inconsistentes de la API
  - Llamadas a los endpoints relevantes para el análisis PA vs SV

Uso:
    from core.api_client import ServicioGeneralClient
    from core.config import API_CONFIG

    client = ServicioGeneralClient.from_config(API_CONFIG)
    programacion = client.get_programacion("17", "1")
"""

import logging
from datetime import datetime, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepciones personalizadas
# ---------------------------------------------------------------------------

class APIClientError(Exception):
    """Error base para ServicioGeneralClient."""


class AuthenticationError(APIClientError):
    """Error de autenticación — credenciales inválidas o respuesta inesperada."""


class APIRequestError(APIClientError):
    """Error en una petición HTTP a la API."""


class APIResponseError(APIClientError):
    """La API respondió con codigo != '00'."""


# ---------------------------------------------------------------------------
# Cliente principal
# ---------------------------------------------------------------------------

class ServicioGeneralClient:
    """
    Cliente para la API REST interna ServicioGeneral.

    Gestiona automáticamente el ciclo de vida del JWT:
      - Login en el primer uso (lazy)
      - Renovación cuando queda menos de `refresh_margin_seconds` para que expire

    Attributes:
        base_url (str): URL base sin trailing slash.
        usuario (str): Usuario de la API.
        clave (str): Clave de la API.
        timeout (int): Timeout en segundos para cada request.
        refresh_margin (int): Segundos antes del vencimiento para renovar el token.
    """

    def __init__(
        self,
        base_url: str,
        usuario: str,
        clave: str,
        timeout: int = 30,
        refresh_margin_seconds: int = 300,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.usuario = usuario
        self.clave = clave
        self.timeout = timeout
        self.refresh_margin = timedelta(seconds=refresh_margin_seconds)

        self._token: str | None = None
        self._token_expires_at: datetime | None = None

        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ------------------------------------------------------------------
    # Constructor alternativo desde config dict
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ServicioGeneralClient":
        """Crea un cliente a partir del dict API_CONFIG de config.py."""
        return cls(
            base_url=config["base_url"],
            usuario=config["usuario"],
            clave=config["clave"],
            timeout=config.get("timeout_seconds", 30),
            refresh_margin_seconds=config.get("token_refresh_margin_seconds", 300),
        )

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------

    def _parse_expires_in(self, expires_str: str) -> datetime:
        """
        Parsea el campo expires_In de la API al formato M/DD/YYYY h:MM:SS AM/PM.

        La API devuelve cadenas como '2/21/2026 10:56:41 AM' (formato regional
        en-US sin cero a la izquierda en mes/día).
        """
        try:
            return datetime.strptime(expires_str, "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            # Fallback: devuelve 1 hora desde ahora para no bloquear si el formato cambia
            logger.warning(
                "No se pudo parsear expires_In='%s'. Usando 1h desde ahora.", expires_str
            )
            return datetime.now() + timedelta(hours=1)

    def _login(self) -> None:
        """Autentica contra /Autorizacion/Login y almacena el token."""
        url = f"{self.base_url}/Autorizacion/Login"
        payload = {"Usuario": self.usuario, "Clave": self.clave}

        logger.info("Autenticando en ServicioGeneral API: %s", url)
        try:
            resp = self._session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise AuthenticationError(
                f"Error de conexión al autenticar: {exc}"
            ) from exc

        data = resp.json()
        if data.get("codigo") != "00":
            raise AuthenticationError(
                f"Login fallido — codigo={data.get('codigo')!r}, "
                f"mensaje={data.get('mensaje')!r}"
            )

        self._token = data["token"]
        self._token_expires_at = self._parse_expires_in(data["expires_In"])
        logger.info("Token JWT obtenido. Expira: %s", self._token_expires_at)

    def _ensure_token(self) -> None:
        """Renueva el token si no existe o está próximo a expirar."""
        if self._token is None or self._token_expires_at is None:
            self._login()
            return
        remaining = self._token_expires_at - datetime.now()
        if remaining <= self.refresh_margin:
            logger.info("Token próximo a expirar (quedan %s). Renovando...", remaining)
            self._login()

    def _headers(self) -> dict[str, str]:
        """Devuelve headers con Authorization Bearer para los requests autenticados."""
        self._ensure_token()
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # Normalización de campos inconsistentes de la API
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        """
        Normaliza campos con naming inconsistente en la API.

        Problema conocido: InformacionConceptoAdicionalxServicio devuelve
        'companiasocio' y 'hojacosto' (todo minúsculas) en lugar de
        'companiaSocio' y 'hojaCosto' (camelCase) como el resto de endpoints.
        """
        normalized: dict[str, Any] = {}
        rename_map = {
            "companiasocio": "companiaSocio",
            "hojacosto": "hojaCosto",
            # Typo en UnidadesxCliente
            "distritoDesccripcion": "distritoDescripcion",
            # Normalizar tS_ZonaDesc → tsZonaDescripcion (igual que UnidadesxCliente)
            "tS_ZonaDesc": "tsZonaDescripcion",
        }
        for key, value in row.items():
            normalized[rename_map.get(key, key)] = value
        return normalized

    # ------------------------------------------------------------------
    # Método genérico de petición POST
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """
        POST autenticado a un endpoint de /Servicio/.

        Args:
            path: Ruta relativa al base_url (ej. '/Servicio/InformacionHoja').
            payload: Body JSON del request.

        Returns:
            La lista 'lista' del response, con campos normalizados.

        Raises:
            APIRequestError: Si hay error de conexión/HTTP.
            APIResponseError: Si la API devuelve codigo != '00'.
        """
        url = f"{self.base_url}{path}"
        headers = self._headers()

        logger.debug("POST %s | payload=%s", url, payload)
        try:
            resp = self._session.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise APIRequestError(f"Error HTTP en POST {url}: {exc}") from exc

        data = resp.json()
        if data.get("codigo") != "00":
            raise APIResponseError(
                f"API error en {path} — codigo={data.get('codigo')!r}, "
                f"mensaje={data.get('mensaje')!r}"
            )

        raw_list: list[dict] = data.get("lista", [])
        return [self._normalize_row(row) for row in raw_list]

    def _get_or_post_no_body(self, path: str) -> list[dict[str, Any]]:
        """
        Intenta GET primero (para endpoints sin body como /Zonas);
        si falla con 405, intenta POST con body vacío.
        """
        url = f"{self.base_url}{path}"
        headers = self._headers()

        try:
            resp = self._session.get(url, headers=headers, timeout=self.timeout)
            if resp.status_code == 405:
                # La API solo acepta POST — intentar con body vacío
                resp = self._session.post(
                    url, json={}, headers=headers, timeout=self.timeout
                )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise APIRequestError(f"Error HTTP en {url}: {exc}") from exc

        data = resp.json()
        if data.get("codigo") != "00":
            raise APIResponseError(
                f"API error en {path} — codigo={data.get('codigo')!r}"
            )

        raw_list: list[dict] = data.get("lista", [])
        return [self._normalize_row(row) for row in raw_list]

    # ------------------------------------------------------------------
    # Métodos públicos por endpoint
    # ------------------------------------------------------------------

    def get_informacion_hoja(
        self, compania_socio: str, hoja_costo: str
    ) -> list[dict[str, Any]]:
        """
        Obtiene la cabecera (metadatos) de una Hoja de Costo.

        Args:
            compania_socio: Código de 8 dígitos de la compañía (ej. '01000000').
            hoja_costo: Identificador de la HC (ej. 'HC000013').
        """
        return self._post(
            "/Servicio/InformacionHoja",
            {"CompaniaSocio": compania_socio, "HojaCosto": hoja_costo},
        )

    def get_informacion_servicio(
        self, compania_socio: str, hoja_costo: str
    ) -> list[dict[str, Any]]:
        """Obtiene los ítems/líneas de costo de una Hoja de Costo."""
        return self._post(
            "/Servicio/InformacionServicio",
            {"CompaniaSocio": compania_socio, "HojaCosto": hoja_costo},
        )

    def get_conceptos_x_servicio(
        self, compania_socio: str, hoja_costo: str
    ) -> list[dict[str, Any]]:
        """
        Obtiene los servicios asignados a la HC con montos, roles y vigencias.

        Nota: el mismo servicio puede aparecer varias veces con distintas vigencias.
        Filtrar por fechaFin >= hoy para obtener el registro activo.
        """
        return self._post(
            "/Servicio/InformacionConceptoxServicio",
            {"CompaniaSocio": compania_socio, "HojaCosto": hoja_costo},
        )

    def get_conceptos_adicionales(
        self, compania_socio: str, hoja_costo: str
    ) -> list[dict[str, Any]]:
        """
        Obtiene los conceptos adicionales de facturación de la HC.

        Nota: Este endpoint tiene naming inconsistente en el response
        (companiasocio/hojacosto en minúsculas), normalizado automáticamente.
        """
        return self._post(
            "/Servicio/InformacionConceptoAdicionalxServicio",
            {"CompaniaSocio": compania_socio, "HojaCosto": hoja_costo},
        )

    def get_programacion(
        self, secuencia_periodo: str, servicio_tareo: str
    ) -> list[dict[str, Any]]:
        """
        Obtiene la programación mensual de empleados (31 días) por periodo y servicio.

        Cada registro contiene campos dia1..dia31 con valores:
          'D' = trabaja, 'X' = descanso, ' ' = sin asignación.

        Args:
            secuencia_periodo: ID del periodo de nómina (ej. '17').
            servicio_tareo: ID del servicio de tareo (ej. '1').
        """
        return self._post(
            "/Servicio/ProgramacionxCliente",
            {"SecuenciaPeriodo": secuencia_periodo, "ServicioTareo": servicio_tareo},
        )

    def get_tareo(
        self, secuencia_periodo: str, servicio_tareo: str
    ) -> list[dict[str, Any]]:
        """
        Obtiene el tareo efectivo mensual (asistencia real vs. programación).

        Structuralmente igual a get_programacion(), pero sin campos est{N}.
        """
        return self._post(
            "/Servicio/TareoxCliente",
            {"SecuenciaPeriodo": secuencia_periodo, "ServicioTareo": servicio_tareo},
        )

    def get_unidades(
        self, cliente: str, grupo_empresarial: str
    ) -> list[dict[str, Any]]:
        """
        Obtiene el catálogo de unidades operativas por cliente o grupo empresarial.

        Nota: latitud/longitud = 0.0 indica que la geolocalización no está cargada.
        No interpretar como coordenada real 0°N 0°E.

        Args:
            cliente: Código de cliente (ej. '7006').
            grupo_empresarial: Código de grupo (ej. '0099').
        """
        return self._post(
            "/Servicio/UnidadesxCliente",
            {"Cliente": cliente, "GrupoEmpresarial": grupo_empresarial},
        )

    def get_zonas(self) -> list[dict[str, Any]]:
        """
        Obtiene el catálogo completo de zonas geográficas operativas.

        No requiere parámetros de entrada.
        """
        return self._get_or_post_no_body("/Servicio/Zonas")

    def get_all_unidades(
        self,
        skip_errors: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Obtiene las unidades operativas de TODA la empresa iterando sobre zonas.

        Estrategia (Opción 2):
          1. Llama a get_zonas() para obtener el catálogo maestro de zonas.
          2. Por cada zona, llama a get_unidades(cliente="", grupo_empresarial=<zona>).
          3. Deduplica por campo 'unidad' (pueden aparecer en varias zonas).

        Args:
            skip_errors: Si True (por defecto), ignora errores individuales por zona
                         y continúa con las demás. Si False, propaga el primer error.

        Returns:
            Lista de dicts con todas las unidades de la empresa, sin duplicados.

        Raises:
            APIRequestError: Si falla get_zonas() o si skip_errors=False y falla
                             alguna zona.

        Notas:
            - Esta llamada es "pesada" — hace 1 + N requests (1 para zonas, N por zona).
              Cachear el resultado a nivel de DataLoader o Django cache es recomendable.
            - Si get_unidades(cliente="", grupo="<zona>") devuelve lista vacía para
              una zona, la zona se omite silenciosamente (no es un error).
        """
        logger.info("get_all_unidades: obteniendo catálogo de zonas...")
        zonas = self.get_zonas()

        if not zonas:
            logger.warning("get_all_unidades: no se encontraron zonas. Retornando lista vacía.")
            return []

        logger.info("get_all_unidades: %d zonas encontradas. Iterando...", len(zonas))

        todas_unidades: dict[str, dict[str, Any]] = {}  # clave=str(unidad) para deduplicar
        errores: list[str] = []

        for zona in zonas:
            codigo_zona = str(zona.get("codigo", ""))
            if not codigo_zona:
                continue

            try:
                unidades_zona = self.get_unidades(
                    cliente="",                         # sin filtro de cliente
                    grupo_empresarial=codigo_zona,      # zona como pivot
                )
                nuevas = 0
                for u in unidades_zona:
                    clave = str(u.get("unidad", ""))
                    if clave and clave not in todas_unidades:
                        todas_unidades[clave] = u
                        nuevas += 1

                logger.debug(
                    "  Zona %s (%s): %d unidades (%d nuevas)",
                    codigo_zona,
                    zona.get("descripcion", ""),
                    len(unidades_zona),
                    nuevas,
                )

            except (APIRequestError, APIResponseError) as exc:
                msg = f"Error en zona {codigo_zona!r}: {exc}"
                errores.append(msg)
                if skip_errors:
                    logger.warning("get_all_unidades: %s — continuando.", msg)
                else:
                    raise

        resultado = list(todas_unidades.values())
        logger.info(
            "get_all_unidades: %d unidades únicas obtenidas de %d zonas. "
            "Errores parciales: %d",
            len(resultado), len(zonas), len(errores),
        )

        if errores:
            logger.warning(
                "get_all_unidades: zonas con error: %s",
                "; ".join(errores),
            )

        return resultado

