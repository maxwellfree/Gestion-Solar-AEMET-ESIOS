#!/usr/bin/env python3
"""
demand.py

Modelo de demanda doméstica para el sistema de gestión solar.

Este módulo describe:

- presencia semanal en la vivienda;
- cargas eléctricas principales;
- cargas flexibles;
- cargas automáticas;
- climatización de verano e invierno;
- producción de agua caliente;
- alternativas solares directas;
- prioridades de uso;
- restricciones de presencia;
- preferencia por preservar la batería;
- perfil horario teórico de demanda de 24 horas.

----------------------------------------------------------------
FILOSOFÍA GENERAL
----------------------------------------------------------------

La vivienda de referencia tiene cinco ocupantes:

    - 2 adultos
    - 3 niños

El criterio principal de gestión es la sostenibilidad.

En particular:

    - se intenta concentrar el consumo en horas solares;
    - se prioriza el consumo fotovoltaico directo;
    - se aprovecha la inercia térmica de la vivienda;
    - se utiliza la red antes que realizar ciclos innecesarios
      de batería;
    - la batería se reserva para situaciones en las que su uso
      esté claramente justificado;
    - se consideran alternativas solares directas, como los
      hornos solares y el sistema solar térmico de ACS.

Los valores de potencia incluidos en esta primera versión son
estimaciones iniciales.

Deberán sustituirse posteriormente por:

    - medidas reales;
    - datos de placa;
    - datos obtenidos del inversor;
    - sensores;
    - hábitos reales de consumo.

Autor: Enrique M. Moreno Pérez
"""


# ==========================================================
# Datos generales de ocupación
# ==========================================================

NUM_ADULTOS = 2

NUM_NINOS = 3

NUM_OCUPANTES = (
    NUM_ADULTOS
    + NUM_NINOS
)


# ==========================================================
# Preferencia energética global
# ==========================================================
#
# La estrategia sostenible debe intentar usar la red antes
# que realizar ciclos de batería de escaso valor.
#
# optimizer.py podrá ignorar esta preferencia si existe una
# razón energética, económica o de seguridad suficientemente
# fuerte.

PRIORIDAD_RED_SOBRE_BATERIA = True


# ==========================================================
# Presencia semanal estándar
# ==========================================================
#
# Esta es una plantilla inicial.
#
# Posteriormente el usuario podrá modificar estas ventanas
# mediante:
#
# - configuración;
# - interfaz gráfica;
# - teléfono móvil;
# - detección automática de presencia;
# - calendario.


PRESENCIA_INVIERNO = {

    "lunes": [
        ("07:00", "09:00"),
        ("14:00", "22:00"),
    ],

    "martes": [
        ("07:00", "09:00"),
        ("14:00", "22:00"),
    ],

    "miercoles": [
        ("07:00", "09:00"),
        ("14:00", "22:00"),
    ],

    "jueves": [
        ("07:00", "09:00"),
        ("14:00", "22:00"),
    ],

    "viernes": [
        ("07:00", "09:00"),
        ("14:00", "22:00"),
    ],

    "sabado": [
        ("08:00", "22:00"),
    ],

    "domingo": [
        ("08:00", "22:00"),
    ],
}


PRESENCIA_VERANO = {

    "lunes": [
        ("08:00", "22:00"),
    ],

    "martes": [
        ("08:00", "22:00"),
    ],

    "miercoles": [
        ("08:00", "22:00"),
    ],

    "jueves": [
        ("08:00", "22:00"),
    ],

    "viernes": [
        ("08:00", "22:00"),
    ],

    "sabado": [
        ("08:00", "22:00"),
    ],

    "domingo": [
        ("08:00", "22:00"),
    ],
}


# ==========================================================
# Horarios térmicos
# ==========================================================

# ----------------------------------------------------------
# Invierno entre semana
# ----------------------------------------------------------
#
# Mañana:
#
#     07:30 -> encendido
#     09:00 -> apagado
#
# Tarde:
#
#     aproximadamente 18:00-18:30 -> encendido
#     22:00 -> apagado
#
# Por la noche la bomba de calor permanece apagada.

CLIMATIZACION_INVIERNO_ENTRE_SEMANA = [
    ("07:30", "09:00"),
    ("18:15", "22:00"),
]


# ----------------------------------------------------------
# Invierno fin de semana
# ----------------------------------------------------------
#
# Existe mayor presencia en la vivienda.
#
# La climatización puede utilizarse durante más horas,
# intentando aprovechar especialmente la franja solar.

