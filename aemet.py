#!/usr/bin/env python3
"""
aemet.py

Módulo encargado de obtener y procesar la predicción meteorológica
proporcionada por AEMET OpenData para su utilización en un sistema
de gestión energética fotovoltaica.

Este módulo tiene una responsabilidad concreta:

    AEMET -> predicción meteorológica -> estimación de disponibilidad solar

No contiene ninguna estrategia de gestión de baterías, precios de
electricidad o programación de electrodomésticos. Esas decisiones
corresponderán al módulo de optimización.

Funciones principales
----------------------
- Resolver el código AEMET de un municipio.
- Consultar la predicción meteorológica oficial de AEMET.
- Procesar nubosidad, precipitación y temperatura.
- Calcular un índice solar diario orientativo entre 0 y 1.
- Obtener previsiones para varios días.
- Seleccionar un intervalo temporal de predicción.

Autor: Enrique M. Moreno Pérez
"""

# ==========================================================
# Importaciones
# ==========================================================

import os
import time
import unicodedata

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

from municipios import MUNICIPIOS

# La caché evita repetir durante el mismo día consultas idénticas a AEMET.
# El primer acceso obtiene los datos de la red y los guarda; los siguientes
# reutilizan la copia local salvo que el usuario haya indicado --refresh.
from cache import (
    get_cache,
    make_key,
    set_cache,
)


# ==========================================================
# Configuración general
# ==========================================================

# Directorio donde está situado este archivo.
DIRECTORIO_PROYECTO = Path(__file__).resolve().parent

# Archivo que contiene las claves privadas de las APIs.
#
# Este archivo NO debe almacenarse en GitHub.
ARCHIVO_TOKENS = DIRECTORIO_PROYECTO / "mytoken.env"

# Endpoint de AEMET correspondiente a la predicción diaria
# por municipio.
BASE_URL_AEMET = (
    "https://opendata.aemet.es/opendata/api/"
    "prediccion/especifica/municipio/diaria/{municipio}"
)

# Tiempo máximo permitido para una petición HTTP.
TIMEOUT_AEMET = 20

# Número de intentos en caso de error temporal o limitación
# de peticiones por parte de AEMET.
REINTENTOS_AEMET = 3


# ==========================================================
# Carga de la clave de AEMET
# ==========================================================

def cargar_aemet_api_key() -> str:
    """
    Carga la clave AEMET_API_KEY desde el archivo mytoken.env.

    Returns
    -------
    str
        Clave de acceso a AEMET OpenData.

    Raises
    ------
    FileNotFoundError
        Si no existe el archivo mytoken.env.

    RuntimeError
        Si el archivo existe pero no contiene AEMET_API_KEY.
    """

    if not ARCHIVO_TOKENS.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de claves: "
            f"{ARCHIVO_TOKENS}"
        )

    load_dotenv(
        dotenv_path=ARCHIVO_TOKENS,
        override=True,
    )

    api_key = os.getenv("AEMET_API_KEY")

    if not api_key:
        raise RuntimeError(
            "No se encontró AEMET_API_KEY "
            "en el archivo mytoken.env."
        )

    return api_key


# La clave se carga una sola vez cuando se importa el módulo.
AEMET_API_KEY = cargar_aemet_api_key()


# ==========================================================
# Normalización de nombres
# ==========================================================

def normalizar_nombre(texto: str) -> str:
    """
    Normaliza nombres de municipios.

    La base de datos municipios.py utiliza nombres normalizados
    sin diferencias entre mayúsculas/minúsculas y sin tildes.

    Ejemplos
    --------
    "Tielmes" -> "tielmes"
    "San Sebastián" -> "san sebastian"
    "  Ávila  " -> "avila"

    Parameters
    ----------
    texto : str
        Texto que se desea normalizar.

    Returns
    -------
    str
        Texto normalizado.
    """

    texto = str(texto).strip().lower()

    # Separar los caracteres acentuados:
    # á -> a + acento
    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    # Eliminar las marcas diacríticas.
    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    # Eliminar espacios repetidos.
    texto = " ".join(
        texto.split()
    )

    return texto


# ==========================================================
# Conversión nombre municipio -> código AEMET
# ==========================================================

