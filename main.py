#!/usr/bin/env python3
"""
main.py

Programa principal del sistema de gestión energética solar.

Este archivo coordina los distintos módulos del proyecto:

    aemet.py
        Obtiene y procesa la predicción meteorológica.

    esios.py
        Obtiene los precios eléctricos horarios.

    config.py
        Define las características físicas y operativas
        de la instalación.

    demand.py
        Define la demanda doméstica, presencia, flexibilidad
        y genera el perfil horario teórico de 24 horas.

    optimizer.py
        Ejecuta la estrategia de gestión seleccionada.

----------------------------------------------------------------
FILOSOFÍA
----------------------------------------------------------------

main.py no contiene lógica de optimización.

Su responsabilidad es únicamente:

    1. Leer los parámetros introducidos por el usuario.
    2. Determinar la fecha de trabajo.
    3. Cargar la configuración física del sistema.
    4. Construir el perfil horario de demanda.
    5. Obtener la previsión meteorológica, utilizando caché cuando proceda.
    6. Obtener los precios eléctricos, utilizando caché cuando proceda.
    7. Incorporar el estado actual de la batería.
    8. Ejecutar la estrategia seleccionada.
    9. Mostrar los resultados.

Esto permite mantener separados:

    datos
        ↓
    modelo físico
        ↓
    modelo de demanda
        ↓
    optimización
        ↓
    presentación

Autor: Enrique M. Moreno Pérez
"""


# ==========================================================
# Importaciones
# ==========================================================

import argparse
import sys

from datetime import datetime

import requests


from aemet import (
    obtener_prevision_solar,
)


from esios import (
    obtener_precios,
    mostrar_tabla,
    mostrar_resumen,
)


from config import (
    obtener_configuracion_sistema,
    ESTRATEGIA_DEFAULT,
)


from optimizer import (
    optimizar,
    ESTRATEGIAS_DISPONIBLES,
)


from demand import (
    obtener_configuracion_demanda,
    mostrar_perfil_demanda,
)

from aemet_hourly import (
    obtener_prevision_horaria,
)

from solar import (
    obtener_perfil_fv_24h,
    mostrar_perfil_fv,
    energia_fv_diaria,
    obtener_pico_fv,
)

from balance import (
    calcular_balance_horario,
    calcular_metricas_balance,
    mostrar_balance,
    mostrar_resumen_balance,
)

from dispatch import (
    generar_plan_sostenible_predictivo,
    calcular_metricas_plan,
    mostrar_plan_horario,
    mostrar_resumen_plan,
)

from weekly import (
    generar_plan_semanal,
    mostrar_plan_semanal,
)

# ==========================================================
# Obtención de la previsión del día actual
# ==========================================================

def seleccionar_prevision_hoy(
    prevision: list,
):
    """
    Selecciona de la predicción AEMET el registro
    correspondiente al día actual.

    Parameters
    ----------
    prevision : list
        Lista de predicciones procesadas por aemet.py.

    Returns
    -------
    dict
        Predicción correspondiente al día actual.

    Raises
    ------
    RuntimeError
        Si AEMET no proporciona predicción para hoy.
    """

    hoy = datetime.now().date()

    for dia in prevision:

        if dia["fecha"] == hoy:
            return dia

    raise RuntimeError(
        "No se encontró predicción meteorológica "
        "para el día actual."
    )


# ==========================================================
# Estado actual del sistema
# ==========================================================

def construir_estado_sistema(
    configuracion,
    soc,
):
    """
    Construye el diccionario que describe el estado actual
    de la instalación.

    En esta primera versión, el único estado dinámico
    proporcionado externamente es el SOC de la batería.

    Posteriormente se podrán añadir:

        - potencia FV instantánea;
        - consumo instantáneo;
        - temperatura de batería;
        - potencia de red;
        - energía diaria acumulada;
        - estado del inversor;
        - datos directos del BMS.

    Parameters
    ----------
    configuracion : dict
        Configuración física devuelta por config.py.

    soc : float
        Estado de carga de la batería entre 0 y 1.

    Returns
    -------
    dict
        Estado del sistema que recibirá optimizer.py.
    """

    return {
        "soc": soc,
        "configuracion": configuracion,
    }