CLIMATIZACION_INVIERNO_FIN_SEMANA = [
    ("08:00", "11:00"),
    ("12:00", "17:00"),
    ("18:00", "22:00"),
]


# ----------------------------------------------------------
# Verano
# ----------------------------------------------------------
#
# Estrategia térmica:
#
# noche:
#     ventilación natural
#
# 11:00:
#     cerrar ventanas
#
# 12:00:
#     encender aire acondicionado
#
# 18:00:
#     apagar aire acondicionado
#
# La vivienda dispone de buen aislamiento y se intenta evitar
# climatización nocturna.

CLIMATIZACION_VERANO = [
    ("12:00", "18:00"),
]

HORA_CIERRE_VENTANAS_VERANO = "11:00"

VENTILACION_NOCTURNA_VERANO = True


# ==========================================================
# Cargas base
# ==========================================================

CARGAS_BASE = [

    {
        "nombre": "frigorifico",

        "descripcion": (
            "Frigorífico y congelador"
        ),

        "potencia_kw": 0.12,

        "flexible": False,

        "automatizable": True,

        "requiere_presencia": False,

        "prioridad": 1,

        "estacional": "todo",

        "duracion_h": None,

        "comentario": (
            "Carga continua modelada mediante "
            "potencia media."
        ),
    },

    {
        "nombre": "standby_electronica",

        "descripcion": (
            "Electrónica, router y consumos en espera"
        ),

        "potencia_kw": 0.06,

        "flexible": False,

        "automatizable": False,

        "requiere_presencia": False,

        "prioridad": 2,

        "estacional": "todo",

        "duracion_h": None,

        "comentario": (
            "Estimación inicial de consumo permanente."
        ),
    },

    {
        "nombre": "iluminacion",

        "descripcion": (
            "Iluminación de la vivienda"
        ),

        "potencia_kw": 0.15,

        "flexible": False,

        "automatizable": False,

        "requiere_presencia": True,

        "prioridad": 2,

        "estacional": "todo",

        "duracion_h": None,

        "comentario": (
            "Consumo medio cuando es necesaria iluminación."
        ),
    },
]


# ==========================================================
# Cocina
# ==========================================================

CARGAS_COCINA = [

    {
        "nombre": "induccion",

        "descripcion": (
            "Placa de inducción"
        ),

        "potencia_kw": 2.0,

        "flexible": False,

        "automatizable": False,

        "requiere_presencia": True,

        "prioridad": 2,

        "estacional": "todo",

        "duracion_h": 0.75,

        "comentario": (
            "Potencia media estimada durante "
            "una sesión de cocina."
        ),
    },

    {
        "nombre": "horno",

        "descripcion": (
            "Horno eléctrico"
        ),

        "potencia_kw": 2.2,

        "flexible": True,

        "automatizable": False,

        "requiere_presencia": True,

        "prioridad": 3,

        "estacional": "todo",

        "duracion_h": 1.0,

        "comentario": (
            "Puede evitarse parcialmente utilizando "
            "los hornos solares."
        ),
    },

    {
        "nombre": "microondas",

        "descripcion": (
            "Microondas"
        ),

        "potencia_kw": 1.2,

        "flexible": False,

        "automatizable": False,

        "requiere_presencia": True,

        "prioridad": 2,

        "estacional": "todo",

        "duracion_h": 0.10,

        "comentario": (
            "Uso breve y dependiente de actividad doméstica."
        ),
    },

    {
        "nombre": "robot_cocina",

        "descripcion": (
            "Robot de cocina"
        ),

        "potencia_kw": 1.2,

        "flexible": True,

        "automatizable": False,

        "requiere_presencia": True,

        "prioridad": 3,

        "estacional": "todo",

        "duracion_h": 0.75,

        "comentario": (
            "Puede desplazarse hacia horas solares."
        ),
    },

    {
        "nombre": "cafetera",

        "descripcion": (
            "Cafetera eléctrica"
        ),

        "potencia_kw": 1.2,

        "flexible": False,

        "automatizable": False,

        "requiere_presencia": True,

        "prioridad": 3,

        "estacional": "todo",

        "duracion_h": 0.05,

        "comentario": (
            "Consumo breve con muy poca "
            "flexibilidad temporal."
        ),
    },
]


