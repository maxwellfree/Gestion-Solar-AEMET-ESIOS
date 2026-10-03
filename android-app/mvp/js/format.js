/**
 * format.js
 * =========
 *
 * Formateo centralizado de magnitudes (UI_MVP.md, §30).
 *
 * Toda la interfaz debe usar estas funciones para no mezclar unidades
 * (W/kW, Wh/kWh, 0.62/62 %). Módulo sin dependencias, verificable con node.
 */

const LOCALE = "es-ES";

function num(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return n;
}

/** Número con separador decimal local y nº de decimales fijo. */
export function formatNumber(value, digits = 1) {
  const n = num(value);
  if (n === null) return "—";
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

/** SOC: internamente 0..1, se muestra como porcentaje. */
export function formatSoc(soc) {
  const n = num(soc);
  if (n === null) return "—";
  return `${Math.round(n * 100)} %`;
}

/** Energía en kWh. */
export function formatEnergy(kwh, digits = 1) {
  const n = num(kwh);
  if (n === null) return "—";
  return `${formatNumber(n, digits)} kWh`;
}

/** Potencia en kW. */
export function formatPower(kw, digits = 1) {
  const n = num(kw);
  if (n === null) return "—";
  return `${formatNumber(n, digits)} kW`;
}

/** Precio en €/kWh. */
export function formatPrice(value, digits = 3) {
  const n = num(value);
  if (n === null) return "—";
  return `${formatNumber(n, digits)} €/kWh`;
}

/** Importe en €. */
export function formatEuro(value, digits = 2) {
  const n = num(value);
  if (n === null) return "—";
  return `${formatNumber(n, digits)} €`;
}

/** Porcentaje ya expresado 0..100. */
export function formatPercent(value, digits = 0) {
  const n = num(value);
  if (n === null) return "—";
  return `${formatNumber(n, digits)} %`;
}

/** Ventana horaria "12:00 – 15:00". */
export function formatTimeWindow(start, end) {
  if (!start && !end) return null;
  if (!start) return `hasta ${end}`;
  if (!end) return `desde ${start}`;
  return `${start} – ${end}`;
}

/** "08:15" a partir de un ISO. */
export function formatUpdated(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit" }).format(d);
}

/** "dom 27 sept" a partir de "2026-09-27". */
export function formatDayLabel(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return String(iso);
  return new Intl.DateTimeFormat(LOCALE, { weekday: "short", day: "numeric", month: "short" }).format(d);
}

/** "21 de septiembre de 2026". */
export function formatLongDate(iso) {
  if (!iso) return "—";
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return String(iso);
  return new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long", year: "numeric" }).format(d);
}

/** Enmascara un secreto: "••••••••ABCD". */
export function maskSecret(value, visible = 4) {
  if (!value) return "";
  const text = String(value);
  if (text.length <= visible) return "•".repeat(text.length);
  return "•".repeat(Math.max(4, text.length - visible)) + text.slice(-visible);
}

export const __test__ = { num };
