/**
 * screens.js
 * ==========
 *
 * Renderizado de las pantallas del MVP con jQuery + componentes OnsenUI.
 *
 * La lógica energética no vive aquí: estas funciones únicamente
 * representan modelos de presentación (mapper.js) y emiten eventos
 * hacia la capa de aplicación (api.js).
 */

import { formatSoc, formatEnergy, formatPower, maskSecret } from "./format.js";

/* ------------------------------------------------------------------ */
/* Utilidades                                                          */
/* ------------------------------------------------------------------ */

function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function cardClass(severity) {
  if (severity === "warning") return "gs-card gs-card--warning";
  if (severity === "important") return "gs-card gs-card--important";
  return "gs-card";
}

function recommendationCard(rec, { primary = false } = {}) {
  const reasons = (rec.reasons || [])
    .map((r) => `<li>${esc(r.text)}${r.detail ? ` <span class="gs-muted">(${esc(r.detail)})</span>` : ""}</li>`)
    .join("");

  const time = rec.timeWindow ? `<div class="gs-card__time">${esc(rec.timeWindow)}</div>` : "";
  const tag = primary ? "Recomendación principal" : "Acción recomendada";

  return `
    <div class="${cardClass(rec.severity)}" data-rec-id="${esc(rec.id)}">
      <div class="gs-card__tag">${tag}</div>
      <div class="gs-card__title">${esc(rec.title)}</div>
      ${time}
      <div class="gs-card__summary">${esc(rec.summary)}</div>
      ${reasons ? `<ul class="gs-card__reasons">${reasons}</ul>` : ""}
      <div class="gs-card__actions">
        <button class="gs-link-btn" data-action="detail" data-rec-id="${esc(rec.id)}">¿Por qué?</button>
      </div>
    </div>`;
}

/* ------------------------------------------------------------------ */
/* Pantalla «Hoy»                                                      */
/* ------------------------------------------------------------------ */

