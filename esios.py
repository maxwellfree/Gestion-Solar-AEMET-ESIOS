#!/usr/bin/env python3
"""
esios.py

Módulo encargado de obtener y procesar los precios eléctricos
proporcionados por la API de ESIOS (Red Eléctrica).

Responsabilidad del módulo
--------------------------

    ESIOS -> indicadores eléctricos -> precios horarios estructurados

Este archivo NO contiene decisiones sobre:

- carga o descarga de baterías;
- autoconsumo;
- vertido a red;
- optimización económica;
- sostenibilidad;
- programación de cargas.

Todas esas decisiones corresponderán posteriormente al módulo
optimizer.py.

Este módulo proporciona principalmente:

- acceso autenticado a la API de ESIOS;
- descarga de indicadores;
- extracción de valores por zona geográfica;
- conversión de €/MWh a €/kWh;
- combinación de precios SPOT, PVPC y excedentes;
- consulta simplificada de todos los precios de una fecha.

Autor: Enrique M. Moreno Pérez
"""

# ==========================================================
# Importaciones
# ==========================================================

import os

from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests
from dotenv import load_dotenv

# La caché evita repetir consultas idénticas a ESIOS durante el mismo día.
# Se almacenan las respuestas originales de cada indicador, no la tabla
# procesada, para conservar los datos de entrada y poder reprocesarlos después.
from cache import (
    get_cache,
    make_key,
    set_cache,
)

# ==========================================================
# Configuración de ESIOS
# ==========================================================

# URL base de la API de ESIOS.
BASE_URL_ESIOS = "https://api.esios.ree.es"

# Identificadores de los indicadores utilizados.
#
# Estos identificadores corresponden a las tres magnitudes
# necesarias para la gestión energética:
#
# - precio del mercado SPOT;
# - precio de compra PVPC;
# - compensación de excedentes de autoconsumo.
#
# Se mantienen centralizados aquí para evitar depender
# de un archivo config.py externo.

PRECIO_SPOT = 600
PRECIO_COMPRA_PVPC = 1001
PRECIO_EXCEDENTES = 1739


# ==========================================================
# Configuración geográfica
# ==========================================================

GEO_ESPANA = 3
GEO_PENINSULA = 8741

# ==========================================================
# Configuración geográfica
# ==========================================================

# Identificador geográfico utilizado por ESIOS para España.
#
# Se emplea, entre otros, en:
# - mercado SPOT;
# - precio de excedentes.
GEO_ESPANA = 3

# Identificador correspondiente a la Península.
#
# Se utiliza para el indicador PVPC.
GEO_PENINSULA = 8741


# ==========================================================
# Configuración general
# ==========================================================

DIRECTORIO_PROYECTO = Path(__file__).resolve().parent

# Archivo privado que contiene las claves API.
#
# Este archivo NO debe publicarse en GitHub.
ARCHIVO_TOKENS = DIRECTORIO_PROYECTO / "mytoken.env"

# Tiempo máximo permitido para cada consulta HTTP.
TIMEOUT_ESIOS = 30


# ==========================================================
# Carga de la clave API
# ==========================================================

def cargar_esios_api_key() -> str:
    """
    Carga ESIOS_API_KEY desde el archivo mytoken.env.

    Returns
    -------
    str
        Clave de acceso a la API de ESIOS.

    Raises
    ------
    FileNotFoundError
        Si no existe el archivo mytoken.env.

    RuntimeError
        Si el archivo existe pero no contiene ESIOS_API_KEY.
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

    api_key = os.getenv(
        "ESIOS_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "No se encontró ESIOS_API_KEY "
            "en el archivo mytoken.env."
        )

    return api_key


# Cargamos la clave una sola vez al importar el módulo.
ESIOS_API_KEY = cargar_esios_api_key()


# ==========================================================
# Cabeceras HTTP
# ==========================================================

HEADERS_ESIOS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "x-api-key": ESIOS_API_KEY,
}


# ==========================================================
# Función HTTP auxiliar
# ==========================================================

def get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Realiza una petición GET a ESIOS y devuelve la respuesta JSON.

    Parameters
    ----------
    url : str
        URL de ESIOS que se desea consultar.

    params : dict, optional
        Parámetros GET de la petición.

    Returns
    -------
    dict
        Respuesta JSON.

    Raises
    ------
    requests.exceptions.RequestException
        Si ocurre algún error HTTP o de conexión.

    ValueError
        Si la respuesta no contiene JSON válido.
    """

    response = requests.get(
        url,
        headers=HEADERS_ESIOS,
        params=params,
        timeout=TIMEOUT_ESIOS,
    )

    response.raise_for_status()

    return response.json()


