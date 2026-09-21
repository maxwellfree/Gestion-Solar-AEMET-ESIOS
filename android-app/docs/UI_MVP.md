# Interfaz Android y MVP

[← Fuentes de datos](DATA_SOURCES.md) · **UI / MVP** · [Plan de
desarrollo →](DEVELOPMENT_PLAN.md)

------------------------------------------------------------------------

## 1. Objetivo de la interfaz

La aplicación Android de **Gestión Solar Predictiva** debe responder,
ante todo, a una pregunta:

> **¿Qué me conviene hacer con mi energía y cuándo?**

La aplicación no debe convertirse inicialmente en un panel técnico lleno
de gráficas. El motor Python ya realiza el trabajo de adquisición de
datos, cálculo y optimización; Android debe convertir ese resultado en
decisiones comprensibles.

La jerarquía de información será:

``` text
1. QUÉ HACER
2. CUÁNDO
3. POR QUÉ
4. QUÉ DATOS SUSTENTAN LA DECISIÓN
```

El usuario debe poder abrir la aplicación y comprender la recomendación
principal en pocos segundos.

------------------------------------------------------------------------

## 2. Principio de diseño

La interfaz debe separar claramente:

``` text
DATO OBSERVADO
PREDICCIÓN
RECOMENDACIÓN
```

Ejemplo:

``` text
SOC actual
62 %
────────────────────────── DATO

Producción FV prevista
4,8 kWh entre 12:00 y 15:00
────────────────────────── PREDICCIÓN

Lavadora
Conviene utilizarla entre 12:00 y 15:00
────────────────────────── RECOMENDACIÓN
```

La recomendación no debe presentarse como una orden automática. En el
MVP, la aplicación **aconseja**, pero no controla el inversor ni activa
cargas.

------------------------------------------------------------------------

## 3. Mapa de navegación

La navegación funcional propuesta es:

``` text
                     ┌───────────────┐
                     │   ARRANQUE    │
                     └───────┬───────┘
                             │
                   ¿configuración completa?
                      │              │
                     NO             SÍ
                      │              │
                      ▼              ▼
              ┌──────────────┐   ┌──────────┐
              │ ONBOARDING   │   │   HOY    │
              └──────┬───────┘   └────┬─────┘
                     │                │
                     └────────┐       │
                              ▼       ▼
                         navegación principal
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
            HOY              SEMANA            ENERGÍA
             │                                   │
             └─────────────────┬─────────────────┘
                               ▼
                            AJUSTES
```

Para el MVP, una barra inferior puede contener:

``` text
Hoy | Semana | Energía | Ajustes
```

No es necesario añadir más destinos principales hasta que exista una
necesidad real.

------------------------------------------------------------------------

## 4. Pantallas del MVP

La especificación funcional se traduce en las siguientes pantallas:

  Pantalla             Objetivo
  -------------------- ---------------------------------------
  Bienvenida           explicar brevemente la aplicación
  Credenciales         configurar AEMET y ESIOS
  Instalación          ubicación, FV, inversor y batería
  Vivienda / demanda   configurar vivienda y cargas
  Estrategia           seleccionar comportamiento de gestión
  Hoy                  mostrar las decisiones prioritarias
  Semana               planificación de próximos días
  Detalle              explicar una recomendación
  Energía              mostrar datos que sustentan el plan
  Ajustes              modificar la configuración

El onboarding puede dividirse internamente en más pasos sin convertir
cada paso en un destino principal.

------------------------------------------------------------------------

# 5. Pantalla de bienvenida

Objetivo: explicar el producto sin sobrecargar al usuario.

``` text
┌──────────────────────────────────────┐
│                                      │
│       GESTIÓN SOLAR PREDICTIVA       │
│                                      │
│ Planifica el uso de tu energía       │
│ combinando previsión meteorológica,  │
│ producción solar, batería, demanda   │
│ y datos del sistema eléctrico.       │
│                                      │
│ La aplicación recomienda acciones.   │
│ No controla automáticamente tus      │
│ equipos.                             │
│                                      │
│          [ COMENZAR ]                │
│                                      │
└──────────────────────────────────────┘
```

