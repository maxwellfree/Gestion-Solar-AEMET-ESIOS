# Interfaz y MVP Android

## Principio de experiencia de usuario

La aplicación no debe ser principalmente un dashboard técnico. Debe
presentar primero **acciones concretas**, y después los datos que las
justifican.

Cada recomendación debe explicar su motivo.

La interfaz debe distinguir claramente:

-   dato observado;
-   predicción;
-   recomendación.

Una recomendación no es una orden al hardware.

## Pantallas mínimas

1.  **Bienvenida**
    -   explicación breve del proyecto.
2.  **Credenciales**
    -   AEMET;
    -   ESIOS;
    -   validación y almacenamiento seguro.
3.  **Configuración**
    -   ubicación;
    -   instalación FV;
    -   inversor;
    -   batería;
    -   vivienda;
    -   cargas;
    -   estrategia.
4.  **Hoy**
    -   acciones recomendadas ordenadas por hora;
    -   producción prevista;
    -   SOC;
    -   precio;
    -   acceso a la explicación.
5.  **Semana**
    -   cargas flexibles;
    -   mejor día;
    -   mejor franja;
    -   motivo.
6.  **Detalle**
    -   trazabilidad de una recomendación;
    -   datos, predicciones y restricciones que la justifican.
7.  **Energía**
    -   producción;
    -   demanda;
    -   batería;
    -   red;
    -   coste.
8.  **Ajustes**
    -   editar instalación;
    -   editar cargas;
    -   estrategia;
    -   gestionar credenciales.
9.  **Estado de datos**
    -   última actualización;
    -   estado de caché;
    -   refrescar.
10. **Acerca de**

-   software experimental;
-   versión;
-   licencia.

## Pantalla «Hoy»

Orden de presentación:

1.  acciones concretas ordenadas por hora;
2.  producción, demanda, batería y coste;
3.  explicación de cada acción.

Lenguaje preferido:

-   «conviene»;
-   «puede esperar»;
-   «mejor mañana».

El usuario no debería tener que interpretar curvas para saber qué hacer.

## Plan semanal

Debe poder desplazar cargas flexibles entre días. Ejemplo conceptual:

``` text
Lavadora → domingo, 12:00–15:00
Motivo → mayor excedente solar previsto
```

Si hoy hay poca producción y dentro de dos días se espera un excedente
mayor, una salida válida puede ser:

> Lavadora: mejor el domingo.

## Explicabilidad

Una recomendación puede justificarse por:

-   producción FV prevista;
-   precio;
-   SOC;
-   presencia;
-   temperatura;
-   flexibilidad;
-   prioridad;
-   restricciones configuradas.

## Definición funcional del MVP

El MVP debe permitir que un usuario nuevo:

-   instale la app sin editar código;
-   introduzca y valide AEMET + ESIOS;
-   configure instalación y cargas;
-   obtenga datos y ejecute el plan;
-   vea recomendaciones de hoy;
-   vea planificación semanal;
-   entienda el motivo de cada recomendación.
