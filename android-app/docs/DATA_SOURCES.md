# Fuentes de datos

[← Configuración y credenciales](CONFIGURATION_AND_CREDENTIALS.md) ·
**Fuentes de datos** · [UI / MVP →](UI_MVP.md)

------------------------------------------------------------------------

## 1. Propósito

**Gestión Solar Predictiva** combina información externa con la
configuración local de la instalación para construir un plan energético.

La arquitectura debe mantener separadas tres etapas:

``` text
FUENTE EXTERNA
      ↓
ADQUISICIÓN / NORMALIZACIÓN
      ↓
MOTOR ENERGÉTICO
      ↓
RECOMENDACIÓN
```

Una fuente externa aporta **datos**. No decide qué debe hacer el
usuario.

En la arquitectura actual intervienen principalmente:

``` text
AEMET  → meteorología
PVGIS  → recurso / producción fotovoltaica
ESIOS  → información económica / sistema eléctrico
```

Los módulos Python asociados son, según la documentación actual:

``` text
aemet.py
aemet_hourly.py
solar.py
esios.py
cache.py
```

------------------------------------------------------------------------

## 2. Flujo general de datos

``` text
                ┌─────────────┐
                │    AEMET    │
                └──────┬──────┘
                       │ meteorología
                       ▼
┌─────────────┐   ┌─────────────────┐   ┌─────────────┐
│    PVGIS    │──▶│  MOTOR PYTHON   │◀──│    ESIOS    │
└─────────────┘   │                 │   └─────────────┘
 recurso FV       │ solar / demand  │     precios/datos
                  │ balance         │
                  │ dispatch        │
                  │ optimizer       │
                  │ weekly          │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ RESULTADO       │
                  │ ESTRUCTURADO    │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ ANDROID         │
                  │ Hoy / Semana    │
                  └─────────────────┘
```

![Arquitectura general y fuentes
externas](images/architecture-overview.png)

Android no debería consultar estas fuentes directamente durante el MVP.
El acceso debe permanecer encapsulado en Python para conservar un único
camino de cálculo.

------------------------------------------------------------------------

# 3. AEMET OpenData

AEMET proporciona la información meteorológica utilizada por el sistema
predictivo.

![AEMET OpenData](images/aemet-opendata.png)

La aplicación Android debe limitarse a:

``` text
recoger la API Key
        ↓
almacenarla de forma segura
        ↓
entregarla al adaptador Python
        ↓
mostrar estado/errores
```

El módulo Python responsable de las consultas sigue siendo:

``` text
aemet.py
aemet_hourly.py
```

## 3.1 Datos necesarios

Los campos concretos deben determinarse revisando qué consume
actualmente el motor.

Conceptualmente, para planificación FV pueden resultar relevantes
variables como:

``` text
fecha y hora
nubosidad
temperatura
precipitación
estado meteorológico
```

Pero **no debe asumirse que todos estos campos son necesarios**. La
lista definitiva debe derivarse de `aemet.py`, `aemet_hourly.py` y de
las funciones que consumen sus resultados.

## 3.2 Normalización

La respuesta externa no debería propagarse sin procesar hasta Compose.

Preferible:

``` text
JSON AEMET
   ↓
aemet.py
   ↓
modelo meteorológico interno
   ↓
solar.py / optimizador
```

Ejemplo conceptual:

``` python
weather = {
    "timestamp": "...",
    "temperature_c": 18.2,
    "cloud_cover": 35.0
}
```

Los nombres anteriores son ilustrativos. Deben sustituirse por la
estructura real del proyecto.

## 3.3 Predicción diaria y horaria

La existencia de `aemet.py` y `aemet_hourly.py` sugiere una separación
entre distintos niveles temporales, pero debe comprobarse en el código.

La planificación diaria puede necesitar una resolución suficientemente
fina para responder preguntas como:

``` text
¿A qué hora conviene poner la lavadora?
```

Por tanto, la capa de datos debe conservar la resolución temporal que
realmente necesite el optimizador.

------------------------------------------------------------------------

# 4. PVGIS

PVGIS proporciona información relacionada con el recurso solar y el
rendimiento fotovoltaico.

