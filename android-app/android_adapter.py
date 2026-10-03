#!/usr/bin/env python3
"""
android_adapter.py
==================

Frontera estable entre la aplicación Android (Capacitor + OnsenUI + Pyodide)
y el motor energético Python existente.

Referencias de diseño
---------------------
    android-app/docs/ARCHITECTURE.md
    android-app/docs/DEVELOPMENT_PLAN.md   (Fases 3-4)

Principio
---------
    Android configura  ->  Python calcula  ->  Android presenta

Este módulo:

    * recibe datos estructurados procedentes de la interfaz;
    * valida la entrada;
    * adapta la configuración al formato que consume el motor
      (sin modificarlo: se inyectan valores en los módulos);
    * invoca las funciones reales del motor en el mismo orden que
      ``main.py``;
    * normaliza la salida a un diccionario JSON-serializable;
    * traduce errores a categorías estables.

NO contiene lógica energética: no reimplementa ``optimizer.py``,
``balance.py`` ni ``solar.py``. Tampoco contiene interfaz de usuario.

Contrato público
----------------

    run_plan(config, credentials, soc, refresh=False, date=None,
             estrategia="sostenible_predictiva", engine=None) -> dict

``run_plan`` nunca lanza excepciones: devuelve siempre un diccionario con
``status`` igual a ``"ok"`` o ``"error"``.

Autor del motor original: Enrique M. Moreno Pérez
Capa de integración: rama ``android-app``
"""

from __future__ import annotations

import importlib
import json
import math
import os
import sys
import traceback
from datetime import date, datetime, timedelta
from typing import Any

# ==========================================================
# Constantes del contrato
# ==========================================================

SCHEMA_VERSION = 1

#: Nombre del archivo de credenciales que espera el motor.
TOKEN_FILENAME = "mytoken.env"

#: Estrategia por defecto del motor.
ESTRATEGIA_DEFAULT = "sostenible_predictiva"

#: Estrategias válidas (deben coincidir con optimizer.ESTRATEGIAS_DISPONIBLES).
ESTRATEGIAS_DISPONIBLES = [
    "economica",
    "autoconsumo",
    "min_ciclos",
    "sostenible_jerarquica",
    "sostenible_predictiva",
]

#: Módulos del motor que se cargan de forma perezosa.
ENGINE_MODULES = [
    "config",
    "demand",
    "cache",
    "aemet",
    "aemet_hourly",
    "esios",
    "solar",
    "balance",
    "dispatch",
    "optimizer",
    "weekly",
]

#: Archivos que el build copia junto al adaptador dentro del runtime Pyodide.
ENGINE_FILES = [
    "config.py",
    "demand.py",
    "cache.py",
    "aemet.py",
    "aemet_hourly.py",
    "esios.py",
    "solar.py",
    "balance.py",
    "dispatch.py",
    "optimizer.py",
    "weekly.py",
    "municipios.py",
]

#: Endpoints usados únicamente para validar credenciales.
AEMET_VALIDATION_URL = "https://opendata.aemet.es/opendata/api/maestro/municipios"
ESIOS_VALIDATION_URL = "https://api.esios.ree.es/indicators"


# ==========================================================
# Errores
# ==========================================================

class AdapterError(Exception):
    """Error controlable con categoría estable para la interfaz."""

    def __init__(self, category: str, message: str, source: str | None = None):
        super().__init__(message)
        self.category = category
        self.message = message
        self.source = source

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "message": self.message,
            "source": self.source,
        }


def classify_exception(exc: BaseException, source: str | None = None) -> AdapterError:
    """Traduce una excepción del motor a una categoría estable.

    Las categorías coinciden con DEVELOPMENT_PLAN.md (Fase 6):

        CONFIGURATION_ERROR, AUTHENTICATION_ERROR, NETWORK_ERROR,
        SERVICE_UNAVAILABLE, INVALID_RESPONSE, ENGINE_ERROR
    """
    if isinstance(exc, AdapterError):
        return exc

    name = type(exc).__name__
    text = str(exc)

    # --- Red -------------------------------------------------------
    if name in ("Timeout", "ReadTimeout", "ConnectTimeout"):
        return AdapterError("NETWORK_ERROR", "La consulta ha excedido el tiempo de espera.", source)

    if name in ("ConnectionError", "SSLError", "RequestException"):
        return AdapterError("NETWORK_ERROR", "No se ha podido conectar con el servicio externo.", source)

    if name == "HTTPError":
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403):
            return AdapterError(
                "AUTHENTICATION_ERROR",
                "La credencial no ha sido aceptada por el servicio.",
                source,
            )
        return AdapterError(
            "SERVICE_UNAVAILABLE",
            "El servicio externo ha respondido con un error.",
            source,
        )

    # --- Credenciales / configuración ------------------------------
    if "mytoken.env" in text or "API_KEY" in text or "api_key" in text:
        return AdapterError("AUTHENTICATION_ERROR", text, source)

    if isinstance(exc, (KeyError, ValueError, TypeError)) and source == "input":
        return AdapterError("CONFIGURATION_ERROR", text, source)

    if isinstance(exc, (KeyError, ValueError, TypeError, RuntimeError, FileNotFoundError)):
        return AdapterError("ENGINE_ERROR", text, source)

    return AdapterError("ENGINE_ERROR", f"{name}: {text}", source)


# ==========================================================
# Localización del motor
# ==========================================================

def engine_dir() -> str:
    """Directorio donde viven los módulos del motor.

    En el build de Pyodide los ficheros ``*.py`` del motor se copian
    junto a este adaptador. En el repositorio el motor está un nivel
    por encima (``../``).
    """
    here = os.path.dirname(os.path.abspath(__file__))

    if os.path.isfile(os.path.join(here, "optimizer.py")):
        return here

    parent = os.path.dirname(here)
    if os.path.isfile(os.path.join(parent, "optimizer.py")):
        return parent

    return here


# ==========================================================
# Credenciales
# ==========================================================

