/**
 * engine.js
 * =========
 *
 * Integración Android <-> Python mediante Pyodide (ARCHITECTURE.md, §5).
 *
 * Oculta el mecanismo de integración tras una interfaz estable, igual que
 * el `PythonGateway` conceptual de la documentación:
 *
 *     interface PythonGateway {
 *         runPlan(config, credentials, soc, refresh, estrategia) -> PlanResult
 *         validateCredential(source, value) -> {source, status, message}
 *         dependencyProbe() -> {modulo: "ok"|error}
 *     }
 *
 * Implementaciones:
 *
 *   * `createPyodideEngine(...)`  -> motor Python real embebido;
 *   * `createDemoEngine()`        -> datos sintéticos (sin red/credenciales).
 */

import { buildDemoResult } from "./demo.js";
import { CONFIG } from "./config.js";

export const PYTHON_URL = CONFIG.pythonUrl;
export const PYTHON_PACKAGES = CONFIG.pythonPackages;
export const BASE_PACKAGES = CONFIG.basePackages;
export const PYODIDE_INDEXES = CONFIG.pyodideIndexes;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing && existing.dataset.loaded === "1") return resolve();
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => {
      script.dataset.loaded = "1";
      resolve();
    };
    script.onerror = () => reject(new Error(`No se pudo cargar ${src}`));
    document.head.appendChild(script);
  });
}

/**
 * Crea el motor Python real embebido en Pyodide.
 *
 * @param {object} options
 * @param {function} [options.onProgress]      mensajes de progreso (UI).
 * @param {string}   [options.pyodideUrl]       ruta del runtime Pyodide.
 * @param {string}   [options.pythonUrl]        ruta de los .py del motor.
 * @param {string}   [options.pythonPackages]   paquetes pip adicionales.
 */
export async function createPyodideEngine(options = {}) {
  const {
    onProgress = () => {},
    pyodideIndexes = PYODIDE_INDEXES,
    pythonUrl = PYTHON_URL,
    pythonPackages = PYTHON_PACKAGES,
    basePackages = BASE_PACKAGES,
  } = options;

  let lastError = null;

  // Se prueban los índices en orden (CDN, luego copia local si existe).
  for (const indexUrl of pyodideIndexes) {
    try {
      onProgress(`Preparando entorno Python (${indexUrl})…`);
      await loadScript(`${indexUrl}pyodide.js`);

      if (typeof globalThis.loadPyodide !== "function") {
        throw new Error("Pyodide no está disponible.");
      }

      const pyodide = await globalThis.loadPyodide({ indexURL: indexUrl });

      onProgress("Cargando módulos base…");
      await pyodide.loadPackage(basePackages);

      const micropip = pyodide.pyimport("micropip");

      onProgress("Instalando dependencias del motor…");

      // Si hay copia local (make vendor-pyodide) se instalan primero las
      // wheels locales; sólo si no existen se recurre a la red.
      let localWheels = {};
      try {
        const resp = await fetch(`${indexUrl}local-packages.json`);
        if (resp.ok) localWheels = await resp.json();
      } catch (err) {
        /* local-packages.json es opcional */
      }

      for (const pkg of pythonPackages) {
        const localFile = localWheels && localWheels[pkg];
        if (localFile) {
          try {
            const url = new URL(`${indexUrl}${localFile}`, document.baseURI).href;
            await micropip.install(url);
            continue;
          } catch (err) {
            /* si falla la wheel local, se intenta desde la red */
          }
        }
        try {
          await micropip.install(pkg);
        } catch (err) {
          onProgress(`Aviso: no se pudo instalar ${pkg}`);
        }
      }

      onProgress("Activando acceso HTTP…");
      await pyodide.runPythonAsync(`
try:
    import pyodide_http
    pyodide_http.patch_all()
except Exception:
    pass
`);

      onProgress("Cargando motor energético…");
      await installEngineFiles(pyodide, pythonUrl);

      return new PyodideEngine(pyodide);
    } catch (err) {
      lastError = err;
      onProgress(`No se pudo usar ${indexUrl}: ${err.message || err}`);
    }
  }

  throw lastError || new Error("No se pudo inicializar Pyodide.");
}

