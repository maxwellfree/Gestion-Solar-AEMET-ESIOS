#!/usr/bin/env python3
"""
config.py

Configuración física y operativa del sistema fotovoltaico.

Este archivo contiene los parámetros que describen la instalación
sobre la que trabaja el optimizador.

La intención es que el algoritmo sea completamente general.

Para adaptar el software a otra instalación, el usuario debería
modificar principalmente este archivo, sin necesidad de alterar:

    aemet.py
    esios.py
    optimizer.py
    main.py

----------------------------------------------------------------
ESTRUCTURA
----------------------------------------------------------------

1. Campo fotovoltaico.
2. Inversor.
3. Baterías.
4. Política de sostenibilidad.
5. Límites operativos.
6. Configuración general del optimizador.

----------------------------------------------------------------
IMPORTANTE
----------------------------------------------------------------

Se distingue explícitamente entre:

A) DATOS DEL FABRICANTE

    Valores físicos o eléctricos del equipo.

B) POLÍTICA DE CONTROL

    Valores elegidos por nuestro algoritmo para operar de forma
    conservadora y sostenible.

Los parámetros de política sostenible NO deben confundirse con
los límites absolutos especificados por el fabricante.

Autor: Enrique M. Moreno Pérez
"""


# ==========================================================
# Identificación del sistema
# ==========================================================

SISTEMA_NOMBRE = (
    "Instalación fotovoltaica residencial de referencia"
)

SISTEMA_DESCRIPCION = (
    "Campo FV de 10 paneles JA Solar de 605 W, "
    "inversor híbrido Deye de 6 kW y dos baterías "
    "Deye SE-G5.1 Pro-B."
)

# ==========================================================
# Localización de la instalación
# ==========================================================
#
# La localización se define una sola vez en config.py.
#
# A partir del nombre del municipio:
#
#     - aemet.py podrá obtener el código municipal AEMET;
#     - solar.py podrá obtener latitud y longitud;
#     - PVGIS podrá proporcionar la irradiancia correspondiente;
#     - main.py ya no tendrá que pedir --municipio.
#
# De esta forma la localización pasa a formar parte de la
# descripción física permanente de la instalación.
#
# IMPORTANTE:
# si existen municipios con el mismo nombre, posteriormente
# podremos utilizar también provincia o código AEMET para
# resolver cualquier ambigüedad.

MUNICIPIO = "Maracena"

PROVINCIA = "Granada"

# ----------------------------------------------------------
# Coordenadas
# ----------------------------------------------------------
#
# No es necesario que el usuario las introduzca manualmente.
#
# Se dejan inicialmente como None porque solar.py podrá
# obtenerlas automáticamente a partir del municipio mediante
# el catálogo de municipios de AEMET.
#
# Una vez resueltas, incluso podremos almacenarlas en caché.

LATITUD = None

LONGITUD = None


# ==========================================================
# Campo fotovoltaico
# ==========================================================

# Número total de módulos instalados.
NUM_PANELES = 10

# Potencia nominal de cada módulo.
PANEL_POTENCIA_W = 605.0

# Potencia fotovoltaica total instalada.
POTENCIA_FV_WP = (
    NUM_PANELES
    * PANEL_POTENCIA_W
)

POTENCIA_FV_KWP = (
    POTENCIA_FV_WP
    / 1000.0
)

# ==========================================================
# Geometría del campo fotovoltaico
# ==========================================================
#
# Estos parámetros describen cómo están físicamente
# instalados los paneles.
#
# Son necesarios para transformar la irradiancia solar
# disponible en irradiancia incidente sobre el plano real
# de los módulos.
#
# ----------------------------------------------------------
# Inclinación
# ----------------------------------------------------------
#
# Ángulo respecto de la horizontal:
#
#      0°  -> panel completamente horizontal
#     30°  -> panel inclinado 30°
#     90°  -> panel vertical
#
# Debe introducirse el valor real de la instalación.

PANEL_INCLINACION_GRADOS = 33.0