def obtener_codigo(municipio: str) -> str:
    """
    Devuelve el código AEMET correspondiente a un municipio.

    Se pueden utilizar dos formas:

        obtener_codigo("Tielmes")
        obtener_codigo("Maracena")

    o directamente:

        obtener_codigo("18127")

    Parameters
    ----------
    municipio : str
        Nombre del municipio o código AEMET de cinco dígitos.

    Returns
    -------
    str
        Código AEMET de cinco dígitos.

    Raises
    ------
    ValueError
        Si el municipio no existe en municipios.py o el código
        suministrado no tiene cinco dígitos.
    """

    municipio = str(municipio).strip()

    # Si el usuario ya proporciona el código AEMET,
    # no es necesario consultar el diccionario.
    if municipio.isdigit():

        if len(municipio) != 5:
            raise ValueError(
                "El código AEMET debe tener cinco dígitos."
            )

        return municipio

    nombre_normalizado = normalizar_nombre(
        municipio
    )

    if nombre_normalizado not in MUNICIPIOS:
        raise ValueError(
            f"No se encontró el municipio '{municipio}' "
            "en la base de datos de municipios."
        )

    return MUNICIPIOS[nombre_normalizado]


# ==========================================================
# Comunicación HTTP con AEMET
# ==========================================================

def get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    retries: int = REINTENTOS_AEMET,
) -> Any:
    """
    Realiza una petición HTTP GET y devuelve la respuesta JSON.

    La función incorpora reintentos automáticos cuando AEMET
    responde con código HTTP 429, que indica que se ha superado
    temporalmente el límite de peticiones.

    Parameters
    ----------
    url : str
        URL que se desea consultar.

    params : dict, optional
        Parámetros de la petición HTTP.

    retries : int
        Número máximo de intentos.

    Returns
    -------
    Any
        Contenido JSON recibido desde AEMET.

    Raises
    ------
    requests.exceptions.RequestException
        Para errores de conexión o HTTP.

    RuntimeError
        Si se alcanza el número máximo de reintentos.
    """

    for intento in range(retries):

        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT_AEMET,
        )

        # AEMET puede limitar temporalmente el número
        # de consultas realizadas.
        if response.status_code == 429:

            espera = 5 * (intento + 1)

            print(
                "AEMET ha limitado temporalmente "
                "las peticiones. "
                f"Esperando {espera} segundos..."
            )

            time.sleep(espera)
            continue

        response.raise_for_status()

        return response.json()

    raise RuntimeError(
        "No se pudo realizar la consulta a AEMET "
        "después de varios intentos."
    )


# ==========================================================
# Descarga de la predicción meteorológica
# ==========================================================

