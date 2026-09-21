# Arquitectura Android ↔ Python

[← README](../README.md) · **Arquitectura** · [Configuración y
credenciales →](CONFIGURATION_AND_CREDENTIALS.md)

------------------------------------------------------------------------

## 1. Propósito

Este documento define la arquitectura técnica propuesta para la rama
`android-app` de **Gestion-Solar-AEMET-ESIOS**.

El objetivo no es rediseñar el motor energético. Android debe construir
una aplicación móvil alrededor del código Python existente y mantener
una frontera clara entre interfaz, estado de presentación, integración
Android--Python, motor energético y acceso a datos.

![Arquitectura general del proyecto](images/architecture-overview.png)

> **Principio fundamental: Android configura y presenta; Python
> calcula.**

Esto permite evolucionar la interfaz sin alterar los algoritmos y
mejorar el motor Python sin reconstruir las pantallas.

------------------------------------------------------------------------

## 2. Restricciones arquitectónicas

### 2.1 No duplicar el motor

No deben reimplementarse en Kotlin, salvo decisión posterior
justificada, la producción FV, meteorología, balance energético,
despacho de batería, optimización, planificación semanal ni las reglas
de decisión existentes.

### 2.2 No interpretar texto de consola

Android no debe ejecutar `main.py` y analizar después cadenas impresas.
El motor debe exponer una interfaz programática y devolver datos
estructurados.

### 2.3 No mezclar UI y APIs

Incorrecto:

``` text
Composable → HTTP AEMET
Composable → HTTP ESIOS
```

Correcto:

``` text
Composable → ViewModel → Repository / PythonGateway
           → adaptador Python → motor → AEMET/PVGIS/ESIOS
```

### 2.4 No introducir secretos en código

API Keys y tokens son datos privados del usuario y nunca constantes del
proyecto.

------------------------------------------------------------------------

## 3. Arquitectura por capas

``` text
┌──────────────────────────────────────────────────────┐
│ PRESENTATION                                         │
│ Jetpack Compose · Screens · Components · Navigation │
└────────────────────────┬─────────────────────────────┘
                         │ UI events / UI state
                         ▼
┌──────────────────────────────────────────────────────┐
│ APPLICATION                                          │
│ ViewModels · use cases · validation                  │
└────────────────────────┬─────────────────────────────┘
                         │ domain request/result
                         ▼
┌──────────────────────────────────────────────────────┐
│ INTEGRATION                                          │
│ PythonGateway · DTO mapping · error translation      │
└────────────────────────┬─────────────────────────────┘
                         │ structured data
                         ▼
┌──────────────────────────────────────────────────────┐
│ PYTHON ENGINE                                        │
│ config · demand · AEMET · solar · ESIOS             │
│ balance · dispatch · optimizer · weekly · cache      │
└────────────────────────┬─────────────────────────────┘
                         │
                 AEMET · PVGIS · ESIOS
```

### Presentation

Responsable de pantallas, navegación, formularios, componentes y
representación de estados `loading`, `success` y `error`.

No contiene fórmulas energéticas, llamadas HTTP a las fuentes ni reglas
de optimización.

### Application

Mantiene el estado, valida entradas, inicia ejecuciones y transforma las
acciones del usuario en peticiones al dominio.

Tecnologías previstas:

``` text
ViewModel
StateFlow / Flow
Coroutines
```

### Integration

Frontera entre Android y Python. Convierte modelos Kotlin a entradas
compatibles con Python, invoca el adaptador, recibe el resultado, lo
transforma a modelos Kotlin y traduce excepciones a errores
controlables.

### Python engine

Responsable de configuración, meteorología, estimación FV, precios,
demanda, balance, batería, despacho, optimización, planificación
semanal, caché y razones de decisión.

------------------------------------------------------------------------

## 4. Módulos Python existentes

### Datos externos

  Archivo             Responsabilidad
  ------------------- -------------------------------------
  `aemet.py`          previsión meteorológica
  `aemet_hourly.py`   previsión horaria
  `solar.py`          producción fotovoltaica / modelo FV
  `esios.py`          precios e información económica
  `cache.py`          reutilización de datos

### Configuración

  Archivo         Responsabilidad
  --------------- -------------------------------------------------
  `config.yaml`   configuración persistente esperada por el motor
  `config.py`     carga/validación de configuración
  `demand.py`     vivienda, cargas, presencia y flexibilidad

Android sustituirá la edición manual por formularios.

### Núcleo

  Archivo          Responsabilidad
  ---------------- -----------------------
  `balance.py`     balance energético
  `dispatch.py`    batería y red
  `optimizer.py`   optimización
  `weekly.py`      planificación semanal

Estos módulos deben permanecer independientes de Android.

`main.py` puede seguir sirviendo a CLI/Linux, pero Android necesita una
entrada distinta que no dependa de `print()` ni de argumentos de
terminal.