def prepare_credentials(credentials: dict | None, write_token_file: bool = True) -> dict:
    """Deja las credenciales disponibles para el motor SIN modificar el motor.

    El motor lee ``AEMET_API_KEY`` y ``ESIOS_API_KEY`` de ``os.environ``
    (cargado desde ``mytoken.env``) en tiempo de importación. Por tanto:

        1. se escriben en ``os.environ`` antes de importar los módulos;
        2. opcionalmente se materializa ``mytoken.env`` en el directorio
           del motor (necesario si algún módulo llama a ``load_dotenv``
           con ``override``).

    Las credenciales nunca se registran en logs ni se devuelven.
    """
    credentials = credentials or {}

    aemet = credentials.get("aemet_api_key") or credentials.get("AEMET_API_KEY")
    esios = (
        credentials.get("esios_token")
        or credentials.get("esios_api_key")
        or credentials.get("ESIOS_API_KEY")
    )

    if aemet:
        os.environ["AEMET_API_KEY"] = str(aemet)
    if esios:
        os.environ["ESIOS_API_KEY"] = str(esios)

    if write_token_file and (aemet or esios):
        _write_token_file(engine_dir(), aemet, esios)

    return {
        "aemet": bool(aemet),
        "esios": bool(esios),
    }


def _write_token_file(directory: str, aemet: str | None, esios: str | None) -> None:
    """Materializa ``mytoken.env`` si su contenido cambiaría.

    Se evita reescribir el archivo cuando ya existe con el mismo
    contenido para no alterar instalaciones locales existentes.
    """
    lines = []
    if aemet:
        lines.append(f"AEMET_API_KEY={aemet}")
    if esios:
        lines.append(f"ESIOS_API_KEY={esios}")

    if not lines:
        return

    path = os.path.join(directory, TOKEN_FILENAME)
    content = "\n".join(lines) + "\n"

    try:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                if handle.read() == content:
                    return
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        # El archivo contiene secretos: restringir permisos donde aplique.
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError:
        # En un sistema de archivos de sólo lectura, basta con os.environ.
        pass


# ==========================================================
# Carga del motor
# ==========================================================

def load_engine():
    """Importa los módulos del motor y devuelve un namespace con ellos."""
    directory = engine_dir()
    if directory not in sys.path:
        sys.path.insert(0, directory)

    namespace = _EngineNamespace()
    for name in ENGINE_MODULES:
        try:
            setattr(namespace, name, importlib.import_module(name))
        except ImportError:
            # Módulos auxiliares opcionales (p. ej. cache) no bloquean.
            setattr(namespace, name, None)
    return namespace


class _EngineNamespace:
    """Contenedor simple para los módulos del motor."""

    config: Any = None
    demand: Any = None
    cache: Any = None
    aemet: Any = None
    aemet_hourly: Any = None
    esios: Any = None
    solar: Any = None
    balance: Any = None
    dispatch: Any = None
    optimizer: Any = None
    weekly: Any = None

    def __repr__(self):  # pragma: no cover - ayuda de depuración
        loaded = [n for n in ENGINE_MODULES if getattr(self, n, None) is not None]
        return f"<EngineNamespace modules={loaded}>"


def dependency_probe() -> dict:
    """Comprueba qué dependencias del motor están disponibles.

    Pensado para la pantalla de diagnóstico (DEVELOPMENT_PLAN.md, Fase 2).
    """
    result = {}

    for module in ("requests", "dotenv", "pytz"):
        try:
            importlib.import_module(module)
            result[module] = "ok"
        except Exception as exc:  # noqa: BLE001 - se reporta el motivo
            result[module] = repr(exc)

    for module in ENGINE_MODULES:
        try:
            directory = engine_dir()
            if directory not in sys.path:
                sys.path.insert(0, directory)
            importlib.import_module(module)
            result[f"engine:{module}"] = "ok"
        except Exception as exc:  # noqa: BLE001
            result[f"engine:{module}"] = repr(exc)

    return result


# ==========================================================
# Validación
# ==========================================================

def validate_credential(source: str, value: str) -> dict:
    """Valida una credencial contra su servicio.

    Reutiliza el motor como única vía de acceso a las APIs
    (DATA_SOURCES.md, §2) y clasifica el resultado en estados
    comprensibles para la interfaz:

        valid, invalid, network_error, service_unavailable,
        configuration_error
    """
    source = (source or "").strip().lower()
    value = (value or "").strip()

    if source not in ("aemet", "esios"):
        return {
            "source": source,
            "status": "configuration_error",
            "message": "Fuente desconocida.",
        }

    if not value:
        return {
            "source": source,
            "status": "configuration_error",
            "message": "La credencial está vacía.",
        }

    env_name = "AEMET_API_KEY" if source == "aemet" else "ESIOS_API_KEY"
    os.environ[env_name] = value

    try:
        directory = engine_dir()
        if directory not in sys.path:
            sys.path.insert(0, directory)

        if source == "aemet":
            module = importlib.import_module("aemet")
            url = AEMET_VALIDATION_URL
            module.get_json(url, params={"api_key": value})
        else:
            module = importlib.import_module("esios")
            # El token se capturó al importar el módulo: se refresca.
            if hasattr(module, "HEADERS_ESIOS"):
                module.HEADERS_ESIOS["x-api-key"] = value
            module.get_json(ESIOS_VALIDATION_URL)

        return {"source": source, "status": "valid", "message": None}

    except AdapterError:
        raise
    except BaseException as exc:  # noqa: BLE001
        error = classify_exception(exc, source=source)
        if error.category == "AUTHENTICATION_ERROR":
            status = "invalid"
        elif error.category == "NETWORK_ERROR":
            status = "network_error"
        elif error.category == "SERVICE_UNAVAILABLE":
            status = "service_unavailable"
        else:
            status = "service_unavailable"
        return {"source": source, "status": status, "message": error.message}


def validate_soc(soc) -> float:
    """Valida y normaliza el SOC a un float en [0, 1]."""
    try:
        value = float(soc)
    except (TypeError, ValueError) as exc:
        raise AdapterError("CONFIGURATION_ERROR", "El SOC debe ser numérico.", "input") from exc

    if value != value:  # NaN
        raise AdapterError("CONFIGURATION_ERROR", "El SOC no puede ser NaN.", "input")

    if not (0.0 <= value <= 1.0):
        raise AdapterError(
            "CONFIGURATION_ERROR",
            "El SOC debe estar entre 0.0 y 1.0 (recibido: %s)." % value,
            "input",
        )

    return value


def validate_estrategia(estrategia: str | None) -> str:
    """Valida la estrategia de gestión."""
    value = estrategia or ESTRATEGIA_DEFAULT
    if value not in ESTRATEGIAS_DISPONIBLES:
        raise AdapterError(
            "CONFIGURATION_ERROR",
            "Estrategia no reconocida: %s" % value,
            "input",
        )
    return value


