#!/usr/bin/env python3
"""
weekly.py

Planificador semanal sostenible de servicios energéticos.

Versión 4.

Esta versión añade una planificación térmica híbrida:

    - primeras 48 horas:
        temperatura horaria AEMET;

    - resto del horizonte semanal:
        Tmax/Tmin de la predicción diaria.

La climatización se decide así con la mejor resolución temporal
disponible y se degrada de forma controlada hacia una planificación
orientativa cuando aumenta el horizonte.

Esta versión incorpora la temperatura prevista por AEMET como variable
de decisión para la climatización semanal.

En verano se utiliza principalmente Tmax para decidir si conviene:
    - no climatizar;
    - retrasar el encendido;
    - climatizar durante parte de la ventana solar;
    - mantener la ventana 12:00-18:00 en días muy cálidos.

En invierno se utiliza Tmin cuando está disponible. Si la predicción
diaria recibida todavía no contiene Tmin, se utiliza Tmax como criterio
provisional y se marca la fuente de decisión.

================================================================
OBJETIVO
================================================================

Este módulo responde a la pregunta:

    ¿Cuándo conviene prestar cada servicio durante la semana?

A diferencia de la versión 1, los servicios NO se planifican
independientemente.

Se considera:

    - disponibilidad solar;
    - presencia;
    - frecuencia semanal;
    - potencia de las cargas;
    - simultaneidad;
    - tipo físico del servicio;
    - restricciones térmicas;
    - restricciones externas;
    - sostenibilidad.

================================================================
TIPOS DE SERVICIO
================================================================

1. TAREA DESPLAZABLE

   Ejemplos:

       lavadora
       horno
       robot de cocina

   Tiene duración definida y puede desplazarse dentro de una
   ventana temporal.

2. CARGA TÉRMICA

   Ejemplos:

       climatización
       ACS

   No debe interpretarse como una tarea puntual de una hora.

   Se controla mediante ventanas de funcionamiento o estados
   térmicos.

3. CARGA CONDICIONAL

   Ejemplo:

       termo eléctrico

   Solo se activa si existe una necesidad física:

       temperatura ACS insuficiente.

4. SERVICIO CON RESTRICCIÓN EXTERNA

   Ejemplo:

       riego

   La sostenibilidad del recurso agua tiene prioridad frente
   al pequeño beneficio eléctrico de ejecutar el servicio
   durante el máximo solar.

================================================================
FILOSOFÍA
================================================================

Orden de prioridad:

    1. satisfacer el servicio;
    2. respetar presencia y restricciones físicas;
    3. aprovechar FV directa;
    4. evitar simultaneidad innecesaria;
    5. evitar batería;
    6. utilizar red para consumos marginales;
    7. economía.

================================================================
LIMITACIÓN ACTUAL
================================================================

Esta versión sigue utilizando principalmente la predicción
AEMET diaria para distribuir servicios entre los 7 días.

La siguiente fase incorporará para las primeras 48 horas:

    P_FV(t)
    demanda(t)
    precio_compra(t)
    precio_venta(t)

y permitirá elegir las horas usando excedentes reales.

Autor: Enrique M. Moreno Pérez
"""

from datetime import datetime, timedelta


# ==========================================================
# Parámetros generales
# ==========================================================

HORIZONTE_DIAS_DEFAULT = 7


# ----------------------------------------------------------
# Clasificación solar
# ----------------------------------------------------------

INDICE_SOLAR_EXCELENTE = 0.85
INDICE_SOLAR_BUENO = 0.70
INDICE_SOLAR_ACEPTABLE = 0.50


# ----------------------------------------------------------
# Límites de planificación
# ----------------------------------------------------------
#
# No es el límite físico del inversor.
#
# Es un límite operativo para evitar concentrar demasiadas
# cargas flexibles simultáneamente.

POTENCIA_SERVICIOS_SIMULTANEA_MAX_KW = 3.0


# ----------------------------------------------------------
# Resolución temporal
# ----------------------------------------------------------

PASO_PLANIFICACION_H = 0.5


# ----------------------------------------------------------
# Ventana solar general
# ----------------------------------------------------------

VENTANA_SOLAR_GENERAL = (
    "10:00",
    "18:00",
)


# ----------------------------------------------------------
# Ventana solar central
# ----------------------------------------------------------

VENTANA_SOLAR_CENTRAL = (
    "12:00",
    "16:00",
)


# ----------------------------------------------------------
# Riego
# ----------------------------------------------------------

VENTANAS_RIEGO_PREFERIDAS = [
    (
        "06:00",
        "08:00",
    ),
    (
        "20:00",
        "22:00",
    ),
]


# ==========================================================
# Utilidades temporales
# ==========================================================