# ==========================================================
# Hornos solares
# ==========================================================
#
# No constituyen una carga eléctrica.
#
# Se modelan como una alternativa tecnológica capaz de
# sustituir parcial o totalmente determinados servicios
# eléctricos de cocción.

HORNOS_SOLARES = {

    "numero_unidades": 2,

    "consumo_electrico_kw": 0.0,

    "requiere_presencia": True,

    "indice_solar_minimo_recomendado": 0.75,

    "servicios_sustituibles": [
        "horno",
        "induccion",
        "robot_cocina",
    ],

    "comentario": (
        "Cuando la previsión solar es favorable, "
        "el optimizador puede recomendar cocinar "
        "mediante hornos solares."
    ),
}


# ==========================================================
# Agua caliente sanitaria
# ==========================================================

ACS = {

    "termo_electrico": {

        "nombre": "termo_electrico",

        "descripcion": (
            "Termo eléctrico de ACS"
        ),

        # Valor provisional.
        "potencia_kw": 2.0,

        "flexible": True,

        "automatizable": True,

        "requiere_presencia": False,

        "prioridad": 2,

        "estacional": "todo",

        "comentario": (
            "Debe utilizarse únicamente cuando "
            "el sistema solar térmico no proporciona "
            "temperatura suficiente."
        ),
    },


    "solar_termico": {

        "disponible": True,

        "conectado_en_serie": True,

        "bomba_intercambio": True,

        # Valor provisional.
        "potencia_bomba_kw": 0.08,

        "prioridad_sobre_termo_electrico": True,

        "comentario": (
            "El sistema solar térmico debe tener prioridad "
            "sobre la resistencia eléctrica."
        ),
    },
}


# ==========================================================
# Lavadora
# ==========================================================

LAVADORA = {

    "nombre": "lavadora",

    "descripcion": (
        "Lavadora"
    ),

    # Potencia media provisional.
    "potencia_kw": 1.0,

    # Pico aproximado durante calentamiento.
    "potencia_pico_kw": 2.0,

    "duracion_h": 1.5,

    "flexible": True,

    "automatizable": False,

    "requiere_presencia": True,

    "prioridad": 3,

    "estacional": "todo",

    # Puede retrasarse hasta un día si el usuario lo permite.
    "max_aplazamiento_h": 24,

    "ventana_solar_preferida": (
        "11:00",
        "17:00",
    ),

    "comentario": (
        "Debe programarse preferentemente durante "
        "producción fotovoltaica y cuando exista "
        "presencia suficiente en la vivienda."
    ),
}


# ==========================================================
# Climatización principal
# ==========================================================

CLIMATIZACION = {

    "planta_superior": {

        "nombre": "bomba_calor_superior",

        "descripcion": (
            "Bomba de calor / aire acondicionado "
            "planta superior"
        ),

        # Valor provisional.
        "potencia_kw": 1.2,

        "flexible": True,

        "automatizable": True,

        "requiere_presencia": True,

        "prioridad": 2,

        "estacional": "todo",
    },


    "planta_inferior": {

        "nombre": "bomba_calor_inferior",

        "descripcion": (
            "Bomba de calor / aire acondicionado "
            "planta inferior"
        ),

        # Valor provisional.
        "potencia_kw": 1.2,

        "flexible": True,

        "automatizable": True,

        "requiere_presencia": True,

        "prioridad": 2,

        "estacional": "todo",
    },
}


# ==========================================================
# Climatización de despensa
# ==========================================================

DESPENSA = {

    "nombre": "ac_despensa",

    "descripcion": (
        "Aire acondicionado de la habitación despensa"
    ),

    # Valor provisional.
    "potencia_kw": 0.7,

    "flexible": True,

    "automatizable": True,

    "requiere_presencia": False,

    "prioridad": 2,

    "estacional": "verano",

    "temperatura_max_c": 22.0,

    "preenfriamiento_solar": True,

    "comentario": (
        "Puede preenfriarse durante horas solares "
        "para reducir funcionamiento posterior."
    ),
}


# ==========================================================
# Riego automático
# ==========================================================

RIEGO = {

    "nombre": "riego",

    "descripcion": (
        "Sistema automático de riego mediante "
        "electroválvulas"
    ),

    "potencia_kw": 0.03,

    "flexible": True,

    "automatizable": True,

    "requiere_presencia": False,

    "prioridad": 4,

    "estacional": "todo",

    # Se priorizan criterios agronómicos.
    "ventanas_preferidas": [
        ("06:00", "09:00"),
        ("20:00", "23:00"),
    ],

    "comentario": (
        "La optimización energética es secundaria "
        "frente a la conveniencia agronómica."
    ),
}