# ==========================================================
# Inyección de configuración en el motor
# ==========================================================
#
# El motor no acepta un objeto de configuración: define constantes de
# módulo y las consume desde ``obtener_configuracion_sistema()`` y
# ``obtener_configuracion_demanda()``. Como no debe modificarse, la
# capa Android escribe esos valores en los módulos antes de invocarlos.
#
# Sólo se exponen en la interfaz parámetros que el motor utiliza
# realmente (DEVELOPMENT_PLAN.md, §34).

def apply_installation_config(config_module, config: dict) -> None:
    """Aplica configuración de instalación a ``config.py``."""
    if not config_module or not config:
        return

    cfg = config.get("config", config)  # tolera envoltorio {config: {...}}
    location = cfg.get("location") or {}
    pv = cfg.get("pv") or {}
    inverter = cfg.get("inverter") or {}
    battery = cfg.get("battery") or {}
    home = cfg.get("home") or {}

    def set_if(attr, value):
        if value is not None:
            setattr(config_module, attr, value)

    # --- Localización -------------------------------------------
    set_if("MUNICIPIO", location.get("municipality"))
    set_if("PROVINCIA", location.get("region"))
    set_if("LATITUD", location.get("latitude"))
    set_if("LONGITUD", location.get("longitude"))

    # --- Campo fotovoltaico --------------------------------------
    panels = pv.get("panels")
    panel_power = pv.get("panel_power_w")
    set_if("NUM_PANELES", panels)
    set_if("PANEL_POTENCIA_W", panel_power)

    if panels is not None and panel_power is not None:
        total_wp = float(panels) * float(panel_power)
        config_module.POTENCIA_FV_WP = total_wp
        config_module.POTENCIA_FV_KWP = total_wp / 1000.0

    set_if("PANEL_INCLINACION_GRADOS", pv.get("inclination_deg"))
    set_if("PANEL_AZIMUT_GRADOS", pv.get("azimuth_deg"))

    # --- Inversor -------------------------------------------------
    set_if("INVERSOR_FABRICANTE", inverter.get("manufacturer"))
    set_if("INVERSOR_MODELO", inverter.get("model"))
    nominal_kw = inverter.get("nominal_kw")
    if nominal_kw is not None:
        config_module.INVERSOR_POTENCIA_NOMINAL_KW = float(nominal_kw)
        config_module.INVERSOR_POTENCIA_NOMINAL_W = float(nominal_kw) * 1000.0

    # --- Batería --------------------------------------------------
    set_if("BATERIA_FABRICANTE", battery.get("manufacturer"))
    set_if("BATERIA_MODELO", battery.get("model"))

    units = battery.get("units")
    capacity_kwh = battery.get("capacity_kwh_unit")
    if units is not None:
        config_module.NUM_BATERIAS = int(units)
    if capacity_kwh is not None:
        config_module.BATERIA_ENERGIA_KWH_UNIDAD = float(capacity_kwh)

    soc_min = battery.get("min_soc")
    soc_max = battery.get("max_soc")
    set_if("SOC_MIN_NORMAL", soc_min)
    set_if("SOC_MAX_NORMAL", soc_max)
    set_if("EFICIENCIA_CICLO_BATERIA", battery.get("efficiency"))

    _recompute_config_derived(config_module)

    # --- Vivienda -------------------------------------------------
    set_if("POTENCIA_BASE_KW", home.get("base_power_kw"))
    apply_demand_config(sys.modules.get("demand"), config)


def apply_demand_config(demand_module, config: dict) -> None:
    """Aplica configuración doméstica a ``demand.py``.

    En el MVP se exponen únicamente ocupación y las cargas flexibles
    principales. El resto de cargas conserva sus valores por defecto del
    motor.
    """
    if not demand_module or not config:
        return

    cfg = config.get("config", config)
    home = cfg.get("home") or {}
    loads = cfg.get("loads") or {}

    adults = home.get("adults")
    children = home.get("children")

    if adults is not None:
        demand_module.NUM_ADULTOS = int(adults)
    if children is not None:
        demand_module.NUM_NINOS = int(children)
    if adults is not None or children is not None:
        demand_module.NUM_OCUPANTES = int(demand_module.NUM_ADULTOS) + int(demand_module.NUM_NINOS)

    if home.get("grid_priority_over_battery") is not None:
        demand_module.PRIORIDAD_RED_SOBRE_BATERIA = bool(home["grid_priority_over_battery"])

    # Lavadora: principal carga flexible expuesta en el MVP.
    lavadora = loads.get("lavadora")
    if lavadora:
        base = dict(getattr(demand_module, "LAVADORA", {}) or {})
        base["potencia_kw"] = lavadora.get("power_kw", base.get("potencia_kw"))
        base["duracion_h"] = lavadora.get("duration_h", base.get("duracion_h"))
        base["flexible"] = bool(lavadora.get("flexible", base.get("flexible", True)))
        window = lavadora.get("window")
        if isinstance(window, (list, tuple)) and len(window) == 2:
            base["ventana_solar_preferida"] = (window[0], window[1])
        demand_module.LAVADORA = base