# ==========================================================
# Catálogo de indicadores
# ==========================================================

def obtener_indicadores() -> List[Dict[str, Any]]:
    """
    Descarga el catálogo completo de indicadores de ESIOS.

    Esta función es principalmente útil para:

    - diagnóstico;
    - búsqueda de nuevos indicadores;
    - comprobación de IDs;
    - desarrollo del programa.

    No será necesario consultar todo el catálogo durante
    el funcionamiento normal del optimizador.

    Returns
    -------
    list
        Lista de indicadores disponibles.
    """

    datos = get_json(
        f"{BASE_URL_ESIOS}/indicators"
    )

    indicadores = datos.get(
        "indicators"
    )

    if indicadores is None:
        raise RuntimeError(
            "La respuesta de ESIOS no contiene "
            "el campo 'indicators'."
        )

    return indicadores


def buscar_indicadores(
    texto: str,
) -> List[Dict[str, Any]]:
    """
    Busca indicadores cuyo nombre contenga un texto determinado.

    Parameters
    ----------
    texto : str
        Texto que se desea buscar.

    Returns
    -------
    list
        Indicadores coincidentes.
    """

    texto = texto.lower().strip()

    indicadores = obtener_indicadores()

    resultados = []

    for indicador in indicadores:

        nombre = str(
            indicador.get(
                "name",
                "",
            )
        )

        if texto in nombre.lower():
            resultados.append(
                indicador
            )

    return resultados


# ==========================================================
# Conversión de fechas
# ==========================================================

def normalizar_fecha(
    fecha: Union[str, date, datetime],
) -> str:
    """
    Convierte distintos tipos de fecha al formato YYYY-MM-DD.

    Se admiten:

        "2026-08-08"
        datetime.date(...)
        datetime.datetime(...)

    Parameters
    ----------
    fecha : str, date o datetime
        Fecha que se desea normalizar.

    Returns
    -------
    str
        Fecha en formato YYYY-MM-DD.

    Raises
    ------
    ValueError
        Si el formato proporcionado no es válido.
    """

    if isinstance(
        fecha,
        datetime,
    ):
        return fecha.strftime(
            "%Y-%m-%d"
        )

    if isinstance(
        fecha,
        date,
    ):
        return fecha.strftime(
            "%Y-%m-%d"
        )

    if isinstance(
        fecha,
        str,
    ):

        fecha = fecha.strip()

        try:
            fecha_obj = datetime.strptime(
                fecha,
                "%Y-%m-%d",
            )

        except ValueError as error:
            raise ValueError(
                "La fecha debe tener formato "
                "YYYY-MM-DD."
            ) from error

        return fecha_obj.strftime(
            "%Y-%m-%d"
        )

    raise TypeError(
        "La fecha debe ser str, date o datetime."
    )


# ==========================================================
# Descarga de un indicador
# ==========================================================