# ----------------------------------------------------------
# Azimut
# ----------------------------------------------------------
#
# Utilizaremos la misma convención que PVGIS:
#
#       0°  -> Sur
#     -90°  -> Este
#     +90°  -> Oeste
#    ±180°  -> Norte
#
# Ejemplos:
#
# PANEL_AZIMUT_GRADOS = 0.0
#     orientación Sur
#
# PANEL_AZIMUT_GRADOS = -30.0
#     30° hacia el Este respecto del Sur
#
# PANEL_AZIMUT_GRADOS = 45.0
#     45° hacia el Oeste respecto del Sur
#
# Debe sustituirse por la orientación real del campo FV.

PANEL_AZIMUT_GRADOS = 0.0


# ----------------------------------------------------------
# Datos eléctricos aproximados del módulo de referencia
# ----------------------------------------------------------
#
# Estos parámetros podrán utilizarse posteriormente para
# construir un modelo físico más detallado de producción FV.
#
# Conviene comprobar siempre estos valores contra la ficha
# técnica exacta del módulo instalado antes de utilizarlos
# para cálculos de protección o diseño eléctrico.

PANEL_VMP_V = 45.05

PANEL_VOC_V = 53.00

PANEL_IMP_A = 13.43

PANEL_ISC_A = 14.09


# ----------------------------------------------------------
# Coeficiente térmico de potencia
# ----------------------------------------------------------
#
# Expresado como fracción por grado Celsius.
#
# Ejemplo:
#
#     -0.0029  ->  -0.29 % / °C
#
# Este valor permitirá mejorar en el futuro la penalización
# térmica actualmente heurística utilizada en aemet.py.

PANEL_COEF_TEMP_PMAX = -0.0029


# ==========================================================
# Inversor
# ==========================================================

INVERSOR_FABRICANTE = "Deye"

INVERSOR_MODELO = (
    "SUN-6K-SG05LP1-EU-AM2-P"
)

# Potencia activa nominal.
INVERSOR_POTENCIA_NOMINAL_W = 6000.0

INVERSOR_POTENCIA_NOMINAL_KW = (
    INVERSOR_POTENCIA_NOMINAL_W
    / 1000.0
)


# ----------------------------------------------------------
# Entrada de batería del inversor
# ----------------------------------------------------------

INVERSOR_BATERIA_V_MIN = 40.0

INVERSOR_BATERIA_V_MAX = 60.0

# Corrientes máximas absolutas admitidas por el inversor.
#
# Estos valores NO significan que el algoritmo deba trabajar
# habitualmente a esas corrientes.

INVERSOR_CORRIENTE_CARGA_MAX_A = 135.0

INVERSOR_CORRIENTE_DESCARGA_MAX_A = 135.0


# ----------------------------------------------------------
# Entrada fotovoltaica
# ----------------------------------------------------------

INVERSOR_PV_VOLTAGE_MAX_V = 500.0

INVERSOR_PV_START_V = 125.0

INVERSOR_MPPT_V_MIN = 150.0

INVERSOR_MPPT_V_MAX = 425.0

INVERSOR_NUM_MPPT = 2


# ==========================================================
# Baterías
# ==========================================================

BATERIA_FABRICANTE = "Deye"

BATERIA_MODELO = "SE-G5.1 Pro-B"

NUM_BATERIAS = 2


# ----------------------------------------------------------
# Parámetros por unidad
# ----------------------------------------------------------

BATERIA_TENSION_NOMINAL_V = 51.2

BATERIA_CAPACIDAD_AH_UNIDAD = 100.0

BATERIA_ENERGIA_KWH_UNIDAD = 5.12


# ----------------------------------------------------------
# Banco completo
# ----------------------------------------------------------
#
# Se considera que las dos baterías trabajan en paralelo.

BATERIA_CAPACIDAD_AH_TOTAL = (
    NUM_BATERIAS
    * BATERIA_CAPACIDAD_AH_UNIDAD
)

BATERIA_ENERGIA_KWH_TOTAL = (
    NUM_BATERIAS
    * BATERIA_ENERGIA_KWH_UNIDAD
)


# ==========================================================
# Corrientes de batería
# ==========================================================

# Corriente recomendada por unidad.
BATERIA_CORRIENTE_RECOMENDADA_A_UNIDAD = 50.0

# Corriente máxima por unidad.
BATERIA_CORRIENTE_MAX_A_UNIDAD = 100.0


# ----------------------------------------------------------
# Valores agregados del banco
# ----------------------------------------------------------