export function renderToday($el, ctx) {
  const { ui, error, soc, busy, demo, engineKind, fellBack, onRun, onDetail } = ctx;

  const parts = [];

  if (demo || fellBack || engineKind === "demo-fallback") {
    const text = fellBack || engineKind === "demo-fallback"
      ? "Modo demostración: motor Python no disponible; se muestran datos de ejemplo sintéticos."
      : "Modo demostración: el motor Python calcula con datos de ejemplo (sin conexión a AEMET/ESIOS/PVGIS).";
    parts.push(`<div class="gs-banner gs-banner--info">${text}</div>`);
  }

  // SOC + botón calcular
  parts.push(`
    <div class="gs-card">
      <div class="gs-card__tag">Estado actual de batería</div>
      <div class="gs-center" style="font-size:28px;font-weight:700;color:var(--gs-primary-dark)">${esc(formatSoc(soc))}</div>
      <input id="soc-range" type="range" min="0" max="100" step="1" value="${Math.round(soc * 100)}" style="width:100%">
      <div class="gs-inline" style="display:flex;gap:8px;margin-top:12px">
        <button class="gs-btn-primary" id="btn-calc" style="flex:1;padding:12px;border:0;border-radius:10px;color:#fff;font-size:16px" ${busy ? "disabled" : ""}>
          ${busy ? "Calculando…" : "CALCULAR PLAN"}
        </button>
        <button id="btn-refresh-now" style="padding:12px 14px;border:1px solid var(--gs-border);border-radius:10px;background:var(--gs-surface);color:var(--gs-text)">
          ↻
        </button>
      </div>
    </div>`);

  if (error) {
    parts.push(`
      <div class="gs-banner gs-banner--error">
        <strong>${esc(error.title)}</strong><br>${esc(error.message)}<br>
        <span class="gs-muted">${esc(error.action)}</span>
      </div>`);
  }

  if (!ui && !error) {
    parts.push(`<div class="gs-empty">Introduce el estado de batería y pulsa «Calcular plan».</div>`);
    $el.html(parts.join(""));
    bindToday($el, ctx);
    return;
  }

  if (ui) {
    // Estado de los datos
    const freshClass = ui.freshness.status === "stale" || ui.freshness.status === "unavailable"
      ? "gs-freshness--stale" : "";
    parts.push(`
      <div class="gs-freshness ${freshClass}">
        <span>Plan para hoy · ${esc(ui.municipio || "")}</span>
        <span class="gs-freshness__status">${esc(ui.freshness.icon)} ${esc(ui.freshness.label)} · ${esc(ui.updatedLabel)}</span>
      </div>`);

    (ui.warnings || [])
      .filter((w) => !w.toLowerCase().includes("modo demostración"))
      .forEach((w) => {
        parts.push(`<div class="gs-banner gs-banner--warning">⚠ ${esc(w)}</div>`);
      });

    if (ui.primary) {
      parts.push(recommendationCard(ui.primary, { primary: true }));
    }

    if (ui.others && ui.others.length) {
      parts.push(`<div class="gs-section-title">Próximas acciones</div>`);
      ui.others.forEach((rec) => parts.push(recommendationCard(rec)));
    }

    // Resumen energético
    const e = ui.energy;
    parts.push(`<div class="gs-section-title">Resumen energético</div>`);
    parts.push(`
      <div class="gs-metric-grid">
        <div class="gs-metric"><div class="gs-metric__label">Producción FV prevista</div><div class="gs-metric__value">${esc(e.pvEnergyLabel)}</div></div>
        <div class="gs-metric"><div class="gs-metric__label">Demanda prevista</div><div class="gs-metric__value">${esc(e.demandEnergyLabel)}</div></div>
        <div class="gs-metric"><div class="gs-metric__label">Pico FV</div><div class="gs-metric__value">${esc(e.pvPeakLabel)}</div></div>
        <div class="gs-metric"><div class="gs-metric__label">Precio mín. compra</div><div class="gs-metric__value">${esc(e.priceMin ? e.priceMin.value : "—")}</div></div>
      </div>`);

    if (e.strategicActions && e.strategicActions.length) {
      parts.push(`<div class="gs-section-title">Estrategia</div>`);
      parts.push(
        `<div class="gs-card"><ul class="gs-card__reasons" style="padding-left:18px">${e.strategicActions
          .map((a) => `<li>${esc(a)}</li>`)
          .join("")}</ul></div>`
      );
    }
  }

  $el.html(parts.join(""));
  bindToday($el, ctx);
}

function bindToday($el, ctx) {
  const { onRun, onDetail } = ctx;
  let soc = ctx.soc;

  $el.find("#soc-range").on("input", function () {
    soc = Number(this.value) / 100;
    $(this).closest(".gs-card").find(".gs-center").text(formatSoc(soc));
  });

  $el.find("#btn-calc").on("click", () => onRun({ soc, refresh: false }));
  $el.find("#btn-refresh-now").on("click", () => onRun({ soc, refresh: true }));

  $el.find('[data-action="detail"]').on("click", function () {
    const id = $(this).data("rec-id");
    onDetail(id);
  });
}

/* ------------------------------------------------------------------ */
/* Pantalla «Semana»                                                   */
/* ------------------------------------------------------------------ */