# ==========================================================
# Presentación de la instalación
# ==========================================================

def mostrar_configuracion(
    configuracion,
):
    """
    Muestra un resumen de la instalación utilizada
    por el optimizador.
    """

    fv = configuracion[
        "fotovoltaica"
    ]

    inversor = configuracion[
        "inversor"
    ]

    bateria = configuracion[
        "bateria"
    ]

    print()
    print("Sistema fotovoltaico")
    print("--------------------")

    print(
        f"Nombre                : "
        f"{configuracion['nombre']}"
    )

    print(
        f"Paneles               : "
        f"{fv['numero_paneles']}"
    )

    print(
        f"Potencia FV instalada : "
        f"{fv['potencia_total_kwp']:.2f} kWp"
    )

    print(
        f"Inversor              : "
        f"{inversor['fabricante']} "
        f"{inversor['modelo']}"
    )

    print(
        f"Potencia inversor     : "
        f"{inversor['potencia_nominal_kw']:.2f} kW"
    )

    print(
        f"Baterías              : "
        f"{bateria['numero_unidades']} × "
        f"{bateria['modelo']}"
    )

    print(
        f"Energía nominal       : "
        f"{bateria['energia_total_kwh']:.2f} kWh"
    )

    print(
        f"Ventana sostenible    : "
        f"{bateria['energia_util_sostenible_kwh']:.3f} kWh"
    )

    print(
        f"SOC normal            : "
        f"{bateria['soc_min_normal'] * 100:.0f}"
        f"–"
        f"{bateria['soc_max_normal'] * 100:.0f} %"
    )


# ==========================================================
# Presentación de la demanda
# ==========================================================

def mostrar_demanda(
    demanda,
):
    """
    Muestra un resumen del modelo doméstico utilizado
    por el optimizador.

    Se presentan:

    - número de ocupantes;
    - número total de cargas;
    - cargas flexibles;
    - cargas automatizables;
    - cargas que requieren presencia;
    - potencia base estimada;
    - energía diaria teórica;
    - política de preservación de batería.
    """

    ocupantes = demanda[
        "ocupantes"
    ]

    cargas = demanda[
        "cargas"
    ]

    numero_flexibles = sum(
        1
        for carga in cargas
        if carga.get(
            "flexible",
            False,
        )
    )

    numero_automaticas = sum(
        1
        for carga in cargas
        if carga.get(
            "automatizable",
            False,
        )
    )

    numero_presencia = sum(
        1
        for carga in cargas
        if carga.get(
            "requiere_presencia",
            False,
        )
    )

    print()
    print("Modelo de demanda")
    print("-----------------")

    print(
        f"Ocupantes              : "
        f"{ocupantes['total']} "
        f"({ocupantes['adultos']} adultos, "
        f"{ocupantes['ninos']} niños)"
    )

    print(
        f"Cargas modeladas       : "
        f"{len(cargas)}"
    )

    print(
        f"Cargas flexibles       : "
        f"{numero_flexibles}"
    )

    print(
        f"Cargas automatizables  : "
        f"{numero_automaticas}"
    )

    print(
        f"Requieren presencia    : "
        f"{numero_presencia}"
    )

    print(
        f"Potencia base estimada : "
        f"{demanda['potencia_base_kw']:.3f} kW"
    )

    energia_diaria = demanda.get(
        "energia_diaria_teorica_kwh"
    )

    if energia_diaria is not None:

        print(
            f"Demanda diaria teórica : "
            f"{energia_diaria:.2f} kWh"
        )

    if demanda.get(
        "prioridad_red_sobre_bateria",
        False,
    ):

        print(
            "Política de batería    : "
            "priorizar red frente a ciclos marginales"
        )


# ==========================================================
# Presentación meteorológica
# ==========================================================