BATERIA_CORRIENTE_RECOMENDADA_A_TOTAL = (
    NUM_BATERIAS
    * BATERIA_CORRIENTE_RECOMENDADA_A_UNIDAD
)

BATERIA_CORRIENTE_MAX_A_TOTAL = (
    NUM_BATERIAS
    * BATERIA_CORRIENTE_MAX_A_UNIDAD
)


# ==========================================================
# Límite físico efectivo de corriente
# ==========================================================
#
# El límite efectivo debe respetar tanto las baterías como
# el inversor.
#
# El elemento más restrictivo determina el máximo absoluto.

CORRIENTE_CARGA_MAX_FISICA_A = min(
    BATERIA_CORRIENTE_MAX_A_TOTAL,
    INVERSOR_CORRIENTE_CARGA_MAX_A,
)

CORRIENTE_DESCARGA_MAX_FISICA_A = min(
    BATERIA_CORRIENTE_MAX_A_TOTAL,
    INVERSOR_CORRIENTE_DESCARGA_MAX_A,
)


# ==========================================================
# Vida útil de referencia
# ==========================================================
#
# Valor declarado bajo las condiciones de ensayo especificadas
# por el fabricante.
#
# Este valor NO debe interpretarse como una vida útil garantizada
# para cualquier condición real de operación.

BATERIA_CICLOS_REFERENCIA = 6000

# Profundidad de descarga asociada a esa referencia.
BATERIA_DOD_REFERENCIA = 0.90

# Estado de salud considerado al final de vida en el ensayo.
BATERIA_EOL_SOH = 0.80


# ==========================================================
# Eficiencias iniciales
# ==========================================================
#
# Estos valores serán refinados posteriormente con datos reales.
#
# Por ahora se utilizan como hipótesis iniciales del modelo.

EFICIENCIA_CARGA_BATERIA = 0.95

EFICIENCIA_DESCARGA_BATERIA = 0.95

EFICIENCIA_CICLO_BATERIA = (
    EFICIENCIA_CARGA_BATERIA
    * EFICIENCIA_DESCARGA_BATERIA
)


# ==========================================================
# Política sostenible de operación
# ==========================================================
#
# A PARTIR DE AQUÍ LOS VALORES YA NO SON ESPECIFICACIONES
# ABSOLUTAS DEL FABRICANTE.
#
# Son decisiones de control conservadoras elegidas para estudiar
# cómo prolongar la vida útil del sistema de almacenamiento.


# ----------------------------------------------------------
# Ventana normal de SOC
# ----------------------------------------------------------

SOC_MIN_NORMAL = 0.20

SOC_MAX_NORMAL = 0.85


# ----------------------------------------------------------
# Ventana excepcional
# ----------------------------------------------------------
#
# Solo debería utilizarse cuando exista una razón operativa
# suficientemente importante.

SOC_MIN_EMERGENCIA = 0.10

SOC_MAX_EMERGENCIA = 0.95


# ==========================================================
# Energía utilizable dentro de la ventana sostenible
# ==========================================================

BATERIA_ENERGIA_UTIL_SOSTENIBLE_KWH = (
    BATERIA_ENERGIA_KWH_TOTAL
    * (
        SOC_MAX_NORMAL
        - SOC_MIN_NORMAL
    )
)


# ==========================================================
# Corrientes preferentes sostenibles
# ==========================================================
#
# Aunque el banco pueda admitir corrientes mayores, la política
# sostenible debería evitar trabajar permanentemente cerca
# de los máximos.
#
# Inicialmente se adopta como referencia la corriente recomendada
# por el fabricante.
#
# Más adelante podremos hacer que este valor dependa del SOC,
# temperatura y estrategia seleccionada.

CORRIENTE_CARGA_PREFERIDA_A = min(
    BATERIA_CORRIENTE_RECOMENDADA_A_TOTAL,
    INVERSOR_CORRIENTE_CARGA_MAX_A,
)

CORRIENTE_DESCARGA_PREFERIDA_A = min(
    BATERIA_CORRIENTE_RECOMENDADA_A_TOTAL,
    INVERSOR_CORRIENTE_DESCARGA_MAX_A,
)


