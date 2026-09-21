# Arquitectura de la aplicación Android

## Flujo general

``` text
Jetpack Compose
      ↓
ViewModel / estado
      ↓
Adaptador Android ↔ Python
      ↓
Motor Python existente
      ↓
AEMET / PVGIS / ESIOS
```

Regla arquitectónica:

**UI ≠ algoritmo ≠ acceso a datos**

## Motor Python existente

### Datos externos

-   `aemet.py`
-   `aemet_hourly.py`
-   `solar.py`
-   `esios.py`
-   `cache.py`

Android no debe volver a implementar estas consultas ni duplicar la
caché.

### Configuración

-   `config.yaml`
-   `config.py`
-   `demand.py`

El asistente Android recoge los datos del usuario y genera la
configuración que espera el motor. `config.yaml` debe actuar como fuente
de verdad para la configuración del sistema, salvo que durante la
implementación se acuerde formalmente otro contrato equivalente.

### Núcleo de cálculo: usar sin modificar salvo necesidad justificada

-   `balance.py` --- balance energético.
-   `dispatch.py` --- gestión de batería y red.
-   `optimizer.py` --- optimización.
-   `weekly.py` --- planificación semanal.

Estos módulos deben permanecer independientes de la UI.

### Orquestación

`main.py` no debe utilizarse desde Android parseando texto de consola.

Debe crearse un adaptador o refactor mínimo que exponga una entrada
reutilizable y devuelva un resultado estructurado.

## Interfaz interna propuesta

``` python
run_plan(config, soc, refresh=False)
```

o, si se trabaja con ruta:

``` python
run_plan(config_path, soc, refresh=False)
```

La elección definitiva debe mantenerse estable una vez acordada.

### Entrada mínima

-   `config` o `config_path`
-   `soc`: `float`, rango 0..1
-   `refresh`: `bool`
-   fecha/horizonte: opcional

### Respuesta mínima

``` text
status / warnings
forecast
demand
energy
today_actions[]
weekly_plan[]
updated_at
cache_status
```

El resultado debe incluir, cuando proceda:

-   resumen de instalación;
-   meteorología;
-   producción FV;
-   perfil de demanda;
-   SOC/batería;
-   importación/exportación;
-   excedente/déficit;
-   precios;
-   recomendaciones horarias;
-   plan semanal;
-   razón de cada decisión.

## Responsabilidades

### Kotlin / Android

-   formularios y navegación;
-   estado de interfaz;
-   almacenamiento local;
-   almacenamiento seguro de credenciales;
-   llamada al adaptador Python;
-   presentación de resultados y errores.

Kotlin no debe conocer fórmulas energéticas, endpoints concretos ni
reglas internas de optimización.

### Python

-   validar/leer configuración;
-   consultar AEMET, PVGIS/modelo FV y ESIOS;
-   calcular demanda, balance, despacho y optimización;
-   generar planificación diaria/semanal;
-   devolver datos estructurados, no texto formateado.
