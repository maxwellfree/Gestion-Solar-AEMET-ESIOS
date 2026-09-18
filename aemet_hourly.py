#!/usr/bin/env python3
"""
aemet_hourly.py

Predicción meteorológica horaria para el sistema de gestión solar.

Este módulo consulta la predicción horaria municipal de AEMET
OpenData y transforma la respuesta en una estructura sencilla
para su uso posterior en solar.py y optimizer.py.

----------------------------------------------------------------
OBJETIVO
----------------------------------------------------------------

aemet.py
    -> predicción diaria / horizonte de varios días.

aemet_hourly.py
    -> predicción horaria / próximas aproximadamente 48 horas.

La información horaria será utilizada principalmente para mejorar
la estimación fotovoltaica:

    - estado del cielo;
    - temperatura;
    - humedad relativa;
    - viento;
    - precipitación;
    - probabilidad de precipitación;
    - probabilidad de tormenta.

----------------------------------------------------------------
SALIDA
----------------------------------------------------------------

La función principal:

    obtener_prevision_horaria()

devuelve una lista como:

[
    {
        "datetime": datetime(...),
        "fecha": date(...),
        "hora": "12:00",

        "temperatura_c": 34.0,
        "humedad_relativa": 25.0,

        "estado_cielo_codigo": "11",
        "estado_cielo": "Despejado",

        "precipitacion_mm": 0.0,
        "prob_precipitacion": 0.0,
        "prob_tormenta": 0.0,

        "viento_velocidad_kmh": 12.0,
        "viento_direccion": "SO",

        "factor_nubosidad": 1.0,
        "factor_meteorologico": 1.0,
    },
    ...
]

----------------------------------------------------------------
IMPORTANTE
----------------------------------------------------------------

El factor meteorológico construido aquí es todavía una
aproximación.

No representa directamente una transmitancia atmosférica ni un
índice físico de claridad.

Su objetivo es proporcionar a solar.py una corrección horaria
mejor que el score meteorológico diario utilizado anteriormente.

Posteriormente podrá calibrarse utilizando producción fotovoltaica
real medida por el inversor.

Autor: Enrique M. Moreno Pérez
"""


# ==========================================================
# Importaciones
# ==========================================================

import os
import sys
import time

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from dotenv import load_dotenv

from municipios import MUNICIPIOS

# La caché evita repetir durante el mismo día consultas idénticas a AEMET.
# Guardamos la respuesta bruta de AEMET y procesamos después sus datos horarios.
from cache import (
    get_cache,
    make_key,
    set_cache,
)


# ==========================================================
# Archivo de claves
# ==========================================================

DIRECTORIO_PROYECTO = (
    Path(__file__).resolve().parent
)

ARCHIVO_TOKENS = (
    DIRECTORIO_PROYECTO
    / "mytoken.env"
)


if not ARCHIVO_TOKENS.exists():

    raise FileNotFoundError(
        f"No se encontró el archivo de claves: "
        f"{ARCHIVO_TOKENS}"
    )


load_dotenv(
    dotenv_path=ARCHIVO_TOKENS,
    override=True,
)


AEMET_API_KEY = os.getenv(
    "AEMET_API_KEY"
)


if not AEMET_API_KEY:

    raise RuntimeError(
        "No se encontró AEMET_API_KEY "
        "en mytoken.env"
    )


# ==========================================================
# Endpoint AEMET
# ==========================================================
#
# Predicción horaria específica para un municipio.
#
# AEMET proporciona predicción horaria municipal para un
# horizonte aproximado de dos días.

BASE_URL = (
    "https://opendata.aemet.es/opendata/api/"
    "prediccion/especifica/municipio/horaria/{municipio}"
)


# ==========================================================
# Conversión municipio -> código AEMET
# ==========================================================

def obtener_codigo_municipio(
    municipio: str,
) -> str:
    """
    Convierte el nombre de un municipio en su código AEMET.

    También admite directamente un código numérico de cinco
    dígitos.

    Parameters
    ----------
    municipio : str
        Nombre o código AEMET.

    Returns
    -------
    str
        Código AEMET de cinco dígitos.
    """

    municipio = str(
        municipio
    ).strip()

    # ------------------------------------------------------
    # Código proporcionado directamente
    # ------------------------------------------------------

    if municipio.isdigit():

        if len(
            municipio
        ) != 5:

            raise ValueError(
                "El código AEMET debe tener "
                "cinco dígitos."
            )

        return municipio

    # ------------------------------------------------------
    # Búsqueda por nombre
    # ------------------------------------------------------

    nombre = (
        municipio
        .lower()
        .strip()
    )

    if nombre not in MUNICIPIOS:

        raise ValueError(
            f"No se encontró el municipio "
            f"'{municipio}' en municipios.py."
        )

    return str(
        MUNICIPIOS[
            nombre
        ]
    )