No es necesario solicitar permisos en esta pantalla salvo que una
funcionalidad concreta los requiera.

------------------------------------------------------------------------

# 6. Onboarding

El onboarding debe implementar lo definido en
[CONFIGURATION_AND_CREDENTIALS.md](CONFIGURATION_AND_CREDENTIALS.md).

Flujo:

``` text
Credenciales
    ↓
Ubicación
    ↓
Sistema FV
    ↓
Inversor
    ↓
Batería
    ↓
Vivienda
    ↓
Cargas
    ↓
Estrategia
    ↓
Resumen
```

Cada paso debe ofrecer:

``` text
ATRÁS
CONTINUAR
```

y guardar temporalmente el estado para no perder los campos al
retroceder.

## Indicador de progreso

Ejemplo:

``` text
Configuración                         3 de 8
━━━━━━━━━━━━━━━━━━━━━━──────────────
```

No debe utilizarse una progresión engañosa si el número de pasos puede
variar.

------------------------------------------------------------------------

# 7. Pantalla «Hoy»

Esta es la pantalla principal de la aplicación.

Debe priorizar decisiones, no telemetría.

Mockup conceptual:

``` text
┌────────────────────────────────────────┐
│ Buenos días                            │
│ Plan para hoy · 21 septiembre         │
│                                        │
│ Datos actualizados 08:15       ↻       │
│                                        │
│ ┌────────────────────────────────────┐ │
│ │ RECOMENDACIÓN PRINCIPAL            │ │
│ │                                    │ │
│ │ Lavadora                           │ │
│ │ 12:00 – 15:00                     │ │
│ │                                    │ │
│ │ Conviene esperar hasta mediodía.   │ │
│ │                                    │ │
│ │ [ ¿POR QUÉ? ]                     │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Próximas acciones                      │
│                                        │
│ 16:00  ...                             │
│ 20:00  ...                             │
│                                        │
│ ────────────────────────────────────── │
│  Hoy     Semana     Energía    Ajustes │
└────────────────────────────────────────┘
```

Los valores son ilustrativos; Android debe mostrar los resultados reales
recibidos del motor.

------------------------------------------------------------------------

## 8. Jerarquía de «Hoy»

Orden recomendado:

``` text
estado de datos
      ↓
recomendación principal
      ↓
acciones secundarias
      ↓
resumen energético
      ↓
acceso al detalle
```

No colocar la gráfica de producción como primer elemento si el usuario
todavía no sabe qué decisión se deriva de ella.

------------------------------------------------------------------------

# 9. Tarjeta de recomendación

Componente reutilizable:

``` kotlin
data class RecommendationUiModel(
    val title: String,
    val timeWindow: String?,
    val summary: String,
    val reasonPreview: String?,
    val severity: RecommendationSeverity
)
```

`severity` no significa necesariamente peligro. Puede utilizarse para
distinguir visualmente:

``` text
NORMAL
IMPORTANT
WARNING
```

Los nombres definitivos deben alinearse con los tipos de recomendación
que produzca realmente el motor.

Composable conceptual:

``` kotlin
@Composable
fun RecommendationCard(
    recommendation: RecommendationUiModel,
    onDetails: () -> Unit
) {
    Card {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = recommendation.title,
                style = MaterialTheme.typography.titleMedium
            )

            recommendation.timeWindow?.let {
                Text(it)
            }

            Text(
                text = recommendation.summary
            )

            TextButton(
                onClick = onDetails
            ) {
                Text("¿Por qué?")
            }
        }
    }
}
```

La lógica energética no pertenece a este componente.

------------------------------------------------------------------------

# 10. Pantalla de detalle

Al pulsar **¿Por qué?**, el usuario debe poder inspeccionar la
justificación.

``` text
┌──────────────────────────────────────┐
│ ← Lavadora                           │
│                                      │
│ Recomendación                        │
│ 12:00 – 15:00                       │
│                                      │
│ ¿Por qué?                            │
│                                      │
│ • Se prevé mayor producción FV.      │
│ • La carga está marcada flexible.    │
│ • El SOC previsto es suficiente.     │
│                                      │
│ Datos utilizados                     │
│ Producción prevista      ...         │
│ SOC                       ...         │
│ Precio                     ...         │
│                                      │
└──────────────────────────────────────┘
```