# ==========================================================
# Sistema UV de agua de cocina
# ==========================================================

UV_COCINA = {

    "nombre": "uv_cocina",

    "descripcion": (
        "Lámpara ultravioleta de tratamiento "
        "de agua en cocina"
    ),

    "potencia_kw": 0.04,

    "flexible": False,

    "automatizable": True,

    "requiere_presencia": False,

    "prioridad": 1,

    "estacional": "todo",

    "control_por_flujo": True,

    "arduino": True,

    "comentario": (
        "La lámpara se activa automáticamente cuando "
        "el caudalímetro detecta flujo de agua."
    ),
}


# ==========================================================
# Perfil base horario
# ==========================================================
#
# Representa la demanda mínima permanente de la vivienda.
#
# Incluye de forma aproximada:
#
# - frigorífico;
# - electrónica;
# - router;
# - pequeños consumos permanentes.
#
# No incluye:
#
# - climatización;
# - cocina;
# - lavadora;
# - ACS eléctrico.

POTENCIA_BASE_KW = 0.18


# ==========================================================
# Prioridad general de servicios
# ==========================================================

PRIORIDADES = {

    1: "esencial",

    2: "importante",

    3: "flexible",

    4: "opcional",
}


# ==========================================================
# Jerarquía sostenible de consumo
# ==========================================================

JERARQUIA_SOSTENIBLE = [

    "evitar_consumo",

    "alternativa_solar_directa",

    "desplazar_carga",

    "almacenamiento_termico",

    "fotovoltaica_directa",

    "red",

    "bateria",

    "vertido",
]


# ==========================================================
# Política de batería
# ==========================================================

POLITICA_BATERIA = {

    # La batería no debe utilizarse automáticamente solo
    # porque exista energía almacenada.
    "uso_por_defecto": False,

    # Preferencia central del caso de referencia.
    "preferir_red_si_beneficio_bateria_bajo": True,

    # Durante la noche la vivienda tiene poca demanda.
    "preservar_bateria_noche": True,

    # El arbitraje económico puro no es prioritario.
    "arbitraje_economico_prioritario": False,

    "comentario": (
        "La batería se considera un recurso de alto coste "
        "ambiental cuya vida útil debe maximizarse."
    ),
}


# ==========================================================
# Obtención de todas las cargas
# ==========================================================

def obtener_cargas():
    """
    Devuelve una lista conjunta con las principales cargas
    eléctricas de la vivienda.

    Returns
    -------
    list
        Cargas configuradas.
    """

    cargas = []

    cargas.extend(
        CARGAS_BASE
    )

    cargas.extend(
        CARGAS_COCINA
    )

    cargas.append(
        ACS["termo_electrico"]
    )

    cargas.append(
        LAVADORA
    )

    cargas.append(
        CLIMATIZACION["planta_superior"]
    )

    cargas.append(
        CLIMATIZACION["planta_inferior"]
    )

    cargas.append(
        DESPENSA
    )

    cargas.append(
        RIEGO
    )

    cargas.append(
        UV_COCINA
    )

    return cargas


# ==========================================================
# Utilidades temporales
# ==========================================================

def es_fin_de_semana(
    fecha,
):
    """
    Devuelve True si la fecha es sábado o domingo.
    """

    return (
        fecha.weekday() >= 5
    )


def estacion_desde_mes(
    mes,
):
    """
    Determina una estación simplificada a partir del mes.

    Esta versión utiliza únicamente:

        verano
        invierno

    Parameters
    ----------
    mes : int
        Mes de 1 a 12.

    Returns
    -------
    str
        "verano" o "invierno".
    """

    if mes in (
        5,
        6,
        7,
        8,
        9,
    ):
        return "verano"

    return "invierno"


# ==========================================================
# Registro horario
# ==========================================================