# ==========================================================
# Descarga JSON con reintentos
# ==========================================================

def get_json(
    url: str,
    params=None,
    retries: int = 3,
):
    """
    Realiza una consulta HTTP y devuelve JSON.

    Implementa un pequeño sistema de reintentos para los
    límites temporales de AEMET.
    """

    for intento in range(
        retries
    ):

        respuesta = requests.get(
            url,
            params=params,
            timeout=25,
        )

        # --------------------------------------------------
        # Rate limit
        # --------------------------------------------------

        if respuesta.status_code == 429:

            espera = (
                5
                * (
                    intento
                    + 1
                )
            )

            print(
                "AEMET ha limitado temporalmente "
                "las peticiones. "
                f"Esperando {espera} segundos..."
            )

            time.sleep(
                espera
            )

            continue

        respuesta.raise_for_status()

        return respuesta.json()

    raise RuntimeError(
        "Demasiados intentos fallidos al consultar AEMET."
    )


# ==========================================================
# Obtención de predicción horaria bruta
# ==========================================================

def fetch_forecast_hourly(
    municipio_id: str,
    api_key: str,
):
    """
    Descarga la predicción horaria de AEMET.

    El endpoint AEMET devuelve inicialmente un JSON que contiene
    una URL en el campo:

        "datos"

    Esa segunda URL contiene la predicción real.
    """

    url = BASE_URL.format(
        municipio=municipio_id
    )

    primera_respuesta = get_json(
        url,
        params={
            "api_key": api_key
        },
    )

    data_url = primera_respuesta.get(
        "datos"
    )

    if not data_url:

        raise RuntimeError(
            "AEMET no devolvió la URL de datos "
            "de predicción horaria."
        )

    forecast = get_json(
        data_url
    )

    if (
        not isinstance(
            forecast,
            list,
        )
        or not forecast
    ):

        raise RuntimeError(
            "Formato inesperado en la predicción "
            "horaria de AEMET."
        )

    return forecast[
        0
    ]


# ==========================================================
# Conversión segura de números
# ==========================================================

def a_float(
    valor,
    default=None,
):
    """
    Convierte un valor a float de forma segura.
    """

    if valor in (
        None,
        "",
    ):
        return default

    try:

        return float(
            valor
        )

    except (
        TypeError,
        ValueError,
    ):

        return default


# ==========================================================
# Extracción de series horarias AEMET
# ==========================================================