Las razones deben proceder del motor cuando afecten a la decisión.

Android puede traducir códigos estables a texto:

``` text
HIGH_PV_FORECAST
→ Se prevé una producción fotovoltaica elevada.

FLEXIBLE_LOAD
→ Esta carga está configurada como flexible.
```

Android **no debe deducir** `HIGH_PV_FORECAST` observando por sí mismo
una curva.

------------------------------------------------------------------------

# 11. Modelo de razones

Modelo conceptual:

``` kotlin
enum class ReasonCode {
    HIGH_PV_FORECAST,
    LOW_PV_FORECAST,
    SUFFICIENT_SOC,
    LOW_SOC,
    FLEXIBLE_LOAD,
    PRICE_WINDOW
}
```

Y:

``` kotlin
data class RecommendationReason(
    val code: ReasonCode,
    val detail: String? = null
)
```

Estos códigos son ejemplos. El conjunto definitivo debe derivarse de la
lógica real del motor.

------------------------------------------------------------------------

# 12. Pantalla «Semana»

Debe responder:

> **¿Qué cargas conviene desplazar y a qué día/franja?**

Mockup:

``` text
┌──────────────────────────────────────┐
│ Semana                               │
│                                      │
│ DOM 27                               │
│ ☀ Buen excedente previsto            │
│                                      │
│ Lavadora        12:00 – 15:00       │
│ Lavavajillas    14:00 – 16:00       │
│                                      │
│ LUN 28                               │
│ Producción moderada                  │
│                                      │
│ ...                                  │
│                                      │
│ ──────────────────────────────────── │
│ Hoy     Semana     Energía   Ajustes │
└──────────────────────────────────────┘
```

La UI puede agrupar por día:

``` kotlin
data class DayPlanUiModel(
    val date: LocalDate,
    val summary: String?,
    val actions: List<RecommendationUiModel>
)
```

------------------------------------------------------------------------

# 13. Plan semanal: evitar falsa precisión

La previsión futura tiene incertidumbre.

La UI no debería presentar una recomendación de varios días como si
tuviera la misma certeza que una observación actual.

Ejemplo de lenguaje:

``` text
Previsión para el domingo
```

mejor que:

``` text
El domingo habrá exactamente...
```

Si el motor proporciona información de confianza/incertidumbre, Android
debe representarla. Si no la proporciona, Android no debe inventar
porcentajes de confianza.

------------------------------------------------------------------------

# 14. Pantalla «Energía»

Esta pantalla ofrece contexto técnico.

Puede incluir:

``` text
producción FV prevista
demanda prevista
SOC
importación de red
excedente
precios
```

La información exacta depende de la salida real del motor.

Mockup:

``` text
┌──────────────────────────────────────┐
│ Energía                              │
│                                      │
│ SOC actual                           │
│ 62 %                                 │
│                                      │
│ Producción FV prevista hoy           │
│ ... kWh                              │
│                                      │
│ Demanda prevista                     │
│ ... kWh                              │
│                                      │
│ [ gráfica horaria ]                  │
│                                      │
│ Datos actualizados: 08:15            │
│                                      │
│ ──────────────────────────────────── │
│ Hoy     Semana     Energía   Ajustes │
└──────────────────────────────────────┘
```

Esta pantalla no debe competir con «Hoy». Es una vista
explicativa/técnica.

------------------------------------------------------------------------

# 15. Gráficas

Las gráficas deben responder a preguntas concretas.

Ejemplo útil:

``` text
kW
│             FV
│           ╭────╮
│      ╭────╯    ╰────╮
│──────┼───────────────┼──── hora
       8      14       20

      ▒ ventana recomendada
```

Puede ser útil superponer:

``` text
producción FV
demanda
ventana recomendada
```

pero debe evitarse una gráfica con demasiadas series si no ayuda a
decidir.

Los colores no deben ser la única forma de transmitir significado; deben
existir etiquetas, iconos o patrones adecuados para accesibilidad.

------------------------------------------------------------------------

# 16. Estado de los datos

Debe existir un componente reutilizable:

``` kotlin
data class DataFreshnessUiModel(
    val updatedAt: String?,
    val status: DataFreshnessStatus
)

enum class DataFreshnessStatus {
    UPDATED,
    CACHED,
    STALE,
    UNAVAILABLE
}
```

Ejemplos visuales:

``` text
✓ Actualizado a las 08:15
◷ Usando datos guardados
⚠ Datos desactualizados
✕ Datos no disponibles
```

Los símbolos son conceptuales; el diseño Material definitivo puede
utilizar iconos.

------------------------------------------------------------------------

# 17. Actualización manual

La pantalla «Hoy» y, si procede, «Energía» deben permitir:

``` text
↻ Actualizar
```

Comportamiento:

``` text
tap
 ↓
Loading
 ↓
run_plan(refresh=True)
 ↓
Success / Warning / Error
```

Durante la actualización no debe borrarse necesariamente el último plan
válido. Puede mantenerse visible con un indicador de actualización hasta
recibir el nuevo resultado.

------------------------------------------------------------------------

# 18. Estado `Loading`

Evitar una pantalla completamente vacía.

Primera carga:

``` text
Preparando tu plan energético…
```

Actualización posterior:

``` text
Actualizando datos…
```

Si ya existe contenido válido, puede mantenerse y mostrar progreso de
forma no bloqueante.

------------------------------------------------------------------------

# 19. Estado de error

Un error debe responder:

``` text
QUÉ HA PASADO
QUÉ PUEDE HACER EL USUARIO
```

Ejemplo:

``` text
No se han podido actualizar los datos de AEMET.

Comprueba tu conexión o vuelve a intentarlo.

[ REINTENTAR ]
```

Si es autenticación:

``` text
La clave de AEMET no ha sido aceptada.

[ REVISAR CREDENCIALES ]
```

No mostrar:

``` text
requests.exceptions.HTTPError...
```

ni un stack trace Python.

------------------------------------------------------------------------

# 20. Advertencias sin bloquear

Si el motor puede trabajar con caché:

``` text
⚠ Sin conexión

El plan utiliza los últimos datos disponibles,
actualizados a las 07:50.
```

La advertencia debe ser visible pero no impedir utilizar una
planificación que el motor considere válida.

------------------------------------------------------------------------

# 21. Ajustes

Estructura:

``` text
Ajustes
│
├── Credenciales
│   ├── AEMET
│   └── ESIOS
│
├── Ubicación
├── Sistema fotovoltaico
├── Inversor
├── Batería
├── Vivienda
├── Cargas
├── Estrategia
│
└── Datos
    ├── última actualización
    └── actualizar ahora
```

La pantalla no debe mostrar la credencial completa.

Ejemplo:

``` text
AEMET API Key
••••••••••••••••••••      [CAMBIAR]
```

------------------------------------------------------------------------

# 22. Configuración de cargas

Pantalla conceptual:

``` text
┌──────────────────────────────────────┐
│ Cargas                               │
│                                      │
│ Lavadora                             │
│ 2,0 kW · 90 min · Flexible           │
│                         [EDITAR]     │
│                                      │
│ Lavavajillas                         │
│ ...                                  │
│                                      │
│           [+ AÑADIR CARGA]           │
└──────────────────────────────────────┘
```

Edición:

``` text
Nombre
Potencia
Duración
Flexibilidad
Ventana permitida
```

Los campos definitivos deben coincidir con `demand.py` y el optimizador.

------------------------------------------------------------------------

# 23. Introducción del SOC

Mientras no exista lectura automática del inversor, el usuario necesita
una forma rápida de indicar el SOC.

Ejemplo:

``` text
Estado actual de batería

          62 %

0 % ─────────●──────────── 100 %

[ CALCULAR PLAN ]
```

Internamente:

``` text
62 % → 0.62
```

Debe respetarse la distinción entre:

``` text
SOC físico introducido
```

y:

``` text
SOC mínimo/máximo configurado
```

------------------------------------------------------------------------

# 24. Navegación Compose

Rutas conceptuales:

``` kotlin
sealed class AppDestination(
    val route: String
) {
    data object Today :
        AppDestination("today")

    data object Week :
        AppDestination("week")

    data object Energy :
        AppDestination("energy")

    data object Settings :
        AppDestination("settings")

    data object RecommendationDetail :
        AppDestination("recommendation/{id}")
}
```

