/**
 * pvgis.js — obtención de la serie PVGIS fuera del navegador
 * ==========================================================
 *
 * PVGIS (`re.jrc.ec.europa.eu`) NO envía cabeceras CORS, por lo que
 * `requests` dentro de Pyodide (que va sobre XHR) no puede consultarlo
 * desde el WebView. En la app Android (Capacitor) se usa el plugin nativo
 * **CapacitorHttp**, que hace la petición con las librerías nativas y por
 * tanto no está sujeto a CORS.
 *
 * Este módulo NO calcula nada del motor: sólo obtiene la serie horaria en
 * el formato de PVGIS (`outputs.hourly`) y, si hace falta, las
 * coordenadas, y se las entrega al adaptador para que el motor las
 * procese (perfil_referencia_fecha, irradiancia, temperatura, balance…).
 *
 * En un navegador normal (sin Capacitor) estas funciones devuelven `null`
 * y el adaptador recurre a su respaldo de cielo despejado.
 */

/** URL y parámetros, idénticos a los del motor (solar.py). */
export const PVGIS_URL = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc";
export const NOMINATIM_URL = "https://nominatim.openstreetmap.org/search";
export const PVGIS_ANIO_INICIO = 2019;
export const PVGIS_ANIO_FIN = 2023;

/** Devuelve el plugin nativo CapacitorHttp si está disponible. */
export function nativeHttp() {
  const cap = typeof window !== "undefined" ? window.Capacitor : undefined;
  const plugin = cap && cap.Plugins && cap.Plugins.CapacitorHttp;
  return plugin && typeof plugin.get === "function" ? plugin : null;
}

/** ¿Se puede usar HTTP nativo (app Android/IOs)? */
export function isNativeHttpAvailable() {
  const cap = typeof window !== "undefined" ? window.Capacitor : undefined;
  if (!nativeHttp()) return false;
  return cap.isNativePlatform ? cap.isNativePlatform() : true;
}

/**
 * Parámetros de la consulta PVGIS, iguales a los del motor.
 * `potencia_kwp = nº paneles × potencia del panel / 1000`.
 */
export function buildPvgisParams(config) {
  const pv = (config && config.pv) || {};
  const kwp = ((Number(pv.panels) || 0) * (Number(pv.panel_power_w) || 0)) / 1000;

  return {
    startyear: PVGIS_ANIO_INICIO,
    endyear: PVGIS_ANIO_FIN,
    pvcalculation: 1,
    peakpower: kwp,
    loss: 0,
    angle: Number(pv.inclination_deg) || 0,
    aspect: Number(pv.azimuth_deg) || 0,
    outputformat: "json",
  };
}

async function nativeGetJson(plugin, url, params, headers) {
  const resp = await plugin.get({
    url,
    params,
    headers: headers || { Accept: "application/json" },
    connectTimeout: 20000,
    readTimeout: 60000,
  });
  if (resp && resp.status && resp.status >= 400) {
    throw new Error(`HTTP ${resp.status}`);
  }
  let data = resp && resp.data;
  if (typeof data === "string") {
    try {
      data = JSON.parse(data);
    } catch (err) {
      return null;
    }
  }
  return data || null;
}

/**
 * Resuelve latitud/longitud. Prioridad: configuración → Nominatim (nativo).
 * @returns {Promise<{latitude:number, longitude:number}|null>}
 */
export async function resolveCoordinates(config) {
  const plugin = nativeHttp();
  if (!plugin) return null;

  const loc = (config && config.location) || {};
  if (loc.latitude != null && loc.longitude != null) {
    return { latitude: Number(loc.latitude), longitude: Number(loc.longitude) };
  }

  const consulta = [loc.municipality, loc.region, loc.country || "España"]
    .filter(Boolean)
    .join(", ");
  if (!consulta) return null;

  try {
    const data = await nativeGetJson(
      plugin,
      NOMINATIM_URL,
      { q: consulta, format: "json", limit: 1, countrycodes: "es" },
      { "User-Agent": "GestionSolarAEMET/1.0 PV-research", Accept: "application/json" }
    );
    if (!Array.isArray(data) || data.length === 0) return null;
    return { latitude: Number(data[0].lat), longitude: Number(data[0].lon) };
  } catch (err) {
    return null;
  }
}

/**
 * Obtiene la serie horaria real de PVGIS mediante HTTP nativo.
 *
 * @returns {Promise<{serie:Array, coordinates:object}|null>} `null` si no
 *   hay HTTP nativo o la consulta falla (el adaptador usará su respaldo).
 */
export async function fetchPvgisSeries(config) {
  const plugin = nativeHttp();
  if (!plugin) return null;

  const coordinates = await resolveCoordinates(config);
  if (!coordinates) return null;

  try {
    const params = {
      ...buildPvgisParams(config),
      lat: coordinates.latitude,
      lon: coordinates.longitude,
    };
    const data = await nativeGetJson(plugin, PVGIS_URL, params);
    const serie = data && data.outputs && data.outputs.hourly;
    if (!Array.isArray(serie) || serie.length === 0) return null;
    return { serie, coordinates };
  } catch (err) {
    return null;
  }
}