export function renderWeek($el, ctx) {
  const { ui, error, onDetail, onRun } = ctx;

  if (error) {
    $el.html(`<div class="gs-banner gs-banner--error"><strong>${esc(error.title)}</strong><br>${esc(error.message)}</div>`);
    return;
  }
  if (!ui) {
    $el.html(`<div class="gs-empty">Calcula un plan para ver la previsión semanal.</div>`);
    return;
  }

  const days = ui.week || [];
  if (!days.length) {
    $el.html(`<div class="gs-empty">No hay previsión semanal disponible.</div>`);
    return;
  }

  const html = days
    .map((day) => {
      const meta = [day.solarQuality ? `☀ ${esc(day.solarQuality)}` : "", day.confidence ? `confianza ${esc(day.confidence)}` : ""]
        .filter(Boolean)
        .join(" · ");
      const actions = day.actions.length
        ? day.actions
            .map(
              (a) => `
          <div class="gs-card">
            <div class="gs-card__title">${esc(a.title)}</div>
            <div class="gs-card__time">${esc(a.timeWindow || "—")}</div>
            <div class="gs-card__summary">${esc(a.summary || "")}</div>
            <div class="gs-card__actions"><button class="gs-link-btn" data-action="detail" data-rec-id="${esc(a.id)}">¿Por qué?</button></div>
          </div>`
            )
            .join("")
        : `<div class="gs-muted" style="padding:6px 4px">Sin servicios desplazables.</div>`;

      return `
        <div class="gs-day">
          <div class="gs-day__head">
            <span class="gs-day__label">${esc(day.label)}</span>
            <span class="gs-day__meta">${meta}</span>
          </div>
          <div class="gs-day__meta gs-muted" style="margin-bottom:6px">
            ${day.temps && day.temps.max != null ? `${esc(day.temps.min)}–${esc(day.temps.max)} °C` : ""}
            ${day.precip != null ? ` · precip. ${esc(day.precip)} %` : ""}
          </div>
          ${actions}
        </div>`;
    })
    .join("");

  $el.html(
    `<div class="gs-banner gs-banner--info">Previsión a varios días: la incertidumbre aumenta con el horizonte.</div>` + html
  );

  $el.find('[data-action="detail"]').on("click", function () {
    onDetail($(this).data("rec-id"));
  });
  if (onRun) $el.find("#btn-week-calc").on("click", () => onRun({ refresh: false }));
}

/* ------------------------------------------------------------------ */
/* Pantalla «Energía»                                                  */
/* ------------------------------------------------------------------ */

export function renderEnergy($el, ctx) {
  const { ui, error } = ctx;

  if (error) {
    $el.html(`<div class="gs-banner gs-banner--error"><strong>${esc(error.title)}</strong><br>${esc(error.message)}</div>`);
    return;
  }
  if (!ui) {
    $el.html(`<div class="gs-empty">Calcula un plan para ver los datos energéticos.</div>`);
    return;
  }

  const e = ui.energy;

  const metricsHtml = (list) =>
    `<div class="gs-metric-grid">${list
      .map((m) => `<div class="gs-metric"><div class="gs-metric__label">${esc(m.label)}</div><div class="gs-metric__value">${esc(m.value)}</div></div>`)
      .join("")}</div>`;

  $el.html(`
    <div class="gs-card">
      <div class="gs-card__tag">SOC actual</div>
      <div class="gs-card__title">${esc(e.socLabel)}</div>
    </div>

    <div class="gs-section-title">Producción FV prevista</div>
    <div class="gs-card">
      <div class="gs-card__title">${esc(e.pvEnergyLabel)}</div>
      <div class="gs-muted">${esc(e.pvPeakLabel)}</div>
      ${chart(e.pvProfile, "potencia_fv_kw", "gs-chart__bar")}
      <div class="gs-chart__legend"><span><i style="background:var(--gs-primary)"></i>FV (kW)</span></div>
    </div>

    <div class="gs-section-title">Demanda prevista</div>
    <div class="gs-card">
      <div class="gs-card__title">${esc(e.demandEnergyLabel)}</div>
      <div class="gs-muted">Potencia base ${esc(e.demandBaseLabel)}</div>
      ${chart(e.demandProfile, "potencia_total_kw", "gs-chart__bar gs-chart__bar--demand")}
      <div class="gs-chart__legend"><span><i style="background:var(--gs-accent)"></i>Demanda (kW)</span></div>
    </div>

    <div class="gs-section-title">Balance</div>
    ${metricsHtml(e.balanceMetrics)}

    <div class="gs-section-title">Plan de batería y red</div>
    ${metricsHtml(e.planMetrics)}

    <div class="gs-section-title">Precios</div>
    <div class="gs-metric-grid">
      ${e.priceMin ? `<div class="gs-metric"><div class="gs-metric__label">${esc(e.priceMin.label)} (${esc(e.priceMin.hora)})</div><div class="gs-metric__value">${esc(e.priceMin.value)}</div></div>` : ""}
      ${e.priceMax ? `<div class="gs-metric"><div class="gs-metric__label">${esc(e.priceMax.label)} (${esc(e.priceMax.hora)})</div><div class="gs-metric__value">${esc(e.priceMax.value)}</div></div>` : ""}
      ${e.priceSell ? `<div class="gs-metric"><div class="gs-metric__label">${esc(e.priceSell.label)} (${esc(e.priceSell.hora)})</div><div class="gs-metric__value">${esc(e.priceSell.value)}</div></div>` : ""}
    </div>

    <div class="gs-freshness" style="margin-top:16px">
      <span>${esc(ui.freshness.icon)} ${esc(ui.freshness.label)}</span>
      <span>Actualizado: ${esc(ui.updatedLabel)}</span>
    </div>
  `);
}

