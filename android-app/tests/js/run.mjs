/**
 * run.mjs — pruebas JavaScript de la UI (sin navegador)
 * =====================================================
 *
 * Verifica los módulos puros (formato, razones, persistencia, mapper)
 * tanto con datos sintéticos como con el contrato real generado por
 * `python3 tests/smoke_adapter.py` (tests/fixtures/plan_result.json).
 *
 *     node tests/js/run.mjs
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import * as format from "../../mvp/js/format.js";
import * as reasons from "../../mvp/js/reasons.js";
import * as store from "../../mvp/js/store.js";
import { mapPlan } from "../../mvp/js/mapper.js";
import { buildDemoResult, buildDemoError } from "../../mvp/js/demo.js";

const HERE = dirname(fileURLToPath(import.meta.url));

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed += 1;
    console.log(`  \x1b[32m✓\x1b[0m ${name}`);
  } catch (err) {
    failed += 1;
    console.error(`  \x1b[31m✗\x1b[0m ${name}\n      ${err.message}`);
  }
}

function eq(actual, expected, msg = "") {
  if (actual !== expected) {
    throw new Error(`${msg} esperado ${JSON.stringify(expected)}, obtenido ${JSON.stringify(actual)}`);
  }
}

function ok(value, msg = "valor falsy") {
  if (!value) throw new Error(msg);
}

function group(title) {
  console.log(`\n\x1b[1m${title}\x1b[0m`);
}

/* -------------------- format.js -------------------- */

group("format.js");
test("formatSoc convierte 0..1 a porcentaje", () => {
  eq(format.formatSoc(0.62), "62 %");
  eq(format.formatSoc(1), "100 %");
});
test("formatEnergy con separador decimal local", () => {
  ok(/^12[,.]5 kWh$/.test(format.formatEnergy(12.5)), format.formatEnergy(12.5));
});
test("formatPower", () => {
  ok(/^5[,.]0 kW$/.test(format.formatPower(5)), format.formatPower(5));
});
test("formatPrice", () => {
  ok(/^0[,.]123 €\/kWh$/.test(format.formatPrice(0.123, 3)), format.formatPrice(0.123, 3));
});
test("formatTimeWindow", () => {
  eq(format.formatTimeWindow("12:00", "15:00"), "12:00 – 15:00");
  eq(format.formatTimeWindow(null, "15:00"), "hasta 15:00");
  eq(format.formatTimeWindow(null, null), null);
});
test("maskSecret oculta salvo la cola", () => {
  ok(format.maskSecret("ABCDEFGH").endsWith("EFGH"));
  ok(format.maskSecret("ABCDEFGH").startsWith("•"));
});
test("valores ausentes devuelven guion", () => {
  eq(format.formatEnergy(null), "—");
  eq(format.formatSoc(undefined), "—");
});

/* -------------------- reasons.js -------------------- */

group("reasons.js");
test("reasonText traduce códigos conocidos", () => {
  ok(reasons.reasonText("HIGH_PV_FORECAST").toLowerCase().includes("fotovoltaica"));
  ok(reasons.reasonText("FLEXIBLE_LOAD").toLowerCase().includes("flexible"));
});
test("reasonText tiene texto por defecto", () => {
  ok(reasons.reasonText("DESCONOCIDO").length > 0);
});
test("severityLabel", () => {
  eq(reasons.severityLabel("warning"), "Atención");
  eq(reasons.severityLabel("important"), "Recomendado");
});

/* -------------------- store.js -------------------- */

group("store.js");
test("defaultConfig contiene la estructura esperada", () => {
  const c = store.defaultConfig();
  ok(c.location.municipality);
  ok(c.pv.panels > 0);
  ok(c.battery.units > 0);
  eq(c.loads.lavadora.flexible, true);
});
test("guardar y cargar configuración", () => {
  const mem = store.memoryStorage();
  const c = store.defaultConfig();
  c.location.municipality = "Motril";
  store.saveConfig(c, mem);
  eq(store.loadConfig(mem).location.municipality, "Motril");
});
test("deepMerge respeta valores anidados", () => {
  const merged = store.deepMerge({ a: { x: 1, y: 2 } }, { a: { y: 5 } });
  eq(merged.a.x, 1);
  eq(merged.a.y, 5);
});
test("validateStep detecta errores", () => {
  ok(store.validateStep("pv", { pv: { panels: 0, panel_power_w: 605 } }).length > 0);
  eq(store.validateStep("pv", { pv: { panels: 10, panel_power_w: 605 } }).length, 0);
});
test("isConfigured requiere credenciales y configuración", () => {
  const c = store.defaultConfig();
  ok(!store.isConfigured(c, store.defaultCredentials()));
  ok(store.isConfigured(c, { aemet_api_key: "x", esios_token: "y" }));
});

/* -------------------- mapper.js -------------------- */

group("mapper.js (datos sintéticos)");
const demo = mapPlan(buildDemoResult(store.defaultConfig(), 0.62, false));
test("estado y frescura", () => {
  eq(demo.status, "ok");
  eq(demo.freshness.status, "cached");
});
test("recomendación principal", () => {
  ok(demo.primary);
  ok(demo.primary.title.length > 0);
  ok(demo.primary.reasons[0].text.length > 0);
});
test("plan semanal", () => {
  eq(demo.week.length, 7);
  ok(demo.week[0].label.length > 0);
});
test("energía", () => {
  ok(demo.energy.pvEnergyLabel.includes("kWh"));
  ok(demo.energy.balanceMetrics.length >= 3);
});
test("error mapeado", () => {
  const err = mapPlan(buildDemoError("AUTHENTICATION_ERROR"));
  eq(err.status, "error");
  ok(err.error.title.toLowerCase().includes("credencial"));
});

/* -------------------- contrato real (fixture) -------------------- */

group("mapper.js (contrato real del adaptador)");
let fixture = null;
try {
  fixture = JSON.parse(readFileSync(join(HERE, "..", "fixtures", "plan_result.json"), "utf8"));
} catch (err) {
  console.error("      (fixture no encontrado: ejecuta antes tests/smoke_adapter.py)");
}

if (fixture) {
  const ui = mapPlan(fixture);
  test("schema_version y estado", () => {
    eq(fixture.schema_version, 1);
    eq(ui.status, "ok");
  });
  test("la recomendación principal tiene ventana horaria", () => {
    ok(ui.primary);
    ok(ui.primary.timeWindow.includes("–"));
  });
  test("los códigos de razón se traducen", () => {
    const codes = ui.primary.reasons.map((r) => r.code);
    ok(codes.length > 0);
    ui.primary.reasons.forEach((r) => ok(r.text.length > 0));
  });
  test("el plan semanal trae días", () => {
    ok(ui.week.length >= 1);
    ok(ui.week[0].date);
  });
  test("energía con perfiles horarios", () => {
    eq(ui.energy.pvProfile.length, 24);
    eq(ui.energy.demandProfile.length, 24);
  });
}

/* -------------------- resumen -------------------- */

console.log(`\n${passed} pruebas correctas, ${failed} fallidas.`);
process.exit(failed === 0 ? 0 : 1);