![PVGIS --- Photovoltaic Geographical Information
System](images/pvgis.png)

Dentro del proyecto, su uso se asocia principalmente a:

``` text
solar.py
```

La responsabilidad de Android no es reproducir PVGIS, sino proporcionar
la configuración física necesaria:

``` text
ubicación
potencia FV
orientación
inclinación
otros parámetros que use realmente solar.py
```

## 4.1 Separación entre recurso y predicción

Debe distinguirse entre:

``` text
recurso / modelo solar
```

y:

``` text
meteorología prevista para hoy
```

El motor puede combinar ambos tipos de información para estimar la
producción futura.

Conceptualmente:

``` text
PVGIS + configuración FV
            │
            ├──────────────┐
            ▼              │
      modelo FV            │
            ▲              │
            │              │
     meteorología AEMET ───┘
            │
            ▼
 producción prevista
```

La implementación real debe verificarse en `solar.py`; este esquema
expresa la responsabilidad arquitectónica, no una ecuación concreta del
motor.

## 4.2 No duplicar cálculos en Android

Incorrecto:

``` text
Python calcula producción FV
Android vuelve a calcular producción FV
```

Correcto:

``` text
Python calcula
Android representa
```

La aplicación puede dibujar una curva recibida del motor, pero no
debería mantener una segunda implementación de la física solar.

------------------------------------------------------------------------

# 5. ESIOS / Red Eléctrica

ESIOS proporciona información del sistema eléctrico utilizada por el
proyecto.

![ESIOS / Red Eléctrica](images/esios-dashboard.png)

El acceso desde el motor se concentra en:

``` text
esios.py
```

Android debe gestionar el token y mostrar los resultados derivados, pero
no incorporar una segunda implementación de la consulta.

## 5.1 Datos económicos

La documentación funcional del proyecto contempla información de precios
para tomar decisiones.

Conceptualmente:

``` text
ESIOS
  ↓
esios.py
  ↓
serie temporal normalizada
  ↓
optimizer.py
  ↓
decisión
```

Ejemplo:

``` text
hora     precio
00:00    ...
01:00    ...
02:00    ...
...
```

No deben fijarse en Android identificadores concretos de indicadores
ESIOS hasta verificar cuáles utiliza `esios.py`.

## 5.2 Separación entre dato y recomendación

ESIOS puede aportar un precio, pero el significado energético depende
del resto del sistema.

Por ejemplo:

``` text
precio bajo
```

no implica automáticamente:

``` text
cargar batería
```

La decisión puede depender también de:

``` text
SOC
producción FV prevista
demanda
límites de batería
estrategia
previsión futura
```

Por ello, la decisión pertenece al optimizador, no al módulo de
adquisición de datos.

------------------------------------------------------------------------

# 6. Dependencias entre fuentes

Las fuentes no deben tratarse como tres paneles independientes.

El valor del sistema aparece al combinarlas:

``` text
AEMET
  │
  ▼
meteorología ───────┐
                    │
PVGIS/config FV ────┼──▶ producción prevista
                    │
                    ▼
                 balance
                    ▲
                    │
demanda ────────────┤
                    │
batería/SOC ────────┤
                    │
ESIOS/precios ──────┘
                    │
                    ▼
               optimización
                    │
                    ▼
             recomendaciones
```

Una recomendación debe poder rastrearse hacia los datos que la
motivaron.

------------------------------------------------------------------------

# 7. Caché

Las APIs externas no deben consultarse innecesariamente.

El proyecto ya contempla:

``` text
cache.py
```

Durante el MVP, la política de caché de datos energéticos debería
permanecer principalmente en Python.

## 7.1 Flujo esperado

``` text
Solicitud
   ↓
¿refresh=True?
   ├── sí ────────────────▶ consultar fuente
   │
   └── no
       ↓
¿hay caché válida?
   ├── sí → utilizar caché
   └── no → consultar fuente
                 ↓
             validar
                 ↓
             guardar
                 ↓
             devolver
```

## 7.2 Qué debe saber Android

Android no necesita conocer todos los detalles internos de `cache.py`.

Sí necesita información suficiente para explicar al usuario el estado de
los datos:

``` text
actualizados
procedentes de caché
desactualizados pero utilizables
no disponibles
```