def nombre_dia_semana(
    fecha,
):
    """
    Devuelve el día de la semana en castellano.
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


def hora_a_decimal(
    hora_txt,
):
    """
    Convierte HH:MM en hora decimal.
    """

    horas, minutos = hora_txt.split(
        ":"
    )

    return (
        int(horas)
        + int(minutos) / 60.0
    )


def decimal_a_hora(
    valor,
):
    """
    Convierte hora decimal en HH:MM.
    """

    valor = valor % 24.0

    hora = int(
        valor
    )

    minutos = int(
        round(
            (
                valor
                - hora
            )
            * 60.0
        )
    )

    if minutos >= 60:

        hora = (
            hora
            + 1
        ) % 24

        minutos = 0

    return (
        f"{hora:02d}:"
        f"{minutos:02d}"
    )


# ==========================================================
# Calidad solar
# ==========================================================

def clasificar_dia_solar(
    score,
):
    """
    Clasifica cualitativamente el recurso solar.
    """

    score = float(
        score
    )

    if score >= INDICE_SOLAR_EXCELENTE:
        return "excelente"

    if score >= INDICE_SOLAR_BUENO:
        return "bueno"

    if score >= INDICE_SOLAR_ACEPTABLE:
        return "aceptable"

    return "malo"


# ==========================================================
# Confianza
# ==========================================================

def confianza_por_horizonte(
    indice_dia,
):
    """
    Clasificación aproximada de confianza.
    """

    if indice_dia <= 1:
        return "alta"

    if indice_dia <= 3:
        return "media"

    return "baja"


# ==========================================================
# Presencia
# ==========================================================

def obtener_ventanas_presencia(
    demanda,
    fecha,
    estacion,
):
    """
    Obtiene las ventanas de presencia del día.
    """

    nombre_dia = nombre_dia_semana(
        fecha
    )

    presencia = demanda.get(
        "presencia",
        {},
    )

    por_estacion = presencia.get(
        estacion,
        {},
    )

    return por_estacion.get(
        nombre_dia,
        [],
    )


def intervalo_dentro_de_ventana(
    inicio,
    fin,
    ventana,
):
    """
    Comprueba si un intervalo está completamente contenido
    en una ventana.
    """

    inicio_d = hora_a_decimal(
        inicio
    )

    fin_d = hora_a_decimal(
        fin
    )

    inicio_v = hora_a_decimal(
        ventana[
            0
        ]
    )

    fin_v = hora_a_decimal(
        ventana[
            1
        ]
    )

    return (
        inicio_d >= inicio_v
        and fin_d <= fin_v
    )


def hay_presencia_en_intervalo(
    ventanas,
    inicio,
    fin,
):
    """
    Comprueba presencia durante todo el servicio.
    """

    for ventana in ventanas:

        if intervalo_dentro_de_ventana(
            inicio,
            fin,
            ventana,
        ):
            return True

    return False


# ==========================================================
# Clasificación de servicios
# ==========================================================

def determinar_tipo_servicio(
    carga,
):
    """
    Clasifica físicamente una carga.

    En esta versión las características físicas conocidas tienen
    prioridad sobre una etiqueta genérica ``tipo_servicio="tarea"``.

    Esto evita que:
        - el termo eléctrico;
        - las bombas de calor;
        - los equipos de aire acondicionado;
        - el riego

    aparezcan erróneamente como tareas desplazables.

    Una etiqueta explícita distinta de ``tarea`` sigue respetándose
    para permitir configuraciones avanzadas desde demand.py.
    """

    nombre = (
        carga.get(
            "nombre",
            ""
        )
        .lower()
    )

    # ------------------------------------------------------
    # Clasificación física prioritaria
    # ------------------------------------------------------

    if (
        "riego" in nombre
        or "electroválvula" in nombre
    ):
        return "restriccion_externa"

    if (
        "termo eléctrico" in nombre
        or "termo electrico" in nombre
    ):
        return "condicional"

    if (
        "aire acondicionado" in nombre
        or "bomba de calor" in nombre
        or "climatización" in nombre
        or "climatizacion" in nombre
    ):
        return "termica"

    if "acs" in nombre:
        return "termica"

    # ------------------------------------------------------
    # Etiqueta explícita para otros servicios
    # ------------------------------------------------------

    tipo_explicitado = carga.get(
        "tipo_servicio"
    )

    if (
        tipo_explicitado
        and tipo_explicitado != "tarea"
    ):
        return tipo_explicitado

    return "tarea"


# ==========================================================
# Frecuencia semanal
# ==========================================================

def frecuencia_semanal_servicio(
    carga,
):
    """
    Obtiene la frecuencia semanal.

    Si demand.py todavía no especifica una frecuencia,
    se utilizan valores iniciales razonables.
    """

    frecuencia = carga.get(
        "frecuencia_semanal"
    )

    if frecuencia is not None:

        return max(
            0,
            int(
                frecuencia
            ),
        )

    nombre = (
        carga.get(
            "nombre",
            ""
        )
        .lower()
    )

    if "lavadora" in nombre:
        return 4

    if "riego" in nombre:
        return 3

    if (
        "horno" in nombre
        or "robot" in nombre
    ):
        return 2

    # Climatización y ACS se tratan por día,
    # no mediante frecuencia de tareas.

    return 1


# ==========================================================
# Extracción de servicios
# ==========================================================

def extraer_servicios(
    demanda,
):
    """
    Extrae las cargas flexibles del modelo doméstico.
    """

    servicios = []

    for carga in demanda.get(
        "cargas",
        [],
    ):

        if not carga.get(
            "flexible",
            False,
        ):
            continue

        tipo = determinar_tipo_servicio(
            carga
        )

        servicios.append(
            {
                "nombre": carga.get(
                    "nombre",
                    "servicio",
                ),

                "descripcion": carga.get(
                    "descripcion",
                    carga.get(
                        "nombre",
                        "servicio",
                    ),
                ),

                "tipo": tipo,

                "potencia_kw": float(
                    carga.get(
                        "potencia_kw",
                        0.0,
                    )
                    or 0.0
                ),

                "duracion_h": float(
                    carga.get(
                        "duracion_h",
                        1.0,
                    )
                    or 1.0
                ),

                "requiere_presencia": carga.get(
                    "requiere_presencia",
                    False,
                ),

                "automatizable": carga.get(
                    "automatizable",
                    False,
                ),

                "prioridad": int(
                    carga.get(
                        "prioridad",
                        3,
                    )
                ),

                "estacional": carga.get(
                    "estacional",
                    "todo",
                ),

                "frecuencia_semanal": (
                    frecuencia_semanal_servicio(
                        carga
                    )
                ),

                "max_aplazamiento_h": float(
                    carga.get(
                        "max_aplazamiento_h",
                        168.0,
                    )
                    or 168.0
                ),
            }
        )

    return servicios


# ==========================================================
# Estacionalidad
# ==========================================================

def servicio_activo_en_estacion(
    servicio,
    estacion,
):
    """
    Comprueba compatibilidad estacional.
    """

    valor = servicio.get(
        "estacional",
        "todo",
    )

    if valor in (
        None,
        "todo",
    ):
        return True

    return (
        valor == estacion
    )


# ==========================================================
# Agenda de potencia
# ==========================================================

def crear_agenda_potencia(
    prevision,
):
    """
    Crea una agenda de potencia flexible programada.

    Estructura:

        agenda[fecha][hora_decimal] = potencia_kw
    """

    agenda = {}

    for dia in prevision:

        fecha = dia[
            "fecha"
        ]

        agenda[
            fecha
        ] = {}

        hora = 0.0

        while hora < 24.0:

            agenda[
                fecha
            ][
                round(
                    hora,
                    2,
                )
            ] = 0.0

            hora += (
                PASO_PLANIFICACION_H
            )

    return agenda


def comprobar_potencia_disponible(
    agenda,
    fecha,
    inicio_h,
    duracion_h,
    potencia_kw,
):
    """
    Comprueba que añadir una carga no supere el límite
    de simultaneidad programada.
    """

    t = inicio_h

    fin = (
        inicio_h
        + duracion_h
    )

    while t < fin:

        clave = round(
            t,
            2,
        )

        potencia_existente = (
            agenda[
                fecha
            ].get(
                clave,
                0.0,
            )
        )

        if (
            potencia_existente
            + potencia_kw
            >
            POTENCIA_SERVICIOS_SIMULTANEA_MAX_KW
        ):
            return False

        t += (
            PASO_PLANIFICACION_H
        )

    return True


def reservar_potencia(
    agenda,
    fecha,
    inicio_h,
    duracion_h,
    potencia_kw,
):
    """
    Reserva potencia para un servicio.
    """

    t = inicio_h

    fin = (
        inicio_h
        + duracion_h
    )

    while t < fin:

        clave = round(
            t,
            2,
        )

        agenda[
            fecha
        ][
            clave
        ] = (
            agenda[
                fecha
            ].get(
                clave,
                0.0,
            )
            + potencia_kw
        )

        t += (
            PASO_PLANIFICACION_H
        )


# ==========================================================
# Generación de intervalos candidatos
# ==========================================================

def generar_intervalos(
    ventana,
    duracion_h,
):
    """
    Genera posibles horas de inicio dentro de una ventana.
    """

    inicio = hora_a_decimal(
        ventana[
            0
        ]
    )

    fin = hora_a_decimal(
        ventana[
            1
        ]
    )

    resultados = []

    t = inicio

    while (
        t
        + duracion_h
        <= fin
        + 1e-9
    ):

        resultados.append(
            (
                t,
                t + duracion_h,
            )
        )

        t += (
            PASO_PLANIFICACION_H
        )

    return resultados


# ==========================================================
# Puntuación solar horaria aproximada
# ==========================================================

def factor_hora_solar(
    hora,
):
    """
    Factor aproximado dentro del día.

    Todavía no utiliza P_FV(t).

    Se utiliza solamente para días en los que tenemos
    predicción diaria pero no perfil horario detallado.
    """

    if hora < 8.0:
        return 0.05

    if hora < 10.0:
        return 0.35

    if hora < 12.0:
        return 0.75

    if hora <= 16.0:
        return 1.0

    if hora <= 18.0:
        return 0.75

    if hora <= 20.0:
        return 0.30

    return 0.05


# ==========================================================
# Puntuación de tarea
# ==========================================================

def puntuar_tarea(
    servicio,
    dia,
    indice_dia,
    inicio_h,
    presencia_valida,
    potencia_programada_kw,
):
    """
    Puntúa una tarea candidata.
    """

    score_solar = float(
        dia.get(
            "score",
            0.5,
        )
    )

    centro_servicio = (
        inicio_h
        + servicio[
            "duracion_h"
        ] / 2.0
    )

    factor_horario = factor_hora_solar(
        centro_servicio
    )

    puntuacion = (
        score_solar
        * factor_horario
        * 100.0
    )

    # ------------------------------------------------------
    # Presencia
    # ------------------------------------------------------

    if servicio[
        "requiere_presencia"
    ]:

        if not presencia_valida:

            return -1e9

        puntuacion += 20.0

    # ------------------------------------------------------
    # Confianza
    # ------------------------------------------------------

    confianza = confianza_por_horizonte(
        indice_dia
    )

    if confianza == "alta":

        puntuacion += 10.0

    elif confianza == "media":

        puntuacion += 4.0

    # ------------------------------------------------------
    # Penalización por simultaneidad
    # ------------------------------------------------------

    puntuacion -= (
        potencia_programada_kw
        * 8.0
    )

    # ------------------------------------------------------
    # Prioridad
    # ------------------------------------------------------

    puntuacion += max(
        0.0,
        5.0
        - servicio[
            "prioridad"
        ],
    )

    return puntuacion


# ==========================================================
# Planificación de tareas
# ==========================================================

def planificar_tareas(
    servicios,
    prevision,
    demanda,
    estacion,
    agenda,
):
    """
    Planifica tareas desplazables conjuntamente.
    """

    resultado = []

    tareas = [
        servicio
        for servicio in servicios
        if servicio[
            "tipo"
        ] == "tarea"
    ]

    # ------------------------------------------------------
    # Primero cargas de mayor potencia/prioridad.
    # ------------------------------------------------------

    tareas.sort(
        key=lambda s: (
            s[
                "prioridad"
            ],
            -s[
                "potencia_kw"
            ],
        )
    )

    for servicio in tareas:

        frecuencia = min(
            servicio[
                "frecuencia_semanal"
            ],
            len(
                prevision
            ),
        )

        dias_utilizados = set()

        for repeticion in range(
            frecuencia
        ):

            candidatos = []

            for indice_dia, dia in enumerate(
                prevision
            ):

                fecha = dia[
                    "fecha"
                ]

                # Evitar concentrar todas las repeticiones
                # del mismo servicio en un único día.

                if fecha in dias_utilizados:
                    continue

                ventanas_presencia = (
                    obtener_ventanas_presencia(
                        demanda,
                        fecha,
                        estacion,
                    )
                )

                intervalos = generar_intervalos(
                    VENTANA_SOLAR_GENERAL,
                    servicio[
                        "duracion_h"
                    ],
                )

                for (
                    inicio_h,
                    fin_h,
                ) in intervalos:

                    inicio_txt = decimal_a_hora(
                        inicio_h
                    )

                    fin_txt = decimal_a_hora(
                        fin_h
                    )

                    presencia_valida = (
                        hay_presencia_en_intervalo(
                            ventanas_presencia,
                            inicio_txt,
                            fin_txt,
                        )
                    )

                    if (
                        servicio[
                            "requiere_presencia"
                        ]
                        and not presencia_valida
                    ):
                        continue

                    if not comprobar_potencia_disponible(
                        agenda,
                        fecha,
                        inicio_h,
                        servicio[
                            "duracion_h"
                        ],
                        servicio[
                            "potencia_kw"
                        ],
                    ):
                        continue

                    potencia_actual = max(
                        agenda[
                            fecha
                        ].get(
                            round(
                                inicio_h,
                                2,
                            ),
                            0.0,
                        ),
                        0.0,
                    )

                    puntuacion = puntuar_tarea(
                        servicio,
                        dia,
                        indice_dia,
                        inicio_h,
                        presencia_valida,
                        potencia_actual,
                    )

                    candidatos.append(
                        {
                            "fecha": fecha,

                            "indice_dia": indice_dia,

                            "inicio_h": inicio_h,

                            "fin_h": fin_h,

                            "inicio": inicio_txt,

                            "fin": fin_txt,

                            "puntuacion": (
                                puntuacion
                            ),

                            "score_solar": float(
                                dia.get(
                                    "score",
                                    0.5,
                                )
                            ),
                        }
                    )

            if not candidatos:
                continue

            mejor = max(
                candidatos,
                key=lambda c: c[
                    "puntuacion"
                ],
            )

            reservar_potencia(
                agenda,
                mejor[
                    "fecha"
                ],
                mejor[
                    "inicio_h"
                ],
                servicio[
                    "duracion_h"
                ],
                servicio[
                    "potencia_kw"
                ],
            )

            dias_utilizados.add(
                mejor[
                    "fecha"
                ]
            )

            resultado.append(
                {
                    "servicio": servicio[
                        "nombre"
                    ],

                    "descripcion": servicio[
                        "descripcion"
                    ],

                    "tipo": "tarea",

                    "fecha": mejor[
                        "fecha"
                    ],

                    "dia_semana": nombre_dia_semana(
                        mejor[
                            "fecha"
                        ]
                    ),

                    "hora_inicio": mejor[
                        "inicio"
                    ],

                    "hora_fin": mejor[
                        "fin"
                    ],

                    "potencia_kw": servicio[
                        "potencia_kw"
                    ],

                    "score_solar": mejor[
                        "score_solar"
                    ],

                    "confianza": confianza_por_horizonte(
                        mejor[
                            "indice_dia"
                        ]
                    ),

                    "numero_ejecucion": (
                        repeticion
                        + 1
                    ),

                    "motivo": (
                        "Servicio colocado en una ventana "
                        "solar evitando concentrar cargas "
                        "flexibles simultáneamente."
                    ),
                }
            )

    return resultado


# ==========================================================
# Planificación de climatización
# ==========================================================

def _valor_temperatura(
    dia,
    *claves,
):
    """
    Recupera una temperatura desde el registro diario de AEMET.

    Se prueban varias claves para mantener compatibilidad con
    distintas versiones de aemet.py.
    """

    for clave in claves:

        valor = dia.get(
            clave
        )

        if valor is None:
            continue

        try:
            return float(
                valor
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

    return None


def obtener_temperaturas_aemet_dia(
    dia,
):
    """
    Devuelve Tmax y Tmin previstas.

    La versión actual de aemet.py ya proporciona Tmax.

    Si en el futuro se añade Tmin al diccionario diario, weekly.py
    empezará a utilizarla automáticamente sin necesidad de cambiar
    esta función.
    """

    tmax = _valor_temperatura(
        dia,
        "tmax",
        "temperatura_max",
        "temperatura_maxima",
    )

    tmin = _valor_temperatura(
        dia,
        "tmin",
        "temperatura_min",
        "temperatura_minima",
    )

    return (
        tmax,
        tmin,
    )


def decidir_climatizacion_verano(
    nombre_servicio,
    tmax,
):
    """
    Decide la ventana de refrigeración a partir de Tmax AEMET.

    Los umbrales son parámetros iniciales de control y podrán
    trasladarse posteriormente a config.py.

    Returns
    -------
    list
        Lista de ventanas (inicio, fin, nivel, motivo).
        Una lista vacía significa que no se recomienda climatizar.
    """

    if tmax is None:

        return [
            (
                "12:00",
                "18:00",
                "sin_dato",
                (
                    "No hay Tmax disponible; se conserva de forma "
                    "provisional la ventana estival habitual."
                ),
            )
        ]

    es_despensa = (
        "despensa"
        in nombre_servicio.lower()
    )

    # ------------------------------------------------------
    # Habitación despensa
    # ------------------------------------------------------
    #
    # Se mantiene un criterio algo más conservador porque el
    # objetivo es conservar alimentos y no únicamente confort.

    if es_despensa:

        if tmax < 26.0:
            return []

        if tmax < 30.0:

            return [
                (
                    "14:00",
                    "17:00",
                    "suave",
                    (
                        f"Tmax AEMET = {tmax:.1f} °C. "
                        "Refrigeración moderada de la despensa."
                    ),
                )
            ]

        if tmax < 34.0:

            return [
                (
                    "13:00",
                    "18:00",
                    "media",
                    (
                        f"Tmax AEMET = {tmax:.1f} °C. "
                        "Conviene anticipar la refrigeración."
                    ),
                )
            ]

        return [
            (
                "12:00",
                "18:00",
                "alta",
                (
                    f"Tmax AEMET = {tmax:.1f} °C. "
                    "Día muy cálido: usar la ventana solar completa."
                ),
            )
        ]

    # ------------------------------------------------------
    # Climatización general de la vivienda
    # ------------------------------------------------------

    if tmax < 27.0:
        return []

    if tmax < 30.0:

        return [
            (
                "15:00",
                "18:00",
                "suave",
                (
                    f"Tmax AEMET = {tmax:.1f} °C. "
                    "Carga térmica moderada; se retrasa el encendido."
                ),
            )
        ]

    if tmax < 34.0:

        return [
            (
                "13:00",
                "18:00",
                "media",
                (
                    f"Tmax AEMET = {tmax:.1f} °C. "
                    "Se aprovecha principalmente la producción FV."
                ),
            )
        ]

    return [
        (
            "12:00",
            "18:00",
            "alta",
            (
                f"Tmax AEMET = {tmax:.1f} °C. "
                "Día muy cálido: mantener la estrategia habitual "
                "12:00-18:00 y priorizar FV directa."
            ),
        )
    ]


def decidir_climatizacion_invierno(
    tmax,
    tmin,
):
    """
    Decide las ventanas de calefacción.

    Se usa Tmin cuando está disponible porque describe mejor la
    necesidad de calefacción matinal.

    Si Tmin todavía no llega desde aemet.py, se utiliza Tmax como
    criterio provisional. El resultado indica explícitamente qué
    temperatura se ha empleado.
    """

    # ------------------------------------------------------
    # Caso preferente: Tmin disponible
    # ------------------------------------------------------

    if tmin is not None:

        if tmin <= 3.0:

            return [
                (
                    "07:30",
                    "09:00",
                    "alta",
                    (
                        f"Tmin AEMET = {tmin:.1f} °C. "
                        "Calefacción matinal recomendada."
                    ),
                ),
                (
                    "18:00",
                    "22:00",
                    "alta",
                    (
                        f"Tmin AEMET = {tmin:.1f} °C. "
                        "Mantener calefacción durante la ocupación "
                        "de la tarde."
                    ),
                ),
            ]

        if tmin <= 7.0:

            return [
                (
                    "07:30",
                    "08:30",
                    "media",
                    (
                        f"Tmin AEMET = {tmin:.1f} °C. "
                        "Apoyo térmico matinal."
                    ),
                ),
                (
                    "18:00",
                    "21:30",
                    "media",
                    (
                        f"Tmin AEMET = {tmin:.1f} °C. "
                        "Calefacción vespertina moderada."
                    ),
                ),
            ]

        if tmin <= 12.0:

            return [
                (
                    "18:00",
                    "21:00",
                    "suave",
                    (
                        f"Tmin AEMET = {tmin:.1f} °C. "
                        "Solo se prevé apoyo térmico vespertino."
                    ),
                )
            ]

        return []

    # ------------------------------------------------------
    # Fallback: solo Tmax disponible
    # ------------------------------------------------------

    if tmax is None:

        return [
            (
                "18:00",
                "22:00",
                "sin_dato",
                (
                    "No hay temperatura mínima prevista. "
                    "Se mantiene provisionalmente la ventana habitual."
                ),
            )
        ]

    if tmax < 10.0:

        return [
            (
                "07:30",
                "09:00",
                "alta",
                (
                    f"Solo se dispone de Tmax AEMET = {tmax:.1f} °C. "
                    "Se prevé un día frío y se recomienda apoyo matinal."
                ),
            ),
            (
                "18:00",
                "22:00",
                "alta",
                (
                    f"Solo se dispone de Tmax AEMET = {tmax:.1f} °C. "
                    "Se prevé calefacción vespertina."
                ),
            ),
        ]

    if tmax < 15.0:

        return [
            (
                "18:00",
                "21:30",
                "media",
                (
                    f"Solo se dispone de Tmax AEMET = {tmax:.1f} °C. "
                    "Se recomienda calefacción vespertina moderada."
                ),
            )
        ]

    if tmax < 18.0:

        return [
            (
                "19:00",
                "21:00",
                "suave",
                (
                    f"Solo se dispone de Tmax AEMET = {tmax:.1f} °C. "
                    "Necesidad térmica prevista reducida."
                ),
            )
        ]

    return []


def indexar_prevision_horaria_por_fecha(
    prevision_horaria,
):
    """
    Agrupa la predicción horaria AEMET por fecha.

    Parameters
    ----------
    prevision_horaria : list or None
        Registros procedentes de
        aemet_hourly.obtener_prevision_horaria().

    Returns
    -------
    dict
        {
            date(...): [registro_00, registro_01, ...],
            ...
        }
    """

    indice = {}

    for registro in prevision_horaria or []:

        fecha = registro.get(
            "fecha"
        )

        if fecha is None:
            continue

        indice.setdefault(
            fecha,
            [],
        ).append(
            registro
        )

    for fecha in indice:

        indice[
            fecha
        ].sort(
            key=lambda r: r.get(
                "datetime"
            )
        )

    return indice


def _hora_registro_decimal(
    registro,
):
    """
    Obtiene la hora decimal de un registro AEMET horario.
    """

    hora = registro.get(
        "hora"
    )

    if hora:

        try:
            return hora_a_decimal(
                hora
            )

        except (
            ValueError,
            AttributeError,
        ):
            pass

    fecha_hora = registro.get(
        "datetime"
    )

    if fecha_hora is not None:

        return (
            fecha_hora.hour
            + fecha_hora.minute / 60.0
        )

    return None


def _temperatura_horaria(
    registro,
):
    """
    Recupera la temperatura horaria AEMET.
    """

    valor = registro.get(
        "temperatura_c"
    )

    if valor is None:
        return None

    try:
        return float(
            valor
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def _registro_en_ventana(
    registro,
    inicio_h,
    fin_h,
):
    """
    Indica si el registro pertenece a una ventana horaria.
    """

    hora = _hora_registro_decimal(
        registro
    )

    if hora is None:
        return False

    return (
        hora >= inicio_h
        and hora < fin_h
    )


def _agrupar_horas_activas(
    registros_activos,
):
    """
    Agrupa registros horarios consecutivos en ventanas.

    Cada registro AEMET representa aproximadamente una hora.
    """

    if not registros_activos:
        return []

    ordenados = sorted(
        registros_activos,
        key=lambda r: _hora_registro_decimal(
            r
        ),
    )

    grupos = []

    grupo_actual = [
        ordenados[
            0
        ]
    ]

    for registro in ordenados[
        1:
    ]:

        hora_anterior = (
            _hora_registro_decimal(
                grupo_actual[
                    -1
                ]
            )
        )

        hora_actual = (
            _hora_registro_decimal(
                registro
            )
        )

        if (
            hora_anterior is not None
            and hora_actual is not None
            and hora_actual
            - hora_anterior
            <= 1.01
        ):

            grupo_actual.append(
                registro
            )

        else:

            grupos.append(
                grupo_actual
            )

            grupo_actual = [
                registro
            ]

    grupos.append(
        grupo_actual
    )

    resultado = []

    for grupo in grupos:

        hora_inicio = (
            _hora_registro_decimal(
                grupo[
                    0
                ]
            )
        )

        hora_fin = (
            _hora_registro_decimal(
                grupo[
                    -1
                ]
            )
            + 1.0
        )

        temperaturas = [
            _temperatura_horaria(
                r
            )
            for r in grupo
        ]

        temperaturas = [
            t
            for t in temperaturas
            if t is not None
        ]

        resultado.append(
            {
                "hora_inicio": decimal_a_hora(
                    hora_inicio
                ),

                "hora_fin": decimal_a_hora(
                    hora_fin
                ),

                "temperatura_min": (
                    min(
                        temperaturas
                    )
                    if temperaturas
                    else None
                ),

                "temperatura_max": (
                    max(
                        temperaturas
                    )
                    if temperaturas
                    else None
                ),

                "registros": grupo,
            }
        )

    return resultado


def decidir_climatizacion_verano_horaria(
    nombre_servicio,
    registros_dia,
):
    """
    Calcula ventanas de refrigeración usando temperatura horaria.

    Se respeta la estrategia doméstica definida:

        - ventilación nocturna;
        - cierre de ventanas aproximadamente a las 11:00;
        - climatización únicamente durante el periodo diurno;
        - apagado alrededor de las 18:00.

    Para la vivienda general:
        encendido si T exterior >= 30 °C.

    Para la despensa:
        encendido si T exterior >= 27 °C.

    Los umbrales son parámetros iniciales y posteriormente
    deberán trasladarse a config.py.
    """

    nombre = nombre_servicio.lower()

    es_despensa = (
        "despensa"
        in nombre
    )

    if es_despensa:

        temperatura_encendido = 27.0

    else:

        temperatura_encendido = 30.0

    # Ventana compatible con el régimen de verano de la vivienda.
    hora_inicio_operacion = 12.0
    hora_fin_operacion = 18.0

    candidatos = []

    for registro in registros_dia:

        if not _registro_en_ventana(
            registro,
            hora_inicio_operacion,
            hora_fin_operacion,
        ):
            continue

        temperatura = (
            _temperatura_horaria(
                registro
            )
        )

        if temperatura is None:
            continue

        if temperatura >= temperatura_encendido:

            candidatos.append(
                registro
            )

    ventanas = (
        _agrupar_horas_activas(
            candidatos
        )
    )

    resultado = []

    for ventana in ventanas:

        tmax = ventana[
            "temperatura_max"
        ]

        if tmax is None:

            nivel = "media"

        elif (
            es_despensa
            and tmax >= 34.0
        ):

            nivel = "alta"

        elif (
            not es_despensa
            and tmax >= 35.0
        ):

            nivel = "alta"

        elif tmax >= 31.0:

            nivel = "media"

        else:

            nivel = "suave"

        resultado.append(
            (
                ventana[
                    "hora_inicio"
                ],

                ventana[
                    "hora_fin"
                ],

                nivel,

                (
                    "Ventana calculada con temperatura horaria AEMET. "
                    f"Umbral de encendido = "
                    f"{temperatura_encendido:.1f} °C."
                ),

                ventana[
                    "temperatura_min"
                ],

                ventana[
                    "temperatura_max"
                ],
            )
        )

    return resultado


def decidir_climatizacion_invierno_horaria(
    registros_dia,
):
    """
    Calcula ventanas de calefacción usando temperatura horaria AEMET.

    Se consideran las ventanas domésticas habituales:

        mañana: 07:00-09:00
        tarde : 18:00-22:00

    Se recomienda calefacción cuando la temperatura exterior
    prevista es <= 12 °C.

    La temperatura interior y la inercia térmica se incorporarán
    en una versión posterior.
    """

    temperatura_encendido = 12.0

    ventanas_operacion = [
        (
            7.0,
            9.0,
        ),
        (
            18.0,
            22.0,
        ),
    ]

    resultado = []

    for (
        inicio_operacion,
        fin_operacion,
    ) in ventanas_operacion:

        candidatos = []

        for registro in registros_dia:

            if not _registro_en_ventana(
                registro,
                inicio_operacion,
                fin_operacion,
            ):
                continue

            temperatura = (
                _temperatura_horaria(
                    registro
                )
            )

            if temperatura is None:
                continue

            if temperatura <= temperatura_encendido:

                candidatos.append(
                    registro
                )

        ventanas = (
            _agrupar_horas_activas(
                candidatos
            )
        )

        for ventana in ventanas:

            tmin = ventana[
                "temperatura_min"
            ]

            if tmin is None:

                nivel = "media"

            elif tmin <= 3.0:

                nivel = "alta"

            elif tmin <= 7.0:

                nivel = "media"

            else:

                nivel = "suave"

            resultado.append(
                (
                    ventana[
                        "hora_inicio"
                    ],

                    ventana[
                        "hora_fin"
                    ],

                    nivel,

                    (
                        "Ventana calculada con temperatura horaria AEMET. "
                        f"Umbral de calefacción = "
                        f"{temperatura_encendido:.1f} °C."
                    ),

                    ventana[
                        "temperatura_min"
                    ],

                    ventana[
                        "temperatura_max"
                    ],
                )
            )

    return resultado


def planificar_cargas_termicas(
    servicios,
    prevision,
    estacion,
    prevision_horaria=None,
):
    """
    Genera la planificación semanal de climatización.

    Estrategia híbrida de la versión 4
    ----------------------------------

    Para los dos primeros días del horizonte, siempre que existan
    registros AEMET horarios:

        -> se utiliza temperatura horaria.

    Para el resto de la semana:

        -> se utiliza Tmax/Tmin diaria.

    Esto evita atribuir precisión horaria a predicciones lejanas
    y mantiene la planificación semanal completa.
    """

    resultado = []

    servicios_termicos = [
        s
        for s in servicios
        if s[
            "tipo"
        ] == "termica"
    ]

    indice_horario = (
        indexar_prevision_horaria_por_fecha(
            prevision_horaria
        )
    )

    # Fechas para las que queremos máxima resolución.
    fechas_alta_resolucion = {
        dia[
            "fecha"
        ]
        for dia in prevision[
            :2
        ]
    }

    for servicio in servicios_termicos:

        nombre = servicio[
            "nombre"
        ].lower()

        # ACS se gestiona separadamente.
        if (
            "acs" in nombre
            or "termo" in nombre
        ):
            continue

        for indice, dia in enumerate(
            prevision
        ):

            fecha = dia[
                "fecha"
            ]

            score = float(
                dia.get(
                    "score",
                    0.5,
                )
            )

            (
                tmax,
                tmin,
            ) = obtener_temperaturas_aemet_dia(
                dia
            )

            registros_horarios_dia = (
                indice_horario.get(
                    fecha,
                    []
                )
            )

            usar_horaria = (
                fecha
                in fechas_alta_resolucion
                and bool(
                    registros_horarios_dia
                )
            )

            # ==================================================
            # Primeras 48 horas: AEMET horario
            # ==================================================

            if usar_horaria:

                if estacion == "verano":

                    ventanas_h = (
                        decidir_climatizacion_verano_horaria(
                            servicio[
                                "nombre"
                            ],
                            registros_horarios_dia,
                        )
                    )

                else:

                    ventanas_h = (
                        decidir_climatizacion_invierno_horaria(
                            registros_horarios_dia
                        )
                    )

                temperatura_control = (
                    "aemet_horario"
                )

                fuente_temperatura = (
                    "AEMET_horario"
                )

                if not ventanas_h:

                    temperaturas_disponibles = [
                        _temperatura_horaria(
                            r
                        )
                        for r in registros_horarios_dia
                    ]

                    temperaturas_disponibles = [
                        t
                        for t in temperaturas_disponibles
                        if t is not None
                    ]

                    resultado.append(
                        {
                            "servicio": servicio[
                                "nombre"
                            ],

                            "descripcion": servicio[
                                "descripcion"
                            ],

                            "tipo": "termica",

                            "fecha": fecha,

                            "dia_semana": nombre_dia_semana(
                                fecha
                            ),

                            "hora_inicio": None,

                            "hora_fin": None,

                            "activo_recomendado": False,

                            "nivel_climatizacion": "no_necesaria",

                            "tmax_aemet": tmax,

                            "tmin_aemet": tmin,

                            "temperatura_horaria_min": (
                                min(
                                    temperaturas_disponibles
                                )
                                if temperaturas_disponibles
                                else None
                            ),

                            "temperatura_horaria_max": (
                                max(
                                    temperaturas_disponibles
                                )
                                if temperaturas_disponibles
                                else None
                            ),

                            "temperatura_control": (
                                temperatura_control
                            ),

                            "fuente_temperatura": (
                                fuente_temperatura
                            ),

                            "score_solar": score,

                            "confianza": confianza_por_horizonte(
                                indice
                            ),

                            "motivo": (
                                "La temperatura horaria exterior prevista "
                                "por AEMET no alcanza el umbral de "
                                "climatización dentro de la ventana "
                                "operativa."
                            ),
                        }
                    )

                    continue

                for (
                    inicio,
                    fin,
                    nivel,
                    estrategia,
                    temp_min_h,
                    temp_max_h,
                ) in ventanas_h:

                    resultado.append(
                        {
                            "servicio": servicio[
                                "nombre"
                            ],

                            "descripcion": servicio[
                                "descripcion"
                            ],

                            "tipo": "termica",

                            "fecha": fecha,

                            "dia_semana": nombre_dia_semana(
                                fecha
                            ),

                            "hora_inicio": inicio,

                            "hora_fin": fin,

                            "activo_recomendado": True,

                            "nivel_climatizacion": nivel,

                            "tmax_aemet": tmax,

                            "tmin_aemet": tmin,

                            "temperatura_horaria_min": temp_min_h,

                            "temperatura_horaria_max": temp_max_h,

                            "temperatura_control": (
                                temperatura_control
                            ),

                            "fuente_temperatura": (
                                fuente_temperatura
                            ),

                            "score_solar": score,

                            "confianza": confianza_por_horizonte(
                                indice
                            ),

                            "motivo": estrategia,
                        }
                    )

                continue

            # ==================================================
            # Días 3-7: predicción diaria
            # ==================================================

            if estacion == "verano":

                ventanas = (
                    decidir_climatizacion_verano(
                        servicio[
                            "nombre"
                        ],
                        tmax,
                    )
                )

                temperatura_control = (
                    "tmax"
                )

            else:

                ventanas = (
                    decidir_climatizacion_invierno(
                        tmax,
                        tmin,
                    )
                )

                temperatura_control = (
                    "tmin"
                    if tmin is not None
                    else "tmax_fallback"
                )

            fuente_temperatura = (
                "AEMET_diario"
            )

            if not ventanas:

                resultado.append(
                    {
                        "servicio": servicio[
                            "nombre"
                        ],

                        "descripcion": servicio[
                            "descripcion"
                        ],

                        "tipo": "termica",

                        "fecha": fecha,

                        "dia_semana": nombre_dia_semana(
                            fecha
                        ),

                        "hora_inicio": None,

                        "hora_fin": None,

                        "activo_recomendado": False,

                        "nivel_climatizacion": "no_necesaria",

                        "tmax_aemet": tmax,

                        "tmin_aemet": tmin,

                        "temperatura_horaria_min": None,

                        "temperatura_horaria_max": None,

                        "temperatura_control": (
                            temperatura_control
                        ),

                        "fuente_temperatura": (
                            fuente_temperatura
                        ),

                        "score_solar": score,

                        "confianza": confianza_por_horizonte(
                            indice
                        ),

                        "motivo": (
                            "La temperatura diaria prevista por AEMET "
                            "no justifica climatización programada."
                        ),
                    }
                )

                continue

            for (
                inicio,
                fin,
                nivel,
                estrategia,
            ) in ventanas:

                resultado.append(
                    {
                        "servicio": servicio[
                            "nombre"
                        ],

                        "descripcion": servicio[
                            "descripcion"
                        ],

                        "tipo": "termica",

                        "fecha": fecha,

                        "dia_semana": nombre_dia_semana(
                            fecha
                        ),

                        "hora_inicio": inicio,

                        "hora_fin": fin,

                        "activo_recomendado": True,

                        "nivel_climatizacion": nivel,

                        "tmax_aemet": tmax,

                        "tmin_aemet": tmin,

                        "temperatura_horaria_min": None,

                        "temperatura_horaria_max": None,

                        "temperatura_control": (
                            temperatura_control
                        ),

                        "fuente_temperatura": (
                            fuente_temperatura
                        ),

                        "score_solar": score,

                        "confianza": confianza_por_horizonte(
                            indice
                        ),

                        "motivo": estrategia,
                    }
                )

    return resultado


# ==========================================================
# ACS
# ==========================================================

def planificar_acs(
    demanda,
    prevision,
):
    """
    Planifica la estrategia ACS.

    El termo eléctrico NO se programa de forma automática.
    """

    acs = demanda.get(
        "acs",
        {},
    )

    if not acs:
        return []

    resultado = []

    for indice, dia in enumerate(
        prevision
    ):

        fecha = dia[
            "fecha"
        ]

        score = float(
            dia.get(
                "score",
                0.5,
            )
        )

        if score >= INDICE_SOLAR_BUENO:

            accion = (
                "Priorizar captación solar térmica y bomba "
                "de intercambio. No activar termo eléctrico "
                "salvo temperatura insuficiente."
            )

            termo = "condicional"

        elif score >= INDICE_SOLAR_ACEPTABLE:

            accion = (
                "Comprobar temperatura del acumulador solar. "
                "Usar termo eléctrico únicamente como apoyo."
            )

            termo = "posible"

        else:

            accion = (
                "Probable necesidad de apoyo eléctrico para ACS. "
                "Preferir una hora de bajo precio o producción FV."
            )

            termo = "probable"

        resultado.append(
            {
                "servicio": "ACS",

                "tipo": "condicional",

                "fecha": fecha,

                "dia_semana": nombre_dia_semana(
                    fecha
                ),

                "hora_inicio": "12:00",

                "hora_fin": "17:00",

                "score_solar": score,

                "confianza": confianza_por_horizonte(
                    indice
                ),

                "estado_termo_electrico": termo,

                "motivo": accion,
            }
        )

    return resultado


# ==========================================================
# Riego
# ==========================================================

def planificar_riego(
    servicios,
    prevision,
):
    """
    Planifica el riego fuera de las horas centrales.

    Se prioriza eficiencia hídrica frente al pequeño ahorro
    eléctrico potencial.
    """

    resultado = []

    servicios_riego = [
        s
        for s in servicios
        if s[
            "tipo"
        ] == "restriccion_externa"
    ]

    for servicio in servicios_riego:

        frecuencia = min(
            servicio[
                "frecuencia_semanal"
            ],
            len(
                prevision
            ),
        )

        # --------------------------------------------------
        # Se prefieren días con menor probabilidad de lluvia.
        # --------------------------------------------------

        dias_ordenados = sorted(
            enumerate(
                prevision
            ),
            key=lambda elemento: (
                float(
                    elemento[
                        1
                    ].get(
                        "precip",
                        0.0,
                    )
                    or 0.0
                ),
                elemento[
                    0
                ],
            ),
        )

        for numero, (
            indice,
            dia,
        ) in enumerate(
            dias_ordenados[
                :frecuencia
            ]
        ):

            fecha = dia[
                "fecha"
            ]

            ventana = (
                VENTANAS_RIEGO_PREFERIDAS[
                    0
                ]
            )

            resultado.append(
                {
                    "servicio": servicio[
                        "nombre"
                    ],

                    "descripcion": servicio[
                        "descripcion"
                    ],

                    "tipo": "restriccion_externa",

                    "fecha": fecha,

                    "dia_semana": nombre_dia_semana(
                        fecha
                    ),

                    "hora_inicio": ventana[
                        0
                    ],

                    "hora_fin": ventana[
                        1
                    ],

                    "potencia_kw": servicio[
                        "potencia_kw"
                    ],

                    "confianza": confianza_por_horizonte(
                        indice
                    ),

                    "numero_ejecucion": (
                        numero
                        + 1
                    ),

                    "motivo": (
                        "Se prioriza eficiencia hídrica y baja "
                        "probabilidad de precipitación frente "
                        "al aprovechamiento del máximo solar."
                    ),
                }
            )

    return resultado


# ==========================================================
# Hornos solares
# ==========================================================

def planificar_hornos_solares(
    demanda,
    prevision,
):
    """
    Identifica oportunidades de cocina solar.
    """

    configuracion = demanda.get(
        "hornos_solares",
        {},
    )

    if not configuracion:
        return []

    umbral = float(
        configuracion.get(
            "indice_solar_minimo_recomendado",
            0.75,
        )
    )

    resultado = []

    for indice, dia in enumerate(
        prevision
    ):

        score = float(
            dia.get(
                "score",
                0.0,
            )
        )

        if score < umbral:
            continue

        fecha = dia[
            "fecha"
        ]

        resultado.append(
            {
                "servicio": "hornos_solares",

                "tipo": "alternativa_solar",

                "fecha": fecha,

                "dia_semana": nombre_dia_semana(
                    fecha
                ),

                "hora_inicio": "12:00",

                "hora_fin": "16:00",

                "score_solar": score,

                "confianza": confianza_por_horizonte(
                    indice
                ),

                "motivo": (
                    "Puede sustituirse parcial o totalmente "
                    "la cocina eléctrica por cocina solar."
                ),
            }
        )

    return resultado


# ==========================================================
# Resumen meteorológico semanal
# ==========================================================

def construir_resumen_dias(
    prevision,
):
    """
    Construye el resumen de los días.
    """

    resultado = []

    for indice, dia in enumerate(
        prevision
    ):

        resultado.append(
            {
                "fecha": dia[
                    "fecha"
                ],

                "dia_semana": nombre_dia_semana(
                    dia[
                        "fecha"
                    ]
                ),

                "score_solar": float(
                    dia.get(
                        "score",
                        0.5,
                    )
                ),

                "calidad_solar": clasificar_dia_solar(
                    dia.get(
                        "score",
                        0.5,
                    )
                ),

                "precipitacion": dia.get(
                    "precip"
                ),

                "temperatura_max": dia.get(
                    "tmax"
                ),

                "temperatura_min": dia.get(
                    "tmin"
                ),

                "confianza": confianza_por_horizonte(
                    indice
                ),
            }
        )

    return resultado


# ==========================================================
# Plan semanal completo
# ==========================================================

def generar_plan_semanal(
    demanda,
    prevision_semanal,
    estacion=None,
    horizonte_dias=HORIZONTE_DIAS_DEFAULT,
    prevision_horaria=None,
):
    """
    Genera un plan semanal coordinado de servicios.
    """

    if not prevision_semanal:

        raise ValueError(
            "No existe predicción semanal."
        )

    prevision = prevision_semanal[
        :horizonte_dias
    ]

    # ------------------------------------------------------
    # Estación
    # ------------------------------------------------------

    if estacion is None:

        estacion = demanda.get(
            "estacion"
        )

    if estacion is None:

        mes = prevision[
            0
        ][
            "fecha"
        ].month

        if mes in (
            5,
            6,
            7,
            8,
            9,
        ):

            estacion = "verano"

        else:

            estacion = "invierno"

    # ------------------------------------------------------
    # Servicios
    # ------------------------------------------------------

    servicios = extraer_servicios(
        demanda
    )

    servicios = [
        s
        for s in servicios
        if servicio_activo_en_estacion(
            s,
            estacion,
        )
    ]

    # ------------------------------------------------------
    # Agenda conjunta de potencia
    # ------------------------------------------------------

    agenda = crear_agenda_potencia(
        prevision
    )

    # ------------------------------------------------------
    # Tareas desplazables
    # ------------------------------------------------------

    tareas = planificar_tareas(
        servicios=servicios,
        prevision=prevision,
        demanda=demanda,
        estacion=estacion,
        agenda=agenda,
    )

    # ------------------------------------------------------
    # Cargas térmicas
    # ------------------------------------------------------

    termicas = planificar_cargas_termicas(
        servicios=servicios,
        prevision=prevision,
        estacion=estacion,
        prevision_horaria=prevision_horaria,
    )

    # ------------------------------------------------------
    # ACS
    # ------------------------------------------------------

    acs = planificar_acs(
        demanda,
        prevision,
    )

    # ------------------------------------------------------
    # Riego
    # ------------------------------------------------------

    riego = planificar_riego(
        servicios,
        prevision,
    )

    # ------------------------------------------------------
    # Hornos solares
    # ------------------------------------------------------

    hornos = planificar_hornos_solares(
        demanda,
        prevision,
    )

    return {
        "version": 4,

        "estacion": estacion,

        "horizonte_dias": len(
            prevision
        ),

        "dias": construir_resumen_dias(
            prevision
        ),

        "tareas": tareas,

        "termicas": termicas,

        "acs": acs,

        "riego": riego,

        "hornos_solares": hornos,

        "agenda_potencia": agenda,
    }


# ==========================================================
# Presentación
# ==========================================================

def mostrar_plan_semanal(
    plan,
):
    """
    Presenta el plan semanal.
    """

    print()
    print("Plan semanal sostenible de servicios")
    print("------------------------------------")

    print(
        f"Versión                : "
        f"{plan['version']}"
    )

    print(
        f"Estación               : "
        f"{plan['estacion']}"
    )

    print(
        f"Horizonte              : "
        f"{plan['horizonte_dias']} días"
    )

    # ======================================================
    # Meteorología
    # ======================================================

    print()
    print("Resumen semanal")
    print("---------------")

    print(
        f"{'Día':<12}"
        f"{'Fecha':<12}"
        f"{'Solar':>8}"
        f"{'Tmax':>8}"
        f"{'Tmin':>8}"
        f"{'Calidad':>12}"
        f"{'Confianza':>12}"
    )

    print(
        "-" * 72
    )

    for dia in plan[
        "dias"
    ]:

        tmax = dia.get(
            "temperatura_max"
        )

        tmin = dia.get(
            "temperatura_min"
        )

        tmax_txt = (
            f"{tmax:.0f}"
            if tmax is not None
            else "-"
        )

        tmin_txt = (
            f"{tmin:.0f}"
            if tmin is not None
            else "-"
        )

        print(
            f"{dia['dia_semana']:<12}"
            f"{dia['fecha'].strftime('%d/%m/%Y'):<12}"
            f"{dia['score_solar']:>8.2f}"
            f"{tmax_txt:>8}"
            f"{tmin_txt:>8}"
            f"{dia['calidad_solar']:>12}"
            f"{dia['confianza']:>12}"
        )

    # ======================================================
    # Tareas
    # ======================================================

    print()
    print("Tareas desplazables")
    print("-------------------")

    if not plan[
        "tareas"
    ]:

        print(
            "No existen tareas desplazables programadas."
        )

    else:

        tareas_ordenadas = sorted(
            plan[
                "tareas"
            ],
            key=lambda x: (
                x[
                    "fecha"
                ],
                x[
                    "hora_inicio"
                ],
            ),
        )

        for tarea in tareas_ordenadas:

            print(
                f"{tarea['dia_semana']} "
                f"{tarea['fecha'].strftime('%d/%m/%Y')} "
                f"{tarea['hora_inicio']}–"
                f"{tarea['hora_fin']} | "
                f"{tarea['descripcion']} "
                f"({tarea['potencia_kw']:.2f} kW)"
            )

    # ======================================================
    # Climatización
    # ======================================================

    if plan[
        "termicas"
    ]:

        print()
        print("Gestión térmica")
        print("---------------")

        for entrada in plan[
            "termicas"
        ]:

            tmax = entrada.get(
                "tmax_aemet"
            )

            tmin = entrada.get(
                "tmin_aemet"
            )

            temperaturas = []

            if tmax is not None:
                temperaturas.append(
                    f"Tmax {tmax:.1f} °C"
                )

            if tmin is not None:
                temperaturas.append(
                    f"Tmin {tmin:.1f} °C"
                )

            fuente = entrada.get(
                "fuente_temperatura",
                "AEMET_diario",
            )

            temp_h_min = entrada.get(
                "temperatura_horaria_min"
            )

            temp_h_max = entrada.get(
                "temperatura_horaria_max"
            )

            if (
                fuente == "AEMET_horario"
                and temp_h_min is not None
                and temp_h_max is not None
            ):

                texto_temperatura = (
                    f"Thor {temp_h_min:.1f}–"
                    f"{temp_h_max:.1f} °C"
                )

            else:

                texto_temperatura = (
                    ", ".join(
                        temperaturas
                    )
                    if temperaturas
                    else "temperatura no disponible"
                )

            if entrada.get(
                "activo_recomendado",
                True,
            ):

                horario = (
                    f"{entrada['hora_inicio']}–"
                    f"{entrada['hora_fin']}"
                )

                decision = (
                    f"CLIMATIZAR ({entrada.get('nivel_climatizacion', 'normal')})"
                )

            else:

                horario = "—"
                decision = "NO CLIMATIZAR"

            print(
                f"{entrada['dia_semana']} "
                f"{entrada['fecha'].strftime('%d/%m/%Y')} | "
                f"{entrada['servicio']} | "
                f"{texto_temperatura} | "
                f"{horario} | "
                f"{decision} | "
                f"{fuente}"
            )

            print(
                f"  Motivo: {entrada['motivo']}"
            )

    # ======================================================
    # ACS
    # ======================================================

    if plan[
        "acs"
    ]:

        print()
        print("ACS")
        print("---")

        for entrada in plan[
            "acs"
        ]:

            print(
                f"{entrada['dia_semana']} "
                f"{entrada['fecha'].strftime('%d/%m/%Y')}: "
                f"{entrada['motivo']}"
            )

    # ======================================================
    # Riego
    # ======================================================

    if plan[
        "riego"
    ]:

        print()
        print("Riego")
        print("-----")

        for entrada in plan[
            "riego"
        ]:

            print(
                f"{entrada['dia_semana']} "
                f"{entrada['fecha'].strftime('%d/%m/%Y')} "
                f"{entrada['hora_inicio']}–"
                f"{entrada['hora_fin']} | "
                f"{entrada['servicio']}"
            )

    # ======================================================
    # Hornos solares
    # ======================================================

    if plan[
        "hornos_solares"
    ]:

        print()
        print("Cocina solar")
        print("------------")

        for entrada in plan[
            "hornos_solares"
        ]:

            print(
                f"{entrada['dia_semana']} "
                f"{entrada['fecha'].strftime('%d/%m/%Y')} "
                f"{entrada['hora_inicio']}–"
                f"{entrada['hora_fin']} | "
                f"índice solar "
                f"{entrada['score_solar']:.2f}"
            )


# ==========================================================
# Prueba independiente
# ==========================================================

if __name__ == "__main__":

    from config import (
        obtener_configuracion_sistema,
    )

    from demand import (
        obtener_configuracion_demanda,
    )

    from aemet import (
        obtener_prevision_solar,
    )

    from aemet_hourly import (
        obtener_prevision_horaria,
    )

    configuracion = (
        obtener_configuracion_sistema()
    )

    municipio = configuracion[
        "localizacion"
    ][
        "municipio"
    ]

    hoy = datetime.now().date()

    demanda = obtener_configuracion_demanda(
        fecha=hoy
    )

    prevision = obtener_prevision_solar(
        municipio
    )

    # ------------------------------------------------------
    # Predicción horaria para las primeras ~48 horas
    # ------------------------------------------------------
    #
    # Si AEMET horario falla temporalmente, el plan semanal
    # sigue funcionando con la predicción diaria.

    try:

        prevision_horaria = (
            obtener_prevision_horaria(
                municipio
            )
        )

    except Exception as error:

        print(
            "Aviso: no se pudo obtener AEMET horario. "
            "Se utilizará planificación térmica diaria."
        )

        print(
            f"Detalle: {error}"
        )

        prevision_horaria = []

    plan = generar_plan_semanal(
        demanda=demanda,
        prevision_semanal=prevision,
        prevision_horaria=prevision_horaria,
    )

    mostrar_plan_semanal(
        plan
    )
