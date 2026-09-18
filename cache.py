#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
cache.py
========

Sistema de caché para Gestión Solar Predictiva.

OBJETIVO
--------
Evitar repetir innecesariamente consultas a servicios externos como AEMET
o ESIOS cada vez que se ejecuta el programa.

La política normal es:

    1. Buscar primero el dato en memoria RAM.
    2. Si no está en RAM, buscarlo en la caché del disco.
    3. Si tampoco está en disco, el módulo que hace la petición consulta
       AEMET/ESIOS y guarda la respuesta mediante set_cache().

Si el usuario ejecuta el programa con --refresh, el programa llamador debe
usar get_cache(..., refresh=True). La primera petición de cada clave ignora la
copia previa y obliga a consultar el servicio externo. Una vez guardada
correctamente la respuesta nueva, las siguientes peticiones idénticas dentro
de esa misma ejecución reutilizan la copia recién actualizada.

IMPORTANTE
----------
Este módulo NO realiza las consultas a AEMET ni a ESIOS. Sólo almacena y
recupera sus resultados. Esto permite mantener separadas la adquisición
de datos y la lógica de caché.

Los tokens y claves API nunca deben incluirse en las claves ni en los datos
de metadatos de la caché.
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime, timedelta


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CACHE_VERSION = 1

# Número de días naturales que se conservarán en disco.
#
# Ejemplo:
#   CACHE_RETENTION_DAYS = 30
#
# significa que se conserva el día actual y los 29 días naturales anteriores.
#
# Si se pone:
#   CACHE_RETENTION_DAYS = 1
#
# sólo se conserva el día actual.
#
# Si se pone:
#   CACHE_RETENTION_DAYS = 0
#
# se desactiva la limpieza automática y se conserva todo indefinidamente.
CACHE_RETENTION_DAYS = 365

# La carpeta "cache" se crea junto a este archivo cache.py.
# De esta forma el funcionamiento no depende del directorio desde el que
# el usuario haya ejecutado main.py.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, ".gitignore", "cache")

# Primer nivel de caché: memoria RAM del proceso actual.
#
# Esta variable sólo existe mientras Python está ejecutándose. Al cerrar el
# programa se pierde, pero la copia del disco permanece para ejecuciones futuras.
_MEMORY_CACHE = {}

# Claves que ya han sido actualizadas mediante --refresh durante ESTA ejecución.
#
# Problema que resuelve:
#   si una misma petición se solicita dos veces en un único proceso ejecutado
#   con --refresh, sólo la primera debe volver a Internet. Después de guardar
#   correctamente la respuesta nueva, las llamadas posteriores deben reutilizar
#   esa copia recién obtenida desde RAM.
#
# El conjunto se pierde al terminar Python, que es exactamente lo deseado:
# una nueva ejecución con --refresh volverá a forzar una actualización.
_REFRESHED_KEYS = set()


# ============================================================================
# FUNCIONES INTERNAS
# ============================================================================

def _today():
    """Devuelve la fecha local de la máquina en formato YYYY-MM-DD."""
    return date.today().isoformat()