Contrato conceptual:

``` json
{
  "cache_status": "valid",
  "updated_at": "2026-09-21T08:15:00"
}
```

Una evolución mejor podría distinguir cada fuente:

``` json
{
  "sources": {
    "aemet": {
      "status": "ok",
      "from_cache": false,
      "updated_at": "..."
    },
    "pvgis": {
      "status": "ok",
      "from_cache": true,
      "updated_at": "..."
    },
    "esios": {
      "status": "ok",
      "from_cache": true,
      "updated_at": "..."
    }
  }
}
```

Este esquema es una propuesta; debe adaptarse a la información que
`cache.py` pueda proporcionar realmente.

------------------------------------------------------------------------

# 8. `refresh`

La interfaz debería ofrecer una acción sencilla:

``` text
Actualizar datos
```

que conceptualmente ejecute:

``` python
run_plan(
    config=config,
    soc=soc,
    refresh=True,
)
```

No es necesario que el usuario entienda la implementación de la caché.

La interfaz puede mostrar:

``` text
Última actualización: 08:15
```

y:

``` text
[ ACTUALIZAR ]
```

------------------------------------------------------------------------

# 9. Funcionamiento sin conexión

Debe diferenciarse entre:

``` text
sin Internet + caché válida
sin Internet + caché antigua
sin Internet + sin datos
```

## Caso A --- caché utilizable

La aplicación puede continuar:

``` text
Sin conexión.
Se están utilizando los últimos datos disponibles.
```

## Caso B --- datos antiguos

Puede mostrarse una advertencia:

``` text
Los datos disponibles no están actualizados.
Las recomendaciones pueden ser menos fiables.
```

## Caso C --- no existen datos

No debe fabricarse una planificación.

``` text
No hay datos suficientes para calcular el plan.
Conéctate a Internet y vuelve a intentarlo.
```

El motor debe decidir cuándo una caché sigue siendo técnicamente
utilizable; Android debe representar esa decisión.

------------------------------------------------------------------------

# 10. Errores por fuente

No todos los fallos significan lo mismo.

Modelo conceptual:

``` text
NETWORK_ERROR
AUTHENTICATION_ERROR
RATE_LIMIT
SERVICE_UNAVAILABLE
INVALID_RESPONSE
DATA_NOT_AVAILABLE
PARSING_ERROR
```

Respuesta estructurada:

``` json
{
  "status": "error",
  "error": {
    "code": "AUTHENTICATION_ERROR",
    "source": "AEMET",
    "message": "No se pudo autenticar la petición."
  }
}
```

La UI puede traducirlo:

``` text
La clave de AEMET no ha sido aceptada.
Revísala en Ajustes → Credenciales.
```

Para:

``` text
SERVICE_UNAVAILABLE
```

el mensaje debe ser distinto:

``` text
AEMET no está disponible temporalmente.
Puedes volver a intentarlo más tarde.
```

------------------------------------------------------------------------

# 11. Datos parciales

Una cuestión importante para el motor es determinar si puede calcular
con una fuente temporalmente ausente.

Ejemplo:

``` text
AEMET ✓
PVGIS ✓
ESIOS ✗
```

Las posibilidades son:

``` text
A) abortar todo el cálculo
B) calcular parcialmente
C) utilizar caché ESIOS
```

Esta decisión pertenece al motor y debe documentarse explícitamente
cuando se revise el comportamiento actual.

Android necesita recibir algo como:

``` json
{
  "status": "partial",
  "warnings": [
    {
      "source": "ESIOS",
      "code": "STALE_DATA"
    }
  ]
}
```

No debe deducir por sí mismo si una recomendación sigue siendo válida.

------------------------------------------------------------------------

# 12. Timestamps y zona horaria

Todas las series temporales deben tener una convención clara.

Debe definirse:

``` text
zona horaria de la fuente
zona horaria de almacenamiento
zona horaria del cálculo
zona horaria presentada al usuario
```

Para una aplicación energética en España, los cambios de horario de
verano/invierno pueden producir días de 23 o 25 horas.

Por ello, debe evitarse modelar una serie diaria suponiendo siempre:

``` text
24 valores = 24 horas
```