def mostrar_prevision(
    prevision,
    municipio,
):
    """
    Muestra de forma compacta la predicción meteorológica
    utilizada por el optimizador.
    """

    fecha = prevision[
        "fecha"
    ].strftime(
        "%d/%m/%Y"
    )

    print()
    print("Previsión meteorológica")
    print("-----------------------")

    print(
        f"Municipio             : "
        f"{municipio}"
    )

    print(
        f"Fecha                 : "
        f"{fecha}"
    )

    print(
        f"Índice solar          : "
        f"{prevision['score']:.3f}"
    )

    print(
        f"Índice de cielo       : "
        f"{prevision['cielo_score']:.3f}"
    )

    print(
        f"Precipitación media   : "
        f"{prevision['precip']:.1f} %"
    )

    print(
        f"Temperatura máxima    : "
        f"{prevision['tmax']} °C"
    )

    print(
        f"Penalización térmica  : "
        f"{prevision['penalizacion_temperatura']:.3f}"
    )

# ==========================================================
# Presentación de generación fotovoltaica
# ==========================================================

def mostrar_generacion_fv(
    energia_fv,
    pico_fv,
):
    """
    Muestra un resumen de la producción fotovoltaica prevista.
    """

    print()
    print("Generación fotovoltaica prevista")
    print("--------------------------------")

    print(
        f"Energía FV diaria      : "
        f"{energia_fv:.2f} kWh"
    )

    if pico_fv:

        print(
            f"Pico FV previsto       : "
            f"{pico_fv['hora']} — "
            f"{pico_fv['potencia_fv_kw']:.2f} kW"
        )

# ==========================================================
# Presentación del plan de optimización
# ==========================================================

def mostrar_plan(
    plan,
):
    """
    Presenta el resultado devuelto por optimizer.py.

    La salida incluye:

        - estrategia;
        - acciones;
        - razones;
        - sostenibilidad;
        - interpretación meteorológica;
        - información económica;
        - demanda prevista;
        - métricas.
    """

    print()
    print("Plan de gestión")
    print("---------------")

    print(
        f"Estrategia seleccionada : "
        f"{plan['estrategia']}"
    )

    # ------------------------------------------------------
    # Acciones
    # ------------------------------------------------------

    acciones = plan.get(
        "acciones",
        [],
    )

    if acciones:

        print()
        print("Acciones recomendadas:")

        for accion in acciones:

            print(
                f"  - {accion}"
            )

    # ------------------------------------------------------
    # Justificación
    # ------------------------------------------------------

    razones = plan.get(
        "razones",
        [],
    )

    if razones:

        print()
        print("Justificación:")

        for razon in razones:

            print(
                f"  - {razon}"
            )

    # ------------------------------------------------------
    # Sostenibilidad
    # ------------------------------------------------------

    sostenibilidad = plan.get(
        "sostenibilidad",
        {},
    )

    if sostenibilidad:

        print()
        print("Estado de sostenibilidad:")

        soc = sostenibilidad.get(
            "soc"
        )

        if soc is not None:

            print(
                f"  SOC actual: "
                f"{soc * 100:.1f} %"
            )

    # ------------------------------------------------------
    # Meteorología procesada
    # ------------------------------------------------------

    meteorologia = plan.get(
        "meteorologia",
        {},
    )

    if meteorologia:

        print()
        print("Interpretación meteorológica:")

        calidad = meteorologia.get(
            "calidad_solar"
        )

        indice = meteorologia.get(
            "indice_solar"
        )

        if calidad is not None:

            print(
                f"  Calidad solar: "
                f"{calidad}"
            )

        if indice is not None:

            print(
                f"  Índice solar: "
                f"{indice:.3f}"
            )

    # ------------------------------------------------------
    # Información económica
    # ------------------------------------------------------

    economia = plan.get(
        "economia",
        {},
    )

    if economia:

        print()
        print("Información económica:")

        compra_minima = economia.get(
            "hora_compra_minima"
        )

        compra_maxima = economia.get(
            "hora_compra_maxima"
        )

        venta_maxima = economia.get(
            "hora_venta_maxima"
        )

        if compra_minima:

            print(
                f"  Compra mínima : "
                f"{compra_minima['hora']} — "
                f"{compra_minima['compra']:.5f} €/kWh"
            )

        if compra_maxima:

            print(
                f"  Compra máxima : "
                f"{compra_maxima['hora']} — "
                f"{compra_maxima['compra']:.5f} €/kWh"
            )

        if venta_maxima:

            print(
                f"  Venta máxima  : "
                f"{venta_maxima['hora']} — "
                f"{venta_maxima['venta']:.5f} €/kWh"
            )

    # ------------------------------------------------------
    # Demanda prevista
    # ------------------------------------------------------

    demanda_plan = plan.get(
        "demanda",
        {},
    )

    if demanda_plan:

        energia_diaria = demanda_plan.get(
            "energia_diaria_teorica_kwh"
        )

        hora_pico = demanda_plan.get(
            "hora_pico_demanda"
        )

        if (
            energia_diaria is not None
            or hora_pico is not None
        ):

            print()
            print("Demanda prevista:")

        if energia_diaria is not None:

            print(
                f"  Energía diaria : "
                f"{energia_diaria:.2f} kWh"
            )

        if hora_pico is not None:

            print(
                f"  Pico teórico   : "
                f"{hora_pico['hora']} — "
                f"{hora_pico['potencia_total_kw']:.2f} kW"
            )

    # ------------------------------------------------------
    # Métricas
    # ------------------------------------------------------

    metricas = plan.get(
        "metricas",
        {},
    )

    if metricas:

        print()
        print("Métricas:")

        hay_metricas = False

        for nombre, valor in metricas.items():

            if valor is None:
                continue

            hay_metricas = True

            print(
                f"  {nombre}: {valor}"
            )

        if not hay_metricas:

            print(
                "  Todavía no disponibles. "
                "Falta incorporar el balance horario "
                "de generación, red y batería."
            )


