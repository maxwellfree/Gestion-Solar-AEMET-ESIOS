/**
 * onboarding.js
 * =============
 *
 * Asistente de configuración inicial (CONFIGURATION_AND_CREDENTIALS.md, §2
 * y UI_MVP.md §6). Recoge:
 *
 *     Credenciales → Ubicación → FV → Inversor → Batería →
 *     Vivienda → Estrategia → Resumen
 *
 * Guarda el estado temporalmente para no perder campos al retroceder y
 * separa credenciales de configuración.
 */

import { formatSoc } from "./format.js";
import { validateStep } from "./store.js";

const STRATEGIES = [
  { value: "sostenible_predictiva", label: "Sostenible predictiva (recomendada)" },
  { value: "sostenible_jerarquica", label: "Sostenible jerárquica" },
  { value: "autoconsumo", label: "Maximizar autoconsumo" },
  { value: "min_ciclos", label: "Minimizar ciclos de batería" },
  { value: "economica", label: "Económica" },
];

function field(label, inputHtml) {
  return `<div class="gs-field"><label>${label}</label>${inputHtml}</div>`;
}

function numberInput(id, value, extra = "") {
  return `<input type="number" id="${id}" value="${value ?? ""}" ${extra}>`;
}

export function createOnboarding($page, { api, draft, onFinish, onExit }) {
  const state = {
    index: 0,
    config: draft.config,
    credentials: draft.credentials,
    validation: { aemet: null, esios: null },
  };

  const steps = [
    {
      id: "credentials",
      title: "Credenciales",
      render: () => {
        const c = state.credentials;
        const v = state.validation;
        return `
          <p class="gs-muted">Introduce tus claves personales. No se enviarán a ningún servidor salvo a las propias APIs.</p>
          ${field(
            "AEMET OpenData — API Key",
            `<input type="password" id="in-aemet" value="${c.aemet_api_key || ""}" autocomplete="off">
             <div class="gs-inline" style="margin-top:6px">
               <button class="gs-btn-primary" id="val-aemet" style="padding:8px 12px;border:0;border-radius:8px;color:#fff">VALIDAR</button>
               <span class="gs-validation gs-validation--${v.aemet ? v.aemet.status : ""}" id="val-aemet-status">${statusText(v.aemet)}</span>
             </div>`
          )}
          ${field(
            "ESIOS — Token personal",
            `<input type="password" id="in-esios" value="${c.esios_token || ""}" autocomplete="off">
             <div class="gs-inline" style="margin-top:6px">
               <button class="gs-btn-primary" id="val-esios" style="padding:8px 12px;border:0;border-radius:8px;color:#fff">VALIDAR</button>
               <span class="gs-validation gs-validation--${v.esios ? v.esios.status : ""}" id="val-esios-status">${statusText(v.esios)}</span>
             </div>`
          )}`;
      },
      read: ($body) => {
        state.credentials.aemet_api_key = $body.find("#in-aemet").val().trim();
        state.credentials.esios_token = $body.find("#in-esios").val().trim();
      },
      validate: () => validateStep("credentials", state.credentials),
    },
    {
      id: "location",
      title: "Ubicación",
      render: () => {
        const l = state.config.location;
        return `
          ${field("País", `<input type="text" id="in-country" value="${l.country || ""}">`)}
          <div class="gs-inline">
            ${field("Provincia / región", `<input type="text" id="in-region" value="${l.region || ""}">`)}
            ${field("Municipio", `<input type="text" id="in-municipality" value="${l.municipality || ""}">`)}
          </div>
          <div class="gs-inline">
            ${field("Latitud (opcional)", numberInput("in-lat", l.latitude, 'step="0.0001"'))}
            ${field("Longitud (opcional)", numberInput("in-lon", l.longitude, 'step="0.0001"'))}
          </div>
          <p class="gs-hint">El municipio es suficiente: el motor resuelve las coordenadas para PVGIS.</p>`;
      },
      read: ($body) => {
        const l = state.config.location;
        l.country = $body.find("#in-country").val().trim();
        l.region = $body.find("#in-region").val().trim();
        l.municipality = $body.find("#in-municipality").val().trim();
        l.latitude = toNumOrNull($body.find("#in-lat").val());
        l.longitude = toNumOrNull($body.find("#in-lon").val());
      },
      validate: () => validateStep("location", state.config),
    },
    {
      id: "pv",
      title: "Sistema fotovoltaico",
      render: () => {
        const p = state.config.pv;
        return `
          <div class="gs-inline">
            ${field("Nº de paneles", numberInput("in-panels", p.panels, 'min="1"'))}
            ${field("Potencia del panel (W)", numberInput("in-ppower", p.panel_power_w, 'min="1"'))}
          </div>
          <div class="gs-inline">
            ${field("Inclinación (°)", numberInput("in-tilt", p.inclination_deg))}
            ${field("Azimut (°)", numberInput("in-azimuth", p.azimuth_deg, 'step="1"'))}
          </div>
          <p class="gs-hint">Azimut PVGIS: 0° = Sur, −90° = Este, +90° = Oeste.</p>`;
      },
      read: ($body) => {
        const p = state.config.pv;
        p.panels = toNumOrNull($body.find("#in-panels").val());
        p.panel_power_w = toNumOrNull($body.find("#in-ppower").val());
        p.inclination_deg = toNumOrNull($body.find("#in-tilt").val());
        p.azimuth_deg = toNumOrNull($body.find("#in-azimuth").val());
      },
      validate: () => validateStep("pv", state.config),
    },
    {
      id: "inverter",
      title: "Inversor",
      render: () => {
        const i = state.config.inverter;
        return `
          ${field("Fabricante", `<input type="text" id="in-inv-fab" value="${i.manufacturer || ""}">`)}
          ${field("Modelo", `<input type="text" id="in-inv-model" value="${i.model || ""}">`)}
          ${field("Potencia nominal (kW)", numberInput("in-inv-kw", i.nominal_kw, 'min="0" step="0.1"'))}`;
      },
      read: ($body) => {
        const i = state.config.inverter;
        i.manufacturer = $body.find("#in-inv-fab").val().trim();
        i.model = $body.find("#in-inv-model").val().trim();
        i.nominal_kw = toNumOrNull($body.find("#in-inv-kw").val());
      },
      validate: () => validateStep("inverter", state.config),
    },
    {
      id: "battery",
      title: "Batería",
      render: () => {
        const b = state.config.battery;
        return `
          <div class="gs-inline">
            ${field("Fabricante", `<input type="text" id="in-bat-fab" value="${b.manufacturer || ""}">`)}
            ${field("Modelo", `<input type="text" id="in-bat-model" value="${b.model || ""}">`)}
          </div>
          <div class="gs-inline">
            ${field("Nº de unidades", numberInput("in-bat-units", b.units, 'min="1"'))}
            ${field("Capacidad por unidad (kWh)", numberInput("in-bat-cap", b.capacity_kwh_unit, 'min="0" step="0.01"'))}
          </div>
          <div class="gs-inline">
            ${field("SOC mínimo (%)", numberInput("in-bat-min", Math.round(b.min_soc * 100), 'min="0" max="100"'))}
            ${field("SOC máximo (%)", numberInput("in-bat-max", Math.round(b.max_soc * 100), 'min="0" max="100"'))}
          </div>`;
      },
      read: ($body) => {
        const b = state.config.battery;
        b.manufacturer = $body.find("#in-bat-fab").val().trim();
        b.model = $body.find("#in-bat-model").val().trim();
        b.units = toNumOrNull($body.find("#in-bat-units").val());
        b.capacity_kwh_unit = toNumOrNull($body.find("#in-bat-cap").val());
        b.min_soc = toNumOrNull($body.find("#in-bat-min").val()) / 100;
        b.max_soc = toNumOrNull($body.find("#in-bat-max").val()) / 100;
      },
      validate: () => validateStep("battery", state.config),
    },
    {
      id: "home",
      title: "Vivienda y cargas",
      render: () => {
        const h = state.config.home;
        const lv = state.config.loads.lavadora;
        return `
          <div class="gs-inline">
            ${field("Adultos", numberInput("in-adults", h.adults, 'min="0"'))}
            ${field("Niños", numberInput("in-children", h.children, 'min="0"'))}
          </div>
          ${field("Potencia base (kW)", numberInput("in-base", h.base_power_kw, 'min="0" step="0.01"'))}
          <div class="gs-field">
            <label><input type="checkbox" id="in-grid" ${h.grid_priority_over_battery ? "checked" : ""}> Priorizar red frente a ciclos marginales de batería</label>
          </div>
          <h3 style="font-size:15px;margin:16px 0 8px">Lavadora (carga flexible)</h3>
          <div class="gs-inline">
            ${field("Potencia (kW)", numberInput("in-lv-power", lv.power_kw, 'min="0" step="0.1"'))}
            ${field("Duración (h)", numberInput("in-lv-dur", lv.duration_h, 'min="0" step="0.1"'))}
          </div>
          <div class="gs-field">
            <label><input type="checkbox" id="in-lv-flex" ${lv.flexible ? "checked" : ""}> Puede desplazarse en el tiempo</label>
          </div>`;
      },
      read: ($body) => {
        const h = state.config.home;
        const lv = state.config.loads.lavadora;
        h.adults = toNumOrNull($body.find("#in-adults").val());
        h.children = toNumOrNull($body.find("#in-children").val());
        h.base_power_kw = toNumOrNull($body.find("#in-base").val());
        h.grid_priority_over_battery = $body.find("#in-grid").is(":checked");
        lv.power_kw = toNumOrNull($body.find("#in-lv-power").val());
        lv.duration_h = toNumOrNull($body.find("#in-lv-dur").val());
        lv.flexible = $body.find("#in-lv-flex").is(":checked");
      },
      validate: () => validateStep("home", state.config),
    },
    {
      id: "strategy",
      title: "Estrategia",
      render: () => {
        const options = STRATEGIES.map(
          (s) => `<option value="${s.value}" ${state.config.strategy === s.value ? "selected" : ""}>${s.label}</option>`
        ).join("");
        return `
          ${field("Estrategia de gestión", `<select id="in-strategy">${options}</select>`)}
          <p class="gs-hint">Determina cómo el motor decide el uso de la batería y la red.</p>`;
      },
      read: ($body) => {
        state.config.strategy = $body.find("#in-strategy").val();
      },
      validate: () => [],
    },
    {
      id: "summary",
      title: "Resumen",
      render: () => {
        const c = state.config;
        const b = c.battery;
        const row = (t, s) =>
          `<div class="gs-item"><div class="gs-item__title">${t}</div><div class="gs-item__sub">${s}</div></div>`;
        return `
          <div class="gs-group">
            ${row("Ubicación", `${c.location.municipality || "—"} (${c.location.region || "—"})`)}
            ${row("Sistema FV", `${c.pv.panels} × ${c.pv.panel_power_w} W`)}
            ${row("Inversor", `${c.inverter.manufacturer} ${c.inverter.model} · ${c.inverter.nominal_kw} kW`)}
            ${row("Batería", `${b.units} × ${b.capacity_kwh_unit} kWh · SOC ${formatSoc(b.min_soc)}–${formatSoc(b.max_soc)}`)}
            ${row("Vivienda", `${c.home.adults} adultos · ${c.home.children} niños`)}
            ${row("Estrategia", c.strategy)}
            ${row("Credenciales", `${state.credentials.aemet_api_key ? "AEMET configurada" : "AEMET pendiente"} · ${state.credentials.esios_token ? "ESIOS configurado" : "ESIOS pendiente"}`)}
          </div>
          <p class="gs-hint" style="margin-top:12px">Al continuar se guardará la configuración y se ejecutará el primer cálculo.</p>`;
      },
      read: () => {},
      validate: () => [],
    },
  ];

  function statusText(v) {
    if (!v) return "";
    const map = {
      valid: "✓ Válida",
      invalid: "✗ No válida",
      network_error: "⚠ Error de conexión",
      service_unavailable: "⚠ Servicio no disponible",
      configuration_error: "⚠ Vacío o incompleto",
    };
    return map[v.status] ? `${map[v.status]}${v.message ? `: ${v.message}` : ""}` : "";
  }

  function render() {
    const step = steps[state.index];
    $page.find("#ob-title").text(step.title);
    $page.find("#ob-step-label").text(`${state.index + 1} de ${steps.length}`);
    $page.find("#ob-progress-fill").css("width", `${((state.index + 1) / steps.length) * 100}%`);
    $page.find("#ob-body").html(step.render());
    $page.find("#ob-errors").attr("hidden", true).empty();
    $page.find("#ob-back").prop("disabled", state.index === 0);
    $page.find("#ob-next").text(state.index === steps.length - 1 ? "FINALIZAR" : "CONTINUAR");
    $page.find("#ob-exit").toggleClass("gs-hidden", state.index === 0);

    if (step.id === "credentials") bindCredentials();
  }

  function readCurrent() {
    steps[state.index].read($page.find("#ob-body"));
  }

  function next() {
    readCurrent();
    const errors = steps[state.index].validate();
    if (errors.length) {
      showErrors(errors);
      return;
    }
    if (state.index === steps.length - 1) {
      finish();
      return;
    }
    state.index += 1;
    render();
  }

  function back() {
    readCurrent();
    if (state.index > 0) {
      state.index -= 1;
      render();
    } else if (onExit) {
      onExit();
    }
  }

  function showErrors(errors) {
    $page
      .find("#ob-errors")
      .removeAttr("hidden")
      .html(errors.map((e) => `• ${e}`).join("<br>"));
  }

  function bindCredentials() {
    const $body = $page.find("#ob-body");

    $body.find("#val-aemet").on("click", async () => {
      const value = $body.find("#in-aemet").val().trim();
      state.credentials.aemet_api_key = value;
      $body.find("#val-aemet-status").attr("class", "gs-validation").text("Validando…");
      const result = await api.validateCredential("aemet", value);
      state.validation.aemet = result;
      $body
        .find("#val-aemet-status")
        .attr("class", `gs-validation gs-validation--${result.status}`)
        .text(statusText(result));
    });

    $body.find("#val-esios").on("click", async () => {
      const value = $body.find("#in-esios").val().trim();
      state.credentials.esios_token = value;
      $body.find("#val-esios-status").attr("class", "gs-validation").text("Validando…");
      const result = await api.validateCredential("esios", value);
      state.validation.esios = result;
      $body
        .find("#val-esios-status")
        .attr("class", `gs-validation gs-validation--${result.status}`)
        .text(statusText(result));
    });
  }

  function finish() {
    if (onFinish) onFinish({ config: state.config, credentials: state.credentials });
  }

  // Enlazar botones (una sola vez).
  $page.find("#ob-next").on("click", next);
  $page.find("#ob-back").on("click", back);

  render();

  return { render, next, back, getState: () => state };
}

function toNumOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
