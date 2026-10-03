# android-app — Desarrollo

Documentación de implementación del MVP de **Gestión Solar Predictiva**
(rama `android-app`). La especificación funcional está en
[`README.md`](README.md) y [`docs/`](docs/).

---

## 1. Principio

> **Android configura → Python calcula → Android presenta.**

El motor Python de la carpeta superior **no se modifica**. La capa Android:

- copia los módulos del motor a `mvp/python/` en tiempo de build;
- adapta la configuración inyectando valores en los módulos (no editando
  los ficheros);
- ejecuta el motor con **Pyodide** dentro del WebView;
- presenta los resultados de forma explicable.

```
android-app/
├── Makefile                  mvp · android · test · serve · clean
├── android_adapter.py        frontera estable Android ↔ motor  (run_plan)
├── app/…                     (n/a) el MVP vive en mvp/
├── mvp/                      MVP (se ejecuta tal cual)
│   ├── index.html
│   ├── css/app.css
│   ├── js/                   módulos ES (formato, mapper, store, engine, ui)
│   ├── python/               GENERADO: motor .py + android_adapter.py
│   └── vendor/lib/           GENERADO: jQuery + OnsenUI
├── tests/                    python (unittest) + js (node)
├── scripts/                  build/vendor/serve/test
└── logs/                     GENERADO: registro de cada comando
```

El motor vive una carpeta por encima y **nunca se toca**:

```
Gestion-Solar-AEMET-ESIOS/    ← motor (intacto)
├── aemet.py · solar.py · esios.py · balance.py · optimizer.py · weekly.py …
└── android-app/              ← este proyecto
```

---

## 2. Comandos

| Comando | Qué hace | Log |
|---|---|---|
| `make mvp` | Copia el motor + adaptador a `mvp/python`, genera `manifest.json` y empaqueta jQuery/OnsenUI. | `logs/mvp-*.log` |
| `make test` | Pruebas Python (`unittest`), prueba de humo del contrato y pruebas JS (node). | `logs/test-*.log` |
| `make serve` | Sirve el MVP en <http://localhost:8080>. | `logs/serve-*.log` |
| `make android` | Crea el proyecto Capacitor en `gestion-solar/`, sincroniza y compila el APK. **Requiere JDK + Android SDK en el host.** | `logs/android-*.log` |
| `make vendor-pyodide` | Copia local del runtime Pyodide + paquetes (arranque sin CDN). | `logs/vendor-pyodide-*.log` |
| `make clean` | Borra artefactos generados (no toca el código fuente). | — |

> El `Makefile` usa `$(CURDIR)` y comillas porque la ruta del vault
> contiene espacios.

### Desarrollo rápido

```bash
cd android-app
make mvp        # prepara mvp/python y mvp/vendor/lib
make serve      # abre http://localhost:8080
make test       # todas las pruebas
```

En el navegador, el botón **«Probar con datos de demostración»** ejecuta
el **motor Python real** sin credenciales ni conexión: únicamente se
sustituyen las llamadas a las APIs externas (AEMET, ESIOS, PVGIS) por
datos de ejemplo. El resto del cálculo (demanda, perfil FV, balance,
despacho de batería, optimización y plan semanal) lo realiza el motor.

### Modo demostración en detalle

`run_plan(..., demo=True)` no usa datos sintéticos en JavaScript: el
adaptador reasigna, **en los módulos ya importados**, las funciones que
acceden a las APIs y deja intacto el resto del motor:

| Fuente | Se sustituye | Sigue ejecutándose (motor real) |
|---|---|---|
| AEMET diaria | `aemet.fetch_forecast` | `aemet.day_solar_score` |
| AEMET horaria | `aemet_hourly.fetch_forecast_hourly` | `aemet_hourly.procesar_dia` |
| ESIOS | `esios.obtener_indicador` | `extraer_precios` / `combinar_precios` |
| PVGIS | `solar.consultar_pvgis` | `perfil_referencia_fecha` |
| — | — | `balance` · `dispatch` · `optimizer` · `weekly` |