def crear_registro_horario(
    hora,
):
    """
    Crea un registro vacío correspondiente a una hora.

    Todas las potencias se expresan en kW.

    Parameters
    ----------
    hora : int
        Hora entera entre 0 y 23.

    Returns
    -------
    dict
        Registro horario inicialmente vacío.
    """

    return {

        "hora": (
            f"{hora:02d}:00"
        ),

        "potencia_base_kw": 0.0,

        "iluminacion_kw": 0.0,

        "climatizacion_kw": 0.0,

        "cocina_kw": 0.0,

        "acs_kw": 0.0,

        "lavadora_kw": 0.0,

        "otros_kw": 0.0,

        "potencia_total_kw": 0.0,

        # Información lógica.
        "presencia": False,

        # Lista de cargas que podrían desplazarse
        # o activarse en esa hora.
        "flexibilidad": [],
    }


def sumar_total_registro(
    registro,
):
    """
    Calcula la potencia total de un registro horario.

    Returns
    -------
    dict
        Registro actualizado.
    """

    registro[
        "potencia_total_kw"
    ] = (

        registro[
            "potencia_base_kw"
        ]

        + registro[
            "iluminacion_kw"
        ]

        + registro[
            "climatizacion_kw"
        ]

        + registro[
            "cocina_kw"
        ]

        + registro[
            "acs_kw"
        ]

        + registro[
            "lavadora_kw"
        ]

        + registro[
            "otros_kw"
        ]
    )

    return registro


# ==========================================================
# Perfil horario de verano
# ==========================================================

def perfil_verano(
    fecha,
):
    """
    Genera el perfil horario teórico de verano.

    Hipótesis
    ---------

    - ventilación natural nocturna;
    - ventanas cerradas aproximadamente a las 11:00;
    - aire acondicionado de 12:00 a 18:00;
    - elevada coincidencia entre climatización y producción FV;
    - consumo nocturno pequeño;
    - cargas flexibles desplazadas hacia horas solares.

    Parameters
    ----------
    fecha : datetime.date
        Fecha del perfil.

    Returns
    -------
    list
        24 registros horarios.
    """

    perfil = []

    for hora in range(24):

        r = crear_registro_horario(
            hora
        )

        # --------------------------------------------------
        # Carga base
        # --------------------------------------------------

        r[
            "potencia_base_kw"
        ] = POTENCIA_BASE_KW

        # --------------------------------------------------
        # Presencia
        # --------------------------------------------------

        if 8 <= hora < 22:

            r[
                "presencia"
            ] = True

        # --------------------------------------------------
        # Iluminación
        # --------------------------------------------------

        if hora < 7:

            r[
                "iluminacion_kw"
            ] = 0.02

        elif 7 <= hora < 9:

            r[
                "iluminacion_kw"
            ] = 0.05

        elif 9 <= hora < 20:

            r[
                "iluminacion_kw"
            ] = 0.01

        elif 20 <= hora < 22:

            r[
                "iluminacion_kw"
            ] = 0.10

        else:

            r[
                "iluminacion_kw"
            ] = 0.03

        # --------------------------------------------------
        # Climatización principal
        # --------------------------------------------------
        #
        # Dos máquinas:
        #
        #     1.2 + 1.2 = 2.4 kW
        #
        # Se trata de una potencia media provisional.

        if 12 <= hora < 18:

            r[
                "climatizacion_kw"
            ] = 2.40

            r[
                "flexibilidad"
            ].append(
                "climatizacion"
            )

        # --------------------------------------------------
        # Cocina
        # --------------------------------------------------

        if hora == 8:

            r[
                "cocina_kw"
            ] = 0.35

        elif hora == 14:

            r[
                "cocina_kw"
            ] = 1.20

        elif hora == 20:

            r[
                "cocina_kw"
            ] = 0.80

        # --------------------------------------------------
        # ACS
        # --------------------------------------------------
        #
        # En verano suponemos una contribución muy elevada
        # del sistema solar térmico.
        #
        # Se deja una pequeña demanda eléctrica potencial
        # como valor provisional.

        if hora == 13:

            r[
                "acs_kw"
            ] = 0.10

        # ACS puede gestionarse en buena parte del periodo
        # solar.

        if 11 <= hora < 17:

            r[
                "flexibilidad"
            ].append(
                "acs"
            )

        # --------------------------------------------------
        # Lavadora
        # --------------------------------------------------
        #
        # No se activa todavía automáticamente.
        #
        # Se ofrece al optimizador una ventana de ejecución.

        if 11 <= hora < 17:

            r[
                "flexibilidad"
            ].append(
                "lavadora"
            )

        # --------------------------------------------------
        # Otros consumos
        # --------------------------------------------------

        r[
            "otros_kw"
        ] = 0.03

        # --------------------------------------------------
        # Finalizar registro
        # --------------------------------------------------

        perfil.append(
            sumar_total_registro(
                r
            )
        )

    return perfil