sin verificar cómo lo resuelven las fuentes y el código actual.

Una representación robusta utiliza timestamps completos en vez de
índices horarios implícitos:

``` json
{
  "timestamp": "2026-09-21T13:00:00+02:00",
  "value": 1.23
}
```

La política exacta debe alinearse con las librerías y estructuras Python
ya utilizadas.

------------------------------------------------------------------------

# 13. Unidades

Las fronteras entre módulos deben definir unidades explícitas.

Ejemplos:

``` text
potencia       kW
energía        kWh
temperatura    °C
SOC            0...1
precio         unidad definida por la fuente/motor
tiempo         timestamp con zona
```

Debe evitarse código ambiguo:

``` python
power = 5000
```

si no está claro si representa:

``` text
5000 W
```

o:

``` text
5000 kW
```

Cuando sea viable, los nombres internos pueden incorporar la unidad:

``` python
power_kw
energy_kwh
temperature_c
```

y Kotlin:

``` kotlin
val powerKw: Double
val energyKwh: Double
```

------------------------------------------------------------------------

# 14. Validación de respuestas externas

Una respuesta HTTP correcta no garantiza datos correctos para el
cálculo.

Después de cada consulta debe verificarse, según corresponda:

``` text
código HTTP
estructura esperada
campos obligatorios
rango temporal
valores nulos
unidades
orden temporal
duplicados
zona horaria
```

Flujo:

``` text
HTTP response
    ↓
parse
    ↓
validate
    ↓
normalize
    ↓
cache
    ↓
motor
```

No:

``` text
HTTP response → optimizer
```

------------------------------------------------------------------------

# 15. Interfaces internas recomendadas

Aunque el motor actual puede no tener todavía esta abstracción,
conceptualmente resulta útil pensar en proveedores:

``` python
class WeatherProvider:
    def get_forecast(self, ...):
        ...

class SolarProvider:
    def get_solar_data(self, ...):
        ...

class PriceProvider:
    def get_prices(self, ...):
        ...
```

Implementaciones:

``` text
AemetWeatherProvider
PvgisSolarProvider
EsiosPriceProvider
```

Esto facilitaría tests y sustitución de fuentes.

No es necesario realizar esta refactorización completa para iniciar el
MVP si implica modificar demasiado código existente.

------------------------------------------------------------------------

# 16. Datos falsos para desarrollo

La UI Android no debería depender permanentemente de APIs reales durante
su construcción.

Pueden crearse fixtures:

``` text
fixtures/
├── weather_sample.json
├── solar_sample.json
├── prices_sample.json
└── plan_sample.json
```

Así puede probarse:

``` text
UI
↓
FakePythonGateway
↓
datos deterministas
```

Ventajas:

``` text
tests reproducibles
sin consumo de API
sin credenciales
desarrollo offline
casos extremos controlados
```

Los fixtures no deben contener respuestas con datos personales ni
credenciales.

------------------------------------------------------------------------

# 17. Trazabilidad

Una recomendación útil debe poder explicar de dónde procede.

Ejemplo:

``` text
Recomendación:
Usar lavadora entre 12:00 y 14:00.

Razones:
• producción FV prevista elevada
• SOC suficiente
• carga flexible
• menor necesidad prevista de importar energía
```

El motor debería devolver las razones ya estructuradas.

Android no debería reconstruir la lógica a partir de las gráficas.

Modelo conceptual:

``` json
{
  "action": "run_load",
  "load": "Lavadora",
  "window": {
    "start": "...",
    "end": "..."
  },
  "reasons": [
    "HIGH_PV_FORECAST",
    "SUFFICIENT_SOC",
    "FLEXIBLE_LOAD"
  ]
}
```

Kotlin puede traducir códigos estables a textos:

``` text
HIGH_PV_FORECAST
→ "Se prevé una producción solar elevada."
```

Esto mantiene separada la decisión del texto de interfaz.

------------------------------------------------------------------------

# 18. Observabilidad para desarrollo

Durante desarrollo conviene registrar:

``` text
fuente consultada
inicio/fin de consulta
caché hit/miss
duración
resultado correcto/error
cantidad de registros
```

Ejemplo:

``` text
[AEMET] request started
[AEMET] cache miss
[AEMET] request completed: 48 records
```

Nunca:

``` text
[AEMET] api_key=...
[ESIOS] token=...
```

------------------------------------------------------------------------

# 19. Tabla de integración que debe completarse

Antes de cerrar la capa de datos conviene documentar el comportamiento
real:

  -------------------------------------------------------------------------------------------
  Fuente     Módulo              Entrada    Salida     Resolución   Caché        Credencial
  ---------- ------------------- ---------- ---------- ------------ ------------ ------------
  AEMET      `aemet.py`          por        por        por revisar  `cache.py` / API Key
                                 revisar    revisar                 verificar    

  AEMET      `aemet_hourly.py`   por        por        horaria /    por revisar  API Key
  horaria                        revisar    revisar    verificar                 

  PVGIS      `solar.py` /        por        por        por revisar  por revisar  verificar
             verificar           revisar    revisar                              

  ESIOS      `esios.py`          por        por        por revisar  `cache.py` / token
                                 revisar    revisar                 verificar    
  -------------------------------------------------------------------------------------------

Los elementos marcados **por revisar/verificar** deben rellenarse
inspeccionando el código real, no mediante suposiciones.

------------------------------------------------------------------------

# 20. Pruebas mínimas por fuente

Para cada proveedor debe probarse:

``` text
respuesta correcta
credencial incorrecta
sin conexión
timeout
respuesta vacía
respuesta malformada
datos antiguos
caché disponible
caché ausente
refresh forzado
```

Y, cuando sea relevante:

``` text
cambio de día
cambio de mes
cambio horario verano/invierno
```

------------------------------------------------------------------------

# 21. Responsabilidad de Android

Android sí debe:

``` text
mostrar estado de actualización
permitir refresh
mostrar errores comprensibles
mostrar advertencias
representar series
mostrar procedencia/fecha cuando sea útil
```

Android no debe:

``` text
implementar una segunda API AEMET
implementar una segunda API ESIOS
recalcular la producción FV
decidir cuándo cargar la batería
interpretar precios para generar decisiones
inferir recomendaciones desde gráficos
```

------------------------------------------------------------------------

# 22. Primer objetivo de integración de datos

Antes de integrar simultáneamente todas las fuentes, conviene demostrar
el recorrido completo de una de ellas:

``` text
Android
   ↓
PythonGateway
   ↓
android_adapter.py
   ↓
módulo de datos
   ↓
fuente externa
   ↓
normalización
   ↓
resultado estructurado
   ↓
Android
```

Después se añade la siguiente fuente manteniendo el mismo patrón.

El criterio importante no es que Android pueda mostrar el JSON bruto,
sino que la frontera Android--Python sea estable y los errores estén
controlados.

------------------------------------------------------------------------

# 23. Nota operativa sobre AEMET

La política de las API Keys de AEMET puede cambiar con el tiempo. Por
ello, la aplicación no debe asumir que una clave válida seguirá siendo
válida indefinidamente.

La interfaz de credenciales debe permitir:

``` text
reemplazar clave
revalidar
detectar error de autenticación
volver al cálculo tras corregirla
```

No debe ser necesario reinstalar la aplicación para renovar una
credencial.

------------------------------------------------------------------------

# 24. Resultado buscado

La capa de datos debe conseguir que el resto del sistema pueda trabajar
con información coherente sin conocer los detalles de cada API:

``` text
AEMET ─┐
PVGIS ─┼─▶ adquisición → validación → normalización → caché
ESIOS ─┘                                      │
                                              ▼
                                      modelos internos
                                              │
                                              ▼
                                        optimizador
                                              │
                                              ▼
                                      plan explicable
```

Esta separación es fundamental para que un cambio en una API externa no
obligue a modificar toda la aplicación Android.

------------------------------------------------------------------------

# 25. Navegación

[← Configuración y credenciales](CONFIGURATION_AND_CREDENTIALS.md) ·
**Fuentes de datos** · [UI / MVP →](UI_MVP.md)

También: [README](../README.md) · [Arquitectura](ARCHITECTURE.md) ·
[Plan de desarrollo](DEVELOPMENT_PLAN.md)