def _recompute_config_derived(config_module) -> None:
    """Recalcula los valores derivados de ``config.py`` tras inyectar
    las constantes de entrada.

    ``config.py`` calcula muchos agregados en tiempo de importación; al
    sobrescribir las entradas hay que recomputarlos para mantener la
    coherencia (p. ej. energía total del banco de baterías).
    """
    num_baterias = float(getattr(config_module, "NUM_BATERIAS", 2))
    cap_unidad = float(getattr(config_module, "BATERIA_ENERGIA_KWH_UNIDAD", 5.12))
    tension = float(getattr(config_module, "BATERIA_TENSION_NOMINAL_V", 51.2))
    cap_ah_unidad = float(getattr(config_module, "BATERIA_CAPACIDAD_AH_UNIDAD", 100.0))

    config_module.BATERIA_ENERGIA_KWH_TOTAL = num_baterias * cap_unidad
    config_module.BATERIA_CAPACIDAD_AH_TOTAL = num_baterias * cap_ah_unidad

    soc_min = float(getattr(config_module, "SOC_MIN_NORMAL", 0.20))
    soc_max = float(getattr(config_module, "SOC_MAX_NORMAL", 0.85))
    config_module.BATERIA_ENERGIA_UTIL_SOSTENIBLE_KWH = (
        config_module.BATERIA_ENERGIA_KWH_TOTAL * (soc_max - soc_min)
    )

    ef_carga = float(getattr(config_module, "EFICIENCIA_CARGA_BATERIA", 0.95))
    ef_descarga = float(getattr(config_module, "EFICIENCIA_DESCARGA_BATERIA", 0.95))
    if getattr(config_module, "EFICIENCIA_CICLO_BATERIA", None) is None:
        config_module.EFICIENCIA_CICLO_BATERIA = ef_carga * ef_descarga

    # Corrientes y potencias preferentes (idénticas a las del módulo).
    inv_carga = float(getattr(config_module, "INVERSOR_CORRIENTE_CARGA_MAX_A", 135.0))
    inv_descarga = float(getattr(config_module, "INVERSOR_CORRIENTE_DESCARGA_MAX_A", 135.0))
    rec_unidad = float(getattr(config_module, "BATERIA_CORRIENTE_RECOMENDADA_A_UNIDAD", 50.0))
    corriente_carga = min(num_baterias * rec_unidad, inv_carga)
    corriente_descarga = min(num_baterias * rec_unidad, inv_descarga)
    config_module.CORRIENTE_CARGA_PREFERIDA_A = corriente_carga
    config_module.CORRIENTE_DESCARGA_PREFERIDA_A = corriente_descarga
    config_module.BATERIA_POTENCIA_CARGA_PREFERIDA_KW = tension * corriente_carga / 1000.0
    config_module.BATERIA_POTENCIA_DESCARGA_PREFERIDA_KW = tension * corriente_descarga / 1000.0


# ==========================================================
# Modo demostración (sin conexión a las APIs externas)
# ==========================================================
#
# El modo demo ejecuta el MOTOR REAL. Únicamente se sustituyen las
# funciones que acceden a las APIs externas por datos de ejemplo con la
# MISMA estructura que espera el motor, de modo que siguen ejecutándose:
#
#     aemet.day_solar_score()                      índice solar diario
#     aemet_hourly.procesar_dia()                  factor meteorológico horario
#     esios.extraer_precios() / combinar_precios() combinación de precios
#     solar.perfil_referencia_fecha()              referencia FV climatológica
#     balance · dispatch · optimizer · weekly      cálculo completo
#
# No se modifica ningún fichero del motor: se reasignan atributos en los
# módulos ya importados (frontera Android).

_DEMO_SCENARIOS = [
    # (descripción del cielo, % precipitación, tmax)
    ("Despejado", 0, 29),
    ("Poco nuboso", 5, 27),
    ("Intervalos nubosos", 20, 25),
    ("Despejado", 0, 31),
    ("Poco nuboso", 10, 26),
    ("Cubierto", 60, 22),
    ("Nuboso", 30, 24),
]


def _install_demo_sources(engine, start_date) -> dict:
    """Sustituye únicamente el acceso a las APIs externas por ejemplos."""
    dias_diarios = _demo_daily_days(start_date, 7)
    dias_horarios = _demo_hourly_days(start_date, 2)
    serie_pvgis = _demo_pvgis_series(engine.solar, start_date)

    engine.aemet.fetch_forecast = lambda *a, **k: dias_diarios
    engine.aemet_hourly.fetch_forecast_hourly = lambda *a, **k: {
        "prediccion": {"dia": dias_horarios}
    }
    engine.esios.obtener_indicador = lambda indicador_id, *a, **k: _demo_esios_indicator(
        indicador_id, start_date
    )
    engine.solar.consultar_pvgis = lambda *a, **k: serie_pvgis

    return {"aemet": True, "esios": True, "pvgis": True}


def _demo_daily_days(start_date, days):
    """Días en el formato BRUTO de AEMET (los procesa day_solar_score)."""
    out = []
    for i in range(days):
        fecha = start_date + timedelta(days=i)
        descripcion, precip, tmax = _DEMO_SCENARIOS[i % len(_DEMO_SCENARIOS)]
        out.append(
            {
                "fecha": fecha.strftime("%Y-%m-%d") + "T00:00:00",
                "probPrecipitacion": [{"value": str(precip)} for _ in range(4)],
                "estadoCielo": [{"descripcion": descripcion} for _ in range(4)],
                "temperatura": {"maxima": str(tmax), "minima": str(tmax - 10)},
            }
        )
    return out


def _demo_hourly_days(start_date, days):
    """Días en el formato BRUTO de AEMET horario (los procesa procesar_dia)."""
    out = []
    for i in range(days):
        fecha = start_date + timedelta(days=i)
        temperatura, humedad, precipitacion, prob_prec, prob_tor, cielo, viento = (
            [] for _ in range(7)
        )
        for h in range(24):
            periodo = "%02d" % h
            sol = max(0.0, math.sin(math.pi * (h - 6) / 12))
            temperatura.append({"periodo": periodo, "value": str(round(15 + 9 * sol, 1))})
            humedad.append({"periodo": periodo, "value": "55"})
            precipitacion.append({"periodo": periodo, "value": "0"})
            prob_prec.append({"periodo": periodo, "value": "0"})
            prob_tor.append({"periodo": periodo, "value": "0"})
            descripcion = "Despejado" if 8 <= h <= 19 else "Poco nuboso"
            cielo.append({"periodo": periodo, "value": "11", "descripcion": descripcion})
            viento.append({"periodo": periodo, "velocidad": ["10"], "direccion": ["N"]})
        out.append(
            {
                "fecha": fecha.strftime("%Y-%m-%d") + "T00:00:00",
                "temperatura": temperatura,
                "humedadRelativa": humedad,
                "precipitacion": precipitacion,
                "probPrecipitacion": prob_prec,
                "probTormenta": prob_tor,
                "estadoCielo": cielo,
                "vientoAndRachaMax": viento,
            }
        )
    return out