function chart(profile, key, barClass) {
  if (!profile || !profile.length) return "";
  const max = Math.max(...profile.map((r) => Number(r[key]) || 0), 0.001);
  const bars = profile
    .map((r) => {
      const h = Math.max(1, Math.round((Number(r[key]) || 0) / max * 100));
      return `<div class="${barClass}" style="height:${h}%" title="${esc(r.hora)}: ${esc(r[key])}"></div>`;
    })
    .join("");
  return `<div class="gs-chart" role="img" aria-label="Perfil horario">${bars}</div>`;
}

/* ------------------------------------------------------------------ */
/* Pantalla «Ajustes»                                                  */
/* ------------------------------------------------------------------ */

export function renderSettings($el, ctx) {
  const { config, credentials, status, engineKind, fellBack, onEdit, onRefreshNow, onClearCredentials, onResetConfig, onProbe } = ctx;

  const c = config || {};
  const loc = c.location || {};
  const pv = c.pv || {};
  const bat = c.battery || {};
  const inv = c.inverter || {};
  const home = c.home || {};

  const item = (title, sub, attrs = "", danger = false) =>
    `<div class="gs-item" ${attrs}>
       <div class="gs-item__body">
         <div class="gs-item__title"${danger ? ' style="color:var(--gs-danger)"' : ""}>${title}</div>
         ${sub ? `<div class="gs-item__sub">${sub}</div>` : ""}
       </div>
     </div>`;

  $el.html(`
    <div class="gs-group-title">Aplicación</div>
    <div class="gs-group">
      ${item("Motor", engineKind === "pyodide" ? "Python embebido (Pyodide)" : "Demostración (datos de ejemplo)")}
      ${item("Estado", `<span id="settings-status">${esc(status || "—")}</span>`)}
    </div>

    <div class="gs-group-title">Datos</div>
    <div class="gs-group">
      ${item("Actualizar datos ahora", "Fuerza la descarga de AEMET / PVGIS / ESIOS", 'data-action="refresh"')}
      ${item("Diagnóstico de entorno", "Comprueba las dependencias Python del motor", 'data-action="probe"')}
    </div>

    <div class="gs-group-title">Credenciales</div>
    <div class="gs-group">
      ${item("AEMET API Key", credentials.aemet_api_key ? esc(maskSecret(credentials.aemet_api_key)) : "No configurada")}
      ${item("ESIOS Token", credentials.esios_token ? esc(maskSecret(credentials.esios_token)) : "No configurado")}
      ${item("Cambiar credenciales", null, 'data-action="edit"')}
      ${item("Eliminar credenciales", null, 'data-action="clear"', true)}
    </div>

    <div class="gs-group-title">Instalación</div>
    <div class="gs-group">
      ${item("Ubicación", `${esc(loc.municipality || "—")}${loc.region ? ` (${esc(loc.region)})` : ""}`)}
      ${item("Sistema FV", `${esc(pv.panels || "—")} × ${esc(pv.panel_power_w || "—")} W · incl. ${esc(pv.inclination_deg || "—")}°`)}
      ${item("Inversor", `${esc(inv.manufacturer || "")} ${esc(inv.model || "")} · ${esc(inv.nominal_kw || "—")} kW`)}
      ${item("Batería", `${esc(bat.units || "—")} × ${esc(bat.capacity_kwh_unit || "—")} kWh · SOC ${esc(formatSoc(bat.min_soc))}–${esc(formatSoc(bat.max_soc))}`)}
      ${item("Vivienda", `${esc(home.adults || 0)} adultos · ${esc(home.children || 0)} niños`)}
      ${item("Estrategia", esc(c.strategy || "—"))}
      ${item("Editar configuración", null, 'data-action="edit-config"')}
      ${item("Restablecer configuración", null, 'data-action="reset"', true)}
    </div>

    <div class="gs-hint" style="margin:16px 4px">Las credenciales no se incluyen en el plan ni en los registros.</div>
  `);

  $el.find('[data-action="refresh"]').on("click", () => onRefreshNow());
  $el.find('[data-action="probe"]').on("click", () => onProbe());
  $el.find('[data-action="edit"], [data-action="edit-config"]').on("click", () => onEdit("credentials"));
  $el.find('[data-action="clear"]').on("click", () => onClearCredentials());
  $el.find('[data-action="reset"]').on("click", () => onResetConfig());
}