# ==========================================================
# Potencia preferente aproximada de batería
# ==========================================================
#
# P = V * I
#
# Se calcula inicialmente utilizando la tensión nominal.
#
# Este valor es solo orientativo porque la tensión real de una
# batería varía durante la carga y descarga.

BATERIA_POTENCIA_CARGA_PREFERIDA_KW = (
    BATERIA_TENSION_NOMINAL_V
    * CORRIENTE_CARGA_PREFERIDA_A
    / 1000.0
)

BATERIA_POTENCIA_DESCARGA_PREFERIDA_KW = (
    BATERIA_TENSION_NOMINAL_V
    * CORRIENTE_DESCARGA_PREFERIDA_A
    / 1000.0
)


# ==========================================================
# Parámetros iniciales de degradación
# ==========================================================
#
# Estos valores NO constituyen todavía un modelo electroquímico.
#
# Son pesos iniciales que permitirán construir una función de
# coste de degradación.
#
# Posteriormente deberán calibrarse mediante bibliografía,
# datos del fabricante y, si es posible, datos experimentales.


# Penalización básica por energía procesada por batería.
PESO_ENERGIA_CICLADA = 1.0

# Penalización adicional asociada a ciclos profundos.
PESO_PROFUNDIDAD_CICLO = 2.0

# Penalización por trabajar cerca de extremos de SOC.
PESO_SOC_EXTREMOS = 2.0

# Penalización por potencias elevadas de carga o descarga.
PESO_POTENCIA_BATERIA = 1.0


# ==========================================================
# Zona preferente de SOC
# ==========================================================
#
# Dentro de esta ventana se considera inicialmente que la
# batería trabaja en una región especialmente favorable.
#
# No es un límite físico, sino una zona preferente para la
# estrategia sostenible.

SOC_ZONA_PREFERENTE_MIN = 0.30

SOC_ZONA_PREFERENTE_MAX = 0.80


# ==========================================================
# Criterio de arbitraje económico
# ==========================================================
#
# Para evitar utilizar la batería por diferencias de precio
# insignificantes, se exige un margen mínimo.
#
# Este margen es todavía provisional.

MARGEN_ECONOMICO_MINIMO_EUR_KWH = 0.02


# ==========================================================
# Prioridad de sostenibilidad
# ==========================================================

SOSTENIBILIDAD_PRIORITARIA = True


# ==========================================================
# Estrategia por defecto
# ==========================================================

ESTRATEGIA_DEFAULT = (
    "sostenible_predictiva"
)


# ==========================================================
# Horizonte de optimización
# ==========================================================
#
# Inicialmente trabajaremos con un horizonte de 24 horas.
#
# Posteriormente podremos ampliarlo a 48 h o varios días,
# especialmente cuando utilicemos la predicción de AEMET.

HORIZONTE_OPTIMIZACION_HORAS = 24


# ==========================================================
# Resolución temporal
# ==========================================================
#
# ESIOS y el modelo inicial trabajan a escala horaria.
#
# Posteriormente podremos migrar a intervalos de 15 minutos.

PASO_TEMPORAL_HORAS = 1.0


# ==========================================================
# Función auxiliar: descripción del sistema
# ==========================================================

