# Plan de desarrollo --- rama `android-app`

## Objetivo

Construir la aplicación Android alrededor del motor Python existente con
la mínima modificación posible del núcleo energético.

## Fase 1 --- Integración

**Entregable:** Android ejecuta el motor con datos de prueba.

**Criterio de salida:** resultado estructurado y reproducible.

Tareas:

-   crear proyecto Android Studio;
-   establecer navegación inicial;
-   crear pantallas vacías;
-   definir ViewModels/estado;
-   decidir e implementar la integración Python--Android del MVP;
-   crear el adaptador estructurado;
-   evitar cualquier parseo de la salida textual de `main.py`.

## Fase 2 --- Onboarding y configuración

**Entregable:** credenciales + configuración completa.

**Criterio de salida:** instalación configurable sin editar archivos
manualmente.

Tareas:

-   AEMET;
-   ESIOS;
-   ubicación;
-   FV;
-   inversor;
-   batería;
-   vivienda;
-   cargas;
-   estrategia;
-   generación/adaptación de la configuración esperada por Python.

## Fase 3 --- Hoy

**Entregable:** lista horaria de recomendaciones.

**Criterio de salida:** cada acción incluye un motivo comprensible.

## Fase 4 --- Semana

**Entregable:** plan de cargas flexibles.

**Criterio de salida:** puede recomendar hoy o días futuros y justificar
la elección.

## Fase 5 --- Robustez

**Entregable:** caché, tratamiento de errores y tests.

**Criterio de salida:** no pierde configuración y no expone secretos.

Incluir:

-   caché;
-   `refresh`;
-   errores de red;
-   credenciales seguras;
-   tests de integración;
-   tests de interfaz mínimos.

## Fase 6 --- Distribución

**Entregable:** APK/AAB documentado.

**Criterio de salida:** compilación reproducible y versión
identificable.

La primera distribución puede realizarse como APK instalable
directamente, sin publicación inicial en Google Play.

## Qué debe tocar `android-app`

-   proyecto Android Studio;
-   Kotlin/Jetpack Compose;
-   capa adaptadora Android--Python;
-   persistencia móvil;
-   almacenamiento seguro;
-   tests de UI e integración;
-   documentación de compilación e instalación.

## Qué debe evitar

-   duplicar algoritmos físicos;
-   alterar el núcleo energético sin necesidad;
-   subir claves reales;
-   acoplar pantallas a texto de terminal;
-   mezclar acceso a APIs con componentes visuales;
-   introducir control de hardware antes de validar el modo
    recomendación.

## Definición de «hecho» para la primera versión

La versión inicial estará lista cuando:

-   un usuario nuevo pueda instalarla sin editar código;
-   pueda introducir y validar credenciales desde la UI;
-   pueda configurar instalación y cargas;
-   la aplicación obtenga datos y calcule el plan;
-   muestre recomendaciones diarias y semanales;
-   explique las recomendaciones;
-   las credenciales permanezcan privadas;
-   la caché evite consultas repetidas;
-   los errores de red sean comprensibles;
-   Python y UI permanezcan desacoplados;
-   existan tests mínimos;
-   exista documentación de compilación;
-   no se envíen órdenes al inversor.
