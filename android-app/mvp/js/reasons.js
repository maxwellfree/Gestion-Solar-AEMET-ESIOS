/**
 * reasons.js
 * ==========
 *
 * Traducción de códigos de razón del motor a texto en español
 * (UI_MVP.md, §10-11).
 *
 * Android traduce códigos estables; NO recalcula la lógica para
 * explicar una decisión. El conjunto de códigos se corresponde con los
 * emitidos por android_adapter.py.
 */

export const REASON_TEXT = {
  HIGH_PV_FORECAST: "Se prevé una producción fotovoltaica elevada.",
  LOW_PV_FORECAST: "Se prevé una producción fotovoltaica reducida.",
  SUFFICIENT_SOC: "El estado de carga de la batería es suficiente.",
  LOW_SOC: "El estado de carga de la batería está por debajo de la ventana sostenible.",
  FLEXIBLE_LOAD: "Esta carga está configurada como flexible.",
  FLEXIBLE_LOADS_AVAILABLE: "Existen cargas flexibles que pueden desplazarse a las horas solares.",
  PRICE_WINDOW: "La franja coincide con un precio de compraventa relevante.",
  EXCESS_SURPLUS: "Se prevé excedente de energía respecto al consumo.",
  BATTERY_RESERVE: "Se preserva una reserva de batería para más adelante.",
  GRID_PRIORITY: "Se prioriza la red frente a ciclos marginales de batería.",
  ENGINE_DECISION: "Decisión calculada por el motor energético.",
};

export const SEVERITY_LABEL = {
  normal: "Informativo",
  important: "Recomendado",
  warning: "Atención",
};

export const FRESHNESS_LABEL = {
  updated: { label: "Datos actualizados", icon: "✓" },
  cached: { label: "Usando datos guardados", icon: "◷" },
  stale: { label: "Datos desactualizados", icon: "⚠" },
  unavailable: { label: "Datos no disponibles", icon: "✕" },
};

export function reasonText(code) {
  return REASON_TEXT[code] || "Decisión calculada por el motor energético.";
}

export function severityLabel(severity) {
  return SEVERITY_LABEL[severity] || SEVERITY_LABEL.normal;
}

export function freshnessInfo(status) {
  return FRESHNESS_LABEL[status] || FRESHNESS_LABEL.unavailable;
}