# ==========================================================
# Perfil horario de invierno laborable
# ==========================================================

def perfil_invierno_laborable(
    fecha,
):
    """
    Genera un perfil horario teórico para un día laborable
    de invierno.

    Hipótesis
    ---------

    - bomba de calor aproximadamente 07:30-09:00;
    - vivienda prácticamente vacía buena parte del día;
    - bomba de calor de nuevo aproximadamente 18:15-22:00;
    - climatización apagada durante la noche;
    - prioridad de red frente a ciclos marginales de batería.

    Returns
    -------
    list
        Perfil horario de 24 registros.
    """

    perfil = []

    for hora in range(24):

        r = crear_registro_horario(
            hora
        )

        # --------------------------------------------------
        # Base
        # --------------------------------------------------

        r[
            "potencia_base_kw"
        ] = POTENCIA_BASE_KW

        # --------------------------------------------------
        # Presencia
        # --------------------------------------------------

        if 7 <= hora < 9:

            r[
                "presencia"
            ] = True

        elif 14 <= hora < 22:

            r[
                "presencia"
            ] = True

        # --------------------------------------------------
        # Iluminación
        # --------------------------------------------------

        if hora < 7:

            r[
                "iluminacion_kw"
            ] = 0.03

        elif 7 <= hora < 9:

            r[
                "iluminacion_kw"
            ] = 0.12

        elif 9 <= hora < 17:

            r[
                "iluminacion_kw"
            ] = 0.01

        elif 17 <= hora < 22:

            r[
                "iluminacion_kw"
            ] = 0.18

        else:

            r[
                "iluminacion_kw"
            ] = 0.03

        # --------------------------------------------------
        # Bomba de calor por la mañana
        # --------------------------------------------------
        #
        # 07:30-08:00:
        # media hora aproximada.
        #
        # 08:00-09:00:
        # hora completa.

        if hora == 7:

            r[
                "climatizacion_kw"
            ] = 1.20

        elif hora == 8:

            r[
                "climatizacion_kw"
            ] = 2.40

        # --------------------------------------------------
        # Bomba de calor por la tarde
        # --------------------------------------------------

        elif hora == 18:

            r[
                "climatizacion_kw"
            ] = 1.80

        elif 19 <= hora < 22:

            r[
                "climatizacion_kw"
            ] = 2.40

        # --------------------------------------------------
        # Cocina
        # --------------------------------------------------

        if hora == 7:

            r[
                "cocina_kw"
            ] = 0.35

        elif hora == 14:

            r[
                "cocina_kw"
            ] = 1.00

        elif hora == 20:

            r[
                "cocina_kw"
            ] = 0.90

        # --------------------------------------------------
        # ACS flexible
        # --------------------------------------------------

        if 11 <= hora < 16:

            r[
                "flexibilidad"
            ].append(
                "acs"
            )

        # --------------------------------------------------
        # Lavadora
        # --------------------------------------------------

        if 14 <= hora < 17:

            r[
                "flexibilidad"
            ].append(
                "lavadora"
            )

        # --------------------------------------------------
        # Otros
        # --------------------------------------------------

        r[
            "otros_kw"
        ] = 0.03

        perfil.append(
            sumar_total_registro(
                r
            )
        )

    return perfil


# ==========================================================
# Perfil horario de invierno en fin de semana
# ==========================================================

