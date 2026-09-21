# Gestión Solar Predictiva --- Android app

## Objetivo

La rama `android-app` convierte el motor Python existente en una
aplicación móvil sencilla para gestión energética doméstica. La
aplicación debe responder, de forma comprensible, a una pregunta
práctica:

> Con la meteorología, los precios, la instalación fotovoltaica, la
> batería y las necesidades de la vivienda, ¿qué conviene hacer hoy y
> durante los próximos días?

El valor principal ya está en el modelo de decisión. Android debe
proporcionar una experiencia móvil simple, segura, explicable y
mantenible.

## Principio de desarrollo

**No reescribir la lógica energética en la interfaz Android.**

La aplicación debe consumir el motor Python mediante una capa de
adaptación estable. La separación conceptual es:

`UI Android → estado/ViewModel → adaptador Android↔Python → motor Python → fuentes externas`

Esto permitirá seguir desarrollando los algoritmos Python sin tener que
rediseñar la interfaz.

## Rama de trabajo

-   Repositorio: `Gestion-Solar-AEMET-ESIOS`
-   Rama móvil: `android-app`
-   La rama `main` contiene el motor estable.
-   La integración posterior debe realizarse mediante Pull Request y
    revisión.

## Tecnologías previstas

-   Kotlin
-   Android Studio
-   Jetpack Compose
-   ViewModel
-   Coroutines para red/cálculo
-   Integración Python--Android para el MVP
-   Almacenamiento seguro de credenciales

## Fuera del alcance inicial

La primera versión **recomienda**, pero no envía órdenes al inversor ni
automatiza hardware. Home Assistant, automatización del inversor y
gráficos avanzados pueden abordarse después.

## Criterio esencial

Tocar lo mínimo posible el núcleo Python. El trabajo Android debe
concentrarse en:

1.  interfaz;
2.  configuración;
3.  almacenamiento seguro;
4.  adaptador Android--Python;
5.  presentación y explicación de resultados;
6.  robustez y tests.