def fetch_forecast(
    municipio_id: str,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Descarga la predicción diaria de AEMET para un municipio.

    AEMET OpenData utiliza dos peticiones:

    1. La primera devuelve una URL temporal en el campo 'datos'.
    2. La segunda URL contiene la predicción meteorológica real.

    Parameters
    ----------
    municipio_id : str
        Código AEMET del municipio.

    api_key : str, optional
        Clave de AEMET. Si no se proporciona se utiliza
        AEMET_API_KEY.

    Returns
    -------
    list
        Lista de días incluidos en la predicción de AEMET.
    """

    if api_key is None:
        api_key = AEMET_API_KEY

    url = BASE_URL_AEMET.format(
        municipio=municipio_id
    )

    # Primera petición:
    # solicitar a AEMET la URL temporal de los datos.
    primera_respuesta = get_json(
        url,
        params={
            "api_key": api_key,
        },
    )

    url_datos = primera_respuesta.get(
        "datos"
    )

    if not url_datos:
        raise RuntimeError(
            "AEMET no proporcionó la URL de datos "
            f"esperada: {primera_respuesta}"
        )

    # Segunda petición:
    # descargar la predicción propiamente dicha.
    forecast = get_json(
        url_datos
    )

    if not isinstance(forecast, list) or not forecast:
        raise RuntimeError(
            "La predicción de AEMET tiene "
            "un formato inesperado."
        )

    dias = (
        forecast[0]
        .get("prediccion", {})
        .get("dia", [])
    )

    if not dias:
        raise RuntimeError(
            "AEMET no ha proporcionado días "
            "de predicción."
        )

    return dias


# ==========================================================
# Procesamiento de la precipitación
# ==========================================================

def avg_precip(
    prob_precip_list: List[Dict[str, Any]],
) -> float:
    """
    Calcula la probabilidad media de precipitación del día.

    AEMET puede proporcionar varias probabilidades asociadas
    a diferentes intervalos horarios. Aquí se obtiene una media
    sencilla de todos los valores disponibles.

    Parameters
    ----------
    prob_precip_list : list
        Lista de probabilidades de precipitación de AEMET.

    Returns
    -------
    float
        Probabilidad media de precipitación en porcentaje.
    """

    valores = []

    for item in prob_precip_list or []:

        valor = item.get("value")

        if valor in ("", None):
            continue

        try:
            valores.append(
                float(valor)
            )

        except (ValueError, TypeError):
            # Si AEMET proporciona algún dato no numérico,
            # simplemente se ignora.
            continue

    if not valores:
        return 0.0

    return sum(valores) / len(valores)


# ==========================================================
# Procesamiento del estado del cielo
# ==========================================================

def puntuacion_estado_cielo(
    descripcion: str,
) -> float:
    """
    Convierte una descripción meteorológica de AEMET en un
    índice aproximado de disponibilidad solar.

    El resultado está comprendido entre 0 y 1.

    Esta función NO pretende calcular todavía la irradiancia
    solar física. Es un indicador meteorológico simplificado
    utilizado para la primera versión del sistema.

    Parameters
    ----------
    descripcion : str
        Descripción textual del estado del cielo.

    Returns
    -------
    float
        Índice entre 0 y 1.
    """

    texto = normalizar_nombre(
        descripcion
    )

    # Se comprueban primero las situaciones más adversas
    # para evitar coincidencias parciales con "nuboso".
    if (
        "tormenta" in texto
        or "cubierto" in texto
    ):
        return 0.10

    if "muy nuboso" in texto:
        return 0.20

    if "intervalos nubosos" in texto:
        return 0.60

    if "nuboso" in texto:
        return 0.40

    if "poco nuboso" in texto:
        return 0.80

    if "despejado" in texto:
        return 1.00

    # Si la descripción no puede clasificarse,
    # se adopta un valor neutral.
    return 0.50


def sky_score(
    estado_cielo_list: List[Dict[str, Any]],
) -> float:
    """
    Calcula una puntuación media diaria del estado del cielo.

    A diferencia de la primera versión del programa, no basta
    con que aparezca una única franja 'despejada' para asignar
    1.0 a todo el día.

    Se calcula la puntuación de cada intervalo meteorológico
    y posteriormente se obtiene la media.

    Parameters
    ----------
    estado_cielo_list : list
        Lista de estados del cielo proporcionados por AEMET.

    Returns
    -------
    float
        Puntuación media entre 0 y 1.
    """

    if not estado_cielo_list:
        return 0.50

    puntuaciones = []

    for item in estado_cielo_list:

        descripcion = (
            item.get("descripcion")
            or ""
        )

        if descripcion:
            puntuaciones.append(
                puntuacion_estado_cielo(
                    descripcion
                )
            )

    if not puntuaciones:
        return 0.50

    return (
        sum(puntuaciones)
        / len(puntuaciones)
    )


# ==========================================================
# Índice solar diario
# ==========================================================

def day_solar_score(
    day: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calcula un índice diario orientativo de aprovechamiento solar.

    El índice combina tres factores meteorológicos:

    1. Estado del cielo.
    2. Probabilidad de precipitación.
    3. Penalización aproximada por temperaturas elevadas.

    El índice resultante está comprendido entre:

        0.0 -> condiciones muy desfavorables
        1.0 -> condiciones muy favorables

    IMPORTANTE
    ----------
    Este índice es actualmente heurístico.

    En versiones posteriores podrá sustituirse o complementarse
    con datos de irradiancia solar, geometría del campo FV,
    orientación, inclinación y temperatura de módulo.

    Parameters
    ----------
    day : dict
        Día meteorológico devuelto por AEMET.

    Returns
    -------
    dict
        Información meteorológica procesada.
    """

    # ------------------------------------------------------
    # Precipitación
    # ------------------------------------------------------

    precip_avg = avg_precip(
        day.get(
            "probPrecipitacion",
            [],
        )
    )

    # ------------------------------------------------------
    # Estado del cielo
    # ------------------------------------------------------

    cielo = sky_score(
        day.get(
            "estadoCielo",
            [],
        )
    )

    # ------------------------------------------------------
    # Temperatura máxima
    # ------------------------------------------------------

    temperatura = day.get(
        "temperatura",
        {},
    )

    tmax = temperatura.get(
        "maxima"
    )

    # En paneles fotovoltaicos, temperaturas elevadas
    # producen generalmente una reducción de eficiencia.
    #
    # Esta penalización es deliberadamente sencilla.
    # Más adelante utilizaremos el coeficiente térmico
    # real de los módulos FV instalados.
    penalizacion_temperatura = 0.0

    try:

        tmax_num = float(
            tmax
        )

        if tmax_num >= 40:
            penalizacion_temperatura = 0.08

        elif tmax_num >= 35:
            penalizacion_temperatura = 0.05

        elif tmax_num >= 30:
            penalizacion_temperatura = 0.02

    except (ValueError, TypeError):
        pass

    # ------------------------------------------------------
    # Factor de precipitación
    # ------------------------------------------------------

    precip_limitada = min(
        max(
            precip_avg,
            0.0,
        ),
        100.0,
    )

    factor_precipitacion = (
        100.0 - precip_limitada
    ) / 100.0

    # ------------------------------------------------------
    # Índice solar
    # ------------------------------------------------------

    # El estado del cielo tiene actualmente mayor peso
    # que la probabilidad de precipitación.
    score = (
        cielo * 0.80
        + factor_precipitacion * 0.20
        - penalizacion_temperatura
    )

    # El resultado se restringe al intervalo [0, 1].
    score = max(
        0.0,
        min(
            1.0,
            score,
        ),
    )

    # ------------------------------------------------------
    # Fecha
    # ------------------------------------------------------

    fecha_txt = (
        day.get(
            "fecha",
            "",
        )[:10]
    )

    if not fecha_txt:
        raise ValueError(
            "El día meteorológico no contiene fecha."
        )

    fecha = datetime.strptime(
        fecha_txt,
        "%Y-%m-%d",
    ).date()

    # ------------------------------------------------------
    # Resultado
    # ------------------------------------------------------

    return {
        "fecha": fecha,

        "score": round(
            score,
            3,
        ),

        "precip": round(
            precip_avg,
            1,
        ),

        "tmax": tmax,

        "cielo_score": round(
            cielo,
            3,
        ),

        "factor_precipitacion": round(
            factor_precipitacion,
            3,
        ),

        "penalizacion_temperatura": (
            penalizacion_temperatura
        ),
    }


# ==========================================================
# Predicción solar completa de un municipio
# ==========================================================

def obtener_prevision_solar(
    municipio: str,
    refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Obtiene y procesa toda la predicción disponible para un municipio.

    Por defecto utiliza una caché diaria para evitar repetir consultas
    idénticas a AEMET. La primera consulta correcta del día se descarga
    desde AEMET y se almacena en RAM y en disco. Las siguientes llamadas
    reutilizan esos datos.

    Si ``refresh=True``, se ignora la caché existente, se vuelve a consultar
    AEMET y, si la respuesta es válida, se sustituye la copia del día.

    Parameters
    ----------
    municipio : str
        Nombre o código AEMET del municipio.

    refresh : bool, optional
        Si es True, fuerza una nueva consulta a AEMET.
        Por defecto es False.

    Returns
    -------
    list
        Lista de días meteorológicos procesados.

    Notes
    -----
    Se almacenan en caché los datos RAW devueltos por AEMET, no el resultado
    de ``day_solar_score()``. De esta forma, si posteriormente se modifica
    nuestro algoritmo de procesamiento, podemos recalcular los índices usando
    exactamente la misma predicción meteorológica original.
    """

    # Resolver primero el código hace que "Tielmes" y "28146", por ejemplo,
    # apunten a la misma entrada de caché.
    codigo = obtener_codigo(
        municipio
    )

    # La clave identifica de manera inequívoca esta fuente y esta petición.
    # La fecha NO necesita incluirse aquí porque cache.py ya separa físicamente
    # las entradas por día.
    clave_cache = make_key(
        "aemet",
        "prediccion_diaria",
        municipio=codigo,
    )

    # Con refresh=False se intenta RAM y después disco.
    # Con refresh=True get_cache() devuelve None deliberadamente.
    dias_raw = get_cache(
        clave_cache,
        refresh=refresh,
    )

    if dias_raw is None:

        # No existe una copia válida o el usuario ha solicitado --refresh.
        # Sólo en este punto se accede realmente a AEMET OpenData.
        dias_raw = fetch_forecast(
            codigo
        )

        # fetch_forecast() ya comprueba que AEMET haya devuelto una lista
        # no vacía de días. Por eso sólo guardamos la caché después de que
        # esta función haya terminado correctamente.
        set_cache(
            clave_cache,
            dias_raw,
            metadata={
                "provider": "AEMET OpenData",
                "request": "prediccion_diaria",
                "municipio": codigo,
            },
        )

    # Procesamos siempre los datos después de recuperarlos.
    # Esto es deliberado: la caché conserva la predicción original de AEMET,
    # mientras que nuestro modelo puede evolucionar independientemente.
    dias_analizados = [
        day_solar_score(dia)
        for dia in dias_raw
    ]

    dias_analizados.sort(
        key=lambda dia: dia["fecha"]
    )

    return dias_analizados


# ==========================================================
# Predicción solar del día actual
# ==========================================================

def obtener_prevision_solar_hoy(
    municipio: str,
    refresh: bool = False,
) -> Dict[str, Any]:
    """
    Obtiene la predicción solar correspondiente al día actual.

    Parameters
    ----------
    municipio : str
        Nombre o código AEMET del municipio.

    refresh : bool, optional
        Si es True, ignora la caché y fuerza una nueva consulta a AEMET.

    Returns
    -------
    dict
        Predicción meteorológica procesada de hoy.
    """

    prevision = obtener_prevision_solar(
        municipio,
        refresh=refresh,
    )

    hoy = datetime.now().date()

    for dia in prevision:

        if dia["fecha"] == hoy:
            return dia

    raise RuntimeError(
        "AEMET no ha proporcionado una predicción "
        "para el día actual."
    )


# ==========================================================
# Utilidades temporales
# ==========================================================

def next_monday(from_date):
    """
    Devuelve la fecha del próximo lunes posterior
    a la fecha indicada.
    """

    days_ahead = (
        7 - from_date.weekday()
    ) % 7

    if days_ahead == 0:
        days_ahead = 7

    return (
        from_date
        + timedelta(
            days=days_ahead
        )
    )


def filter_days(
    analyzed: List[Dict[str, Any]],
    modo: str,
) -> List[Dict[str, Any]]:
    """
    Filtra una predicción meteorológica según el intervalo
    solicitado.

    Modos disponibles
    -----------------
    hoy
        Desde hoy.

    manana
        Desde mañana.

    proximo_lunes
        Desde el próximo lunes.

    El horizonte máximo solicitado es de siete días, aunque
    AEMET puede proporcionar menos días de predicción.

    Parameters
    ----------
    analyzed : list
        Predicción ya procesada.

    modo : str
        Modo temporal.

    Returns
    -------
    list
        Días disponibles dentro del intervalo solicitado.
    """

    hoy = datetime.now().date()

    if modo == "hoy":

        inicio = hoy

    elif modo == "manana":

        inicio = (
            hoy
            + timedelta(days=1)
        )

    elif modo == "proximo_lunes":

        inicio = next_monday(
            hoy
        )

    else:

        raise ValueError(
            f"Modo no válido: '{modo}'. "
            "Valores permitidos: "
            "hoy, manana, proximo_lunes."
        )

    fin = (
        inicio
        + timedelta(days=7)
    )

    return [
        dia
        for dia in analyzed
        if (
            inicio
            <= dia["fecha"]
            < fin
        )
    ]


# ==========================================================
# Utilidades descriptivas
# ==========================================================

def nombre_dia(fecha) -> str:
    """
    Devuelve el nombre del día de la semana en castellano.
    """

    nombres = [
        "lunes",
        "martes",
        "miércoles",
        "jueves",
        "viernes",
        "sábado",
        "domingo",
    ]

    return nombres[
        fecha.weekday()
    ]


def franja_aproximada(
    score: float,
) -> str:
    """
    Devuelve una franja solar orientativa basada en el índice.

    Esta función es únicamente descriptiva.

    No se utilizará como sustituto de una predicción horaria
    cuando el sistema evolucione hacia el control predictivo.
    """

    if score >= 0.80:
        return "12:00 a 16:00"

    if score >= 0.65:
        return "12:00 a 15:00"

    if score >= 0.50:
        return "13:00 a 15:00"

    return (
        "sin una franja especialmente favorable"
    )