------------------------------------------------------------------------

## 5. Adaptador Python

Se propone introducir, por ejemplo:

``` text
android_adapter.py
```

El nombre puede cambiar antes de consolidar la API.

Interfaz conceptual:

``` python
def run_plan(config, soc: float, refresh: bool = False) -> dict:
    # Ejecuta el motor y devuelve un resultado estructurado.
    ...
```

Pseudocódigo de orquestación:

``` python
def run_plan(config, soc: float, refresh: bool = False) -> dict:
    validate_soc(soc)

    # Nombres conceptuales: sustituir por las funciones reales.
    weather = load_weather(config, refresh=refresh)
    solar = calculate_solar(config, weather)
    prices = load_prices(config, refresh=refresh)
    demand = calculate_demand(config)

    energy = calculate_balance(
        solar=solar,
        demand=demand,
        soc=soc,
        config=config,
    )

    today = build_today_plan(
        energy=energy,
        prices=prices,
        config=config,
    )

    week = build_weekly_plan(
        config=config,
        refresh=refresh,
    )

    return {
        "status": "ok",
        "warnings": [],
        "forecast": weather,
        "demand": demand,
        "energy": energy,
        "today_actions": today,
        "weekly_plan": week,
    }
```

**Importante:** `load_weather`, `calculate_solar`, etc. son nombres de
diseño, no se afirma que existan actualmente. Deben sustituirse por las
funciones reales del repositorio.

------------------------------------------------------------------------

## 6. Contrato de entrada

La especificación actual requiere como mínimo:

``` text
config/config_path
soc
refresh
fecha/horizonte (opcional)
```

Ejemplo serializable:

``` json
{
  "soc": 0.62,
  "refresh": false,
  "date": null,
  "horizon_days": 7
}
```

Hay dos estrategias a validar.

### A. Android genera `config.yaml`

``` text
Android forms → config.yaml → config.py → motor
```

Ventaja: máxima compatibilidad inicial con un motor que ya espere YAML.

### B. Android entrega un objeto

``` text
Android → JSON/Map → adaptador Python → modelo interno
```

Ventaja: menor dependencia del sistema de archivos.

La elección debe hacerse después de revisar cómo consume realmente la
configuración el código Python.

------------------------------------------------------------------------

## 7. Contrato de salida

Estructura mínima conceptual:

``` json
{
  "status": "ok",
  "warnings": [],
  "updated_at": "2026-09-21T08:10:00",
  "cache_status": "valid",
  "forecast": {},
  "demand": {},
  "energy": {
    "soc": 0.62
  },
  "today_actions": [],
  "weekly_plan": []
}
```

Debe poder representar meteorología, producción FV, demanda,
batería/SOC, importación/exportación, excedente/déficit, precios,
recomendaciones horarias, plan semanal y razones.

No deben inventarse campos para completar el esquema: el contrato
definitivo se construirá a partir de las salidas reales del motor.

### Ejemplo de recomendación diaria

``` json
{
  "time": "12:30",
  "action": "Ejecutar lavavajillas",
  "priority": 2,
  "reason": "Coincide con una franja de producción fotovoltaica elevada."
}
```

### Ejemplo semanal

``` json
{
  "load": "Lavadora",
  "day": "2026-09-27",
  "start": "12:00",
  "end": "15:00",
  "reason": "Mayor excedente solar previsto."
}
```

Son ejemplos de contrato, no afirmaciones sobre la salida actual del
motor.

------------------------------------------------------------------------

## 8. DTOs Kotlin

Una vez estabilizado el contrato Python:

``` kotlin
data class PlanRequest(
    val soc: Double,
    val refresh: Boolean = false
)

data class TodayActionDto(
    val time: String?,
    val action: String,
    val priority: Int?,
    val reason: String
)

data class WeeklyActionDto(
    val load: String,
    val day: String,
    val start: String?,
    val end: String?,
    val reason: String
)

data class PlanResultDto(
    val status: String,
    val warnings: List<String>,
    val updatedAt: String?,
    val cacheStatus: String?,
    val todayActions: List<TodayActionDto>,
    val weeklyPlan: List<WeeklyActionDto>
)
```

Estos tipos son una propuesta inicial y deben ajustarse al contrato
real.

------------------------------------------------------------------------

## 9. `PythonGateway`

El mecanismo de integración debe quedar oculto tras una interfaz:

``` kotlin
interface PythonGateway {
    suspend fun runPlan(request: PlanRequest): PlanResultDto
}
```

El resto de Android trabaja contra `PythonGateway`, no contra una
biblioteca concreta.

Implementación conceptual:

