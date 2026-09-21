# Configuración y credenciales

## Primera ejecución

Antes de poder calcular recomendaciones, el usuario debe proporcionar:

-   API Key de AEMET OpenData;
-   token/API Key de ESIOS.

Las credenciales se obtienen fuera de la aplicación mediante los
procedimientos oficiales de cada servicio.

## Seguridad

Las credenciales:

-   no deben incluirse en Git;
-   no deben aparecer en logs;
-   no deben aparecer en informes;
-   no deben quedar visibles en capturas de depuración;
-   no deben incluirse en archivos exportados;
-   deben mostrarse ocultas en la interfaz;
-   deben poder sustituirse;
-   deben almacenarse de forma segura en el dispositivo.

## Asistente de configuración

Secuencia prevista:

``` text
Credenciales
    ↓
Ubicación
    ↓
Fotovoltaica
    ↓
Inversor
    ↓
Batería
    ↓
Vivienda
    ↓
Cargas y estrategia
```

### Ubicación

-   provincia;
-   municipio;
-   código AEMET, resuelto automáticamente cuando sea posible.

### Instalación fotovoltaica

-   número de paneles;
-   potencia por panel;
-   inclinación;
-   orientación/azimut.

### Inversor

-   fabricante;
-   modelo;
-   potencia.

### Batería

-   modelo;
-   número de unidades;
-   capacidad;
-   SOC normal;
-   SOC de emergencia;
-   eficiencias.

### Vivienda

-   ocupación;
-   presencia;
-   hábitos relevantes;
-   características necesarias para el modelo.

### Cargas

Cada carga debe poder describirse mediante:

-   nombre;
-   potencia;
-   duración;
-   flexible/no flexible;
-   automatizable;
-   prioridad;
-   requisitos de presencia;
-   ventana horaria;
-   flexibilidad entre días cuando proceda.

### Estrategia

Valor inicial previsto:

`sustainable_predictiva`

Debe permitirse modificar posteriormente toda la configuración desde
**Ajustes**.

## Ejecución diaria

Además de la configuración persistente, la ejecución puede requerir:

-   SOC actual;
-   opción `refresh`;
-   fecha/horizonte cuando sea necesario.

## Estado

La aplicación debe conservar o mostrar:

-   última actualización;
-   estado de caché;
-   errores de API;
-   disponibilidad de datos almacenados.