def _demo_pvgis_series(solar_module, start_date):
    """Serie horaria en el formato que consume ``perfil_referencia_fecha``."""
    to_utc = _local_to_utc(solar_module)

    serie = []
    for d in range(2):
        fecha = start_date + timedelta(days=d)
        for h in range(24):
            sol = max(0.0, math.sin(math.pi * (h - 6) / 12))
            serie.append(
                {
                    "time": to_utc(fecha, h).strftime("%Y%m%d:%H%M"),
                    "G(i)": round(950.0 * sol, 1),
                    "T2m": round(18.0 + 9.0 * sol, 1),
                    "WS10m": 2.0,
                    "P": round(6050.0 * sol * 0.85, 1),
                }
            )
    return serie


def _local_to_utc(solar_module):
    """Devuelve una función (fecha, hora local) -> datetime UTC."""
    try:
        import pytz

        zona = getattr(solar_module, "ZONA_HORARIA_LOCAL", None) or pytz.timezone("Europe/Madrid")
        return lambda fecha, hora: zona.localize(
            datetime(fecha.year, fecha.month, fecha.day, hora, 0, 0)
        ).astimezone(pytz.utc)
    except Exception:  # sin pytz: se asume UTC (la curva se desplaza, no falla)
        return lambda fecha, hora: datetime(fecha.year, fecha.month, fecha.day, hora, 0, 0)


def _demo_esios_indicator(indicador_id, start_date):
    """Indicador ESIOS simulado (lo procesan extraer_precios/combinar_precios)."""
    if indicador_id == 600:  # SPOT (España)
        geo_id, geo_name = 3, "España"
        perfil = lambda h: 0.07 if 2 <= h <= 6 else (0.19 if 19 <= h <= 22 else 0.12)  # noqa: E731
    elif indicador_id == 1001:  # PVPC compra (Península)
        geo_id, geo_name = 8741, "Península"
        perfil = lambda h: 0.10 if 2 <= h <= 6 else (0.24 if 19 <= h <= 22 else 0.15)  # noqa: E731
    else:  # excedentes (España)
        geo_id, geo_name = 3, "España"
        perfil = lambda h: 0.05 if 2 <= h <= 6 else (0.03 if 19 <= h <= 22 else 0.07)  # noqa: E731

    values = []
    for h in range(24):
        values.append(
            {
                "geo_id": geo_id,
                "geo_name": geo_name,
                "datetime": "%sT%02d:00:00.000+02:00" % (start_date.isoformat(), h),
                "value": perfil(h) * 1000.0,
            }
        )
    return {"indicator": indicador_id, "values": values}


# ==========================================================
# Orquestación
# ==========================================================

def run_plan(
    config: dict | None = None,
    credentials: dict | None = None,
    soc: float = 0.60,
    refresh: bool = False,
    date=None,
    estrategia: str | None = None,
    demo: bool = False,
    engine=None,
) -> dict:
    """Ejecuta el motor y devuelve un resultado estructurado.

    Parameters
    ----------
    config : dict
        Configuración de la instalación (formularios Android).
    credentials : dict
        ``{"aemet_api_key": ..., "esios_token": ...}``. Nunca se devuelve.
    soc : float
        Estado de carga entre 0.0 y 1.0.
    refresh : bool
        Fuerza la descarga de datos externos (ignora la caché).
    date : datetime.date, optional
        Fecha de cálculo. Por defecto, hoy.
    estrategia : str, optional
        Estrategia del optimizador.
    demo : bool
        Modo demostración/offline. El motor Python se ejecuta con
        normalidad, pero las funciones de acceso a las APIs externas
        (AEMET, ESIOS, PVGIS) se sustituyen por datos de ejemplo. De este
        modo el cálculo (demanda, FV, balance, despacho, optimización y
        plan semanal) es el del motor real, sin conexiones de red.
    engine : namespace, optional
        Inyección del motor (pruebas). Si es ``None`` se carga el real.

    Returns
    -------
    dict
        Contrato JSON-serializable (ver ``docs/ARCHITECTURE.md``).
    """
    updated_at = datetime.now().isoformat(timespec="seconds")
    warnings: list[str] = []

    try:
        soc_value = validate_soc(soc)
        estrategia_value = validate_estrategia(estrategia)

        # En modo demo no se exigen credenciales reales: las funciones de
        # red están sustituidas, pero los módulos del motor las leen al
        # importarse. Se usan valores ficticios si no hay credenciales.
        if demo:
            credentials = credentials or {}
            if not (credentials.get("aemet_api_key") or credentials.get("esios_token")):
                credentials = {"aemet_api_key": "DEMO_OFFLINE", "esios_token": "DEMO_OFFLINE"}

        if engine is None:
            prepare_credentials(credentials)
            engine = load_engine()

        _require(engine, "config")
        _require(engine, "demand")
        _require(engine, "aemet")
        _require(engine, "aemet_hourly")
        _require(engine, "esios")
        _require(engine, "solar")
        _require(engine, "balance")
        _require(engine, "dispatch")
        _require(engine, "optimizer")
        _require(engine, "weekly")

        apply_installation_config(engine.config, config or {})

        configuracion = engine.config.obtener_configuracion_sistema()
        municipio = configuracion["localizacion"]["municipio"]

        hoy = date or _today()

        if demo:
            _install_demo_sources(engine, hoy)
            warnings.append(
                "Modo demostración: datos de ejemplo, sin conexión a AEMET/ESIOS/PVGIS."
            )

        demanda = engine.demand.obtener_configuracion_demanda(fecha=hoy)

        prevision_completa = engine.aemet.obtener_prevision_solar(municipio, refresh=refresh)
        prevision_hoy = _seleccionar_prevision_hoy(prevision_completa, hoy)

        prevision_horaria = engine.aemet_hourly.obtener_prevision_horaria(municipio, refresh=refresh)
        precios = engine.esios.obtener_precios(hoy, refresh=refresh)

        plan_semanal = engine.weekly.generar_plan_semanal(
            demanda=demanda,
            prevision_semanal=prevision_completa,
            prevision_horaria=prevision_horaria,
        )

        perfil_fv = engine.solar.obtener_perfil_fv_24h(
            fecha=hoy,
            configuracion=configuracion,
            prevision_horaria=prevision_horaria,
            prevision_diaria=prevision_hoy,
        )
        energia_fv = engine.solar.energia_fv_diaria(perfil_fv)
        pico_fv = engine.solar.obtener_pico_fv(perfil_fv)

        sistema = {
            "soc": soc_value,
            "configuracion": configuracion,
            "perfil_fv_24h": perfil_fv,
            "energia_fv_diaria_kwh": energia_fv,
            "pico_fv": pico_fv,
        }

        perfil_demanda = demanda["perfil_24h"]
        balance = engine.balance.calcular_balance_horario(
            perfil_demanda=perfil_demanda,
            perfil_fv=perfil_fv,
            precios=precios,
        )
        metricas_balance = engine.balance.calcular_metricas_balance(balance)

        sistema["balance_24h"] = balance
        sistema["metricas_balance"] = metricas_balance

        plan_horario = engine.dispatch.generar_plan_sostenible_predictivo(
            balance=balance,
            configuracion=configuracion,
            soc_inicial=soc_value,
        )
        metricas_plan = engine.dispatch.calcular_metricas_plan(plan_horario, configuracion)

        sistema["plan_horario"] = plan_horario
        sistema["metricas_plan"] = metricas_plan

        plan = engine.optimizer.optimizar(
            sistema=sistema,
            prevision=prevision_hoy,
            precios=precios,
            demanda=demanda,
            estrategia=estrategia_value,
        )

        warnings.extend(_build_warnings(configuracion, soc_value, prevision_hoy))

        result = _build_result(
            configuracion=configuracion,
            municipio=municipio,
            soc=soc_value,
            estrategia=estrategia_value,
            refresh=refresh,
            updated_at=updated_at,
            prevision_hoy=prevision_hoy,
            prevision_horaria=prevision_horaria,
            perfil_fv=perfil_fv,
            energia_fv=energia_fv,
            pico_fv=pico_fv,
            demanda=demanda,
            precios=precios,
            balance=balance,
            metricas_balance=metricas_balance,
            plan_horario=plan_horario,
            metricas_plan=metricas_plan,
            plan=plan,
            plan_semanal=plan_semanal,
            warnings=warnings,
            demo=demo,
            engine=engine,
        )
        result["status"] = "ok"
        return result

    except AdapterError as exc:
        return _error_result(exc, soc, updated_at)

    except BaseException as exc:  # noqa: BLE001 - contrato: nunca propagar
        adapter_error = classify_exception(exc)
        adapter_error.message = (
            f"{adapter_error.message}\n(DEBUG: {traceback.format_exc()})"
            if os.environ.get("GS_DEBUG")
            else adapter_error.message
        )
        return _error_result(adapter_error, soc, updated_at)