No es necesario utilizar exactamente esta representación; sirve para
mantener rutas centralizadas.

------------------------------------------------------------------------

# 25. `AppState`

Puede existir un estado global limitado a navegación y configuración
general:

``` kotlin
data class AppState(
    val onboardingComplete: Boolean,
    val selectedDestination: String
)
```

Los resultados energéticos no deberían convertirse indiscriminadamente
en estado global si pertenecen a una pantalla o repositorio concreto.

------------------------------------------------------------------------

# 26. `TodayUiState`

Propuesta más completa:

``` kotlin
sealed interface TodayUiState {

    data object Loading : TodayUiState

    data class Content(
        val plan: TodayPlanUiModel,
        val refreshing: Boolean = false
    ) : TodayUiState

    data class Error(
        val message: String,
        val canRetry: Boolean
    ) : TodayUiState
}
```

Mantener `Content(refreshing=true)` permite actualizar sin sustituir
toda la pantalla por un spinner.

------------------------------------------------------------------------

# 27. Modelo UI separado del DTO

No conviene mostrar directamente `PlanResultDto`.

Flujo:

``` text
Python
  ↓
PlanResultDto
  ↓
PlanUiMapper
  ↓
TodayPlanUiModel
  ↓
Compose
```

Ejemplo:

``` kotlin
data class TodayPlanUiModel(
    val dateLabel: String,
    val mainRecommendation: RecommendationUiModel?,
    val otherRecommendations: List<RecommendationUiModel>,
    val freshness: DataFreshnessUiModel
)
```

Esto permite modificar textos y presentación sin cambiar el contrato
Python.

------------------------------------------------------------------------

# 28. Componentes reutilizables

Una primera biblioteca de componentes puede contener:

``` text
RecommendationCard
DataFreshnessBanner
EnergyMetricCard
SocIndicator
DayPlanCard
WarningBanner
ErrorPanel
LoadingPanel
SectionHeader
```

No crear abstracciones demasiado complejas antes de utilizarlas en
varias pantallas.

------------------------------------------------------------------------

# 29. Accesibilidad

Desde el MVP:

-   texto legible con escalado de fuente;
-   controles con áreas táctiles adecuadas;
-   `contentDescription` donde corresponda;
-   no depender únicamente del color;
-   contraste suficiente;
-   orden de lectura lógico;
-   mensajes comprensibles para lectores de pantalla.

Ejemplo:

``` kotlin
Icon(
    imageVector = Icons.Default.Refresh,
    contentDescription = "Actualizar datos"
)
```

------------------------------------------------------------------------

# 30. Formato de magnitudes

La UI debe centralizar unidades y formatos.

Ejemplo:

``` kotlin
fun formatEnergy(kwh: Double): String =
    "%.1f kWh".format(kwh)

fun formatSoc(soc: Double): String =
    "${(soc * 100).roundToInt()} %"
```

En una implementación final conviene utilizar formato dependiente de
`Locale` en vez de construir manualmente todas las cadenas.

No mezclar:

``` text
W / kW
Wh / kWh
0.62 / 62 %
```

sin una política definida.

------------------------------------------------------------------------

# 31. Textos y recursos

Los textos visibles no deberían estar dispersos como literales por todos
los composables.

Preferible:

``` text
res/values/strings.xml
```

Ejemplo:

``` xml
<string name="today_title">Hoy</string>
<string name="why">¿Por qué?</string>
<string name="refresh">Actualizar</string>
```

Esto facilita mantenimiento y futura traducción.

------------------------------------------------------------------------

# 32. Modo claro/oscuro

No es una funcionalidad energética, pero utilizar Material Theme desde
el inicio evita acoplar colores manuales.

``` kotlin
MaterialTheme {
    SolarPredictiveApp()
}
```

No es necesario diseñar dos aplicaciones distintas; los componentes
deben apoyarse en el tema.

------------------------------------------------------------------------

# 33. No diseñar todavía una pantalla de control

El MVP no debe incluir botones como:

``` text
ENCENDER LAVADORA
CARGAR BATERÍA
DESCONECTAR RED
```