/* ------------------------------------------------------------------ */
/* Pantalla de detalle                                                 */
/* ------------------------------------------------------------------ */

export function renderDetail($el, ctx) {
  const { rec, ui } = ctx;
  if (!rec) {
    $el.html(`<div class="gs-empty">No se encontró la recomendación.</div>`);
    return;
  }

  const reasons = (rec.reasons || [])
    .map((r) => `<li>${esc(r.text)}${r.detail ? ` <span class="gs-muted">(${esc(r.detail)})</span>` : ""}</li>`)
    .join("");

  const metrics = Object.entries(rec.metrics || {})
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `<li><strong>${esc(k)}</strong>: ${esc(v)}</li>`)
    .join("");

  $el.html(`
    <div class="gs-card">
      <div class="gs-card__tag">Recomendación</div>
      <div class="gs-card__title">${esc(rec.title)}</div>
      ${rec.timeWindow ? `<div class="gs-card__time">${esc(rec.timeWindow)}</div>` : ""}
      <div class="gs-card__summary">${esc(rec.summary)}</div>
    </div>

    <div class="gs-section-title">¿Por qué?</div>
    <div class="gs-card">
      ${reasons ? `<ul class="gs-card__reasons" style="padding-left:18px">${reasons}</ul>` : `<div class="gs-muted">Sin justificación estructurada.</div>`}
    </div>

    ${metrics ? `<div class="gs-section-title">Datos utilizados</div><div class="gs-card"><ul class="gs-card__reasons" style="padding-left:18px">${metrics}</ul></div>` : ""}

    <div class="gs-hint" style="margin:12px 4px">
      La decisión procede del motor energético. La aplicación sólo la presenta.
    </div>
  `);
}

/* ------------------------------------------------------------------ */
/* Estados auxiliares                                                  */
/* ------------------------------------------------------------------ */

export function renderError($el, error) {
  $el.html(`
    <div class="gs-banner gs-banner--error">
      <strong>${esc(error.title)}</strong><br>${esc(error.message)}<br>
      <span class="gs-muted">${esc(error.action)}</span>
    </div>`);
}

export function renderLoading($el, message = "Preparando tu plan energético…") {
  $el.html(`<div class="gs-empty"><div class="gs-spinner" style="border-top-color:var(--gs-primary)"></div><p>${esc(message)}</p></div>`);
}

export const __test__ = { esc, recommendationCard, cardClass };
