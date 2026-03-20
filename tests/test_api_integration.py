"""
Tests para api_client.py y api_transformer.py usando mocks (sin red real).

Ejecutar desde la raíz del proyecto:
    python -m pytest tests/test_api_integration.py -v

O desde core/:
    python -m pytest ../tests/test_api_integration.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import pytest
import polars as pl

# ---------------------------------------------------------------------------
# Fixtures de datos de muestra (simulan respuesta real de la API)
# ---------------------------------------------------------------------------

SAMPLE_LOGIN_RESPONSE = {
    "codigo": "00",
    "mensaje": "Exitoso",
    "expires_In": "2/21/2026 10:56:41 AM",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.token",
    "refresh_token": "743e1a76449947a29dcfa0cf0ace1718",
}

SAMPLE_PROGRAMACION = [
    {
        "unidad": 25,
        "servicio": "41",
        "descripcion": "AGENTE SEGURIDAD 12 HRS L/D DÍA",
        "secuenciaCosto": 1,
        "numeroPuesto": 0,
        "numeroTitular": 0,
        "tipoEmpleado": "Descansero",
        "fila": 2,
        "empleado": 65517,
        "nombreEmpleado": "RENGIFO HUAYTA, HUGO",
        "documento": "05342401",
        # Días: 5 días 'D'
        "dia1": " ", "est1": " ", "dia2": " ", "est2": " ",
        "dia3": " ", "est3": " ", "dia4": "D", "est4": " ",
        "dia5": " ", "est5": " ", "dia6": " ", "est6": " ",
        "dia7": " ", "est7": " ", "dia8": " ", "est8": " ",
        "dia9": " ", "est9": " ", "dia10": " ", "est10": " ",
        "dia11": " ", "est11": " ", "dia12": "D", "est12": " ",
        "dia13": "D", "est13": " ", "dia14": " ", "est14": " ",
        "dia15": " ", "est15": " ", "dia16": " ", "est16": " ",
        "dia17": " ", "est17": " ", "dia18": " ", "est18": " ",
        "dia19": " ", "est19": " ", "dia20": " ", "est20": " ",
        "dia21": "D", "est21": " ", "dia22": " ", "est22": " ",
        "dia23": " ", "est23": " ", "dia24": " ", "est24": " ",
        "dia25": " ", "est25": " ", "dia26": " ", "est26": " ",
        "dia27": " ", "est27": " ", "dia28": " ", "est28": " ",
        "dia29": "D", "est29": " ", "dia30": " ", "est30": " ",
        "dia31": " ", "est31": " ",
    },
    {
        "unidad": 25,
        "servicio": "41",
        "descripcion": "AGENTE SEGURIDAD 12 HRS L/D DÍA",
        "secuenciaCosto": 1,
        "numeroPuesto": 1,
        "numeroTitular": 1,
        "tipoEmpleado": "Titular",
        "fila": 1,
        "empleado": 76485,
        "nombreEmpleado": "YUPE INUMA, HERLIS",
        "documento": "05363466",
        # Días: 26 días 'D', 4 días 'X'
        "dia1": "D", "est1": " ", "dia2": "D", "est2": " ",
        "dia3": "D", "est3": " ", "dia4": "X", "est4": " ",
        "dia5": "D", "est5": " ", "dia6": "D", "est6": " ",
        "dia7": "D", "est7": " ", "dia8": "D", "est8": " ",
        "dia9": "D", "est9": " ", "dia10": "D", "est10": " ",
        "dia11": "D", "est11": " ", "dia12": "X", "est12": " ",
        "dia13": "X", "est13": " ", "dia14": "D", "est14": " ",
        "dia15": "D", "est15": " ", "dia16": "D", "est16": " ",
        "dia17": "D", "est17": " ", "dia18": "D", "est18": " ",
        "dia19": "D", "est19": " ", "dia20": "D", "est20": " ",
        "dia21": "X", "est21": " ", "dia22": "D", "est22": " ",
        "dia23": "D", "est23": " ", "dia24": "D", "est24": " ",
        "dia25": "D", "est25": " ", "dia26": "D", "est26": " ",
        "dia27": "D", "est27": " ", "dia28": "D", "est28": " ",
        "dia29": "X", "est29": " ", "dia30": "D", "est30": " ",
        "dia31": "D", "est31": " ",
    },
]

SAMPLE_UNIDADES = [
    {
        "unidad": 25,
        "descripcion": "Unidad Test Centro",
        "cliente": 0,
        "descripcionCliente": None,
        "grupoEmpresarial": None,
        "desGrupoEmpresarial": "GRUPO TEST",
        "departamento": "15",
        "provincia": "01",
        "codigoPostal": "01",
        "zona": "027",
        "estado": "A",  # Activo
        "esGrupoEmpresarial": "S",
        "clasificacion": None,
        "latitud": 0.0,
        "longitud": 0.0,
        "codigoGerente": 109656,
        "gerenteNombre": "BABILONIA SARMIENTO, OMAR IVAN",
        "codigoJefe": 127256,
        "jefeNombre": "GOMEZ MARTINEZ, MAYRA DENISSE",
        "codigoResponsable": 94276,
        "responsableNombre": "CUEVA MENDO, BRANDDI",
        "tsZonaDescripcion": "ZONA N6",
        "zonal": None,
        "zonalDescripcion": None,
        "departamentoDescripcion": "LIMA",
        "provinciaDescripcion": "LIMA",
        "distritoDescripcion": "SAN ISIDRO",  # typo corregido por api_client
        "clasificacionDescripcion": None,
        "flagNoValidarUbicacion": "N",
        "empleadoResponsable": None,
    }
]


# ---------------------------------------------------------------------------
# Tests de ServicioGeneralClient
# ---------------------------------------------------------------------------

class TestServicioGeneralClient:
    """Tests para la autenticación y llamadas HTTP del cliente."""

    def _make_client(self):
        from api_client import ServicioGeneralClient
        return ServicioGeneralClient(
            base_url="http://192.168.1.44/ServicioGeneral",
            usuario="USUWEB",
            clave="160821",
        )

    def test_from_config(self):
        from api_client import ServicioGeneralClient
        from config import API_CONFIG
        client = ServicioGeneralClient.from_config(API_CONFIG)
        assert client.base_url == API_CONFIG["base_url"].rstrip("/")
        assert client.usuario == API_CONFIG["usuario"]

    def test_login_exitoso(self):
        """Login con credenciales válidas debe almacenar el token."""
        from api_client import ServicioGeneralClient

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_LOGIN_RESPONSE
        mock_response.raise_for_status.return_value = None

        client = self._make_client()
        with patch.object(client._session, "post", return_value=mock_response):
            client._login()

        assert client._token == SAMPLE_LOGIN_RESPONSE["token"]
        assert client._token_expires_at is not None

    def test_login_credenciales_invalidas(self):
        """Login con respuesta de error debe lanzar AuthenticationError."""
        from api_client import ServicioGeneralClient, AuthenticationError

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "codigo": "01",
            "mensaje": "Credenciales inválidas",
        }
        mock_response.raise_for_status.return_value = None

        client = self._make_client()
        with patch.object(client._session, "post", return_value=mock_response):
            with pytest.raises(AuthenticationError):
                client._login()

    def test_normalize_row_companiasocio(self):
        """_normalize_row debe corregir naming inconsistente de ConceptoAdicional."""
        from api_client import ServicioGeneralClient
        client = self._make_client()

        raw = {"companiasocio": "01000000", "hojacosto": "HC000013", "importe": 75.0}
        normalized = client._normalize_row(raw)

        assert "companiaSocio" in normalized
        assert "hojaCosto" in normalized
        assert normalized["companiaSocio"] == "01000000"
        assert normalized["hojaCosto"] == "HC000013"
        # El campo original no debe quedar
        assert "companiasocio" not in normalized

    def test_normalize_row_ts_zona(self):
        """_normalize_row debe unificar tS_ZonaDesc → tsZonaDescripcion."""
        from api_client import ServicioGeneralClient
        client = self._make_client()

        raw = {"tS_ZonaDesc": "ZONA S1", "codigo": "001"}
        normalized = client._normalize_row(raw)

        assert "tsZonaDescripcion" in normalized
        assert normalized["tsZonaDescripcion"] == "ZONA S1"
        assert "tS_ZonaDesc" not in normalized

    def test_get_programacion_retorna_lista(self):
        """get_programacion debe retornar lista de dicts con todos los campos."""
        from api_client import ServicioGeneralClient

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "codigo": "00",
            "mensaje": "Satisfactorio",
            "lista": SAMPLE_PROGRAMACION,
        }
        mock_response.raise_for_status.return_value = None

        client = self._make_client()
        client._token = "fake_token"
        # Fijar expires_at en el futuro para evitar re-login durante el test
        client._token_expires_at = datetime.now() + timedelta(hours=1)

        with patch.object(client._session, "post", return_value=mock_response):
            result = client.get_programacion("17", "1")

        assert len(result) == 2
        assert result[0]["servicio"] == "41"
        assert "dia1" in result[0]

    def test_parse_expires_in_formato_correcto(self):
        """_parse_expires_in debe parsear el formato regional de la API."""
        from api_client import ServicioGeneralClient
        from datetime import datetime
        client = self._make_client()

        dt = client._parse_expires_in("2/21/2026 10:56:41 AM")
        assert dt == datetime(2026, 2, 21, 10, 56, 41)

    def test_parse_expires_in_formato_invalido_no_falla(self):
        """Con formato inválido, debe devolver fecha fallback sin lanzar excepción."""
        from api_client import ServicioGeneralClient
        client = self._make_client()

        result = client._parse_expires_in("fecha-invalida")
        assert result is not None  # debe devolver fallback


# ---------------------------------------------------------------------------
# Tests de api_transformer
# ---------------------------------------------------------------------------

class TestApiTransformer:
    """Tests para las funciones de transformación de listas a DataFrames."""

    def test_programacion_to_sv_dataframe_columnas(self):
        """El DataFrame debe tener exactamente las columnas del esquema SV."""
        from api_transformer import programacion_to_sv_dataframe, SV_SCHEMA

        df = programacion_to_sv_dataframe(SAMPLE_PROGRAMACION, SAMPLE_UNIDADES)

        assert set(df.columns) == set(SV_SCHEMA.keys())

    def test_programacion_to_sv_dataframe_filas(self):
        """Debe crear una fila por registro de programación."""
        from api_transformer import programacion_to_sv_dataframe

        df = programacion_to_sv_dataframe(SAMPLE_PROGRAMACION, SAMPLE_UNIDADES)
        assert len(df) == len(SAMPLE_PROGRAMACION)  # 2 empleados

    def test_count_dias_trabajados_descansero(self):
        """Descansero con 5 días 'D' debe resultar en Q°=5.0."""
        from api_transformer import programacion_to_sv_dataframe

        df = programacion_to_sv_dataframe(SAMPLE_PROGRAMACION, SAMPLE_UNIDADES)
        # Primer registro: Descansero con días 4, 12, 13, 21, 29 = 5 días
        descansero_row = df.filter(pl.col("Tipo_Empleado") == "Descansero")
        assert descansero_row["Q° PER. FACTOR - REQUERIDO"][0] == 5.0

    def test_count_dias_trabajados_titular(self):
        """Titular con 26 días 'D' (4 días 'X') debe resultar en Q°=26.0."""
        from api_transformer import programacion_to_sv_dataframe

        df = programacion_to_sv_dataframe(SAMPLE_PROGRAMACION, SAMPLE_UNIDADES)
        titular_row = df.filter(pl.col("Tipo_Empleado") == "Titular")
        # 31 días - 4 días 'X' = 27... pero días en blanco no cuentan, X tampoco
        # Solo 'D' cuenta: 31 - 4 X = 27, pero dia1 es D, revisemos:
        # Días D: 1,2,3,5,6,7,8,9,10,11,14,15,16,17,18,19,20,22,23,24,25,26,27,28,30,31 = 26 D
        assert titular_row["Q° PER. FACTOR - REQUERIDO"][0] == 26.0

    def test_enriquecimiento_unidades(self):
        """El DataFrame debe enriquecerse con datos de la unidad (zona, gerente)."""
        from api_transformer import programacion_to_sv_dataframe

        df = programacion_to_sv_dataframe(SAMPLE_PROGRAMACION, SAMPLE_UNIDADES)

        assert df["ZONA"][0] == "027"
        assert "BABILONIA" in df["GERENTE"][0]
        assert "GOMEZ" in df["JEFE"][0]
        assert df["Nombre Unidad"][0] == "Unidad Test Centro"

    def test_estado_activo_mapea_aprobado(self):
        """Unidad con estado 'A' debe mapearse a 'Aprobado'."""
        from api_transformer import programacion_to_sv_dataframe

        df = programacion_to_sv_dataframe(SAMPLE_PROGRAMACION, SAMPLE_UNIDADES)
        assert df["Estado"][0] == "Aprobado"

    def test_lista_vacia_retorna_dataframe_con_esquema(self):
        """Lista vacía debe retornar DataFrame vacío con el schema correcto."""
        from api_transformer import programacion_to_sv_dataframe, SV_SCHEMA

        df = programacion_to_sv_dataframe([], [])
        assert len(df) == 0
        # El schema debe preservarse incluso vacío
        assert set(df.columns) == set(SV_SCHEMA.keys())

    def test_tareo_to_dataframe(self):
        """tareo_to_dataframe debe producir DataFrame con columnas básicas y dias_reales."""
        from api_transformer import tareo_to_dataframe

        # Reutilizamos muestra de programación (misma estructura para tareo sin est{N})
        tareo_data = [
            {k: v for k, v in rec.items() if not k.startswith("est")}
            for rec in SAMPLE_PROGRAMACION
        ]
        df = tareo_to_dataframe(tareo_data)

        assert "empleado" in df.columns
        assert "dias_reales" in df.columns
        assert len(df) == 2

    def test_unidades_to_dataframe(self):
        """unidades_to_dataframe debe incluir la corrección del typo distritoDescripcion."""
        from api_transformer import unidades_to_dataframe

        df = unidades_to_dataframe(SAMPLE_UNIDADES)
        assert "distrito" in df.columns
        assert df["zona"][0] == "027"

    def test_zonas_to_dataframe(self):
        """zonas_to_dataframe debe mapear tsZonaDescripcion (ya normalizado)."""
        from api_transformer import zonas_to_dataframe

        zonas_data = [
            {
                "codigo": "027",
                "descripcion": "ZONA N6",
                "tsZonaDescripcion": "ZONA N6",  # ya normalizado por api_client
                "codigoGerente": 109656,
                "gerenteNombre": "BABILONIA SARMIENTO, OMAR IVAN",
                "codigoJefe": 127256,
                "jefeNombre": "GOMEZ MARTINEZ, MAYRA DENISSE",
                "codigoResponsable": 94276,
                "responsableNombre": "CUEVA MENDO, BRANDDI",
            }
        ]
        df = zonas_to_dataframe(zonas_data)
        assert df["codigo_zona"][0] == "027"
        assert "BABILONIA" in df["gerente"][0]


# ---------------------------------------------------------------------------
# Tests de DataLoader.load_servicio_vivo_from_api
# ---------------------------------------------------------------------------

class TestDataLoaderApi:
    """Tests de integración del método load_servicio_vivo_from_api."""

    def test_load_sv_from_api_retorna_dataframe_compatible(self):
        """load_servicio_vivo_from_api debe retornar DataFrame con esquema SV."""
        from data_loader import DataLoader
        from api_transformer import SV_SCHEMA

        mock_client = MagicMock()
        mock_client.get_programacion.return_value = SAMPLE_PROGRAMACION
        mock_client.get_unidades.return_value = SAMPLE_UNIDADES

        loader = DataLoader()
        df = loader.load_servicio_vivo_from_api(
            client=mock_client,
            secuencia_periodo="17",
            servicio_tareo="1",
            cliente="7006",
            grupo_empresarial="0099",
        )

        assert isinstance(df, pl.DataFrame)
        assert set(df.columns) == set(SV_SCHEMA.keys())
        assert len(df) == 2

    def test_load_sv_from_api_llama_endpoints_correctos(self):
        """Debe llamar a get_programacion y get_unidades con los parámetros correctos."""
        from data_loader import DataLoader

        mock_client = MagicMock()
        mock_client.get_programacion.return_value = []
        mock_client.get_unidades.return_value = []

        loader = DataLoader()
        loader.load_servicio_vivo_from_api(
            client=mock_client,
            secuencia_periodo="17",
            servicio_tareo="1",
            cliente="7006",
            grupo_empresarial="0099",
        )

        mock_client.get_programacion.assert_called_once_with("17", "1")
        mock_client.get_unidades.assert_called_once_with("7006", "0099")

    def test_load_sv_from_api_error_lanza_data_loader_error(self):
        """Si la API falla, debe lanzar DataLoaderError."""
        from data_loader import DataLoader, DataLoaderError
        from api_client import APIRequestError

        mock_client = MagicMock()
        mock_client.get_programacion.side_effect = APIRequestError("Timeout")

        loader = DataLoader()
        with pytest.raises(DataLoaderError):
            loader.load_servicio_vivo_from_api(
                client=mock_client,
                secuencia_periodo="17",
                servicio_tareo="1",
                cliente="7006",
                grupo_empresarial="0099",
            )


# ---------------------------------------------------------------------------
# Tests de tareo_to_pa_dataframe y load_personal_asignado_from_api
# (Personal Asignado real = TareoxCliente)
# ---------------------------------------------------------------------------

class TestPersonalAsignadoApi:
    """
    Tests para la integración TareoxCliente → df_pa.

    Concepto: TareoxCliente = tareo real = Personal Asignado efectivo.
              ProgramacionxCliente = planificado = Servicio Vivo.
    """

    # Datos de tareo (sin campos est{N} a diferencia de programación)
    SAMPLE_TAREO = [
        {
            "unidad": 25,
            "servicio": "41",
            "descripcion": "AGENTE SEGURIDAD 12 HRS L/D DÍA",
            "empleado": 65517,
            "nombreEmpleado": "RENGIFO HUAYTA, HUGO",
            "documento": "05342401",
            "tipoEmpleado": "Descansero",
            # 5 días reales trabajados
            "dia1": " ", "dia2": " ", "dia3": " ", "dia4": "D",
            "dia5": " ", "dia6": " ", "dia7": " ", "dia8": " ",
            "dia9": " ", "dia10": " ", "dia11": " ", "dia12": "D",
            "dia13": "D", "dia14": " ", "dia15": " ", "dia16": " ",
            "dia17": " ", "dia18": " ", "dia19": " ", "dia20": " ",
            "dia21": "D", "dia22": " ", "dia23": " ", "dia24": " ",
            "dia25": " ", "dia26": " ", "dia27": " ", "dia28": " ",
            "dia29": "D", "dia30": " ", "dia31": " ",
        },
        {
            "unidad": 25,
            "servicio": "41",
            "descripcion": "AGENTE SEGURIDAD 12 HRS L/D DÍA",
            "empleado": 76485,
            "nombreEmpleado": "YUPE INUMA, HERLIS",
            "documento": "05363466",
            "tipoEmpleado": "Titular",
            # 26 días reales trabajados (4 X)
            "dia1": "D", "dia2": "D", "dia3": "D", "dia4": "X",
            "dia5": "D", "dia6": "D", "dia7": "D", "dia8": "D",
            "dia9": "D", "dia10": "D", "dia11": "D", "dia12": "X",
            "dia13": "X", "dia14": "D", "dia15": "D", "dia16": "D",
            "dia17": "D", "dia18": "D", "dia19": "D", "dia20": "D",
            "dia21": "X", "dia22": "D", "dia23": "D", "dia24": "D",
            "dia25": "D", "dia26": "D", "dia27": "D", "dia28": "D",
            "dia29": "X", "dia30": "D", "dia31": "D",
        },
    ]

    def test_tareo_to_pa_dataframe_columnas_core(self):
        """El DataFrame PA debe tener las columnas core del Excel Personal Asignado."""
        from api_transformer import tareo_to_pa_dataframe

        df = tareo_to_pa_dataframe(self.SAMPLE_TAREO, SAMPLE_UNIDADES)

        # Columnas que el Excel PA tiene y que AnalysisEngine espera
        core_cols = {
            "ESTADO", "COD CLIENTE", "COD UNID", "COD SERVICIO", "COD GRUPO",
            "TIPO DE COMPAÑÍA", "CLIENTE", "UNIDAD", "TIPO DE SERVCIO", "GRUPO",
            "LIDER ZONAL / COORDINADOR", "JEFE DE OPERACIONES",
            "GERENTE REGIONAL", "SECTOR", "DEPARTAMENTO",
        }
        assert core_cols.issubset(set(df.columns))

    def test_tareo_to_pa_columnas_diagnosticas(self):
        """El DataFrame PA debe incluir columnas diagnósticas de la API."""
        from api_transformer import tareo_to_pa_dataframe

        df = tareo_to_pa_dataframe(self.SAMPLE_TAREO, SAMPLE_UNIDADES)

        diagnosticas = {"COD EMPLEADO", "NOMBRE EMPLEADO", "DOCUMENTO", "TIPO EMPLEADO", "DIAS_TAREO"}
        assert diagnosticas.issubset(set(df.columns))

    def test_tareo_to_pa_dias_trabajados_descansero(self):
        """DIAS_TAREO del Descansero debe ser 5.0."""
        from api_transformer import tareo_to_pa_dataframe

        df = tareo_to_pa_dataframe(self.SAMPLE_TAREO, SAMPLE_UNIDADES)
        descansero = df.filter(pl.col("TIPO EMPLEADO") == "Descansero")
        assert descansero["DIAS_TAREO"][0] == 5.0

    def test_tareo_to_pa_dias_trabajados_titular(self):
        """DIAS_TAREO del Titular debe ser 26.0."""
        from api_transformer import tareo_to_pa_dataframe

        df = tareo_to_pa_dataframe(self.SAMPLE_TAREO, SAMPLE_UNIDADES)
        titular = df.filter(pl.col("TIPO EMPLEADO") == "Titular")
        assert titular["DIAS_TAREO"][0] == 26.0

    def test_tareo_to_pa_estado_activo(self):
        """Empleado en unidad activa (estado='A') → ESTADO='ACTIVO'."""
        from api_transformer import tareo_to_pa_dataframe

        df = tareo_to_pa_dataframe(self.SAMPLE_TAREO, SAMPLE_UNIDADES)
        assert df["ESTADO"][0] == "ACTIVO"

    def test_tareo_to_pa_jerarquia_operativa(self):
        """GERENTE REGIONAL y JEFE DE OPERACIONES deben venir de UnidadesxCliente."""
        from api_transformer import tareo_to_pa_dataframe

        df = tareo_to_pa_dataframe(self.SAMPLE_TAREO, SAMPLE_UNIDADES)
        assert "BABILONIA" in df["GERENTE REGIONAL"][0]
        assert "GOMEZ" in df["JEFE DE OPERACIONES"][0]

    def test_tareo_to_pa_lista_vacia(self):
        """Lista vacía debe retornar DataFrame vacío con esquema PA_SCHEMA."""
        from api_transformer import tareo_to_pa_dataframe, PA_SCHEMA

        df = tareo_to_pa_dataframe([], [])
        assert len(df) == 0
        assert set(df.columns) == set(PA_SCHEMA.keys())

    def test_load_pa_from_api_retorna_dataframe_compatible(self):
        """load_personal_asignado_from_api() debe retornar DataFrame con columnas core del PA."""
        from data_loader import DataLoader
        from api_transformer import PA_SCHEMA

        mock_client = MagicMock()
        mock_client.get_tareo.return_value = self.SAMPLE_TAREO
        mock_client.get_unidades.return_value = SAMPLE_UNIDADES

        loader = DataLoader()
        df = loader.load_personal_asignado_from_api(
            client=mock_client,
            secuencia_periodo="17",
            servicio_tareo="1",
            cliente="7006",
            grupo_empresarial="0099",
        )

        assert isinstance(df, pl.DataFrame)
        assert set(df.columns) == set(PA_SCHEMA.keys())
        assert len(df) == 2
        assert df["COD EMPLEADO"].dtype == pl.Int64

    def test_load_pa_from_api_llama_tareo_no_programacion(self):
        """PA usa get_tareo (real), NO get_programacion (planificado)."""
        from data_loader import DataLoader

        mock_client = MagicMock()
        mock_client.get_tareo.return_value = []
        mock_client.get_unidades.return_value = []

        loader = DataLoader()
        loader.load_personal_asignado_from_api(
            client=mock_client,
            secuencia_periodo="17",
            servicio_tareo="1",
            cliente="7006",
            grupo_empresarial="0099",
        )

        mock_client.get_tareo.assert_called_once_with("17", "1")
        mock_client.get_programacion.assert_not_called()  # NO debe llamar a programacion

    def test_load_pa_from_api_error_lanza_data_loader_error(self):
        """Si TareoxCliente falla, debe lanzar DataLoaderError."""
        from data_loader import DataLoader, DataLoaderError
        from api_client import APIRequestError

        mock_client = MagicMock()
        mock_client.get_tareo.side_effect = APIRequestError("Connection refused")

        loader = DataLoader()
        with pytest.raises(DataLoaderError):
            loader.load_personal_asignado_from_api(
                client=mock_client,
                secuencia_periodo="17",
                servicio_tareo="1",
                cliente="7006",
                grupo_empresarial="0099",
            )


# ---------------------------------------------------------------------------
# Tests de Empresa Completa (get_all_unidades + load_empresa_completa)
# ---------------------------------------------------------------------------

class TestEmpresaCompleta:
    """
    Tests para la cobertura de TODA la empresa:
      - get_all_unidades(): itera sobre zonas, deduplica
      - load_empresa_completa(): carga PA + SV de un solo golpe
    """

    SAMPLE_ZONAS = [
        {
            "codigo": "027",
            "descripcion": "ZONA N6",
            "tsZonaDescripcion": "ZONA N6",
            "codigoGerente": 109656,
            "gerenteNombre": "BABILONIA SARMIENTO, OMAR IVAN",
            "codigoJefe": 127256,
            "jefeNombre": "GOMEZ MARTINEZ, MAYRA DENISSE",
            "codigoResponsable": 94276,
            "responsableNombre": "CUEVA MENDO, BRANDDI",
        },
        {
            "codigo": "028",
            "descripcion": "ZONA S1",
            "tsZonaDescripcion": "ZONA S1",
            "codigoGerente": 100001,
            "gerenteNombre": "GERENTE SUR, NOMBRE",
            "codigoJefe": 100002,
            "jefeNombre": "JEFE SUR, NOMBRE",
            "codigoResponsable": 100003,
            "responsableNombre": "RESPONSABLE SUR, NOMBRE",
        },
    ]

    UNIDADES_ZONA_027 = [
        {
            "unidad": 25,
            "descripcion": "Unidad Centro",
            "cliente": 0,
            "descripcionCliente": None,
            "desGrupoEmpresarial": "GRUPO TEST",
            "zona": "027",
            "estado": "A",
            "esGrupoEmpresarial": "S",
            "tsZonaDescripcion": "ZONA N6",
            "gerenteNombre": "BABILONIA SARMIENTO, OMAR IVAN",
            "jefeNombre": "GOMEZ MARTINEZ, MAYRA DENISSE",
            "responsableNombre": "CUEVA MENDO, BRANDDI",
            "departamentoDescripcion": "LIMA",
        }
    ]

    UNIDADES_ZONA_028 = [
        {
            "unidad": 99,
            "descripcion": "Unidad Sur",
            "cliente": 0,
            "descripcionCliente": None,
            "desGrupoEmpresarial": "GRUPO SUR",
            "zona": "028",
            "estado": "A",
            "esGrupoEmpresarial": "S",
            "tsZonaDescripcion": "ZONA S1",
            "gerenteNombre": "GERENTE SUR, NOMBRE",
            "jefeNombre": "JEFE SUR, NOMBRE",
            "responsableNombre": "RESPONSABLE SUR, NOMBRE",
            "departamentoDescripcion": "AREQUIPA",
        }
    ]

    def _make_client(self):
        from api_client import ServicioGeneralClient
        client = ServicioGeneralClient(
            base_url="http://192.168.1.44/ServicioGeneral",
            usuario="USUWEB",
            clave="160821",
        )
        client._token = "fake"
        client._token_expires_at = datetime.now() + timedelta(hours=1)
        return client

    def test_get_all_unidades_itera_zonas(self):
        """get_all_unidades debe llamar a get_unidades una vez por zona."""
        from api_client import ServicioGeneralClient

        client = self._make_client()

        def mock_zonas():
            return self.SAMPLE_ZONAS

        def mock_unidades(cliente, grupo_empresarial):
            if grupo_empresarial == "027":
                return self.UNIDADES_ZONA_027
            elif grupo_empresarial == "028":
                return self.UNIDADES_ZONA_028
            return []

        client.get_zonas = mock_zonas
        client.get_unidades = mock_unidades

        resultado = client.get_all_unidades()

        assert len(resultado) == 2  # una por zona (sin duplicados)
        codigos = {str(u["unidad"]) for u in resultado}
        assert "25" in codigos
        assert "99" in codigos

    def test_get_all_unidades_deduplica(self):
        """Si la misma unidad aparece en dos zonas, solo se incluye una vez."""
        from api_client import ServicioGeneralClient

        client = self._make_client()

        # Unidad 25 aparece en ambas zonas
        client.get_zonas = lambda: self.SAMPLE_ZONAS
        client.get_unidades = lambda c='', g='', **kw: self.UNIDADES_ZONA_027  # siempre devuelve la misma

        resultado = client.get_all_unidades()
        assert len(resultado) == 1  # deduplicada

    def test_get_all_unidades_skip_errors_true(self):
        """Con skip_errors=True, ignora zonas fallidas y devuelve las exitosas."""
        from api_client import ServicioGeneralClient, APIRequestError

        client = self._make_client()
        client.get_zonas = lambda: self.SAMPLE_ZONAS

        def mock_unidades_con_error(cliente, grupo_empresarial):
            if grupo_empresarial == "027":
                return self.UNIDADES_ZONA_027
            raise APIRequestError("Timeout en zona 028")

        client.get_unidades = mock_unidades_con_error

        resultado = client.get_all_unidades(skip_errors=True)
        # Debe devolver las de la zona 027 aunque la 028 haya fallado
        assert len(resultado) == 1
        assert str(resultado[0]["unidad"]) == "25"

    def test_get_all_unidades_skip_errors_false_propaga_error(self):
        """Con skip_errors=False, propaga el primer error de zona."""
        from api_client import ServicioGeneralClient, APIRequestError

        client = self._make_client()
        client.get_zonas = lambda: self.SAMPLE_ZONAS

        def siempre_falla(cliente, grupo_empresarial):
            raise APIRequestError("Fallo total")

        client.get_unidades = siempre_falla

        with pytest.raises(APIRequestError):
            client.get_all_unidades(skip_errors=False)

    def test_get_all_unidades_sin_zonas(self):
        """Si no hay zonas, devuelve lista vacía sin error."""
        from api_client import ServicioGeneralClient

        client = self._make_client()
        client.get_zonas = lambda: []

        resultado = client.get_all_unidades()
        assert resultado == []

    def test_load_empresa_completa_retorna_tuple(self):
        """load_empresa_completa debe retornar (df_pa, df_sv) como tuple."""
        from data_loader import DataLoader

        todas_unidades = self.UNIDADES_ZONA_027 + self.UNIDADES_ZONA_028

        mock_client = MagicMock()
        mock_client.get_all_unidades.return_value = todas_unidades
        mock_client.get_tareo.return_value = TestPersonalAsignadoApi.SAMPLE_TAREO
        mock_client.get_programacion.return_value = SAMPLE_PROGRAMACION

        loader = DataLoader()
        resultado = loader.load_empresa_completa(
            client=mock_client,
            secuencia_periodo="17",
        )

        assert isinstance(resultado, tuple)
        assert len(resultado) == 2
        df_pa, df_sv = resultado
        assert isinstance(df_pa, pl.DataFrame)
        assert isinstance(df_sv, pl.DataFrame)

    def test_load_empresa_completa_llama_get_all_unidades(self):
        """load_empresa_completa debe usar get_all_unidades (no get_unidades)."""
        from data_loader import DataLoader

        mock_client = MagicMock()
        mock_client.get_all_unidades.return_value = []
        mock_client.get_tareo.return_value = []
        mock_client.get_programacion.return_value = []

        DataLoader().load_empresa_completa(mock_client, secuencia_periodo="17")

        mock_client.get_all_unidades.assert_called_once()
        mock_client.get_unidades.assert_not_called()  # no debe llamar get_unidades individual

    def test_load_empresa_completa_periodo_parametrizable(self):
        """El periodo debe pasarse correctamente a get_tareo y get_programacion."""
        from data_loader import DataLoader

        mock_client = MagicMock()
        mock_client.get_all_unidades.return_value = []
        mock_client.get_tareo.return_value = []
        mock_client.get_programacion.return_value = []

        DataLoader().load_empresa_completa(mock_client, secuencia_periodo="16")

        mock_client.get_tareo.assert_called_once_with("16", "1")
        mock_client.get_programacion.assert_called_once_with("16", "1")