No se modifica ningún fichero del motor. El resultado incluye
`"demo": true`, `sources.*.status = "demo"` y un aviso. Si Pyodide no
está disponible, la interfaz cae a un generador sintético en JS
(`mvp/js/demo.js`) sólo como último recurso.

---

## 3. Contrato Android ↔ Python

`android_adapter.py` expone:

```python
run_plan(config, credentials, soc, refresh=False, date=None,
         estrategia="sostenible_predictiva", engine=None) -> dict
```

Nunca lanza excepciones: devuelve siempre `{"status": "ok" | "error", ...}`.

El adaptador reproduce el mismo recorrido que `main.py`:

```
config.obtener_configuracion_sistema()
 → demand.obtener_configuracion_demanda(fecha)
 → aemet.obtener_prevision_solar(municipio, refresh)
 → aemet_hourly.obtener_prevision_horaria(municipio, refresh)
 → esios.obtener_precios(fecha, refresh)
 → weekly.generar_plan_semanal(...)
 → solar.obtener_perfil_fv_24h(...) + energia_fv_diaria + obtener_pico_fv
 → balance.calcular_balance_horario + calcular_metricas_balance
 → dispatch.generar_plan_sostenible_predictivo + calcular_metricas_plan
 → optimizer.optimizar(...)
```

Salida (resumida):

```jsonc
{
  "schema_version": 1,
  "status": "ok",
  "warnings": [],
  "updated_at": "2026-09-21T10:30:00",
  "cache_status": "updated|cached",
  "input":       { "soc": 0.62, "estrategia": "…", "municipio": "…" },
  "forecast":    { "quality": "alta", "score": 0.82, … },
  "pv":          { "energia_kwh": 12.5, "pico": {…}, "perfil": [ …24 ] },
  "demand":      { "energia_diaria_kwh": …, "perfil": [ …24 ] },
  "energy":      { "balance_metrics": {…}, "plan_metrics": {…} },
  "prices":      { "serie": [ … ], "min_compra": {…}, "max_venta": {…} },
  "today_actions": [
    { "id": "…", "kind": "battery|grid|solar|load",
      "title": "…", "time_window": "12:00 – 15:00",
      "summary": "…", "severity": "normal|important|warning",
      "reasons": [ { "code": "HIGH_PV_FORECAST", "detail": null } ] }
  ],
  "weekly_plan":  [ { "date": "…", "weekday": "…",
                      "actions": [ … ] } ],
  "strategic":    { "acciones": [ … ], "razones": [ … ], "metricas": {…} }
}
```

Los **códigos de razón** se derivan de clasificaciones ya calculadas por
el motor (calidad solar, precios, SOC); Android **no** recalcula física.
La traducción a texto está en `mvp/js/reasons.js`.

---

## 4. Credenciales

- El motor lee `AEMET_API_KEY` y `ESIOS_API_KEY` de `os.environ`
  (vía `mytoken.env`) **en tiempo de importación**.
- El adaptador, antes de importar el motor, escribe esas variables en
  `os.environ` y materializa `mytoken.env` en el directorio del motor
  (`prepare_credentials`).
- Las credenciales se guardan aparte de la configuración
  (`gs.credentials.v1` frente a `gs.config.v1`) y **nunca** aparecen en
  el plan ni en los registros.

> **MVP**: se usa `localStorage`. El almacenamiento cifrado propio de
> Android (Keystore) queda para una fase posterior.

Validación independiente por fuente (`validate_credential`): reutiliza
`aemet.get_json` / `esios.get_json` y devuelve
`valid | invalid | network_error | service_unavailable`.

---

## 5. Configuración de la instalación

Los formularios se traducen al formato del motor inyectando valores en
`config.py` y `demand.py` (el motor no acepta un objeto de config):

