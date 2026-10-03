/**
 * config.js
 * =========
 *
 * Configuración de empaquetado del MVP. Puede ajustarse sin tocar el
 * código de la aplicación.
 */

export const CONFIG = {
  /**
   * Índice de Pyodide.
   *
   * Por defecto se carga el runtime desde el CDN oficial. Si se desea un
   * funcionamiento sin depender de la red, ejecutar `make vendor-pyodide`
   * y dejar la ruta local en primer lugar.
   */
  pyodideIndexes: [
    "./vendor/pyodide/",
    "https://cdn.jsdelivr.net/pyodide/v0.27.8/full/",
  ],

  /** Directorio con los .py del motor (generado por `make mvp`). */
  pythonUrl: "./python/",

  /** Paquetes Python a instalar con micropip (además de micropip/pytz). */
  pythonPackages: ["python-dotenv", "requests", "pyodide-http"],

  /** Paquetes base cargados con loadPackage. */
  basePackages: ["micropip", "pytz"],
};
