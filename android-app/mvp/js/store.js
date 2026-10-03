/**
 * store.js
 * ========
 *
 * Persistencia local de la configuración y de los secretos.
 *
 * Se separan deliberadamente (CONFIGURATION_AND_CREDENTIALS.md, §1):
 *
 *     CONFIGURACIÓN  -> clave "gs.config.v1"
 *     CREDENCIALES   -> clave "gs.credentials.v1"
 *
 * Nota MVP: se usa localStorage. El almacenamiento cifrado propio de
 * Android (Keystore) queda para una fase posterior; aun así las
 * credenciales nunca se mezclan con la configuración ni con los logs.
 *
 * El almacenamiento es inyectable para poder probarse con node.
 */

export const CONFIG_KEY = "gs.config.v1";
export const CREDENTIALS_KEY = "gs.credentials.v1";

export function defaultConfig() {
  return {
    schema_version: 1,
    location: {
      country: "España",
      region: "Granada",
      municipality: "Maracena",
      latitude: null,
      longitude: null,
    },
    pv: {
      panels: 10,
      panel_power_w: 605,
      inclination_deg: 33,
      azimuth_deg: 0,
    },
    inverter: {
      manufacturer: "Deye",
      model: "SUN-6K-SG05LP1-EU-AM2-P",
      nominal_kw: 6,
    },
    battery: {
      manufacturer: "Deye",
      model: "SE-G5.1 Pro-B",
      units: 2,
      capacity_kwh_unit: 5.12,
      min_soc: 0.2,
      max_soc: 0.85,
      efficiency: 0.9,
    },
    home: {
      adults: 2,
      children: 3,
      base_power_kw: 0.18,
      grid_priority_over_battery: true,
    },
    loads: {
      lavadora: {
        enabled: true,
        power_kw: 1.0,
        duration_h: 1.5,
        flexible: true,
        window: ["11:00", "17:00"],
      },
    },
    strategy: "sostenible_predictiva",
  };
}

export function defaultCredentials() {
  return { aemet_api_key: "", esios_token: "" };
}

/** Fusiona `patch` sobre `base` respetando objetos anidados. */
export function deepMerge(base, patch) {
  if (Array.isArray(base) || Array.isArray(patch)) return patch;
  if (typeof base !== "object" || base === null) return patch;
  if (typeof patch !== "object" || patch === null) return patch;

  const out = { ...base };
  for (const key of Object.keys(patch)) {
    out[key] = deepMerge(base[key], patch[key]);
  }
  return out;
}

function getStorage(storage) {
  if (storage) return storage;
  if (typeof localStorage !== "undefined") return localStorage;
  return memoryStorage();
}

/** Almacenamiento en memoria (usado en tests y como reserva). */
export function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

export function loadConfig(storage) {
  const store = getStorage(storage);
  try {
    const raw = store.getItem(CONFIG_KEY);
    if (!raw) return defaultConfig();
    return deepMerge(defaultConfig(), JSON.parse(raw));
  } catch (err) {
    return defaultConfig();
  }
}

export function saveConfig(config, storage) {
  const store = getStorage(storage);
  store.setItem(CONFIG_KEY, JSON.stringify(config));
  return config;
}

export function resetConfig(storage) {
  const store = getStorage(storage);
  store.removeItem(CONFIG_KEY);
  return defaultConfig();
}

export function loadCredentials(storage) {
  const store = getStorage(storage);
  try {
    const raw = store.getItem(CREDENTIALS_KEY);
    if (!raw) return defaultCredentials();
    return deepMerge(defaultCredentials(), JSON.parse(raw));
  } catch (err) {
    return defaultCredentials();
  }
}

export function saveCredentials(credentials, storage) {
  const store = getStorage(storage);
  store.setItem(CREDENTIALS_KEY, JSON.stringify(credentials));
  return credentials;
}

export function clearCredentials(storage) {
  const store = getStorage(storage);
  store.removeItem(CREDENTIALS_KEY);
  return defaultCredentials();
}

/** ¿Están las credenciales presentes? */
export function hasCredentials(credentials) {
  return Boolean(credentials && credentials.aemet_api_key && credentials.esios_token);
}

/** ¿La configuración mínima está completa? */
export function hasConfig(config) {
  if (!config) return false;
  const mun = config.location && config.location.municipality;
  const panels = config.pv && Number(config.pv.panels) > 0;
  const units = config.battery && Number(config.battery.units) > 0;
  return Boolean(mun && panels && units);
}

export function isConfigured(config, credentials) {
  return hasConfig(config) && hasCredentials(credentials);
}

/**
 * Valida un paso del onboarding.
 * Devuelve un array de mensajes; vacío significa "correcto".
 */
export function validateStep(step, data) {
  const errors = [];
  if (step === "credentials") {
    if (!data.aemet_api_key) errors.push("Falta la clave de AEMET.");
    if (!data.esios_token) errors.push("Falta el token de ESIOS.");
  }
  if (step === "location") {
    if (!data.location || !data.location.municipality) errors.push("Indica el municipio.");
  }
  if (step === "pv") {
    const pv = data.pv || {};
    if (!(Number(pv.panels) > 0)) errors.push("El número de paneles debe ser mayor que cero.");
    if (!(Number(pv.panel_power_w) > 0)) errors.push("La potencia del panel debe ser mayor que cero.");
  }
  if (step === "inverter") {
    if (!(Number(data.inverter && data.inverter.nominal_kw) > 0)) errors.push("Indica la potencia nominal del inversor.");
  }
  if (step === "battery") {
    const b = data.battery || {};
    if (!(Number(b.units) > 0)) errors.push("Indica el número de baterías.");
    if (!(Number(b.capacity_kwh_unit) > 0)) errors.push("Indica la capacidad por batería.");
    if (Number(b.min_soc) >= Number(b.max_soc)) errors.push("El SOC mínimo debe ser menor que el máximo.");
  }
  if (step === "home") {
    const h = data.home || {};
    if (Number(h.adults) < 0 || Number(h.children) < 0) errors.push("La ocupación no puede ser negativa.");
    if (Number(h.adults) + Number(h.children) <= 0) errors.push("Indica al menos un ocupante.");
  }
  return errors;
}

export const __test__ = { getStorage };