| UI | Motor (`config.py`) |
|---|---|
| `location.municipality/region/latitude/longitude` | `MUNICIPIO`, `PROVINCIA`, `LATITUD`, `LONGITUD` |
| `pv.panels`, `pv.panel_power_w` | `NUM_PANELES`, `PANEL_POTENCIA_W` (+ recálculo de kWp) |
| `pv.inclination_deg`, `pv.azimuth_deg` | `PANEL_INCLINACION_GRADOS`, `PANEL_AZIMUT_GRADOS` |
| `inverter.*` | `INVERSOR_*` |
| `battery.units/capacity_kwh_unit` | `NUM_BATERIAS`, `BATERIA_ENERGIA_KWH_UNIDAD` (+ agregados) |
| `battery.min_soc/max_soc` | `SOC_MIN_NORMAL`, `SOC_MAX_NORMAL` |
| `home.adults/children` | `demand.NUM_ADULTOS`, `NUM_NINOS`, `NUM_OCUPANTES` |
| `home.grid_priority_over_battery` | `demand.PRIORIDAD_RED_SOBRE_BATERIA` |
| `loads.lavadora.*` | `demand.LAVADORA` |

Sólo se exponen parámetros que el motor utiliza realmente.

---

## 6. Pruebas

```bash
make test
```

- **Python** (`tests/test_adapter.py`): validación, contrato, agrupación
  de acciones, códigos de razón, clasificación de errores, credenciales y
  **inyección de configuración contra los módulos reales**
  (`config.py`, `demand.py`, sin red).
- **Humo** (`tests/smoke_adapter.py`): ejecuta `run_plan` con un motor de
  prueba y escribe `tests/fixtures/plan_result.json`.
- **JS** (`tests/js/run.mjs`): formato, razones, persistencia y `mapper`
  (contra datos sintéticos **y** contra el fixture del contrato real).

---

## 7. Limitaciones conocidas del MVP

1. **Pyodide desde CDN o copia local.** El runtime se carga desde
   `https://cdn.jsdelivr.net/pyodide/v0.27.8/full/` (configurable en
   `mvp/js/config.js`). `make vendor-pyodide` descarga el runtime **y los
   paquetes del motor** (micropip, pytz, packaging, requests y sus
   dependencias, pyodide-http —desde la distribución de Pyodide— y
   python-dotenv desde PyPI) a `mvp/vendor/pyodide/`, generando
   `local-packages.json`. Con esa copia el arranque es **sin red**.
   Detalle importante: los `.whl` deben quedar **junto a** `pyodide.js`
   (Pyodide resuelve `indexURL + file_name`); el CDN tampoco usa
   `full/packages/`, sirve los `.whl` en `full/<archivo>`.
2. **Dependencias Python con micropip.** `python-dotenv`, `requests` y
   `pyodide-http` se instalan desde PyPI en el primer arranque (el motor
   necesita Internet para AEMET/PVGIS/ESIOS de todos modos).
3. **Caché en memoria.** El sistema de archivos de Pyodide es efímero:
   la caché del motor no persiste entre sesiones.
4. **Procedencia de la caché.** El motor no expone si un dato vino de
   caché o de red; el adaptador informa `updated/cached` según `refresh`
   y no inventa información por fuente (`sources.from_cache = null`).
5. **Cargas.** El MVP expone Lavadora + ocupación; el resto de cargas
   conserva los valores por defecto del motor.
6. **Secretos** en `localStorage` (ver §4).
7. **Modo demostración.** Ejecuta el motor real con fuentes de datos
   simuladas (ver §2). No es una simulación paralela en JavaScript.

---

## 8. Estructura de la navegación

```
ARRANQUE ──¿configurado?── no ─▶ BIENVENIDA → ONBOARDING (8 pasos)
               │ sí
               ▼
             HOY  ⇄  SEMANA  ⇄  ENERGÍA  ⇄  AJUSTES
               └─ DETALLE (¿Por qué?)
```

- La gestión de pantallas es propia (`Screen` en `mvp/js/app.js`) sobre
  `#app`, para no depender del comportamiento frágil de `ons-navigator`
  con páginas generadas dinámicamente.
- Se usan componentes **OnsenUI** (`ons-button`, `ons-*`) y **jQuery**
  para el DOM y los eventos, conforme a `AGENTS.md`.

---

## 9. Convenciones

- Ejecutar `make` desde `android-app/`.
- Código y textos de la UI en **español**.
- No añadir campos de configuración que el motor no utilice.
- No versionar credenciales, keystores ni `mytoken.env`.