``` kotlin
class EmbeddedPythonGateway(
    private val mapper: PythonResultMapper
) : PythonGateway {

    override suspend fun runPlan(
        request: PlanRequest
    ): PlanResultDto = withContext(Dispatchers.IO) {

        val rawResult = callPython(
            soc = request.soc,
            refresh = request.refresh
        )

        mapper.map(rawResult)
    }
}
```

`callPython(...)` dependerá de la tecnología de integración finalmente
elegida.

Esta abstracción permite sustituir en el futuro Python embebido por una
implementación Kotlin o incluso por un servicio remoto sin modificar las
pantallas.

------------------------------------------------------------------------

## 10. Repository

``` kotlin
interface EnergyRepository {
    suspend fun calculatePlan(
        soc: Double,
        refresh: Boolean
    ): PlanResultDto
}
```

``` kotlin
class EnergyRepositoryImpl(
    private val pythonGateway: PythonGateway
) : EnergyRepository {

    override suspend fun calculatePlan(
        soc: Double,
        refresh: Boolean
    ): PlanResultDto =
        pythonGateway.runPlan(
            PlanRequest(
                soc = soc,
                refresh = refresh
            )
        )
}
```

Esta capa evita que los `ViewModel` dependan directamente de la
integración Python.

------------------------------------------------------------------------

## 11. ViewModel y estado

``` kotlin
sealed interface TodayUiState {
    data object Idle : TodayUiState
    data object Loading : TodayUiState

    data class Success(
        val result: PlanResultDto
    ) : TodayUiState

    data class Error(
        val message: String
    ) : TodayUiState
}
```

``` kotlin
class TodayViewModel(
    private val repository: EnergyRepository
) : ViewModel() {

    private val _uiState =
        MutableStateFlow<TodayUiState>(TodayUiState.Idle)

    val uiState: StateFlow<TodayUiState> =
        _uiState.asStateFlow()

    fun calculate(
        soc: Double,
        refresh: Boolean = false
    ) {
        viewModelScope.launch {
            _uiState.value = TodayUiState.Loading

            _uiState.value = try {
                val result = repository.calculatePlan(
                    soc = soc,
                    refresh = refresh
                )
                TodayUiState.Success(result)
            } catch (e: Exception) {
                TodayUiState.Error(
                    e.message ?: "Error desconocido"
                )
            }
        }
    }
}
```

En la aplicación final será preferible mapear categorías de error y no
mostrar directamente `e.message`.

------------------------------------------------------------------------

## 12. Compose

``` kotlin
@Composable
fun TodayScreen(
    viewModel: TodayViewModel
) {
    val state by viewModel.uiState.collectAsState()

    when (val current = state) {
        TodayUiState.Idle -> Unit
        TodayUiState.Loading -> CircularProgressIndicator()

        is TodayUiState.Success ->
            TodayContent(current.result)

        is TodayUiState.Error ->
            Text(current.message)
    }
}
```

La pantalla no conoce AEMET, PVGIS, ESIOS, las ecuaciones del balance ni
la forma de ejecutar Python.

------------------------------------------------------------------------

## 13. Estructura propuesta

``` text
app/
└── src/main/
    ├── java/.../
    │   ├── ui/
    │   │   ├── onboarding/
    │   │   ├── today/
    │   │   ├── week/
    │   │   ├── energy/
    │   │   ├── settings/
    │   │   └── components/
    │   │
    │   ├── domain/
    │   │   └── model/
    │   │
    │   ├── data/
    │   │   ├── repository/
    │   │   ├── local/
    │   │   └── mapper/
    │   │
    │   └── integration/
    │       └── python/
    │
    └── python/
        ├── android_adapter.py
        ├── aemet.py
        ├── aemet_hourly.py
        ├── solar.py
        ├── esios.py
        ├── cache.py
        ├── balance.py
        ├── dispatch.py
        ├── optimizer.py
        └── weekly.py
```

La ubicación física definitiva de Python dependerá de la solución de
integración elegida. Este árbol expresa responsabilidades, no una
configuración Gradle definitiva.

------------------------------------------------------------------------

## 14. Errores estructurados

Python no debería obligar a Android a analizar mensajes arbitrarios.

Ejemplo conceptual:

``` python
class PlanningError(Exception):
    code = "PLANNING_ERROR"

class ConfigurationError(PlanningError):
    code = "CONFIGURATION_ERROR"

class ExternalApiError(PlanningError):
    code = "EXTERNAL_API_ERROR"

class AuthenticationError(ExternalApiError):
    code = "AUTHENTICATION_ERROR"
```

Respuesta:

``` json
{
  "status": "error",
  "error": {
    "code": "AUTHENTICATION_ERROR",
    "source": "AEMET",
    "message": "No se pudo validar la credencial."
  }
}
```

Android debe traducirlo a un mensaje comprensible. No debe mostrar un
*stack trace* Python al usuario final.

------------------------------------------------------------------------

## 15. Caché y `refresh`