# ==========================================================
# Programa principal
# ==========================================================

def main():
    """
    Función principal del programa.

    Coordina la lectura de la configuración, la predicción
    meteorológica, los precios eléctricos, el modelo de demanda
    y el optimizador energético.
    """

    # ======================================================
    # Argumentos de línea de comandos
    # ======================================================

    parser = argparse.ArgumentParser(
        description=(
            "Sistema de gestión energética residencial "
            "con criterios económicos y de sostenibilidad."
        )
    )

    parser.add_argument(
        "--soc",
        type=float,
        default=0.60,
        help=(
            "Estado de carga inicial de la batería "
            "expresado entre 0 y 1. "
            "Ejemplo: --soc 0.60"
        ),
    )

    parser.add_argument(
        "--estrategia",
        type=str,
        default="sostenible_predictiva",
        help=(
            "Estrategia de gestión energética. "
            "Por defecto: sostenible_predictiva."
        ),
    )

    parser.add_argument(
        "--mostrar-precios",
        action="store_true",
        help="Muestra la tabla horaria de precios eléctricos.",
    )

    parser.add_argument(
        "--mostrar-demanda",
        action="store_true",
        help="Muestra el perfil horario teórico de demanda.",
    )

    parser.add_argument(
        "--mostrar-solar",
        action="store_true",
        help=(
        "Muestra el perfil horario físico-predictivo "
        "de generación fotovoltaica."
        ),
    ) 

    parser.add_argument(
        "--mostrar-balance",
        action="store_true",
        help=(
            "Muestra el balance horario entre "
            "FV, demanda y precios."
        ),
    )

    parser.add_argument(
        "--mostrar-plan-horario",
        action="store_true",
        help=(
            "Muestra las decisiones energéticas "
            "hora a hora."
        ),
    )

    parser.add_argument(
        "--mostrar-semanal",
        action="store_true",
        help=(
            "Muestra el plan semanal sostenible "
            "de servicios domésticos."
        ),
    )


    parser.add_argument(
        "--refresh",
        action="store_true",
        help=(
            "Ignora la caché local y fuerza una nueva descarga "
            "de los datos externos (AEMET y ESIOS)."
        ),
    )

    args = parser.parse_args()

    try:
        # ==================================================
        # 1. Configuración física de la instalación
        # ==================================================

        configuracion = obtener_configuracion_sistema()

        # ==================================================
        # 2. Localización
        # ==================================================
        #
        # El municipio ya no se solicita por línea de
        # comandos. Forma parte de la configuración
        # permanente de la instalación.

        municipio = configuracion[
            "localizacion"
        ][
            "municipio"
        ]

        # ==================================================
        # 3. Estado inicial de la batería
        # ==================================================

        sistema = {
            "soc": args.soc,
        }


        # ==================================================
        # 4. Fecha de trabajo
        # ==================================================

        hoy = datetime.now().date()

        # ==================================================
        # 5. Configuración de demanda
        # ==================================================
        #
        # Al proporcionar la fecha, demand.py genera también
        # el perfil horario teórico de 24 horas.

        demanda = (
            obtener_configuracion_demanda(
                fecha=hoy
            )
        )

        # ==================================================
        # 6. Predicción AEMET
        # ==================================================

        prevision_completa = (
            obtener_prevision_solar(
                municipio,
                refresh=args.refresh,
            )
        )

        prevision_hoy = (
            seleccionar_prevision_hoy(
                prevision_completa
            )
        )

        # ==================================================
        # 7. Predicción meteorológica horaria AEMET
        # ==================================================

        prevision_horaria = obtener_prevision_horaria(
            municipio,
            refresh=args.refresh,
        )

        # ==================================================
        # 8. Precios ESIOS
        # ==================================================

        precios = obtener_precios(
            hoy,
            refresh=args.refresh,
        )

        # ==================================================
        # Planificación semanal de servicios
        # ==================================================
        #
        # weekly.py utiliza la predicción AEMET de varios días
        # y la configuración doméstica para responder a:
        #
        #     ¿cuándo conviene prestar cada servicio?
        #
        # Esta planificación todavía no modifica directamente
        # el perfil horario utilizado por dispatch.py.
        #
        # De momento constituye una capa de planificación
        # superior que posteriormente alimentará demand.py.

        plan_semanal = generar_plan_semanal(
            demanda=demanda,
            prevision_semanal=prevision_completa,
            prevision_horaria=prevision_horaria,
        )

        # ==================================================
        # 9. Producción fotovoltaica prevista
        # ==================================================

        perfil_fv = obtener_perfil_fv_24h(
            fecha=hoy,
            configuracion=configuracion,
            prevision_horaria=prevision_horaria,
            prevision_diaria=prevision_hoy,
        )
        
        energia_fv = energia_fv_diaria(
            perfil_fv
        )

        pico_fv = obtener_pico_fv(
            perfil_fv
        ) 


        # ==================================================
        # 10. Estado físico actual
        # ==================================================

        sistema = construir_estado_sistema(
            configuracion,
            args.soc,
        )
        sistema[
            "perfil_fv_24h"
        ] = perfil_fv

        sistema[
            "energia_fv_diaria_kwh"
        ] = energia_fv

        sistema[
            "pico_fv"
        ] = pico_fv

        # ==================================================
        # 11. Balance FV - demanda - precios
        # ==================================================

        perfil_demanda = demanda[
            "perfil_24h"
        ]

        balance = calcular_balance_horario(
            perfil_demanda=perfil_demanda,
            perfil_fv=perfil_fv,
            precios=precios,
        )

        metricas_balance = calcular_metricas_balance(
            balance
        )

        # Incorporamos también el balance al estado físico.
        # optimizer.py podrá utilizarlo en el siguiente paso.

        sistema[
            "balance_24h"
        ] = balance

        sistema[
            "metricas_balance"
        ] = metricas_balance

        # ==================================================
        # 12. Despacho sostenible predictivo
        # ==================================================

        plan_horario = (
            generar_plan_sostenible_predictivo(
                balance=balance,
                configuracion=configuracion,
                soc_inicial=args.soc,
            )
        )

        metricas_plan = (
            calcular_metricas_plan(
                plan_horario,
                configuracion,
            )
        )

        sistema[
            "plan_horario"
        ] = plan_horario

        sistema[
            "metricas_plan"
        ] = metricas_plan

        # ==================================================
        # 13. Optimización
        # ==================================================

        plan = optimizar(
            sistema=sistema,
            prevision=prevision_hoy,
            precios=precios,
            demanda=demanda,
            estrategia=args.estrategia,
        )

        # ==================================================
        # 13. Presentación
        # ==================================================

        print()
        print("=" * 70)
        print("GESTIÓN SOLAR PREDICTIVA")
        print("=" * 70)

        mostrar_configuracion(
            configuracion
        )

        mostrar_demanda(
            demanda
        )

        # --------------------------------------------------
        # Perfil horario de demanda
        # --------------------------------------------------

        if args.mostrar_demanda:

            perfil_24h = demanda.get(
                "perfil_24h"
            )

            if perfil_24h:

                mostrar_perfil_demanda(
                    perfil_24h
                )

        # ==================================================
        # Plan semanal
        # ==================================================

        if args.mostrar_semanal:

            mostrar_plan_semanal(
                plan_semanal
            )

        # --------------------------------------------------
        # Meteorología
        # --------------------------------------------------

        mostrar_prevision(
            prevision_hoy,
            municipio,
        )

        # --------------------------------------------------
        # Generación fotovoltaica
        # --------------------------------------------------

        mostrar_generacion_fv(
            energia_fv,
            pico_fv,
        )

        # --------------------------------------------------
        # Perfil FV completo solo si el usuario lo solicita.
        # --------------------------------------------------

        if args.mostrar_solar:

            mostrar_perfil_fv(
                perfil_fv
            )

        # --------------------------------------------------
        # Precios
        # --------------------------------------------------

        if args.mostrar_precios:

            mostrar_tabla(
                precios
            )

            mostrar_resumen(
                precios
            )


        # --------------------------------------------------
        # Resumen del balance energético
        # --------------------------------------------------

        mostrar_resumen_balance(
            metricas_balance
        )

        # Tabla horaria completa solo si se solicita.

        if args.mostrar_balance:

            mostrar_balance(
                balance
            )


        # ==================================================
        # Resumen del despacho horario
        # ==================================================

        mostrar_resumen_plan(
            metricas_plan
        )

        # --------------------------------------------------
        # Plan horario detallado
        # --------------------------------------------------
        #
        # Solo se muestra si el usuario utiliza:
        #
        #     --mostrar-plan-horario
        #
        # De esta forma evitamos imprimir siempre
        # una tabla de 24 filas.

        if args.mostrar_plan_horario:

            mostrar_plan_horario(
                plan_horario
            )

        # ==================================================
        # Plan estratégico general
        # ==================================================
        #
        # Este es el resultado generado por optimizer.py.
        #
        # No debe confundirse con plan_horario:
        #
        #     plan_horario -> decisiones hora a hora
        #     plan         -> recomendaciones estratégicas
        #

        mostrar_plan(
            plan
        )

        print()
        print("=" * 70)

    # ======================================================
    # Errores de conexión
    # ======================================================

    except requests.exceptions.Timeout:

        print(
            "Error: alguna consulta ha excedido "
            "el tiempo máximo de espera.",
            file=sys.stderr,
        )

        sys.exit(1)

    except requests.exceptions.HTTPError as error:

        print(
            f"Error HTTP al consultar las APIs: "
            f"{error}",
            file=sys.stderr,
        )

        sys.exit(1)

    except requests.exceptions.RequestException as error:

        print(
            f"Error de conexión con las APIs: "
            f"{error}",
            file=sys.stderr,
        )

        sys.exit(1)

    # ======================================================
    # Errores de procesamiento
    # ======================================================

    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        TypeError,
        RuntimeError,
    ) as error:

        print(
            f"Error al procesar los datos: "
            f"{error}",
            file=sys.stderr,
        )

        sys.exit(1)


# ==========================================================
# Punto de entrada
# ==========================================================

if __name__ == "__main__":
    main()