def perfil_invierno_fin_semana(
    fecha,
):
    """
    Genera el perfil de invierno para sábado o domingo.

    Durante el fin de semana existe mayor presencia y mayor
    posibilidad de desplazar climatización y cargas hacia
    las horas solares.

    Returns
    -------
    list
        Perfil horario de 24 registros.
    """

    perfil = []

    for hora in range(24):

        r = crear_registro_horario(
            hora
        )

        # --------------------------------------------------
        # Base
        # --------------------------------------------------

        r[
            "potencia_base_kw"
        ] = POTENCIA_BASE_KW

        # --------------------------------------------------
        # Presencia
        # --------------------------------------------------

        if 8 <= hora < 22:

            r[
                "presencia"
            ] = True

        # --------------------------------------------------
        # Iluminación
        # --------------------------------------------------

        if hora < 8:

            r[
                "iluminacion_kw"
            ] = 0.03

        elif 8 <= hora < 17:

            r[
                "iluminacion_kw"
            ] = 0.03

        elif 17 <= hora < 22:

            r[
                "iluminacion_kw"
            ] = 0.16

        else:

            r[
                "iluminacion_kw"
            ] = 0.03

        # --------------------------------------------------
        # Climatización
        # --------------------------------------------------

        if 8 <= hora < 11:

            r[
                "climatizacion_kw"
            ] = 2.0

        elif 12 <= hora < 17:

            r[
                "climatizacion_kw"
            ] = 1.6

            r[
                "flexibilidad"
            ].append(
                "climatizacion"
            )

        elif 18 <= hora < 22:

            r[
                "climatizacion_kw"
            ] = 2.2

        # --------------------------------------------------
        # Cocina
        # --------------------------------------------------

        if hora == 9:

            r[
                "cocina_kw"
            ] = 0.40

        elif hora == 14:

            r[
                "cocina_kw"
            ] = 1.20

        elif hora == 20:

            r[
                "cocina_kw"
            ] = 0.90

        # --------------------------------------------------
        # ACS
        # --------------------------------------------------

        if 11 <= hora < 16:

            r[
                "flexibilidad"
            ].append(
                "acs"
            )

        # --------------------------------------------------
        # Lavadora
        # --------------------------------------------------

        if 10 <= hora < 17:

            r[
                "flexibilidad"
            ].append(
                "lavadora"
            )

        # --------------------------------------------------
        # Otros
        # --------------------------------------------------

        r[
            "otros_kw"
        ] = 0.03

        perfil.append(
            sumar_total_registro(
                r
            )
        )

    return perfil


# ==========================================================
# Selector general de perfil de demanda
# ==========================================================

def obtener_perfil_demanda_24h(
    fecha,
    estacion=None,
):
    """
    Genera el perfil horario teórico correspondiente
    a una fecha.

    Parameters
    ----------
    fecha : datetime.date
        Fecha para la que se construye el perfil.

    estacion : str, optional
        Puede ser:

            "verano"
            "invierno"

        Si no se proporciona, se determina automáticamente
        a partir del mes.

    Returns
    -------
    list
        Lista de 24 registros horarios.
    """

    if estacion is None:

        estacion = estacion_desde_mes(
            fecha.month
        )

    estacion = (
        str(estacion)
        .strip()
        .lower()
    )

    if estacion == "verano":

        return perfil_verano(
            fecha
        )

    if estacion == "invierno":

        if es_fin_de_semana(
            fecha
        ):

            return perfil_invierno_fin_semana(
                fecha
            )

        return perfil_invierno_laborable(
            fecha
        )

    raise ValueError(
        f"Estación no válida: '{estacion}'. "
        "Valores permitidos: verano, invierno."
    )


# ==========================================================
# Energía diaria del perfil
# ==========================================================

def energia_diaria_perfil(
    perfil,
):
    """
    Calcula la energía diaria aproximada.

    Cada registro representa una hora.

    Por tanto:

        E = suma(P_i * 1 h)

    Parameters
    ----------
    perfil : list
        Perfil horario.

    Returns
    -------
    float
        Energía diaria en kWh.
    """

    return sum(

        registro[
            "potencia_total_kw"
        ]

        for registro in perfil
    )


# ==========================================================
# Presentación del perfil
# ==========================================================

def mostrar_perfil_demanda(
    perfil,
):
    """
    Muestra por terminal el perfil horario de demanda.
    """

    print()
    print("Perfil horario teórico de demanda")
    print("---------------------------------")

    print(
        f"{'Hora':<8}"
        f"{'Base':>8}"
        f"{'Luz':>8}"
        f"{'Clima':>10}"
        f"{'Cocina':>10}"
        f"{'ACS':>8}"
        f"{'Lavadora':>11}"
        f"{'Otros':>8}"
        f"{'Total':>10}"
    )

    print(
        "-" * 81
    )

    for r in perfil:

        print(
            f"{r['hora']:<8}"
            f"{r['potencia_base_kw']:>8.2f}"
            f"{r['iluminacion_kw']:>8.2f}"
            f"{r['climatizacion_kw']:>10.2f}"
            f"{r['cocina_kw']:>10.2f}"
            f"{r['acs_kw']:>8.2f}"
            f"{r['lavadora_kw']:>11.2f}"
            f"{r['otros_kw']:>8.2f}"
            f"{r['potencia_total_kw']:>10.2f}"
        )

    energia = energia_diaria_perfil(
        perfil
    )

    print()

    print(
        f"Demanda diaria teórica: "
        f"{energia:.2f} kWh"
    )