def construir_diccionario_horario(
    lista,
    campo_valor="value",
):
    """
    Convierte una lista AEMET con entradas horarias en:

        {
            0: valor,
            1: valor,
            ...
        }

    Muchos campos de AEMET utilizan:

        {
            "value": ...,
            "periodo": "12"
        }
    """

    resultado = {}

    for elemento in lista or []:

        periodo = elemento.get(
            "periodo"
        )

        if periodo in (
            None,
            "",
        ):
            continue

        try:

            hora = int(
                periodo
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        resultado[
            hora
        ] = elemento.get(
            campo_valor
        )

    return resultado


# ==========================================================
# Estado del cielo
# ==========================================================

def construir_estado_cielo(
    lista,
):
    """
    Construye un diccionario horario con código y descripción
    del estado del cielo.
    """

    resultado = {}

    for elemento in lista or []:

        periodo = elemento.get(
            "periodo"
        )

        if periodo in (
            None,
            "",
        ):
            continue

        try:

            hora = int(
                periodo
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        resultado[
            hora
        ] = {
            "codigo": elemento.get(
                "value"
            ),

            "descripcion": (
                elemento.get(
                    "descripcion"
                )
                or ""
            ),
        }

    return resultado


# ==========================================================
# Viento
# ==========================================================

def construir_viento(
    lista,
):
    """
    Construye información horaria de viento.
    """

    resultado = {}

    for elemento in lista or []:

        periodo = elemento.get(
            "periodo"
        )

        if periodo in (
            None,
            "",
        ):
            continue

        try:

            hora = int(
                periodo
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        velocidad = elemento.get(
            "velocidad"
        )

        if isinstance(
            velocidad,
            list,
        ):

            velocidad = (
                velocidad[0]
                if velocidad
                else None
            )

        direccion = elemento.get(
            "direccion"
        )

        if isinstance(
            direccion,
            list,
        ):

            direccion = (
                direccion[0]
                if direccion
                else None
            )

        resultado[
            hora
        ] = {
            "velocidad_kmh": a_float(
                velocidad
            ),

            "direccion": direccion,
        }

    return resultado


# ==========================================================
# Factor de nubosidad
# ==========================================================

def factor_nubosidad_desde_descripcion(
    descripcion: str,
) -> float:
    """
    Asigna un factor aproximado de disponibilidad solar a partir
    del estado del cielo previsto por AEMET.

    Este factor NO es todavía una transmitancia atmosférica
    estrictamente física.

    Se emplea como aproximación inicial para modular la
    irradiancia climatológica de PVGIS.

    Returns
    -------
    float
        Factor entre aproximadamente 0.10 y 1.00.
    """

    texto = (
        descripcion
        or ""
    ).lower()

    # ------------------------------------------------------
    # Casos muy desfavorables primero
    # ------------------------------------------------------

    if (
        "torment" in texto
        or "cubierto con lluvia" in texto
        or "muy nuboso con lluvia" in texto
    ):

        return 0.15

    if (
        "cubierto" in texto
        or "muy nuboso" in texto
    ):

        return 0.25

    # ------------------------------------------------------
    # Nubosidad importante
    # ------------------------------------------------------

    if (
        "nuboso" in texto
        and "intervalos" not in texto
    ):

        return 0.45

    # ------------------------------------------------------
    # Nubosidad variable
    # ------------------------------------------------------

    if "intervalos nubosos" in texto:

        return 0.65

    # ------------------------------------------------------
    # Poco nuboso
    # ------------------------------------------------------

    if "poco nuboso" in texto:

        return 0.85

    # ------------------------------------------------------
    # Despejado
    # ------------------------------------------------------

    if "despejado" in texto:

        return 1.00

    # ------------------------------------------------------
    # Desconocido
    # ------------------------------------------------------

    return 0.70


# ==========================================================
# Factor de precipitación
# ==========================================================

def factor_precipitacion(
    prob_precipitacion,
    precipitacion_mm,
):
    """
    Calcula una penalización meteorológica complementaria.

    La nubosidad es el factor principal.

    La precipitación se utiliza como corrección adicional.
    """

    prob = a_float(
        prob_precipitacion,
        0.0,
    )

    mm = a_float(
        precipitacion_mm,
        0.0,
    )

    prob = max(
        0.0,
        min(
            100.0,
            prob,
        ),
    )

    # ------------------------------------------------------
    # Corrección suave por probabilidad
    # ------------------------------------------------------

    factor_prob = (
        1.0
        - 0.003
        * prob
    )

    # ------------------------------------------------------
    # Corrección adicional si existe lluvia prevista
    # ------------------------------------------------------

    if mm >= 5.0:

        factor_mm = 0.65

    elif mm >= 1.0:

        factor_mm = 0.80

    elif mm > 0.0:

        factor_mm = 0.90

    else:

        factor_mm = 1.0

    factor = (
        factor_prob
        * factor_mm
    )

    return max(
        0.50,
        min(
            1.0,
            factor,
        ),
    )


# ==========================================================
# Factor meteorológico horario
# ==========================================================

def calcular_factor_meteorologico(
    descripcion_cielo,
    prob_precipitacion,
    precipitacion_mm,
    prob_tormenta,
):
    """
    Construye un factor horario meteorológico inicial.

    La variable dominante es el estado del cielo.

    Las probabilidades de lluvia y tormenta actúan como
    correcciones complementarias.
    """

    factor_cielo = (
        factor_nubosidad_desde_descripcion(
            descripcion_cielo
        )
    )

    factor_precip = (
        factor_precipitacion(
            prob_precipitacion,
            precipitacion_mm,
        )
    )

    tormenta = a_float(
        prob_tormenta,
        0.0,
    )

    factor_tormenta = (
        1.0
        - 0.004
        * max(
            0.0,
            min(
                100.0,
                tormenta,
            ),
        )
    )

    factor = (
        factor_cielo
        * factor_precip
        * factor_tormenta
    )

    return max(
        0.10,
        min(
            1.0,
            factor,
        ),
    )


# ==========================================================
# Procesamiento de un día AEMET
# ==========================================================

def procesar_dia(
    dia: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Convierte un día de predicción AEMET en registros horarios.
    """

    fecha_texto = (
        dia.get(
            "fecha",
            ""
        )[:10]
    )

    if not fecha_texto:

        return []

    fecha = datetime.strptime(
        fecha_texto,
        "%Y-%m-%d",
    ).date()

    # ------------------------------------------------------
    # Series simples
    # ------------------------------------------------------

    temperatura = construir_diccionario_horario(
        dia.get(
            "temperatura",
            []
        )
    )

    humedad = construir_diccionario_horario(
        dia.get(
            "humedadRelativa",
            []
        )
    )

    precipitacion = construir_diccionario_horario(
        dia.get(
            "precipitacion",
            []
        )
    )

    prob_precipitacion = construir_diccionario_horario(
        dia.get(
            "probPrecipitacion",
            []
        )
    )

    prob_tormenta = construir_diccionario_horario(
        dia.get(
            "probTormenta",
            []
        )
    )

    # ------------------------------------------------------
    # Estado del cielo
    # ------------------------------------------------------

    cielo = construir_estado_cielo(
        dia.get(
            "estadoCielo",
            []
        )
    )

    # ------------------------------------------------------
    # Viento
    # ------------------------------------------------------

    viento = construir_viento(
        dia.get(
            "vientoAndRachaMax",
            []
        )
    )

    # ======================================================
    # Construcción de las 24 horas
    # ======================================================

    registros = []

    for hora in range(
        24
    ):

        cielo_hora = cielo.get(
            hora,
            {},
        )

        descripcion_cielo = cielo_hora.get(
            "descripcion",
            "",
        )

        precipitacion_hora = a_float(
            precipitacion.get(
                hora
            ),
            0.0,
        )

        prob_precipitacion_hora = a_float(
            prob_precipitacion.get(
                hora
            ),
            0.0,
        )

        prob_tormenta_hora = a_float(
            prob_tormenta.get(
                hora
            ),
            0.0,
        )

        factor_nubosidad = (
            factor_nubosidad_desde_descripcion(
                descripcion_cielo
            )
        )

        factor_meteo = (
            calcular_factor_meteorologico(
                descripcion_cielo,
                prob_precipitacion_hora,
                precipitacion_hora,
                prob_tormenta_hora,
            )
        )

        viento_hora = viento.get(
            hora,
            {},
        )

        fecha_hora = datetime.combine(
            fecha,
            datetime.min.time(),
        ).replace(
            hour=hora
        )

        registros.append(
            {
                "datetime": fecha_hora,

                "fecha": fecha,

                "hora": (
                    f"{hora:02d}:00"
                ),

                "temperatura_c": a_float(
                    temperatura.get(
                        hora
                    )
                ),

                "humedad_relativa": a_float(
                    humedad.get(
                        hora
                    )
                ),

                "estado_cielo_codigo": cielo_hora.get(
                    "codigo"
                ),

                "estado_cielo": (
                    descripcion_cielo
                ),

                "precipitacion_mm": (
                    precipitacion_hora
                ),

                "prob_precipitacion": (
                    prob_precipitacion_hora
                ),

                "prob_tormenta": (
                    prob_tormenta_hora
                ),

                "viento_velocidad_kmh": (
                    viento_hora.get(
                        "velocidad_kmh"
                    )
                ),

                "viento_direccion": (
                    viento_hora.get(
                        "direccion"
                    )
                ),

                "factor_nubosidad": round(
                    factor_nubosidad,
                    3,
                ),

                "factor_meteorologico": round(
                    factor_meteo,
                    3,
                ),
            }
        )

    return registros


# ==========================================================
# Función principal
# ==========================================================

def obtener_prevision_horaria(
    municipio: str,
    refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Obtiene la predicción horaria procesada para un municipio.

    La respuesta bruta de AEMET se conserva en una caché diaria. Esto evita
    repetir las dos peticiones HTTP necesarias cada vez que se ejecuta el
    programa y, además, permite conservar la predicción original para futuras
    tareas de validación.

    Con ``refresh=False`` se intenta utilizar primero la caché. Con
    ``refresh=True`` se ignora la copia existente y se solicita una nueva
    predicción a AEMET.

    Parameters
    ----------
    municipio : str
        Nombre o código municipal.

    refresh : bool, optional
        Si es True, fuerza una nueva consulta a AEMET.
        Por defecto es False.

    Returns
    -------
    list
        Registros horarios ordenados cronológicamente.

    Notes
    -----
    Se almacena el JSON bruto devuelto por AEMET antes de aplicar
    ``procesar_dia()``. Por tanto, si en el futuro cambia nuestro cálculo del
    factor meteorológico, podremos reprocesar la predicción histórica original.
    """

    # Normalizamos primero el municipio a su código oficial. De esta forma
    # distintas formas de referirse al mismo municipio comparten caché.
    codigo = obtener_codigo_municipio(
        municipio
    )

    # La clave identifica la petición. cache.py añade por separado la fecha
    # diaria, por lo que no es necesario incorporarla aquí.
    clave_cache = make_key(
        "aemet",
        "prediccion_horaria",
        municipio=codigo,
    )

    # Si existe una entrada válida para hoy se reutiliza. Si el usuario ha
    # indicado --refresh, get_cache() devuelve None y obliga a descargar.
    forecast = get_cache(
        clave_cache,
        refresh=refresh,
    )

    if forecast is None:

        # Esta función realiza las dos peticiones propias de AEMET OpenData:
        # primero obtiene la URL temporal y después descarga el JSON real.
        forecast = fetch_forecast_hourly(
            codigo,
            AEMET_API_KEY,
        )

        # fetch_forecast_hourly() ya valida que AEMET haya devuelto una lista
        # no vacía. Sólo después de una descarga correcta actualizamos caché.
        set_cache(
            clave_cache,
            forecast,
            metadata={
                "provider": "AEMET OpenData",
                "request": "prediccion_horaria",
                "municipio": codigo,
            },
        )

    # A partir de aquí no importa si forecast procede de Internet o del disco:
    # el procesamiento meteorológico es exactamente el mismo.
    dias = (
        forecast.get(
            "prediccion",
            {}
        ).get(
            "dia",
            []
        )
    )

    if not dias:

        raise RuntimeError(
            "AEMET no devolvió predicción horaria."
        )

    registros = []

    for dia in dias:

        registros.extend(
            procesar_dia(
                dia
            )
        )

    registros.sort(
        key=lambda registro: registro[
            "datetime"
        ]
    )

    return registros


# ==========================================================
# Selección de un día
# ==========================================================

def seleccionar_dia(
    prevision_horaria,
    fecha,
):
    """
    Selecciona las horas correspondientes a una fecha concreta.
    """

    return [
        registro
        for registro in prevision_horaria
        if registro[
            "fecha"
        ] == fecha
    ]


# ==========================================================
# Presentación
# ==========================================================

def mostrar_prevision_horaria(
    prevision_horaria,
):
    """
    Muestra por terminal la predicción horaria procesada.
    """

    print()
    print("Predicción meteorológica horaria AEMET")
    print("--------------------------------------")

    print(
        f"{'Fecha':<12}"
        f"{'Hora':<7}"
        f"{'Temp':>7}"
        f"{'HR':>7}"
        f"{'Cielo':>24}"
        f"{'Pprec':>8}"
        f"{'Fmet':>8}"
    )

    print(
        "-" * 73
    )

    for registro in prevision_horaria:

        fecha_txt = registro[
            "fecha"
        ].strftime(
            "%d/%m/%Y"
        )

        temperatura = registro.get(
            "temperatura_c"
        )

        humedad = registro.get(
            "humedad_relativa"
        )

        descripcion = (
            registro.get(
                "estado_cielo",
                ""
            )
        )

        prob_prec = registro.get(
            "prob_precipitacion",
            0.0,
        )

        factor = registro.get(
            "factor_meteorologico",
            1.0,
        )

        temp_txt = (
            f"{temperatura:.0f}"
            if temperatura is not None
            else "-"
        )

        humedad_txt = (
            f"{humedad:.0f}"
            if humedad is not None
            else "-"
        )

        print(
            f"{fecha_txt:<12}"
            f"{registro['hora']:<7}"
            f"{temp_txt:>7}"
            f"{humedad_txt:>7}"
            f"{descripcion[:23]:>24}"
            f"{prob_prec:>8.0f}"
            f"{factor:>8.2f}"
        )


# ==========================================================
# Prueba directa
# ==========================================================

if __name__ == "__main__":

    try:

        # --------------------------------------------------
        # Para la prueba aislada se obtiene el municipio
        # directamente desde config.py.
        # --------------------------------------------------

        from config import (
            obtener_configuracion_sistema,
        )

        configuracion = (
            obtener_configuracion_sistema()
        )

        municipio = configuracion[
            "localizacion"
        ][
            "municipio"
        ]

        datos = obtener_prevision_horaria(
            municipio
        )

        mostrar_prevision_horaria(
            datos
        )

    except (
        FileNotFoundError,
        ValueError,
        RuntimeError,
        requests.exceptions.RequestException,
    ) as error:

        print(
            f"Error: {error}",
            file=sys.stderr,
        )

        sys.exit(1)