def _json_default(value):
    """
    Convierte algunos objetos habituales a tipos que JSON puede almacenar.

    Es útil, por ejemplo, si una respuesta contiene datetime o determinados
    escalares/arrays de NumPy. Si el objeto no se puede convertir de manera
    segura, se lanza TypeError en vez de guardar datos ambiguos.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if hasattr(value, "tolist"):
        return value.tolist()

    if hasattr(value, "item"):
        return value.item()

    raise TypeError(
        "Objeto de tipo {} no serializable en la caché".format(
            type(value).__name__
        )
    )


def _safe_key(key):
    """
    Convierte una clave lógica en un nombre de archivo seguro.

    Así evitamos que caracteres especiales puedan interpretarse como partes
    de una ruta del sistema de archivos.
    """
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(key))


def _cache_path(key, valid_date=None):
    """
    Devuelve la ruta de disco correspondiente a una clave.

    Estructura resultante:

        cache/
            2026-09-18/
                aemet__hourly__xxxxxxxxxxxxxxxx.json
                esios__prices__xxxxxxxxxxxxxxxx.json

    Separar por fecha evita que una ejecución de hoy reutilice accidentalmente
    una predicción descargada ayer.
    """
    valid_date = valid_date or _today()

    return os.path.join(
        CACHE_DIR,
        valid_date,
        _safe_key(key) + ".json",
    )


def _parse_directory_date(directory_name):
    """
    Intenta interpretar el nombre de una carpeta como YYYY-MM-DD.

    Devuelve un objeto date si es válido o None si no lo es. Las carpetas que
    no tengan formato de fecha no se borran automáticamente.
    """
    try:
        return datetime.strptime(directory_name, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# ============================================================================
# CREACIÓN DE CLAVES
# ============================================================================

def make_key(provider, request, **parameters):
    """
    Construye una clave estable que identifica una petición.

    Ejemplos conceptuales:

        make_key("aemet", "hourly", municipio="18127")

        make_key("esios", "indicator", indicator=1001)

    Si cambian los parámetros que determinan la respuesta, cambia también
    la clave y, por tanto, se crea una entrada de caché diferente.

    ATENCIÓN:
    No pasar tokens, contraseñas ni API keys dentro de **parameters.
    """
    payload = {
        "provider": str(provider).lower().strip(),
        "request": str(request).lower().strip(),
        "parameters": parameters,
    }

    # Serializamos siempre en el mismo orden para obtener exactamente el mismo
    # hash cuando la petición sea la misma.
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_json_default,
    )

    # Usamos sólo los primeros 16 caracteres: son suficientes para diferenciar
    # cómodamente las peticiones de este proyecto sin crear nombres enormes.
    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()[:16]

    return "{}__{}__{}".format(
        payload["provider"],
        payload["request"],
        digest,
    )


# ============================================================================
# LECTURA DE CACHÉ
# ============================================================================

def get_cache(key, refresh=False, valid_date=None):
    """
    Recupera un dato almacenado.

    Orden normal de búsqueda:

        RAM -> disco -> None

    Semántica especial de ``refresh=True``
    --------------------------------------
    Durante una ejecución iniciada con --refresh queremos exactamente esto:

        primera petición de una clave
            -> ignorar RAM/disco
            -> devolver None
            -> el módulo llamador consulta Internet
            -> set_cache() guarda la respuesta nueva

        siguientes peticiones de ESA MISMA clave y fecha
            -> reutilizar la respuesta recién descargada desde RAM

    De esta forma ``--refresh`` significa "actualizar una vez cada petición
    distinta durante esta ejecución", y no "consultar Internet cada vez que
    cualquier función vuelva a pedir el mismo dato".

    Parameters
    ----------
    key : str
        Clave generada normalmente mediante make_key().

    refresh : bool
        Si es False, se utiliza la política normal RAM -> disco -> None.

        Si es True y la clave todavía NO ha sido refrescada correctamente en
        esta ejecución, se ignora la caché previa y se devuelve None.

        Si es True pero set_cache() ya ha guardado correctamente una respuesta
        nueva para esa clave durante esta ejecución, se devuelve esa copia nueva
        desde RAM.

    valid_date : str o None
        Fecha YYYY-MM-DD de la caché que queremos consultar. Normalmente se deja
        en None y se utiliza automáticamente la fecha actual.

    Returns
    -------
    object
        Los datos guardados si existe una entrada válida y utilizable.

    None
        Si no existe una entrada válida o si refresh=True exige todavía una
        actualización de esa clave.
    """
    valid_date = valid_date or _today()
    memory_key = (valid_date, key)

    # ----------------------------------------------------------------------
    # MODO --refresh
    # ----------------------------------------------------------------------
    #
    # Una clave sólo puede considerarse "refrescada" DESPUÉS de que set_cache()
    # haya terminado correctamente. Por tanto, si la consulta HTTP falla, la
    # caché antigua no se marca como nueva ni se sobrescribe accidentalmente.
    if refresh:
        if memory_key not in _REFRESHED_KEYS:
            return None

        # Si ya se refrescó en esta ejecución, la nueva respuesta debería estar
        # en RAM. La devolvemos directamente para no repetir la petición HTTP.
        if memory_key in _MEMORY_CACHE:
            return _MEMORY_CACHE[memory_key]

        # Caso defensivo: si otro código hubiese eliminado la entrada de RAM
        # después de refrescarla, permitimos leer del disco la copia recién
        # escrita. No debería ser el camino habitual, pero hace el módulo más
        # robusto frente a futuras ampliaciones.
        path = _cache_path(key, valid_date)

        if not os.path.isfile(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as fh:
                envelope = json.load(fh)

            if envelope.get("cache_version") != CACHE_VERSION:
                return None

            if envelope.get("key") != key:
                return None

            if envelope.get("valid_date") != valid_date:
                return None

            if "data" not in envelope:
                return None

            data = envelope["data"]
            _MEMORY_CACHE[memory_key] = data
            return data

        except (OSError, ValueError, TypeError):
            return None

    # ----------------------------------------------------------------------
    # NIVEL 1: RAM
    # ----------------------------------------------------------------------
    if memory_key in _MEMORY_CACHE:
        return _MEMORY_CACHE[memory_key]

    # ----------------------------------------------------------------------
    # NIVEL 2: DISCO
    # ----------------------------------------------------------------------
    path = _cache_path(key, valid_date)

    if not os.path.isfile(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as fh:
            envelope = json.load(fh)

        # Estas comprobaciones evitan aceptar accidentalmente un archivo
        # antiguo, incompatible o que corresponda a otra petición.
        if envelope.get("cache_version") != CACHE_VERSION:
            return None

        if envelope.get("key") != key:
            return None

        if envelope.get("valid_date") != valid_date:
            return None

        if "data" not in envelope:
            return None

        data = envelope["data"]

        # Una vez leído del disco lo copiamos a RAM. Las siguientes consultas
        # de esta misma ejecución ya no necesitarán acceder al disco.
        _MEMORY_CACHE[memory_key] = data

        return data

    except (OSError, ValueError, TypeError):
        # Un JSON incompleto o corrupto nunca debe bloquear el programa.
        # Devolvemos None para que el llamador pueda volver a consultar la API.
        return None


# ============================================================================
# ESCRITURA DE CACHÉ
# ============================================================================

def set_cache(key, data, valid_date=None, metadata=None):
    """
    Guarda datos tanto en RAM como en disco.

    Esta función debe llamarse SOLAMENTE después de comprobar que la respuesta
    recibida de AEMET, ESIOS u otro proveedor es válida.

    La escritura en disco es atómica: primero se crea un archivo temporal y,
    sólo cuando se ha escrito completamente, sustituye al archivo definitivo.
    Así reducimos el riesgo de dejar un JSON incompleto si Python se interrumpe.
    """
    valid_date = valid_date or _today()
    path = _cache_path(key, valid_date)
    directory = os.path.dirname(path)

    os.makedirs(directory, exist_ok=True)

    # El "envelope" contiene los datos y una pequeña cantidad de metadatos
    # útiles para saber posteriormente cuándo y por qué se creó el archivo.
    envelope = {
        "cache_version": CACHE_VERSION,
        "key": key,
        "valid_date": valid_date,
        "stored_at": datetime.now().astimezone().isoformat(),
        "metadata": metadata or {},
        "data": data,
    }

    # Creamos el temporal dentro de la misma carpeta para que os.replace()
    # pueda realizar una sustitución atómica en el mismo sistema de archivos.
    fd, temporary_path = tempfile.mkstemp(
        prefix=".cache_",
        suffix=".tmp",
        dir=directory,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(
                envelope,
                fh,
                ensure_ascii=False,
                sort_keys=True,
                default=_json_default,
            )
            fh.flush()
            os.fsync(fh.fileno())

        os.replace(temporary_path, path)

    except Exception:
        # Si algo falla, eliminamos el temporal para no dejar basura.
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise

    # Guardamos simultáneamente el objeto original en RAM.
    memory_key = (valid_date, key)
    _MEMORY_CACHE[memory_key] = data

    # Marcamos la clave como actualizada en ESTA ejecución.
    #
    # Es importante hacerlo aquí, después de que os.replace() haya terminado
    # correctamente. Si la descarga o la escritura fallasen antes, la clave no
    # quedaría marcada y una siguiente llamada con --refresh volvería a intentar
    # obtener una respuesta válida del proveedor.
    _REFRESHED_KEYS.add(memory_key)

    # Aprovechamos una escritura correcta para hacer mantenimiento.
    cleanup_old_cache()

    return path


# ============================================================================
# RETENCIÓN Y LIMPIEZA
# ============================================================================

def cleanup_old_cache(retention_days=None):
    """
    Elimina automáticamente carpetas de caché demasiado antiguas.

    Por defecto utiliza CACHE_RETENTION_DAYS.

    Ejemplo con CACHE_RETENTION_DAYS = 30:
        - se conserva hoy;
        - se conservan los 29 días naturales anteriores;
        - se eliminan carpetas fechadas más antiguas.

    Si retention_days == 0, la limpieza queda desactivada y se conserva todo.

    Sólo se eliminan directorios cuyo nombre sea una fecha válida YYYY-MM-DD.
    Por seguridad, cualquier otro archivo o carpeta dentro de cache/ se ignora.
    """
    if retention_days is None:
        retention_days = CACHE_RETENTION_DAYS

    try:
        retention_days = int(retention_days)
    except (TypeError, ValueError):
        raise ValueError("retention_days debe ser un número entero")

    if retention_days < 0:
        raise ValueError("retention_days no puede ser negativo")

    # Cero significa explícitamente "conservar indefinidamente".
    if retention_days == 0:
        return []

    if not os.path.isdir(CACHE_DIR):
        return []

    today = date.today()

    # Para 30 días queremos hoy + 29 días anteriores.
    oldest_allowed = today - timedelta(days=retention_days - 1)

    removed = []

    for name in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, name)

        if not os.path.isdir(path):
            continue

        directory_date = _parse_directory_date(name)

        # No tocamos carpetas que no sean claramente nuestras carpetas fechadas.
        if directory_date is None:
            continue

        if directory_date < oldest_allowed:
            try:
                shutil.rmtree(path)
                removed.append(path)
            except OSError:
                # La limpieza nunca debe impedir que funcione el programa.
                pass

    return removed


# ============================================================================
# UTILIDADES DE DEPURACIÓN Y MANTENIMIENTO
# ============================================================================

def invalidate_cache(key=None, valid_date=None):
    """
    Invalida manualmente la caché.

    Normalmente no será necesario utilizar esta función porque --refresh será
    el mecanismo habitual para forzar una nueva consulta.

    - key=None:
        vacía únicamente la caché RAM del proceso actual.

    - key=<clave>:
        elimina esa entrada de RAM y de disco para la fecha indicada.
    """
    valid_date = valid_date or _today()

    if key is None:
        _MEMORY_CACHE.clear()
        _REFRESHED_KEYS.clear()
        return

    memory_key = (valid_date, key)

    _MEMORY_CACHE.pop(memory_key, None)
    _REFRESHED_KEYS.discard(memory_key)

    path = _cache_path(key, valid_date)

    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def cache_status(key, valid_date=None):
    """
    Devuelve información sobre dónde se encuentra una entrada.

    Posibles valores de "source":
        "ram"  -> ya está cargada en memoria;
        "disk" -> existe en disco pero aún no se ha cargado en RAM;
        "miss" -> no existe.

    Es útil para mensajes de diagnóstico durante el desarrollo.
    """
    valid_date = valid_date or _today()
    memory_key = (valid_date, key)
    path = _cache_path(key, valid_date)

    if memory_key in _MEMORY_CACHE:
        source = "ram"
    elif os.path.isfile(path):
        source = "disk"
    else:
        source = "miss"

    return {
        "source": source,
        "date": valid_date,
        "path": path,
    }


# Alias cortos opcionales.
get = get_cache
set = set_cache
invalidate = invalidate_cache