def _require(engine, name: str) -> None:
    module = getattr(engine, name, None)
    if module is None:
        raise AdapterError("ENGINE_ERROR", f"Módulo del motor no disponible: {name}", "engine")


def _today():
    return datetime.now().date()


def _seleccionar_prevision_hoy(prevision, hoy):
    target = hoy
    for dia in prevision or []:
        fecha = dia.get("fecha")
        if isinstance(fecha, datetime):
            fecha = fecha.date()
        if fecha == target:
            return dia
    raise AdapterError(
        "INVALID_RESPONSE",
        "No se encontró predicción meteorológica para el día actual.",
        "aemet",
    )


def _build_warnings(configuracion, soc, prevision_hoy):
    warnings = []
    bateria = configuracion.get("bateria", {})
    soc_min = bateria.get("soc_min_normal")
    soc_max = bateria.get("soc_max_normal")

    if soc_min is not None and soc < soc_min:
        warnings.append(
            "El SOC actual está por debajo de la ventana sostenible configurada."
        )
    if soc_max is not None and soc > soc_max:
        warnings.append(
            "El SOC actual está por encima de la ventana sostenible configurada."
        )
    if not prevision_hoy:
        warnings.append("No hay predicción meteorológica disponible.")
    return warnings


# ==========================================================
# Construcción del contrato de salida
# ==========================================================

def _build_result(**ctx) -> dict:
    engine = ctx["engine"]
    plan = ctx["plan"] or {}
    plan_semanal = ctx["plan_semanal"] or {}
    demo = bool(ctx.get("demo"))

    calidad = _calidad_solar(plan, ctx["prevision_hoy"])
    today_actions = _build_today_actions(ctx["plan_horario"], calidad, ctx["configuracion"], ctx["soc"])
    weekly_plan = _build_weekly_plan(plan_semanal)

    source_status = "demo" if demo else "ok"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "demo": demo,
        "warnings": ctx["warnings"],
        "updated_at": ctx["updated_at"],
        "cache_status": "updated" if ctx["refresh"] else "cached",
        # Nota: el motor no expone la procedencia por fuente; el adaptador
        # no la inventa (DATA_SOURCES.md, §7.2). En modo demo todas las
        # fuentes son datos de ejemplo.
        "sources": {
            "aemet": {"status": source_status, "from_cache": None},
            "pvgis": {"status": source_status, "from_cache": None},
            "esios": {"status": source_status, "from_cache": None},
        },
        "input": {
            "soc": ctx["soc"],
            "estrategia": ctx["estrategia"],
            "municipio": ctx["municipio"],
            "refresh": ctx["refresh"],
            "date": _iso(ctx["prevision_hoy"].get("fecha")),
        },
        "forecast": {
            "date": _iso(ctx["prevision_hoy"].get("fecha")),
            "score": ctx["prevision_hoy"].get("score"),
            "cielo_score": ctx["prevision_hoy"].get("cielo_score"),
            "precip": ctx["prevision_hoy"].get("precip"),
            "tmax": ctx["prevision_hoy"].get("tmax"),
            "tmin": ctx["prevision_hoy"].get("tmin"),
            "quality": calidad,
            "hourly": _compact_hourly_forecast(ctx["prevision_horaria"]),
        },
        "pv": {
            "energia_kwh": ctx["energia_fv"],
            "pico": ctx["pico_fv"],
            "perfil": [
                {
                    "hora": h.get("hora"),
                    "potencia_fv_kw": h.get("potencia_fv_kw"),
                    "irradiancia_predicha_wm2": h.get("irradiancia_predicha_wm2"),
                    "estado_cielo": h.get("estado_cielo"),
                    "temperatura_ambiente_c": h.get("temperatura_ambiente_c"),
                }
                for h in (ctx["perfil_fv"] or [])
            ],
        },
        "demand": {
            "ocupantes": ctx["demanda"].get("ocupantes"),
            "potencia_base_kw": ctx["demanda"].get("potencia_base_kw"),
            "energia_diaria_kwh": ctx["demanda"].get("energia_diaria_teorica_kwh"),
            "perfil": _compact_demand(ctx["demanda"].get("perfil_24h")),
        },
        "energy": {
            "balance_metrics": ctx["metricas_balance"],
            "plan_metrics": ctx["metricas_plan"],
            "balance": ctx["balance"],
        },
        "prices": _build_prices(ctx["precios"], plan),
        "today_actions": today_actions,
        "weekly_plan": weekly_plan,
        "strategic": {
            "estrategia": plan.get("estrategia"),
            "acciones": plan.get("acciones", []),
            "razones": plan.get("razones", []),
            "metricas": plan.get("metricas", {}),
            "sostenibilidad": plan.get("sostenibilidad", {}),
            "economia": plan.get("economia", {}),
        },
    }


