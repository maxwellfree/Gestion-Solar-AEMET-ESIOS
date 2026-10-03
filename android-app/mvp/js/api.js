/**
 * api.js
 * ======
 *
 * Capa de aplicación: coordina la persistencia (store), el motor
 * (engine) y las peticiones de la interfaz. Los ViewModels/pantallas
 * hablan con esta API, nunca directamente con Pyodide
 * (ARCHITECTURE.md, §10-11).
 */

import * as store from "./store.js";
import { createPyodideEngine, createDemoEngine, isPyodideAvailable } from "./engine.js";

export class SolarApi {
  /**
   * @param {object} [options]
   * @param {"auto"|"pyodide"|"demo"} [options.mode]
   * @param {function} [options.onStatus]  callback(mensaje) para la UI.
   * @param {object}   [options.storage]   almacenamiento inyectable.
   */
  constructor(options = {}) {
    this.mode = options.mode || "auto";
    this.demo = this.mode === "demo";
    this.onStatus = options.onStatus || (() => {});
    this.storage = options.storage;
    this.engine = null;
    this.enginePromise = null;
    this.fellBackToDemo = false;
    this.lastResult = null;
  }

  // --- Configuración y credenciales -------------------------------

  getConfig() {
    return store.loadConfig(this.storage);
  }

  saveConfig(config) {
    return store.saveConfig(config, this.storage);
  }

  getCredentials() {
    return store.loadCredentials(this.storage);
  }

  saveCredentials(credentials) {
    return store.saveCredentials(credentials, this.storage);
  }

  clearCredentials() {
    return store.clearCredentials(this.storage);
  }

  resetConfig() {
    return store.resetConfig(this.storage);
  }

  isConfigured() {
    return store.isConfigured(this.getConfig(), this.getCredentials());
  }

  // --- Motor -------------------------------------------------------

  async ensureEngine() {
    if (this.engine) return this.engine;
    if (this.enginePromise) return this.enginePromise;

    this.enginePromise = (async () => {
      // Se intenta SIEMPRE el motor Python real. En modo demostración el
      // propio motor Python usa datos de ejemplo (demo=true); sólo si
      // Pyodide no está disponible se recurre a datos sintéticos en JS.
      try {
        this.engine = await createPyodideEngine({ onProgress: this.onStatus });
        this.onStatus(
          this.demo ? "Motor Python listo (modo demostración)." : "Motor Python listo."
        );
      } catch (err) {
        if (this.mode === "pyodide") throw err;
        this.fellBackToDemo = true;
        this.demo = true;
        this.onStatus("Motor Python no disponible: usando datos de ejemplo sintéticos.");
        this.engine = createDemoEngine();
      }
      return this.engine;
    })();

    return this.enginePromise;
  }

  async pyodideAvailable() {
    return isPyodideAvailable();
  }

  // --- Operaciones -------------------------------------------------

  /**
   * Ejecuta el plan energético.
   * @returns {Promise<object>} resultado con el contrato real.
   */
  async runPlan({ soc, refresh = false, estrategia = null } = {}) {
    const engine = await this.ensureEngine();
    const config = this.getConfig();
    const credentials = this.getCredentials();

    const result = await engine.runPlan({
      config,
      credentials,
      soc,
      refresh,
      estrategia: estrategia || config.strategy,
      demo: this.demo,
    });

    this.lastResult = result;
    return result;
  }

  async validateCredential(source, value) {
    const engine = await this.ensureEngine();
    return engine.validateCredential(source, value);
  }

  async dependencyProbe() {
    const engine = await this.ensureEngine();
    return engine.dependencyProbe();
  }
}