def obtener_configuracion_sistema():
    """
    Devuelve los parámetros principales del sistema en forma
    de diccionario.

    Esta función concentra toda la descripción física y
    operativa de la instalación.

    De esta manera los demás módulos no necesitan importar
    individualmente decenas de constantes de config.py.

    Returns
    -------
    dict
        Configuración completa del sistema.
    """

    return {

        # --------------------------------------------------
        # Identificación
        # --------------------------------------------------

        "nombre": SISTEMA_NOMBRE,

        # --------------------------------------------------
        # Localización
        # --------------------------------------------------
        #
        # El municipio será utilizado tanto por AEMET como
        # por el futuro modelo solar basado en PVGIS.
        #
        # Latitud y longitud pueden ser None inicialmente.
        # solar.py podrá resolverlas automáticamente.

        "localizacion": {

            "municipio": (
                MUNICIPIO
            ),

            "provincia": (
                PROVINCIA
            ),

            "latitud": (
                LATITUD
            ),

            "longitud": (
                LONGITUD
            ),
        },

        # --------------------------------------------------
        # Campo fotovoltaico
        # --------------------------------------------------

        "fotovoltaica": {

            "numero_paneles": (
                NUM_PANELES
            ),

            "potencia_panel_w": (
                PANEL_POTENCIA_W
            ),

            "potencia_total_kwp": (
                POTENCIA_FV_KWP
            ),

            # Geometría de instalación.
            "inclinacion_grados": (
                PANEL_INCLINACION_GRADOS
            ),

            "azimut_grados": (
                PANEL_AZIMUT_GRADOS
            ),

            # Parámetros eléctricos del módulo.
            "vmp_v": (
                PANEL_VMP_V
            ),

            "voc_v": (
                PANEL_VOC_V
            ),

            "imp_a": (
                PANEL_IMP_A
            ),

            "isc_a": (
                PANEL_ISC_A
            ),

            # Coeficiente térmico de potencia.
            "coef_temp_pmax": (
                PANEL_COEF_TEMP_PMAX
            ),
        },

            "inversor": {
            "fabricante": INVERSOR_FABRICANTE,
            "modelo": INVERSOR_MODELO,
            "potencia_nominal_kw": (
                INVERSOR_POTENCIA_NOMINAL_KW
            ),
            "corriente_carga_max_a": (
                INVERSOR_CORRIENTE_CARGA_MAX_A
            ),
            "corriente_descarga_max_a": (
                INVERSOR_CORRIENTE_DESCARGA_MAX_A
            ),
        },

        "bateria": {
            "fabricante": BATERIA_FABRICANTE,
            "modelo": BATERIA_MODELO,
            "numero_unidades": NUM_BATERIAS,

            "tension_nominal_v": (
                BATERIA_TENSION_NOMINAL_V
            ),

            "capacidad_total_ah": (
                BATERIA_CAPACIDAD_AH_TOTAL
            ),

            "energia_total_kwh": (
                BATERIA_ENERGIA_KWH_TOTAL
            ),

            "energia_util_sostenible_kwh": (
                BATERIA_ENERGIA_UTIL_SOSTENIBLE_KWH
            ),

            "corriente_carga_preferida_a": (
                CORRIENTE_CARGA_PREFERIDA_A
            ),

            "corriente_descarga_preferida_a": (
                CORRIENTE_DESCARGA_PREFERIDA_A
            ),

            "potencia_carga_preferida_kw": (
                BATERIA_POTENCIA_CARGA_PREFERIDA_KW
            ),

            "potencia_descarga_preferida_kw": (
                BATERIA_POTENCIA_DESCARGA_PREFERIDA_KW
            ),

            "soc_min_normal": SOC_MIN_NORMAL,
            "soc_max_normal": SOC_MAX_NORMAL,

            "soc_min_emergencia": (
                SOC_MIN_EMERGENCIA
            ),

            "soc_max_emergencia": (
                SOC_MAX_EMERGENCIA
            ),

            "soc_preferente_min": (
                SOC_ZONA_PREFERENTE_MIN
            ),

            "soc_preferente_max": (
                SOC_ZONA_PREFERENTE_MAX
            ),

            "eficiencia_ciclo": (
                EFICIENCIA_CICLO_BATERIA
            ),

            "ciclos_referencia": (
                BATERIA_CICLOS_REFERENCIA
            ),

            "dod_referencia": (
                BATERIA_DOD_REFERENCIA
            ),
        },

        "sostenibilidad": {
            "prioritaria": (
                SOSTENIBILIDAD_PRIORITARIA
            ),

            "peso_energia_ciclada": (
                PESO_ENERGIA_CICLADA
            ),

            "peso_profundidad_ciclo": (
                PESO_PROFUNDIDAD_CICLO
            ),

            "peso_soc_extremos": (
                PESO_SOC_EXTREMOS
            ),

            "peso_potencia_bateria": (
                PESO_POTENCIA_BATERIA
            ),
        },

        "optimizacion": {
            "estrategia_default": (
                ESTRATEGIA_DEFAULT
            ),

            "horizonte_horas": (
                HORIZONTE_OPTIMIZACION_HORAS
            ),

            "paso_temporal_horas": (
                PASO_TEMPORAL_HORAS
            ),

            "margen_economico_minimo": (
                MARGEN_ECONOMICO_MINIMO_EUR_KWH
            ),
        },
    }
