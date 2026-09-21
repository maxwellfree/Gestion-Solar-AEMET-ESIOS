# Gestión Solar Predictiva --- Android

Aplicación Android para **Gestion-Solar-AEMET-ESIOS**, construida sobre
el motor Python existente del proyecto.

La finalidad de esta rama es desarrollar una interfaz Android que
permita configurar la instalación energética del usuario, gestionar las
credenciales necesarias, ejecutar el modelo predictivo existente y
presentar sus recomendaciones de forma clara y visual.

> **Principio clave:** la aplicación Android configura, llama al motor
> Python existente y muestra sus resultados. El objetivo no es
> reprogramar en Kotlin el modelo energético.

------------------------------------------------------------------------

## Arquitectura general

La arquitectura prevista separa claramente la interfaz móvil, el motor
de cálculo y las fuentes externas de datos:

``` text
Aplicación Android
Kotlin + Jetpack Compose
        │
        │ configuración / credenciales / SOC
        ▼
Adaptador Android ↔ Python
        │
        ▼
Motor Python existente
        │
        ├── AEMET OpenData
        ├── PVGIS
        └── ESIOS / Red Eléctrica
        │
        ▼
Resultados estructurados
        │
        ▼
Android: recomendaciones, planificación y gráficos
```

El motor Python conserva la responsabilidad sobre la meteorología,
producción fotovoltaica, precios, demanda, balance energético, batería,
optimización y planificación.

------------------------------------------------------------------------

## Documentación

La documentación del desarrollo Android se divide en los siguientes
documentos:

### [1. Arquitectura](docs/ARCHITECTURE.md)

Describe la separación entre Android y Python, los módulos existentes y
la capa de adaptación que debe permitir a Android ejecutar el motor sin
depender de la salida de consola.

### [2. Configuración y credenciales](docs/CONFIGURATION_AND_CREDENTIALS.md)

Define el proceso de primera configuración:

-   API Key de AEMET;
-   token de ESIOS;
-   ubicación;
-   instalación fotovoltaica;
-   inversor;
-   batería;
-   vivienda;
-   cargas;
-   estrategia de gestión.

También establece los requisitos para el almacenamiento seguro de
credenciales.

### [3. Fuentes de datos](docs/DATA_SOURCES.md)

Describe las fuentes externas utilizadas por el proyecto:

-   **AEMET OpenData** --- previsión meteorológica;
-   **PVGIS** --- radiación y producción fotovoltaica;
-   **ESIOS / Red Eléctrica** --- precios y datos del sistema eléctrico;
-   caché local para evitar consultas innecesarias.

### [4. Interfaz y MVP](docs/UI_MVP.md)

Define las pantallas y la experiencia de usuario de la primera versión
Android:

-   bienvenida;
-   credenciales;
-   configuración;
-   plan para hoy;
-   planificación semanal;
-   detalle y explicación de decisiones;
-   energía;
-   ajustes;
-   estado de los datos.

La aplicación debe mostrar primero **qué conviene hacer** y después los
datos que justifican la recomendación.

### [5. Plan de desarrollo](docs/DEVELOPMENT_PLAN.md)

Organiza el trabajo en fases:

1.  integración Android--Python;
2.  onboarding y configuración;
3.  recomendaciones para hoy;
4.  planificación semanal;
5.  robustez, caché, errores y tests;
6.  generación y distribución del APK/AAB.

------------------------------------------------------------------------

## Motor Python existente

La intención es reutilizar los módulos existentes con las mínimas
modificaciones necesarias.

### Acceso a datos

``` text
aemet.py
aemet_hourly.py
solar.py
esios.py
cache.py
```

### Cálculo y optimización

``` text
balance.py
dispatch.py
optimizer.py
weekly.py
```

Estos módulos no deben duplicarse en Kotlin salvo que exista una razón
técnica documentada.

------------------------------------------------------------------------

## Adaptador Android--Python

Android no debe interpretar texto generado por `main.py`.

Debe existir una interfaz reutilizable que reciba la configuración y el
estado actual y devuelva resultados estructurados. Conceptualmente:

``` python
run_plan(config, soc, refresh=False)
```

La respuesta deberá proporcionar datos estructurados para que Android
pueda construir independientemente la presentación:

``` text
status
warnings
forecast
demand
energy
today_actions
weekly_plan
updated_at
cache_status
```

------------------------------------------------------------------------

## Filosofía de la interfaz

El usuario no debería necesitar interpretar gráficas complejas para
decidir cuándo utilizar una carga.

La aplicación debe poder producir recomendaciones del tipo:

``` text
Lavadora
Domingo · 12:00–15:00

Recomendación:
Esperar hasta el domingo.

Motivo:
Se prevé un excedente fotovoltaico mayor y la carga es flexible.
```

Debe distinguirse siempre entre:

-   **datos observados**;
-   **predicciones**;
-   **recomendaciones**.

Una recomendación no constituye una orden enviada al inversor.

------------------------------------------------------------------------

## Alcance de la primera versión

El MVP debe permitir:

-   instalar la aplicación sin editar código;
-   introducir y validar las credenciales AEMET y ESIOS;
-   configurar la instalación FV, batería y vivienda;
-   definir las cargas;
-   ejecutar el motor Python;
-   consultar las recomendaciones del día;
-   consultar la planificación semanal;
-   comprender por qué se recomienda cada acción;
-   actualizar los datos manualmente;
-   trabajar con caché cuando sea apropiado.

La primera versión será un **sistema de recomendación**. El control
automático del inversor o de dispositivos domésticos queda fuera del
alcance inicial.

------------------------------------------------------------------------

## Rama de desarrollo

El desarrollo Android se realiza en:

``` text
android-app
```

La rama `main` contiene la versión principal del proyecto y está
protegida.

Los cambios que eventualmente deban incorporarse a `main` se realizarán
mediante **Pull Request** y revisión.

------------------------------------------------------------------------

## Seguridad

Nunca deben incorporarse al repositorio:

-   API Keys reales;
-   tokens ESIOS;
-   credenciales personales;
-   archivos de configuración que contengan secretos.

Las credenciales utilizadas por la aplicación deberán almacenarse de
forma segura en el dispositivo y no aparecer en logs, informes ni
archivos exportados.

------------------------------------------------------------------------

## Distribución

La primera versión no necesita publicarse en Google Play.

El objetivo inicial es generar un **APK instalable directamente en
Android**, manteniendo también una compilación reproducible y
documentada.

------------------------------------------------------------------------

## Estado del proyecto

**Fase actual:** preparación de la arquitectura y documentación para
iniciar el desarrollo Android.

El siguiente objetivo técnico es conseguir que una aplicación Android
mínima pueda llamar al motor Python con datos de prueba y recibir un
resultado estructurado.

------------------------------------------------------------------------

## Índice rápido

  ---------------------------------------------------------------------------------------------------------------
  Documento                                                                   Contenido
  --------------------------------------------------------------------------- -----------------------------------
  [ARCHITECTURE.md](docs/ARCHITECTURE.md)                                     Arquitectura Android--Python

  [CONFIGURATION_AND_CREDENTIALS.md](docs/CONFIGURATION_AND_CREDENTIALS.md)   Configuración y seguridad

  [DATA_SOURCES.md](docs/DATA_SOURCES.md)                                     AEMET, PVGIS, ESIOS y caché

  [UI_MVP.md](docs/UI_MVP.md)                                                 Pantallas y experiencia de usuario

  [DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)                             Fases y entregables
  ---------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

**Gestión Solar Predictiva --- Android app**\
Septiembre de 2026