# ==========================================================
# Obtención de configuración completa de demanda
# ==========================================================

def obtener_configuracion_demanda(
    fecha=None,
    estacion=None,
):
    """
    Devuelve toda la configuración doméstica.

    Esta es la interfaz principal de demand.py.

    Además de la configuración estática, si se proporciona
    una fecha se genera automáticamente:

        - perfil_24h;
        - energía diaria teórica;
        - estación utilizada.

    Parameters
    ----------
    fecha : datetime.date, optional
        Fecha para la que se quiere generar el perfil.

    estacion : str, optional
        "verano" o "invierno".

        Si no se proporciona, se determina automáticamente.

    Returns
    -------
    dict
        Configuración completa.
    """

    configuracion = {

        # --------------------------------------------------
        # Ocupación
        # --------------------------------------------------

        "ocupantes": {

            "adultos": (
                NUM_ADULTOS
            ),

            "ninos": (
                NUM_NINOS
            ),

            "total": (
                NUM_OCUPANTES
            ),
        },

        # --------------------------------------------------
        # Presencia
        # --------------------------------------------------

        "presencia": {

            "invierno": (
                PRESENCIA_INVIERNO
            ),

            "verano": (
                PRESENCIA_VERANO
            ),
        },

        # --------------------------------------------------
        # Horarios térmicos
        # --------------------------------------------------

        "climatizacion_horarios": {

            "invierno_entre_semana": (
                CLIMATIZACION_INVIERNO_ENTRE_SEMANA
            ),

            "invierno_fin_semana": (
                CLIMATIZACION_INVIERNO_FIN_SEMANA
            ),

            "verano": (
                CLIMATIZACION_VERANO
            ),

            "cierre_ventanas_verano": (
                HORA_CIERRE_VENTANAS_VERANO
            ),

            "ventilacion_nocturna_verano": (
                VENTILACION_NOCTURNA_VERANO
            ),
        },

        # --------------------------------------------------
        # Potencia base
        # --------------------------------------------------

        "potencia_base_kw": (
            POTENCIA_BASE_KW
        ),

        # --------------------------------------------------
        # Cargas
        # --------------------------------------------------

        "cargas": (
            obtener_cargas()
        ),

        # --------------------------------------------------
        # ACS
        # --------------------------------------------------

        "acs": (
            ACS
        ),

        # --------------------------------------------------
        # Hornos solares
        # --------------------------------------------------

        "hornos_solares": (
            HORNOS_SOLARES
        ),

        # --------------------------------------------------
        # Política de batería
        # --------------------------------------------------

        "politica_bateria": (
            POLITICA_BATERIA
        ),

        "jerarquia_sostenible": (
            JERARQUIA_SOSTENIBLE
        ),

        "prioridad_red_sobre_bateria": (
            PRIORIDAD_RED_SOBRE_BATERIA
        ),

        # --------------------------------------------------
        # Resultados horarios
        # --------------------------------------------------

        "perfil_24h": None,

        "energia_diaria_teorica_kwh": None,

        "estacion": None,

        "tipo_dia": None,
    }

    # ======================================================
    # Generación del perfil horario
    # ======================================================

    if fecha is not None:

        # --------------------------------------------------
        # Determinar estación
        # --------------------------------------------------

        if estacion is None:

            estacion_usada = estacion_desde_mes(
                fecha.month
            )

        else:

            estacion_usada = (
                str(estacion)
                .strip()
                .lower()
            )

        # --------------------------------------------------
        # Generar perfil
        # --------------------------------------------------

        perfil = obtener_perfil_demanda_24h(
            fecha=fecha,
            estacion=estacion_usada,
        )

        # --------------------------------------------------
        # Guardar resultados
        # --------------------------------------------------

        configuracion[
            "perfil_24h"
        ] = perfil

        configuracion[
            "energia_diaria_teorica_kwh"
        ] = energia_diaria_perfil(
            perfil
        )

        configuracion[
            "estacion"
        ] = estacion_usada

        if es_fin_de_semana(
            fecha
        ):

            configuracion[
                "tipo_dia"
            ] = "fin_semana"

        else:

            configuracion[
                "tipo_dia"
            ] = "laborable"

    return configuracion