async function installEngineFiles(pyodide, pythonUrl) {
  let manifest;
  try {
    const response = await fetch(`${pythonUrl}manifest.json`);
    if (!response.ok) throw new Error(String(response.status));
    manifest = await response.json();
  } catch (err) {
    throw new Error(
      "No se encuentra python/manifest.json. Ejecuta «make mvp» para generar el runtime."
    );
  }

  pyodide.FS.mkdirTree("/engine");
  for (const file of manifest.files) {
    const response = await fetch(`${pythonUrl}${file}`);
    if (!response.ok) throw new Error(`No se pudo cargar ${file}`);
    const text = await response.text();
    pyodide.FS.writeFile(`/engine/${file}`, text);
  }

  await pyodide.runPythonAsync(`
import sys
if "/engine" not in sys.path:
    sys.path.insert(0, "/engine")
import android_adapter
`);

  return manifest;
}

class PyodideEngine {
  constructor(pyodide) {
    this.kind = "pyodide";
    this.pyodide = pyodide;
  }

  async runPlan({ config, credentials, soc, refresh = false, estrategia = null, demo = false, pvgis = null }) {
    const payload = JSON.stringify({ config, credentials, soc, refresh, estrategia, demo, pvgis });
    this.pyodide.globals.set("__gs_payload", payload);
    try {
      const output = await this.pyodide.runPythonAsync(`
import json
import android_adapter
_payload = json.loads(__gs_payload)
_result = android_adapter.run_plan(
    config=_payload.get("config"),
    credentials=_payload.get("credentials"),
    soc=_payload.get("soc"),
    refresh=bool(_payload.get("refresh")),
    estrategia=_payload.get("estrategia"),
    demo=bool(_payload.get("demo")),
    pvgis_series=_payload.get("pvgis"),
)
android_adapter.dumps(_result)
`);
      return JSON.parse(output);
    } finally {
      this.pyodide.globals.delete("__gs_payload");
    }
  }

  async validateCredential(source, value) {
    this.pyodide.globals.set("__gs_source", source);
    this.pyodide.globals.set("__gs_value", value);
    try {
      const output = await this.pyodide.runPythonAsync(`
import json
import android_adapter
json.dumps(android_adapter.validate_credential(__gs_source, __gs_value))
`);
      return JSON.parse(output);
    } catch (err) {
      return { source, status: "service_unavailable", message: String(err) };
    } finally {
      this.pyodide.globals.delete("__gs_source");
      this.pyodide.globals.delete("__gs_value");
    }
  }

  async dependencyProbe() {
    const output = await this.pyodide.runPythonAsync(`
import json
import android_adapter
json.dumps(android_adapter.dependency_probe())
`);
    return JSON.parse(output);
  }
}

/**
 * Motor de demostración de reserva (SIN Python).
 *
 * Sólo se usa si Pyodide no está disponible. El modo demostración normal
 * ejecuta el motor Python real con datos de ejemplo (demo=true), de modo
 * que el cálculo lo realiza el motor.
 */
export function createDemoEngine() {
  return {
    kind: "demo-fallback",
    async runPlan({ config, soc, refresh = false }) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      return buildDemoResult(config, soc, refresh);
    },
    async validateCredential(source) {
      await new Promise((resolve) => setTimeout(resolve, 350));
      return { source, status: "valid", message: null };
    },
    async dependencyProbe() {
      return { demo: "ok" };
    },
  };
}

/** ¿Parece que algún runtime Pyodide está disponible? */
export async function isPyodideAvailable(pyodideIndexes = PYODIDE_INDEXES) {
  for (const indexUrl of pyodideIndexes) {
    try {
      const response = await fetch(`${indexUrl}pyodide.js`, { method: "HEAD" });
      if (response.ok) return true;
    } catch (err) {
      /* siguiente índice */
    }
  }
  return false;
}