def _calidad_solar(plan, prevision_hoy) -> str:
    meteorologia = (plan or {}).get("meteorologia") or {}
    calidad = meteorologia.get("calidad_solar")
    if calidad:
        return calidad
    score = float((prevision_hoy or {}).get("score") or 0.5)
    if score >= 0.75:
        return "alta"
    if score >= 0.50:
        return "media"
    return "baja"


def _build_today_actions(plan_horario, calidad, configuracion, soc):
    """Agrupa las decisiones horarias del despacho en recomendaciones.

    Las acciones por hora proceden de ``dispatch.generar_plan_sostenible_predictivo``;
    los códigos de razón se derivan de clasificaciones ya calculadas por el
    motor (calidad solar, precios, SOC), sin recalcular física.
    """
    if not plan_horario:
        return []

    informative = {"CARGAR_BATERIA", "VENDER", "DESCARGAR_BATERIA", "COMPRAR_RED"}

    groups = []
    current = None

    for registro in plan_horario:
        accion = (registro.get("accion") or "").strip()
        tokens = [t for t in (x.strip() for x in accion.split("+")) if t]
        key = " + ".join(tokens)

        if current and current["key"] == key:
            current["horas"].append(registro)
        else:
            current = {"key": key, "tokens": tokens, "horas": [registro]}
            groups.append(current)

    acciones = []
    for group in groups:
        tokens = group["tokens"]
        if not tokens:
            continue
        if all(t in ("EQUILIBRIO",) for t in tokens):
            continue
        if not (set(tokens) & informative):
            # Autoconsumo continuo: se omiten las horas sin decisión propia.
            continue

        horas = group["horas"]
        start = horas[0].get("hora")
        end = _hora_fin(horas[-1].get("hora"))
        dominant = _dominant_token(tokens)

        acciones.append(
            {
                "id": f"today-{start}-{dominant.lower()}",
                "kind": _action_kind(dominant),
                "title": _action_title(dominant),
                "time_window": f"{start} – {end}",
                "start": start,
                "end": end,
                "summary": _action_summary(dominant, calidad),
                "severity": _action_severity(dominant, calidad),
                "metrics": {
                    "fv_kw": _avg(horas, "fv_kw"),
                    "demanda_kw": _avg(horas, "demanda_kw"),
                    "precio_compra": _avg(horas, "precio_compra"),
                    "coste_neto_eur": _sum(horas, "coste_neto_eur"),
                },
                "reasons": _action_reasons(dominant, tokens, calidad, configuracion, soc, horas),
            }
        )

    acciones.sort(key=lambda a: (_severity_rank(a["severity"]), a["start"]))
    return acciones


def _dominant_token(tokens):
    priority = ["DESCARGAR_BATERIA", "CARGAR_BATERIA", "VENDER", "COMPRAR_RED", "AUTOCONSUMO", "EQUILIBRIO"]
    for token in priority:
        if token in tokens:
            return token
    return tokens[0]


def _action_kind(token):
    return {
        "CARGAR_BATERIA": "battery",
        "DESCARGAR_BATERIA": "battery",
        "VENDER": "grid",
        "COMPRAR_RED": "grid",
        "AUTOCONSUMO": "solar",
        "EQUILIBRIO": "solar",
    }.get(token, "solar")


def _action_title(token):
    return {
        "CARGAR_BATERIA": "Cargar batería con excedente solar",
        "DESCARGAR_BATERIA": "Usar la batería en vez de la red",
        "VENDER": "Verter excedente a la red",
        "COMPRAR_RED": "Cubrir demanda desde la red",
        "AUTOCONSUMO": "Aprovechar la producción solar",
        "EQUILIBRIO": "Sistema equilibrado",
    }.get(token, token)


def _action_summary(token, calidad):
    if token == "CARGAR_BATERIA":
        return "Conviene almacenar el excedente solar previsto en la batería."
    if token == "DESCARGAR_BATERIA":
        return "Conviene apoyarse en la batería en lugar de comprar red."
    if token == "VENDER":
        return "Se prevé excedente; conviene verterlo a la red."
    if token == "COMPRAR_RED":
        return "Será necesario recurrir a la red en esta franja."
    if token == "AUTOCONSUMO":
        return "La producción solar cubre el consumo directo."
    return "Sin decisión energética relevante."


def _action_severity(token, calidad):
    if token == "COMPRAR_RED":
        return "warning"
    if token in ("CARGAR_BATERIA", "DESCARGAR_BATERIA", "VENDER"):
        return "important"
    return "normal"


def _severity_rank(severity):
    return {"warning": 0, "important": 1, "normal": 2}.get(severity, 3)


def _action_reasons(token, tokens, calidad, configuracion, soc, horas):
    reasons = []
    bateria = (configuracion or {}).get("bateria", {})
    soc_min = bateria.get("soc_min_normal")

    if calidad == "alta":
        reasons.append({"code": "HIGH_PV_FORECAST", "detail": None})
    elif calidad == "baja":
        reasons.append({"code": "LOW_PV_FORECAST", "detail": None})

    if soc_min is not None:
        if soc is not None and soc < soc_min:
            reasons.append({"code": "LOW_SOC", "detail": None})
        elif soc is not None and soc >= soc_min:
            reasons.append({"code": "SUFFICIENT_SOC", "detail": None})

    if token in ("VENDER",) or "VENDER" in tokens:
        reasons.append({"code": "EXCESS_SURPLUS", "detail": None})

    precios = [_num(h.get("precio_compra")) for h in horas if h.get("precio_compra") is not None]
    if precios:
        reasons.append({"code": "PRICE_WINDOW", "detail": None})

    if not reasons:
        reasons.append({"code": "ENGINE_DECISION", "detail": None})

    return reasons