``` text
Abrir app
   ↓
¿caché válida?
   ├── sí → reutilizar
   └── no → consultar fuente
   ↓
ejecutar planificación
   ↓
mostrar updated_at
```

La acción **Actualizar datos ahora** debe activar conceptualmente:

``` python
refresh=True
```

Durante el MVP, Android no debería crear una segunda política de caché
para AEMET/ESIOS que compita con `cache.py`.

------------------------------------------------------------------------

## 16. Concurrencia

Red y cálculo no deben bloquear el hilo principal:

``` kotlin
withContext(Dispatchers.IO) {
    pythonGateway.runPlan(request)
}
```

La UI debe representar al menos:

``` text
Idle
Loading
Success
Error
```

------------------------------------------------------------------------

## 17. Persistencia

Hay dos clases de datos.

### Configuración funcional

Municipio, FV, inversor, batería, cargas y estrategia.

Puede persistirse localmente y utilizarse para reconstruir la
configuración esperada por Python.

### Secretos

AEMET API Key y token ESIOS.

Deben almacenarse mediante mecanismos protegidos de Android y mantenerse
separados de la configuración ordinaria.

Véase
[CONFIGURATION_AND_CREDENTIALS.md](CONFIGURATION_AND_CREDENTIALS.md).

------------------------------------------------------------------------

## 18. Testabilidad

La interfaz permite sustituir Python en tests:

``` kotlin
class FakePythonGateway : PythonGateway {

    override suspend fun runPlan(
        request: PlanRequest
    ): PlanResultDto {

        return PlanResultDto(
            status = "ok",
            warnings = emptyList(),
            updatedAt = "2026-09-21T08:00:00",
            cacheStatus = "test",
            todayActions = listOf(
                TodayActionDto(
                    time = "13:00",
                    action = "Ejecutar lavavajillas",
                    priority = 1,
                    reason = "Excedente FV previsto"
                )
            ),
            weeklyPlan = emptyList()
        )
    }
}
```

Así puede desarrollarse la UI aunque la integración Python todavía no
esté terminada.

------------------------------------------------------------------------

## 19. Primer prototipo vertical

Antes de construir todas las pantallas:

``` text
Pantalla Android
      ↓
TodayViewModel
      ↓
EnergyRepository
      ↓
PythonGateway
      ↓
android_adapter.py
      ↓
motor Python
      ↓
resultado estructurado
      ↓
Compose
```

### Criterio de éxito

El prototipo queda validado cuando:

1.  Android arranca;
2.  acepta un SOC de prueba;
3.  llama realmente a Python;
4.  Python devuelve una estructura;
5.  Kotlin la convierte a un modelo;
6.  Compose muestra al menos un resultado;
7.  un error Python se presenta de forma controlada.

Hasta validar este circuito no es necesario construir todas las
pantallas definitivas.

------------------------------------------------------------------------

## 20. Decisiones todavía abiertas

La documentación disponible no determina todos los detalles. Deben
validarse durante la implementación.

### Tecnología Python--Android

Debe probarse la solución concreta y comprobar:

-   versión de Python soportada;
-   compatibilidad de dependencias;
-   bibliotecas con componentes nativos;
-   tamaño del APK;
-   red y almacenamiento;
-   arquitecturas ARM;
-   construcción reproducible.

### Dependencias

Debe inventariarse el `requirements` real del motor. Las dependencias
nativas pueden condicionar la integración.

### Configuración

Debe decidirse entre:

``` text
config.yaml
```

y:

``` text
objeto / JSON
```

sin romper la versión Python/Linux.

### Esquema de salida

Debe derivarse de la salida real del motor y estabilizarse antes de
acoplar toda la UI.

------------------------------------------------------------------------

## 21. Regla para futuras modificaciones

Antes de añadir código:

**¿Es presentación?** → Compose.

**¿Es estado de pantalla?** → ViewModel / application.

**¿Traduce Android ↔ Python?** → integration.

**¿Es una decisión energética?** → Python.

**¿Consulta AEMET, PVGIS o ESIOS?** → acceso a datos/motor Python.

------------------------------------------------------------------------

## 22. Resultado buscado

La frontera estable permite evolucionar hacia:

``` text
                    ┌── motor Python actual
                    │
UI Android ─ Gateway┼── futura implementación Kotlin
                    │
                    └── posible servicio remoto
```

Para el MVP, la prioridad es reutilizar el motor Python existente.

------------------------------------------------------------------------

## 23. Navegación

[← README](../README.md) · **Arquitectura** · [Configuración y
credenciales →](CONFIGURATION_AND_CREDENTIALS.md)

También: [Fuentes de datos](DATA_SOURCES.md) · [UI / MVP](UI_MVP.md) ·
[Plan de desarrollo](DEVELOPMENT_PLAN.md)