si la aplicación no ejecuta realmente esas acciones.

En esta fase, la semántica correcta es:

``` text
RECOMENDADO
CONVIENE
PLAN PREVISTO
```

Esto evita que el usuario confunda una recomendación con el estado real
de un equipo.

------------------------------------------------------------------------

# 34. Definición funcional del MVP

El MVP de interfaz está terminado cuando el usuario puede realizar este
recorrido:

``` text
Instalar APK
    ↓
Abrir aplicación
    ↓
Completar onboarding
    ↓
Introducir SOC
    ↓
Calcular
    ↓
Ver «Hoy»
    ↓
Abrir «¿Por qué?»
    ↓
Ver «Semana»
    ↓
Consultar «Energía»
    ↓
Modificar «Ajustes»
    ↓
Cerrar aplicación
    ↓
Abrir de nuevo sin perder configuración
```

------------------------------------------------------------------------

# 35. Orden recomendado de implementación UI

No construir todas las pantallas simultáneamente.

### Fase UI 1 --- prototipo vertical

``` text
SOC
↓
botón Calcular
↓
Loading
↓
PythonGateway
↓
una recomendación
```

### Fase UI 2 --- «Hoy»

``` text
TodayScreen
RecommendationCard
ErrorPanel
DataFreshnessBanner
```

### Fase UI 3 --- onboarding

``` text
credenciales
instalación
batería
vivienda/cargas
estrategia
```

### Fase UI 4 --- detalle

``` text
RecommendationDetailScreen
razones
datos de apoyo
```

### Fase UI 5 --- semana

``` text
WeekScreen
DayPlanCard
```

### Fase UI 6 --- energía y ajustes

``` text
EnergyScreen
SettingsScreen
```

Este orden permite validar pronto la integración real Android--Python.

------------------------------------------------------------------------

# 36. Primera pantalla técnica para David

Antes del diseño final puede implementarse una pantalla de diagnóstico
temporal:

``` text
ANDROID ↔ PYTHON TEST

SOC
[ 60 ]

[ RUN PYTHON ]

Status:
ok

First action:
Lavadora 12:00–15:00
```

Esta pantalla puede eliminarse cuando la integración esté validada.

Su función es separar dos problemas:

``` text
¿funciona Android ↔ Python?
```

de:

``` text
¿está terminada la interfaz?
```

------------------------------------------------------------------------

# 37. Criterios de aceptación por pantalla

Una pantalla no se considera terminada solo porque visualmente exista.

Debe cumplir:

``` text
estado normal
estado loading
estado vacío
estado error
datos largos
datos ausentes/opcionales
navegación atrás
rotación/recreación cuando corresponda
accesibilidad básica
```

Para pantallas que consultan datos:

``` text
caché
refresh
sin conexión
```

------------------------------------------------------------------------

# 38. Qué no debe hacer la UI

La UI no debe contener código como:

``` kotlin
if (pvForecast > demand && soc > 0.5) {
    recommendation = "Pon la lavadora"
}
```

Ese tipo de regla pertenece al motor.

Compose debe recibir:

``` kotlin
recommendation.summary
```

y representarlo.

Este principio es esencial para evitar dos motores de decisión
distintos: uno Python y otro Android.

------------------------------------------------------------------------

# 39. Resultado buscado

La experiencia final debe poder resumirse así:

``` text
DATOS COMPLEJOS
AEMET · PVGIS · ESIOS · FV · batería · demanda
                      ↓
                 MOTOR PYTHON
                      ↓
             PLAN ESTRUCTURADO
                      ↓
                 ANDROID
                      ↓
        «Esto es lo que conviene hacer»
                      ↓
               «y este es el motivo»
```

La complejidad permanece disponible para quien quiera inspeccionarla,
pero no se impone como primera experiencia.

------------------------------------------------------------------------

## 40. Navegación

[← Fuentes de datos](DATA_SOURCES.md) · **UI / MVP** · [Plan de
desarrollo →](DEVELOPMENT_PLAN.md)

También: [README](../README.md) · [Arquitectura](ARCHITECTURE.md) ·
[Configuración y credenciales](CONFIGURATION_AND_CREDENTIALS.md)