def _build_weekly_plan(plan_semanal):
    if not plan_semanal:
        return []

    dias = plan_semanal.get("dias") or []
    by_date = {}

    def ensure(fecha):
        key = _iso(fecha)
        if key not in by_date:
            by_date[key] = {
                "date": key,
                "weekday": None,
                "solar_quality": None,
                "confidence": None,
                "temps": {},
                "precip": None,
                "actions": [],
            }
        return by_date[key]

    for dia in dias:
        entry = ensure(dia.get("fecha"))
        entry["weekday"] = dia.get("dia_semana")
        entry["solar_quality"] = dia.get("calidad_solar")
        entry["confidence"] = dia.get("confianza")
        entry["temps"] = {
            "max": dia.get("temperatura_max"),
            "min": dia.get("temperatura_min"),
        }
        entry["precip"] = dia.get("precipitacion")

    for tarea in plan_semanal.get("tareas") or []:
        entry = ensure(tarea.get("fecha"))
        entry["actions"].append(
            {
                "id": "week-%s-%s" % (_iso(tarea.get("fecha")), tarea.get("servicio")),
                "title": tarea.get("descripcion") or tarea.get("servicio"),
                "start": tarea.get("hora_inicio"),
                "end": tarea.get("hora_fin"),
                "potencia_kw": tarea.get("potencia_kw"),
                "summary": tarea.get("motivo"),
                "kind": "load",
                "reasons": _weekly_reasons(tarea),
            }
        )

    for section, kind in (
        ("termicas", "climate"),
        ("acs", "acs"),
        ("riego", "irrigation"),
        ("hornos_solares", "appliance"),
    ):
        for item in plan_semanal.get(section) or []:
            if not isinstance(item, dict):
                continue
            fecha = item.get("fecha") or item.get("dia")
            if fecha is None and section == "acs":
                # El ACS puede venir agrupado por días; se omite si no hay fecha.
                continue
            entry = ensure(fecha)
            entry["actions"].append(
                {
                    "id": "week-%s-%s" % (_iso(fecha), section),
                    "title": item.get("descripcion") or item.get("servicio") or section,
                    "start": item.get("hora_inicio") or item.get("inicio"),
                    "end": item.get("hora_fin") or item.get("fin"),
                    "potencia_kw": item.get("potencia_kw"),
                    "summary": item.get("motivo") or item.get("razon"),
                    "kind": kind,
                    "reasons": _weekly_reasons(item),
                }
            )

    ordered = sorted(by_date.values(), key=lambda d: d["date"] or "")
    return ordered


def _weekly_reasons(item):
    reasons = []
    score = item.get("score_solar")
    if score is not None:
        if float(score) >= 0.7:
            reasons.append({"code": "HIGH_PV_FORECAST", "detail": None})
        elif float(score) < 0.5:
            reasons.append({"code": "LOW_PV_FORECAST", "detail": None})
    if item.get("flexible") or "tarea" in str(item.get("tipo", "tarea")):
        reasons.append({"code": "FLEXIBLE_LOAD", "detail": None})
    if not reasons:
        reasons.append({"code": "ENGINE_DECISION", "detail": None})
    return reasons


def _build_prices(precios, plan):
    serie = []
    for p in precios or []:
        if not isinstance(p, dict):
            continue
        serie.append(
            {
                "hora": p.get("hora"),
                "compra": p.get("precio_compra", p.get("compra")),
                "venta": p.get("precio_venta", p.get("venta")),
            }
        )

    economia = (plan or {}).get("economia") or {}
    return {
        "serie": serie,
        "min_compra": economia.get("hora_compra_minima"),
        "max_compra": economia.get("hora_compra_maxima"),
        "max_venta": economia.get("hora_venta_maxima"),
    }


def _compact_hourly_forecast(prevision_horaria):
    if not prevision_horaria:
        return []
    # La estructura del motor es una lista de días con horas anidadas.
    out = []
    for dia in prevision_horaria:
        if not isinstance(dia, dict):
            continue
        out.append(
            {
                "date": _iso(dia.get("fecha")),
                "horas": dia.get("horas") or dia.get("horario") or [],
            }
        )
    return out


def _compact_demand(perfil):
    if not perfil:
        return []
    out = []
    for reg in perfil:
        if not isinstance(reg, dict):
            continue
        out.append(
            {
                "hora": reg.get("hora"),
                "potencia_total_kw": reg.get("potencia_total_kw"),
            }
        )
    return out


# ==========================================================
# Utilidades
# ==========================================================

def _avg(rows, key):
    values = [_num(r.get(key)) for r in rows if r.get(key) is not None]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _sum(rows, key):
    values = [_num(r.get(key)) for r in rows if r.get(key) is not None]
    values = [v for v in values if v is not None]
    if not values:
        return None
    return round(sum(values), 5)


def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _hora_fin(hora):
    """Devuelve la hora de fin (inicio de la hora siguiente)."""
    try:
        hh = int(str(hora).split(":")[0])
    except (ValueError, TypeError):
        return hora
    if hh >= 23:
        return "24:00"
    return "%02d:00" % (hh + 1)


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _jsonable(obj):
    """Convierte estructuras del motor a tipos JSON-serializables."""
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return None
        return obj
    if isinstance(obj, (datetime, date)):
        return _iso(obj)
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    return str(obj)


def _error_result(error: AdapterError, soc, updated_at) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "warnings": [],
        "updated_at": updated_at,
        "cache_status": "unavailable",
        "error": error.to_dict(),
        "input": {"soc": soc},
        "forecast": {},
        "pv": {},
        "demand": {},
        "energy": {},
        "prices": {},
        "today_actions": [],
        "weekly_plan": [],
        "strategic": {},
    }


# ==========================================================
# Saneado del contrato (garantiza JSON-safe)
# ==========================================================

def normalize_result(result: dict) -> dict:
    """Devuelve una copia del resultado con tipos JSON-estrictos."""
    return _jsonable(result)  # type: ignore[return-value]


def dumps(result: dict) -> str:
    """Serializa el resultado a JSON (uso desde Python / pruebas)."""
    return json.dumps(normalize_result(result), ensure_ascii=False)


if __name__ == "__main__":  # pragma: no cover - utilidad de depuración
    print(json.dumps(dependency_probe(), indent=2, ensure_ascii=False))
