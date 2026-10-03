/**
 * app.js
 * ======
 *
 * Arranque y navegación del MVP (UI_MVP.md, §3).
 *
 *     ARRANQUE ──¿configurado?── no ─▶ ONBOARDING ─┐
 *                    │ sí                          │
 *                    ▼                             ▼
 *                  HOY ◀──────── navegación principal ────────▶ AJUSTES
 *                  └─ detalle (¿Por qué?) · Semana · Energía
 *
 * Gestión de pantallas: pila propia sobre #app. Se usan componentes
 * OnsenUI (ons-page, ons-toolbar, ons-list, ons-button) pero la
 * navegación se controla explícitamente para evitar dependencias
 * frágiles de ons-navigator con páginas generadas dinámicamente.
 */

import { SolarApi } from "./api.js";
import { mapPlan } from "./mapper.js";
import { createOnboarding } from "./onboarding.js";
import * as store from "./store.js";
import {
  renderToday,
  renderWeek,
  renderEnergy,
  renderSettings,
  renderDetail,
} from "./screens.js";

const $ = window.jQuery;

/* ------------------------------------------------------------------ */
/* Pila de pantallas                                                   */
/* ------------------------------------------------------------------ */

const Screen = {
  container: null,
  stack: [],

  init(container) {
    this.container = container;
    this.stack = [];
  },

  _mount(page) {
    page.classList.add("gs-screen");
    this.container.appendChild(page);
    // Fuerza el "upgrade" de los componentes OnsenUI insertados.
    if (window.ons && window.ons.forcePlatformStyling) {
      try {
        window.ons.forcePlatformStyling();
      } catch (err) {
        /* opcional */
      }
    }
    return page;
  },

  _showOnly(page) {
    for (const child of Array.from(this.container.children)) {
      child.classList.toggle("gs-screen--hidden", child !== page);
    }
  },

  replace(page) {
    this.container.innerHTML = "";
    this.stack = [this._mount(page)];
    this._showOnly(page);
    return page;
  },

  reset(page) {
    return this.replace(page);
  },

  push(page) {
    this._mount(page);
    this.stack.push(page);
    this._showOnly(page);
    return page;
  },

  pop() {
    const page = this.stack.pop();
    if (page && page.parentNode) page.parentNode.removeChild(page);
    const top = this.stack[this.stack.length - 1];
    if (top) this._showOnly(top);
    return top;
  },
};

