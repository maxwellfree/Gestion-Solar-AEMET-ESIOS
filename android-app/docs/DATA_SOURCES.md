# Fuentes de datos externas

La aplicación Android no debe reproducir directamente la lógica de
acceso a estas fuentes. El acceso permanece en el motor Python y se
consume mediante el adaptador.

## AEMET OpenData

Uso previsto:

-   previsión meteorológica;
-   datos horarios cuando estén disponibles;
-   información necesaria para la predicción energética.

Requiere API Key del usuario.

Módulos relacionados:

-   `aemet.py`
-   `aemet_hourly.py`

## PVGIS / modelo fotovoltaico

Uso previsto:

-   estimación de producción fotovoltaica;
-   radiación solar;
-   estimación asociada a ubicación, inclinación y orientación.

Módulo relacionado:

-   `solar.py`

## ESIOS --- Red Eléctrica

Uso previsto:

-   precios;
-   datos del sistema eléctrico utilizados por el modelo;
-   información económica necesaria para las decisiones.

Requiere token del usuario.

Módulo relacionado:

-   `esios.py`

## Caché

Módulo:

-   `cache.py`

Comportamiento previsto:

1.  al abrir la aplicación, leer primero la caché válida del día;
2.  consultar únicamente los datos necesarios;
3.  calcular el plan;
4.  mostrar las recomendaciones;
5.  informar de la fecha/hora de última actualización.

Cerrar y volver a abrir la aplicación no debe generar consultas
innecesarias.

La acción **Actualizar datos ahora** debe ser funcionalmente equivalente
a `--refresh`.

Si no existe conexión de red, la aplicación puede utilizar los últimos
datos disponibles cuando sean suficientemente recientes, mostrando
claramente la limitación.
