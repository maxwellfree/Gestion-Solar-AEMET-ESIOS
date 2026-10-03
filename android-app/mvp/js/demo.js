/**
 * demo.js
 * =======
 *
 * Resultado de ejemplo con la MISMA forma que el contrato real del
 * adaptador. Se usa como "FakePythonGateway" (DEVELOPMENT_PLAN.md, §26)
 * para poder desarrollar y probar la interfaz sin credenciales ni red.
 *
 * No contiene ninguna lógica energética real: son datos sintéticos.
 */

const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];

function isoPlus(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function hourlyPv(h) {
  if (h < 8 || h > 19) return 0;
  const x = (h - 13.5) / 4.5;
  return Math.max(0, 5.6 * Math.exp(-x * x));
}

export function buildDemoResult(config = {}, soc = 0.62, refresh = false) {
  const pvProfile = [];
  const demandProfile = [];
  const balance = [];
  const planHorario = [];

  for (let h = 0; h < 24; h++) {
    const fv = Number(hourlyPv(h).toFixed(3));
    const demanda = Number((0.3 + (h >= 19 && h <= 22 ? 0.5 : 0) + (h >= 7 && h <= 8 ? 0.4 : 0)).toFixed(3));
    pvProfile.push({
      hora: `${String(h).padStart(2, "0")}:00`,
      potencia_fv_kw: fv,
      irradiancia_predicha_wm2: Math.round(fv * 160),
      estado_cielo: fv > 2 ? "despejado" : "poco nuboso",
      temperatura_ambiente_c: 18 + (h >= 12 && h <= 17 ? 7 : 0),
    });
    demandProfile.push({ hora: `${String(h).padStart(2, "0")}:00`, potencia_total_kw: demanda });
    balance.push({
      hora: `${String(h).padStart(2, "0")}:00`,
      fv_kw: fv,
      demanda_kw: demanda,
      excedente_kw: Number(Math.max(0, fv - demanda).toFixed(3)),
      deficit_kw: Number(Math.max(0, demanda - fv).toFixed(3)),
      precio_compra: Number((0.09 + 0.02 * Math.sin(h)).toFixed(4)),
      precio_venta: Number((0.05 + 0.01 * Math.cos(h)).toFixed(4)),
    });

    let accion = "AUTOCONSUMO";
    if (fv - demanda > 1.0) accion = "CARGAR_BATERIA + AUTOCONSUMO";
    else if (h >= 20 && h <= 22) accion = "DESCARGAR_BATERIA + AUTOCONSUMO";
    else if (fv < 0.2 && h >= 2 && h <= 5) accion = "COMPRAR_RED + EQUILIBRIO";

    planHorario.push({
      hora: `${String(h).padStart(2, "0")}:00`,
      fv_kw: fv,
      demanda_kw: demanda,
      precio_compra: 0.11,
      soc_inicio: soc,
      accion,
      razon: accion.includes("CARGAR") ? "Excedente solar disponible." : "Gestión estándar.",
      coste_neto_eur: 0,
    });
  }

  const energiaFv = Number(pvProfile.reduce((acc, r) => acc + r.potencia_fv_kw, 0).toFixed(2));
  const energiaDemanda = Number(demandProfile.reduce((acc, r) => acc + r.potencia_total_kw, 0).toFixed(2));
  const lavadora = (config.loads && config.loads.lavadora) || {};
  const horaInicio = lavadora.window ? lavadora.window[0] : "12:00";
  const horaFin = lavadora.window ? lavadora.window[1] : "15:00";

  return {
    schema_version: 1,
    status: "ok",
    warnings: [],
    updated_at: new Date().toISOString().slice(0, 19),
    cache_status: refresh ? "updated" : "cached",
    sources: {
      aemet: { status: "ok", from_cache: null },
      pvgis: { status: "ok", from_cache: null },
      esios: { status: "ok", from_cache: null },
    },
    input: { soc, estrategia: config.strategy || "sostenible_predictiva", municipio: (config.location || {}).municipality || "Maracena", refresh, date: isoPlus(0) },
    forecast: { date: isoPlus(0), score: 0.82, cielo_score: 0.75, precip: 5, tmax: 27, tmin: 15, quality: "alta", hourly: [] },
    pv: {
      energia_kwh: energiaFv,
      pico: { hora: "14:00", potencia_fv_kw: 5.6 },
      perfil: pvProfile,
    },
    demand: {
      ocupantes: { adultos: 2, ninos: 3, total: 5 },
      potencia_base_kw: 0.18,
      energia_diaria_kwh: energiaDemanda,
      perfil: demandProfile,
    },
    energy: {
      balance_metrics: { energia_fv_kwh: energiaFv, energia_demanda_kwh: energiaDemanda, autoconsumo_pct: 58.4, energia_excedente_kwh: 4.2 },
      plan_metrics: { soc_final: 0.54, energia_cargada_bateria_kwh: 6.1, energia_descargada_bateria_kwh: 4.8, ciclos_equivalentes: 0.118, compra_red_kwh: 2.7, venta_red_kwh: 1.1 },
      balance,
    },
    prices: {
      serie: balance.map((r) => ({ hora: r.hora, compra: r.precio_compra, venta: r.precio_venta })),
      min_compra: { hora: "04:00", compra: 0.07 },
      max_compra: { hora: "20:00", compra: 0.19 },
      max_venta: { hora: "14:00", venta: 0.11 },
    },
    today_actions: [
      {
        id: "today-12:00-cargar_bateria",
        kind: "battery",
        title: "Cargar batería con excedente solar",
        time_window: "12:00 – 15:00",
        start: "12:00",
        end: "15:00",
        summary: "Conviene almacenar el excedente solar previsto en la batería.",
        severity: "important",
        metrics: { fv_kw: 4.9, demanda_kw: 0.3, precio_compra: 0.11, coste_neto_eur: 0 },
        reasons: [{ code: "HIGH_PV_FORECAST", detail: null }, { code: "SUFFICIENT_SOC", detail: null }],
      },
      {
        id: "today-12:00-lavadora",
        kind: "load",
        title: `Lavadora (${lavadora.duracion_h || 1.5} h)`,
        time_window: `${horaInicio} – ${horaFin}`,
        start: horaInicio,
        end: horaFin,
        summary: "Se prevé mayor excedente fotovoltaico y la carga está configurada como flexible.",
        severity: "important",
        metrics: { potencia_kw: lavadora.power_kw || 1.0 },
        reasons: [{ code: "HIGH_PV_FORECAST", detail: null }, { code: "FLEXIBLE_LOAD", detail: null }],
      },
      {
        id: "today-20:00-descargar_bateria",
        kind: "battery",
        title: "Usar la batería en vez de la red",
        time_window: "20:00 – 23:00",
        start: "20:00",
        end: "23:00",
        summary: "Conviene apoyarse en la batería en lugar de comprar red.",
        severity: "important",
        metrics: { precio_compra: 0.19 },
        reasons: [{ code: "SUFFICIENT_SOC", detail: null }, { code: "PRICE_WINDOW", detail: null }],
      },
    ],
    weekly_plan: [0, 1, 2, 3, 4, 5, 6].map((i) => ({
      date: isoPlus(i),
      weekday: DIAS[(new Date().getDay() + i) % 7],
      solar_quality: ["excelente", "bueno", "aceptable", "excelente", "bueno", "malo", "bueno"][i],
      confidence: i <= 1 ? "alta" : i <= 3 ? "media" : "baja",
      temps: { max: 27 - i, min: 15 - (i % 3) },
      precip: [5, 10, 30, 5, 0, 60, 15][i],
      actions:
        i % 2 === 0
          ? [
              {
                id: `week-${isoPlus(i)}-lavadora`,
                kind: "load",
                title: "Lavadora",
                time_window: "12:00 – 13:30",
                start: "12:00",
                end: "13:30",
                summary: "Mayor excedente solar previsto.",
                severity: "important",
                metrics: { potencia_kw: 1.0 },
                reasons: [{ code: "HIGH_PV_FORECAST", detail: null }, { code: "FLEXIBLE_LOAD", detail: null }],
              },
            ]
          : [],
    })),
    strategic: {
      estrategia: config.strategy || "sostenible_predictiva",
      acciones: [
        "Concentrar las cargas flexibles en las horas de mayor disponibilidad solar.",
        "Priorizar autoconsumo directo.",
        "Evitar cargar desde red salvo necesidad energética justificada.",
      ],
      razones: [
        "La estrategia sostenible predictiva busca reducir los ciclos equivalentes de la batería.",
      ],
      metricas: {},
      sostenibilidad: { soc },
      economia: {},
    },
  };
}

export function buildDemoError(category = "NETWORK_ERROR") {
  return {
    schema_version: 1,
    status: "error",
    warnings: [],
    updated_at: new Date().toISOString().slice(0, 19),
    cache_status: "unavailable",
    error: { category, message: "Demostración: error simulado.", source: null },
    input: { soc: 0.6 },
    today_actions: [],
    weekly_plan: [],
  };
}