const App = {
  api: null,
  soc: 0.62,
  ui: null,
  error: null,
  busy: false,
  status: "—",
  index: {},
  $shell: null,

  async boot() {
    await onsReady();

    Screen.init(document.getElementById("app"));
    this.api = new SolarApi({
      mode: this.initialMode(),
      onStatus: (message) => this.setStatus(message),
    });

    this.showBoot("Iniciando…");
    const config = this.api.getConfig();
    const credentials = this.api.getCredentials();

    if (store.isConfigured(config, credentials)) {
      this.gotoShell();
      this.hideBoot();
      this.run({ refresh: false, quiet: true });
    } else {
      this.gotoWelcome();
      this.hideBoot();
    }
  },

  initialMode() {
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get("demo") === "1") return "demo";
      const saved = window.localStorage.getItem("gs.mode");
      if (saved === "demo" || saved === "pyodide") return saved;
    } catch (err) {
      /* ignore */
    }
    return "auto";
  },

  // --- Fábrica de páginas -----------------------------------------

  instantiate(templateId) {
    return document.getElementById(templateId).content.firstElementChild.cloneNode(true);
  },

  // --- Navegación --------------------------------------------------

  gotoWelcome() {
    const page = this.instantiate("tpl-welcome");
    Screen.replace(page);

    page.querySelector("#btn-start").addEventListener("click", () => this.startOnboarding());
    page.querySelector("#btn-demo").addEventListener("click", () => {
      try {
        window.localStorage.setItem("gs.mode", "demo");
      } catch (err) {
        /* ignore */
      }
      // Modo demostración: se usa el MOTOR PYTHON con datos de ejemplo
      // (demo=true), no datos sintéticos en JS.
      this.api.mode = "demo";
      this.api.demo = true;
      this.api.enginePromise = null;
      this.gotoShell();
      this.run({ refresh: false });
    });
  },

  startOnboarding() {
    const page = this.instantiate("tpl-onboarding");
    Screen.push(page);

    createOnboarding($(page), {
      api: this.api,
      draft: { config: this.api.getConfig(), credentials: this.api.getCredentials() },
      onExit: () => Screen.pop(),
      onFinish: ({ config, credentials }) => {
        this.api.saveConfig(config);
        this.api.saveCredentials(credentials);
        this.gotoShell();
        this.run({ refresh: true });
      },
    });

    page.querySelector("#ob-exit").addEventListener("click", () => Screen.pop());
  },

  gotoShell() {
    const page = this.instantiate("tpl-shell");
    Screen.reset(page);
    this.$shell = $(page);
    this.bindShell();
    this.renderAll();
  },

  bindShell() {
    this.$shell.find("#btn-refresh").on("click", () => this.run({ refresh: true }));

    this.$shell.find(".gs-tab").on("click", (event) => {
      const $tab = $(event.currentTarget);
      const view = $tab.data("view");
      this.$shell.find(".gs-tab").removeClass("gs-tab--active");
      $tab.addClass("gs-tab--active");
      this.$shell.find(".gs-view").removeClass("gs-view--active");
      this.$shell.find("#view-" + view).addClass("gs-view--active");
      this.$shell.find("#shell-title").text($tab.data("title"));
    });
  },

  openDetail(recId) {
    const rec = this.index[recId];
    if (!rec) return;
    const page = this.instantiate("tpl-detail");
    page.querySelector("#detail-title").textContent = rec.title;
    renderDetail($(page.querySelector("#detail-body")), { rec, ui: this.ui });
    Screen.push(page);
    page.querySelector("#detail-back").addEventListener("click", () => Screen.pop());
  },

  // --- Estado / render --------------------------------------------

  setStatus(message) {
    this.status = message;
    $("#boot-message").text(message);
    const $status = this.$shell && this.$shell.find("#settings-status");
    if ($status && $status.length) $status.text(message);
  },

  rebuildIndex() {
    this.index = {};
    if (!this.ui) return;
    const all = [
      ...(this.ui.primary ? [this.ui.primary] : []),
      ...(this.ui.others || []),
      ...(this.ui.week || []).flatMap((d) => d.actions || []),
    ];
    all.forEach((rec) => {
      this.index[rec.id] = rec;
    });
  },

  renderAll() {
    if (!this.$shell) return;
    const ctx = {
      ui: this.ui,
      error: this.error,
      soc: this.soc,
      busy: this.busy,
      demo: this.api.demo,
      engineKind: this.api.engine ? this.api.engine.kind : this.api.mode,
      fellBack: this.api.fellBackToDemo,
      onRun: (opts) => this.run(opts),
      onDetail: (id) => this.openDetail(id),
    };

    renderToday(this.$shell.find("#view-hoy"), ctx);
    renderWeek(this.$shell.find("#view-semana"), ctx);
    renderEnergy(this.$shell.find("#view-energia"), ctx);
    renderSettings(this.$shell.find("#view-ajustes"), {
      config: this.api.getConfig(),
      credentials: this.api.getCredentials(),
      status: this.status,
      engineKind: this.api.engine ? this.api.engine.kind : this.api.mode,
      fellBack: this.api.fellBackToDemo,
      onEdit: () => this.startOnboarding(),
      onRefreshNow: () => this.run({ refresh: true }),
      onClearCredentials: () => this.clearCredentials(),
      onResetConfig: () => this.resetConfig(),
      onProbe: () => this.probe(),
    });
    this.rebuildIndex();
  },

  async run({ soc = null, refresh = false, quiet = false } = {}) {
    if (soc !== null) this.soc = soc;
    this.busy = true;
    this.error = null;

    // El overlay se muestra también en el primer cálculo si el motor aún
    // no está inicializado (la carga de Pyodide puede tardar).
    const needOverlay = !quiet || !this.api.engine;
    if (needOverlay) {
      this.showBoot(refresh ? "Actualizando datos…" : "Preparando tu plan energético…");
    }

    try {
      const result = await this.api.runPlan({ soc: this.soc, refresh });
      if (result.status === "error") {
        this.ui = null;
        this.error = mapPlan(result).error;
      } else {
        this.ui = mapPlan(result);
        this.error = null;
      }
    } catch (err) {
      this.ui = null;
      this.error = mapPlan({ status: "error", error: { category: "ENGINE_ERROR", message: String(err) } }).error;
    } finally {
      this.busy = false;
      this.hideBoot();
      this.renderAll();
    }
  },

  async probe() {
    this.setStatus("Ejecutando diagnóstico…");
    try {
      const probe = await this.api.dependencyProbe();
      const text = Object.entries(probe)
        .map(([k, v]) => `${k}: ${v}`)
        .join(" · ");
      this.setStatus(`Diagnóstico: ${text}`);
    } catch (err) {
      this.setStatus(`Diagnóstico no disponible: ${err}`);
    }
  },

  clearCredentials() {
    if (!window.confirm("¿Eliminar las credenciales guardadas?")) return;
    this.api.clearCredentials();
    this.renderAll();
  },

  resetConfig() {
    if (!window.confirm("¿Restablecer la configuración de la instalación?")) return;
    this.api.resetConfig();
    this.renderAll();
  },

  // --- Overlay -----------------------------------------------------

  showBoot(message) {
    $("#boot-message").text(message);
    $("#boot-overlay").removeAttr("hidden");
  },

  hideBoot() {
    $("#boot-overlay").attr("hidden", true);
  },
};

function onsReady() {
  return new Promise((resolve) => {
    if (window.ons && window.ons.ready) {
      window.ons.ready(resolve);
    } else {
      document.addEventListener("DOMContentLoaded", resolve);
    }
  });
}

window.addEventListener("error", (event) => {
  console.error("[gs] error no controlado", event.error || event.message);
});
window.addEventListener("unhandledrejection", (event) => {
  console.error("[gs] promesa rechazada", event.reason);
});

App.boot();

export default App;