def obtener_indicador(
    indicador_id: int,
    fecha_inicio: Union[str, date, datetime],
    fecha_fin: Union[str, date, datetime],
    time_trunc: str = "hour",
    time_agg: str = "average",
    refresh: bool = False,
) -> Dict[str, Any]:
    """
    Obtiene un indicador de ESIOS para un intervalo temporal.

    La respuesta original del campo ``indicator`` se guarda en una caché
    diaria. La clave incluye todos los parámetros que pueden modificar la
    respuesta: ID del indicador, fechas, resolución y agregación.

    Parameters
    ----------
    indicador_id : int
        Identificador numérico del indicador ESIOS.

    fecha_inicio : str, date o datetime
        Fecha inicial.

    fecha_fin : str, date o datetime
        Fecha final.

    time_trunc : str
        Resolución temporal solicitada.

    time_agg : str
        Tipo de agregación utilizada por ESIOS.

    refresh : bool, optional
        Si es True, ignora la caché existente y fuerza una nueva consulta.

    Returns
    -------
    dict
        Contenido original del campo 'indicator' devuelto por ESIOS.
    """

    inicio = normalizar_fecha(
        fecha_inicio
    )

    fin = normalizar_fecha(
        fecha_fin
    )

    # Todos estos parámetros afectan potencialmente al resultado y, por tanto,
    # deben formar parte de la clave. La API key nunca se incluye.
    clave_cache = make_key(
        "esios",
        "indicador",
        indicador_id=int(indicador_id),
        fecha_inicio=inicio,
        fecha_fin=fin,
        time_trunc=time_trunc,
        time_agg=time_agg,
        locale="es",
    )

    indicador = get_cache(
        clave_cache,
        refresh=refresh,
    )

    if indicador is not None:
        return indicador

    url = (
        f"{BASE_URL_ESIOS}/indicators/"
        f"{indicador_id}"
    )

    parametros = {
        "start_date": (
            f"{inicio}T00:00:00"
        ),
        "end_date": (
            f"{fin}T23:59:59"
        ),
        "time_trunc": time_trunc,
        "time_agg": time_agg,
        "locale": "es",
    }

    # Sólo llegamos aquí si no había caché válida o se ha solicitado refresh.
    datos = get_json(
        url,
        params=parametros,
    )

    indicador = datos.get(
        "indicator"
    )

    if indicador is None:
        raise RuntimeError(
            f"La respuesta del indicador "
            f"{indicador_id} no contiene "
            "el campo 'indicator'."
        )

    # Guardamos únicamente después de validar que la respuesta contiene el
    # indicador esperado. Así una respuesta errónea nunca sustituye a la caché.
    set_cache(
        clave_cache,
        indicador,
        metadata={
            "provider": "ESIOS - Red Electrica",
            "request": "indicador",
            "indicador_id": int(indicador_id),
            "fecha_inicio": inicio,
            "fecha_fin": fin,
            "time_trunc": time_trunc,
            "time_agg": time_agg,
        },
    )

    return indicador


# ==========================================================
# Extracción de valores de una zona geográfica
# ==========================================================

def extraer_precios(
    indicador: Dict[str, Any],
    geo_id: int,
) -> List[Dict[str, Any]]:
    """
    Extrae los valores de precio correspondientes a una
    determinada zona geográfica.

    Cada registro resultante contiene:

        datetime
        hora
        precio_mwh
        precio_kwh
        zona

    Parameters
    ----------
    indicador : dict
        Indicador completo devuelto por ESIOS.

    geo_id : int
        Identificador geográfico.

    Returns
    -------
    list
        Serie temporal ordenada.
    """

    resultados = []

    for registro in indicador.get(
        "values",
        [],
    ):

        if registro.get(
            "geo_id"
        ) != geo_id:
            continue

        datetime_texto = registro.get(
            "datetime"
        )

        if not datetime_texto:
            continue

        # ESIOS incluye zona horaria y milisegundos.
        # Para combinar las distintas series nos basta
        # con conservar YYYY-MM-DDTHH:MM:SS.
        fecha_hora = datetime.strptime(
            datetime_texto[:19],
            "%Y-%m-%dT%H:%M:%S",
        )

        try:

            precio_mwh = float(
                registro["value"]
            )

        except (
            KeyError,
            ValueError,
            TypeError,
        ):
            continue

        # ESIOS proporciona estos indicadores en €/MWh.
        #
        # Para gestión doméstica resulta más cómodo trabajar
        # en €/kWh.
        precio_kwh = (
            precio_mwh / 1000.0
        )

        resultados.append(
            {
                "datetime": fecha_hora,
                "fecha": fecha_hora.date(),
                "hora": fecha_hora.strftime(
                    "%H:%M"
                ),
                "precio_mwh": precio_mwh,
                "precio_kwh": precio_kwh,
                "zona": registro.get(
                    "geo_name",
                    "",
                ),
            }
        )

    resultados.sort(
        key=lambda registro: (
            registro["datetime"]
        )
    )

    return resultados


