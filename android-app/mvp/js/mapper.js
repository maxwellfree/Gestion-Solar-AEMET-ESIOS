/**
 * mapper.js
 * =========
 *
 * Convierte el contrato de salida del adaptador Python
 * (`run_plan(...) -> dict`) en modelos de presentación.
 *
 * Flujo (UI_MVP.md, §27):
 *
 *     Python -> PlanResultDto -> mapPlan() -> modelos UI -> pantallas
 *
 * Es un módulo puro: no toca el DOM ni el motor. Verificable con node.
 */

import {
  formatSoc,
  formatEnergy,
  formatPower,
  formatPrice,
  formatPercent,
  formatNumber,
  formatTimeWindow,
  formatUpdated,
  formatDayLabel,
} from "./format.js";
import { reasonText, severityLabel, freshnessInfo } from "./reasons.js";

/** Modelo de tarjeta de recomendación (UI_MVP.md, §9). */
function toRecommendation(action) {
  const reasons = (action.reasons || []).map((r) => ({
    code: r.code,
    text: reasonText(r.code),
    detail: r.detail || null,
  }));

  return {
    id: action.id,
    kind: action.kind || "solar",
    title: action.title,
    timeWindow: formatTimeWindow(action.start, action.end),
    start: action.start || null,
    end: action.end || null,
    summary: action.summary || "",
    reasonPreview: reasons.length ? reasons[0].text : null,
    severity: action.severity || "normal",
    severityLabel: severityLabel(action.severity),
    reasons,
    metrics: action.metrics || {},
    data: action.data || {},
  };
}

export function mapPlan(result) {
  if (!result || result.status === "error") {
    return { status: "error", error: mapError(result) };
  }

  const freshness = freshnessInfo(result.cache_status);
  const actions = (result.today_actions || []).map(toRecommendation);

  return {
    status: "ok",
    updatedAt: result.updated_at || null,
    updatedLabel: formatUpdated(result.updated_at),
    freshness: {
      status: result.cache_status || "unavailable",
      label: freshness.label,
      icon: freshness.icon,
    },
    warnings: result.warnings || [],
    soc: {
      value: result.input && result.input.soc,
      label: formatSoc(result.input && result.input.soc),
    },
    strategy: result.input && result.input.estrategia,
    municipio: result.input && result.input.municipio,
    primary: actions.length ? actions[0] : null,
    others: actions.slice(1),
    week: mapWeek(result.weekly_plan),
    energy: mapEnergy(result),
    raw: result,
  };
}

export function mapWeek(weeklyPlan) {
  return (weeklyPlan || []).map((day) => ({
    date: day.date,
    label: formatDayLabel(day.date),
    weekday: day.weekday || null,
    solarQuality: day.solar_quality || null,
    confidence: day.confidence || null,
    temps: day.temps || {},
    precip: day.precip,
    actions: (day.actions || []).map(toRecommendation),
  }));
}

export function mapEnergy(result) {
  const pv = result.pv || {};
  const demand = result.demand || {};
  const energy = result.energy || {};
  const prices = result.prices || {};
  const strategic = result.strategic || {};

  const balance = energy.balance_metrics || {};
  const plan = energy.plan_metrics || {};
  const pico = pv.pico || null;

  return {
    socLabel: formatSoc(result.input && result.input.soc),
    pvEnergyLabel: formatEnergy(pv.energia_kwh),
    pvEnergy: pv.energia_kwh,
    pvPeakLabel: pico ? `${formatPower(pico.potencia_fv_kw)} a las ${pico.hora}` : "—",
    demandEnergyLabel: formatEnergy(demand.energia_diaria_kwh),
    demandBaseLabel: formatPower(demand.potencia_base_kw),
    pvProfile: pv.perfil || [],
    demandProfile: demand.perfil || [],
    balanceMetrics: [
      metric("Energía FV", formatEnergy(balance.energia_fv_kwh)),
      metric("Energía demanda", formatEnergy(balance.energia_demanda_kwh)),
      metric("Autoconsumo", balance.autoconsumo_pct == null ? "—" : formatPercent(balance.autoconsumo_pct)),
      metric("Excedente", formatEnergy(balance.energia_excedente_kwh)),
    ],
    planMetrics: [
      metric("SOC final", formatSoc(plan.soc_final)),
      metric("Energía cargada", formatEnergy(plan.energia_cargada_bateria_kwh)),
      metric("Energía descargada", formatEnergy(plan.energia_descargada_bateria_kwh)),
      metric("Ciclos equivalentes", formatNumber(plan.ciclos_equivalentes, 3)),
      metric("Compra red", formatEnergy(plan.compra_red_kwh)),
      metric("Venta red", formatEnergy(plan.venta_red_kwh)),
    ],
    priceMin: prices.min_compra ? priceEntry("Compra mínima", prices.min_compra, "compra") : null,
    priceMax: prices.max_compra ? priceEntry("Compra máxima", prices.max_compra, "compra") : null,
    priceSell: prices.max_venta ? priceEntry("Venta máxima", prices.max_venta, "venta") : null,
    prices: prices.serie || [],
    strategicActions: strategic.acciones || [],
    strategicReasons: strategic.razones || [],
  };
}

function metric(label, value) {
  return { label, value };
}

function priceEntry(label, entry, key) {
  return {
    label,
    hora: entry.hora,
    value: formatPrice(entry[key]),
  };
}

export function mapError(result) {
  const error = (result && result.error) || {};
  const category = error.category || "ENGINE_ERROR";
  const messages = {
    CONFIGURATION_ERROR: {
      title: "Configuración incompleta",
      action: "Revisa los datos de la instalación en Ajustes.",
    },
    AUTHENTICATION_ERROR: {
      title: "Credencial no aceptada",
      action: "Revisa las credenciales de AEMET y ESIOS.",
    },
    NETWORK_ERROR: {
      title: "Sin conexión",
      action: "Comprueba tu conexión a Internet o vuelve a intentarlo.",
    },
    SERVICE_UNAVAILABLE: {
      title: "Servicio no disponible",
      action: "La fuente de datos no responde. Inténtalo de nuevo más tarde.",
    },
    INVALID_RESPONSE: {
      title: "Respuesta no válida",
      action: "Los datos recibidos no tienen el formato esperado.",
    },
    ENGINE_ERROR: {
      title: "Error del motor energético",
      action: "No se ha podido calcular el plan. Vuelve a intentarlo.",
    },
  };
  const info = messages[category] || messages.ENGINE_ERROR;
  return {
    category,
    title: info.title,
    message: error.message || "Error desconocido.",
    action: info.action,
    source: error.source || null,
  };
}

export const __test__ = { toRecommendation, metric, priceEntry };