# ==========================================================
# Combinación de las tres series de precios
# ==========================================================

def combinar_precios(
    spot: List[Dict[str, Any]],
    pvpc: List[Dict[str, Any]],
    excedentes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Combina las series SPOT, PVPC y excedentes utilizando
    fecha y hora como clave común.

    El resultado tendrá una fila por intervalo temporal.

    Parameters
    ----------
    spot : list
        Precio SPOT de España.

    pvpc : list
        Precio de compra PVPC para Península.

    excedentes : list
        Precio de compensación de excedentes.

    Returns
    -------
    list
        Tabla combinada.
    """

    spot_por_fecha = {
        registro["datetime"]: registro
        for registro in spot
    }

    pvpc_por_fecha = {
        registro["datetime"]: registro
        for registro in pvpc
    }

    excedentes_por_fecha = {
        registro["datetime"]: registro
        for registro in excedentes
    }

    # Solo conservamos fechas presentes en las tres series.
    fechas_comunes = sorted(
        set(spot_por_fecha)
        & set(pvpc_por_fecha)
        & set(excedentes_por_fecha)
    )

    tabla = []

    for fecha_hora in fechas_comunes:

        precio_spot = (
            spot_por_fecha[
                fecha_hora
            ]["precio_kwh"]
        )

        precio_compra = (
            pvpc_por_fecha[
                fecha_hora
            ]["precio_kwh"]
        )

        precio_venta = (
            excedentes_por_fecha[
                fecha_hora
            ]["precio_kwh"]
        )

        tabla.append(
            {
                "datetime": fecha_hora,
                "fecha": fecha_hora.date(),
                "hora": fecha_hora.strftime(
                    "%H:%M"
                ),
                "spot": precio_spot,
                "compra": precio_compra,
                "venta": precio_venta,

                # Diferencia entre el coste evitado
                # de compra y el ingreso obtenido
                # vendiendo ese mismo kWh.
                #
                # Esta magnitud NO es todavía una decisión
                # de optimización; es únicamente un dato
                # económico que optimizer.py podrá utilizar.
                "diferencia_compra_venta": (
                    precio_compra
                    - precio_venta
                ),
            }
        )

    return tabla


# ==========================================================
# Consulta conjunta de precios
# ==========================================================

def obtener_precios(
    fecha: Union[str, date, datetime],
    refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Obtiene todos los precios eléctricos relevantes para una fecha.

    Internamente consulta tres indicadores independientes de ESIOS:

    - mercado SPOT;
    - precio de compra PVPC;
    - compensación de excedentes.

    Cada indicador dispone de su propia entrada de caché. Esto permite
    reutilizar por separado cualquier serie ya descargada y conserva los
    datos originales para futuras tareas de validación.

    Parameters
    ----------
    fecha : str, date o datetime
        Fecha deseada.

    refresh : bool, optional
        Si es True, fuerza la actualización de los tres indicadores ESIOS.

    Returns
    -------
    list
        Tabla temporal combinada con precios SPOT, compra PVPC,
        compensación de excedentes y diferencia compra-venta.
    """

    fecha_txt = normalizar_fecha(
        fecha
    )

    # ------------------------------------------------------
    # Mercado SPOT
    # ------------------------------------------------------

    indicador_spot = obtener_indicador(
        PRECIO_SPOT,
        fecha_txt,
        fecha_txt,
        refresh=refresh,
    )

    precios_spot = extraer_precios(
        indicador_spot,
        GEO_ESPANA,
    )

    # ------------------------------------------------------
    # Precio de compra PVPC
    # ------------------------------------------------------

    indicador_pvpc = obtener_indicador(
        PRECIO_COMPRA_PVPC,
        fecha_txt,
        fecha_txt,
        refresh=refresh,
    )

    precios_pvpc = extraer_precios(
        indicador_pvpc,
        GEO_PENINSULA,
    )

    # ------------------------------------------------------
    # Compensación de excedentes
    # ------------------------------------------------------

    indicador_excedentes = obtener_indicador(
        PRECIO_EXCEDENTES,
        fecha_txt,
        fecha_txt,
        refresh=refresh,
    )

    precios_excedentes = extraer_precios(
        indicador_excedentes,
        GEO_ESPANA,
    )

    # ------------------------------------------------------
    # Combinación final
    # ------------------------------------------------------

    return combinar_precios(
        precios_spot,
        precios_pvpc,
        precios_excedentes,
    )


def obtener_precios_hoy(
    refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Atajo para obtener los precios correspondientes al día actual.

    Parameters
    ----------
    refresh : bool, optional
        Si es True, fuerza una nueva consulta de los indicadores ESIOS.
    """

    return obtener_precios(
        datetime.now().date(),
        refresh=refresh,
    )


# ==========================================================
# Resumen estadístico
# ==========================================================

def resumir_precios(
    tabla: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calcula un pequeño resumen estadístico de una tabla
    de precios.

    Esta función no toma decisiones de optimización.

    Únicamente identifica:

    - compra mínima;
    - compra máxima;
    - venta mínima;
    - venta máxima.

    Parameters
    ----------
    tabla : list
        Tabla devuelta por obtener_precios().

    Returns
    -------
    dict
        Resumen de precios.
    """

    if not tabla:
        return {}

    return {
        "compra_minima": min(
            tabla,
            key=lambda registro: (
                registro["compra"]
            ),
        ),

        "compra_maxima": max(
            tabla,
            key=lambda registro: (
                registro["compra"]
            ),
        ),

        "venta_minima": min(
            tabla,
            key=lambda registro: (
                registro["venta"]
            ),
        ),

        "venta_maxima": max(
            tabla,
            key=lambda registro: (
                registro["venta"]
            ),
        ),
    }


# ==========================================================
# Presentación opcional
# ==========================================================

def mostrar_tabla(
    tabla: List[Dict[str, Any]],
) -> None:
    """
    Muestra por terminal una tabla sencilla de precios.

    Esta función se mantiene únicamente como herramienta
    de diagnóstico y visualización.

    No forma parte de la lógica de optimización.
    """

    if not tabla:
        print(
            "No hay datos de precios disponibles."
        )
        return

    fecha_txt = tabla[0][
        "datetime"
    ].strftime(
        "%Y-%m-%d"
    )

    print()
    print(
        f"Precios eléctricos para el día "
        f"{fecha_txt}"
    )

    print(
        "Valores expresados en €/kWh"
    )

    print()

    print(
        f"{'Hora':<8}"
        f"{'SPOT':>12}"
        f"{'Compra PVPC':>16}"
        f"{'Excedentes':>16}"
        f"{'Diferencia':>16}"
    )

    print(
        "-" * 68
    )

    for registro in tabla:

        print(
            f"{registro['hora']:<8}"
            f"{registro['spot']:>12.5f}"
            f"{registro['compra']:>16.5f}"
            f"{registro['venta']:>16.5f}"
            f"{registro['diferencia_compra_venta']:>16.5f}"
        )


def mostrar_resumen(
    tabla: List[Dict[str, Any]],
) -> None:
    """
    Muestra el resumen de precios por terminal.

    Es una función de presentación, no de decisión.
    """

    resumen = resumir_precios(
        tabla
    )

    if not resumen:
        print(
            "No hay datos para calcular "
            "el resumen."
        )
        return

    compra_minima = resumen[
        "compra_minima"
    ]

    compra_maxima = resumen[
        "compra_maxima"
    ]

    venta_minima = resumen[
        "venta_minima"
    ]

    venta_maxima = resumen[
        "venta_maxima"
    ]

    print()
    print("Resumen")
    print("-------")

    print(
        "Compra PVPC mínima : "
        f"{compra_minima['hora']} — "
        f"{compra_minima['compra']:.5f} €/kWh"
    )

    print(
        "Compra PVPC máxima : "
        f"{compra_maxima['hora']} — "
        f"{compra_maxima['compra']:.5f} €/kWh"
    )

    print(
        "Excedentes mínimos : "
        f"{venta_minima['hora']} — "
        f"{venta_minima['venta']:.5f} €/kWh"
    )

    print(
        "Excedentes máximos : "
        f"{venta_maxima['hora']} — "
        f"{venta_maxima['venta']:.5f} €/kWh"
    )
