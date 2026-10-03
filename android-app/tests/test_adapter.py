#!/usr/bin/env python3
"""
test_adapter.py
===============

Pruebas del adaptador Android <-> motor Python.

Se ejecutan sin red y sin credenciales reales:

    * la orquestación se prueba con un motor de prueba inyectado
      (``engine=``), verificando el mismo recorrido que ``main.py``;
    * la inyección de configuración se prueba contra los módulos
      reales ``config.py`` y ``demand.py`` (no necesitan red).

Ejecución:

    python3 -m unittest discover -s tests -v
    # o
    make test
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)
ENGINE_DIR = os.path.dirname(APP_DIR)

sys.path.insert(0, APP_DIR)
sys.path.insert(0, ENGINE_DIR)

import android_adapter as adapter  # noqa: E402


# ==========================================================
# Motor de prueba
# ==========================================================

HOY = date(2026, 9, 21)


def _perfil_fv():
    return [
        {
            "hora": "%02d:00" % h,
            "potencia_fv_kw": round(max(0.0, 5.0 - abs(13 - h)), 4),
            "irradiancia_predicha_wm2": 800.0 if 10 <= h <= 16 else 0.0,
            "estado_cielo": "despejado",
            "temperatura_ambiente_c": 20.0,
        }
        for h in range(24)
    ]


def _perfil_demanda():
    return [
        {"hora": "%02d:00" % h, "potencia_total_kw": 0.3 + (0.4 if 19 <= h <= 22 else 0.0)}
        for h in range(24)
    ]


def _balance():
    rows = []
    for h in range(24):
        fv = round(max(0.0, 5.0 - abs(13 - h)), 4)
        rows.append(
            {
                "hora": "%02d:00" % h,
                "demanda_kw": 0.4,
                "fv_kw": fv,
                "balance_kw": round(fv - 0.4, 4),
                "autoconsumo_kw": round(min(fv, 0.4), 4),
                "excedente_kw": round(max(fv - 0.4, 0.0), 4),
                "deficit_kw": round(max(0.4 - fv, 0.0), 4),
                "precio_compra": 0.12,
                "precio_venta": 0.06,
                "coste_neto_eur": 0.0,
            }
        )
    return rows


def _plan_horario():
    rows = []
    for h in range(24):
        if 12 <= h <= 13:
            accion, razon = "CARGAR_BATERIA", "Excedente solar disponible."
        elif h in (20, 21):
            accion, razon = "DESCARGAR_BATERIA + AUTOCONSUMO", "Precio elevado."
        else:
            accion, razon = "AUTOCONSUMO", "Producción solar."
        rows.append(
            {
                "hora": "%02d:00" % h,
                "demanda_kw": 0.4,
                "fv_kw": 1.0,
                "precio_compra": 0.12,
                "precio_venta": 0.06,
                "soc_inicio": 0.6,
                "soc_objetivo": 0.6,
                "soc_fin": 0.6,
                "autoconsumo_kw": 0.4,
                "carga_bateria_kw": 0.0,
                "descarga_bateria_kw": 0.0,
                "compra_red_kw": 0.0,
                "venta_red_kw": 0.0,
                "deficit_futuro_valioso_kwh": 0.0,
                "accion": accion,
                "razon": razon,
                "coste_compra_eur": 0.0,
                "ingreso_venta_eur": 0.0,
                "coste_neto_eur": 0.0,
            }
        )
    return rows


def build_fake_engine():
    config = SimpleNamespace(
        obtener_configuracion_sistema=lambda: {
            "nombre": "Instalación de prueba",
            "localizacion": {"municipio": "Maracena", "provincia": "Granada"},
            "bateria": {"soc_min_normal": 0.20, "soc_max_normal": 0.85},
        },
        NUM_PANELES=10,
        PANEL_POTENCIA_W=605.0,
        POTENCIA_FV_KWP=6.05,
        PANEL_INCLINACION_GRADOS=33.0,
        PANEL_AZIMUT_GRADOS=0.0,
        MUNICIPIO="Maracena",
        PROVINCIA="Granada",
        LATITUD=None,
        LONGITUD=None,
        NUM_BATERIAS=2,
        BATERIA_ENERGIA_KWH_UNIDAD=5.12,
        SOC_MIN_NORMAL=0.20,
        SOC_MAX_NORMAL=0.85,
    )
    demand = SimpleNamespace(
        obtener_configuracion_demanda=lambda fecha=None: {
            "ocupantes": {"adultos": 2, "ninos": 3, "total": 5},
            "potencia_base_kw": 0.18,
            "energia_diaria_teorica_kwh": 8.4,
            "perfil_24h": _perfil_demanda(),
        },
        NUM_ADULTOS=2,
        NUM_NINOS=3,
        NUM_OCUPANTES=5,
        PRIORIDAD_RED_SOBRE_BATERIA=True,
        LAVADORA={"nombre": "lavadora", "potencia_kw": 1.0, "duracion_h": 1.5, "flexible": True},
    )
    aemet = SimpleNamespace(
        obtener_prevision_solar=lambda municipio, refresh=False: [
            {
                "fecha": HOY,
                "score": 0.82,
                "cielo_score": 0.7,
                "precip": 5.0,
                "tmax": 25,
                "tmin": 15,
            },
            {"fecha": date(2026, 9, 22), "score": 0.6, "precip": 20.0, "tmax": 23, "tmin": 14},
        ]
    )
    aemet_hourly = SimpleNamespace(
        obtener_prevision_horaria=lambda municipio, refresh=False: [
            {"fecha": HOY, "horas": [{"hora": "12:00", "temperatura_c": 22.0, "estado_cielo": "despejado"}]}
        ]
    )
    esios = SimpleNamespace(
        obtener_precios=lambda fecha, refresh=False: [
            {"hora": "%02d:00" % h, "precio_compra": 0.12, "precio_venta": 0.06} for h in range(24)
        ]
    )
    solar = SimpleNamespace(
        obtener_perfil_fv_24h=lambda fecha, configuracion, prevision_horaria=None, prevision_diaria=None: _perfil_fv(),
        energia_fv_diaria=lambda perfil: 12.5,
        obtener_pico_fv=lambda perfil: {"hora": "13:00", "potencia_fv_kw": 5.0},
    )
    balance = SimpleNamespace(
        calcular_balance_horario=lambda perfil_demanda, perfil_fv, precios: _balance(),
        calcular_metricas_balance=lambda balance: {
            "energia_demanda_kwh": 8.4,
            "energia_fv_kwh": 12.5,
            "autoconsumo_pct": 55.0,
        },
    )
    dispatch = SimpleNamespace(
        generar_plan_sostenible_predictivo=lambda balance, configuracion, soc_inicial: _plan_horario(),
        calcular_metricas_plan=lambda plan, configuracion: {"soc_final": 0.6, "ciclos_equivalentes": 0.1},
    )
    optimizer = SimpleNamespace(
        optimizar=lambda sistema, prevision, precios, demanda=None, estrategia="sostenible_predictiva": {
            "estrategia": estrategia,
            "acciones": ["Concentrar las cargas flexibles en las horas de mayor disponibilidad solar."],
            "razones": ["La estrategia sostenible busca reducir ciclos de batería."],
            "metricas": {"energia_fv_kwh": 12.5},
            "sostenibilidad": {"soc": sistema.get("soc")},
            "meteorologia": {"calidad_solar": "alta", "indice_solar": 0.82},
            "economia": {
                "hora_compra_minima": {"hora": "03:00", "compra": 0.08},
                "hora_compra_maxima": {"hora": "20:00", "compra": 0.25},
                "hora_venta_maxima": {"hora": "13:00", "venta": 0.10},
            },
            "demanda": {"energia_diaria_teorica_kwh": 8.4},
        },
    )
    weekly = SimpleNamespace(
        generar_plan_semanal=lambda demanda, prevision_semanal, prevision_horaria=None: {
            "version": 4,
            "estacion": "verano",
            "horizonte_dias": 2,
            "dias": [
                {
                    "fecha": HOY,
                    "dia_semana": "lunes",
                    "calidad_solar": "excelente",
                    "confianza": "alta",
                    "temperatura_max": 25,
                    "temperatura_min": 15,
                    "precipitacion": 5.0,
                },
                {
                    "fecha": date(2026, 9, 22),
                    "dia_semana": "martes",
                    "calidad_solar": "bueno",
                    "confianza": "alta",
                    "temperatura_max": 23,
                    "temperatura_min": 14,
                    "precipitacion": 20.0,
                },
            ],
            "tareas": [
                {
                    "servicio": "lavadora",
                    "descripcion": "Lavadora",
                    "tipo": "tarea",
                    "fecha": HOY,
                    "dia_semana": "lunes",
                    "hora_inicio": "12:00",
                    "hora_fin": "13:30",
                    "potencia_kw": 1.0,
                    "score_solar": 0.82,
                    "confianza": "alta",
                    "motivo": "Mayor excedente solar previsto.",
                }
            ],
            "termicas": [],
            "acs": [],
            "riego": [],
            "hornos_solares": [],
        }
    )
    return SimpleNamespace(
        config=config,
        demand=demand,
        aemet=aemet,
        aemet_hourly=aemet_hourly,
        esios=esios,
        solar=solar,
        balance=balance,
        dispatch=dispatch,
        optimizer=optimizer,
        weekly=weekly,
    )


# ==========================================================
# Pruebas
# ==========================================================

class TestValidation(unittest.TestCase):
    def test_soc_valido(self):
        self.assertEqual(adapter.validate_soc(0.62), 0.62)
        self.assertEqual(adapter.validate_soc(1), 1.0)

    def test_soc_fuera_de_rango(self):
        with self.assertRaises(adapter.AdapterError) as ctx:
            adapter.validate_soc(1.5)
        self.assertEqual(ctx.exception.category, "CONFIGURATION_ERROR")

    def test_soc_no_numerico(self):
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_soc("alto")

    def test_estrategia_invalida(self):
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_estrategia("desconocida")

    def test_estrategia_por_defecto(self):
        self.assertEqual(adapter.validate_estrategia(None), adapter.ESTRATEGIA_DEFAULT)


class TestRunPlanContract(unittest.TestCase):
    def setUp(self):
        self.engine = build_fake_engine()
        self.config = {
            "location": {"municipality": "Maracena", "region": "Granada"},
            "pv": {"panels": 12, "panel_power_w": 500.0, "inclination_deg": 30, "azimuth_deg": 0},
            "battery": {"units": 2, "capacity_kwh_unit": 5.12, "min_soc": 0.2, "max_soc": 0.9},
            "home": {"adults": 2, "children": 2},
            "loads": {"lavadora": {"flexible": True, "power_kw": 1.1, "duration_h": 2.0}},
            "strategy": "sostenible_predictiva",
        }

    def test_run_plan_ok(self):
        result = adapter.run_plan(
            config=self.config,
            soc=0.62,
            refresh=False,
            date=HOY,
            engine=self.engine,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["schema_version"], adapter.SCHEMA_VERSION)
        self.assertEqual(result["input"]["soc"], 0.62)
        self.assertEqual(result["forecast"]["quality"], "alta")
        self.assertTrue(result["pv"]["perfil"])
        self.assertTrue(result["today_actions"])
        self.assertTrue(result["weekly_plan"])
        self.assertEqual(result["cache_status"], "cached")

    def test_run_plan_refresh(self):
        result = adapter.run_plan(config=self.config, soc=0.5, refresh=True, date=HOY, engine=self.engine)
        self.assertEqual(result["cache_status"], "updated")

    def test_resultado_json_serializable(self):
        result = adapter.run_plan(config=self.config, soc=0.62, date=HOY, engine=self.engine)
        text = adapter.dumps(result)
        self.assertIn('"schema_version"', text)
        json.loads(text)

    def test_today_actions_agrupadas(self):
        result = adapter.run_plan(config=self.config, soc=0.62, date=HOY, engine=self.engine)
        titles = [a["title"] for a in result["today_actions"]]
        self.assertTrue(any("batería" in t for t in titles))
        carga = next(a for a in result["today_actions"] if a["kind"] == "battery" and "Cargar" in a["title"])
        self.assertEqual(carga["start"], "12:00")
        self.assertEqual(carga["end"], "14:00")

    def test_reason_codes_presentes(self):
        result = adapter.run_plan(config=self.config, soc=0.10, date=HOY, engine=self.engine)
        codes = {r["code"] for a in result["today_actions"] for r in a["reasons"]}
        self.assertIn("HIGH_PV_FORECAST", codes)
        self.assertIn("LOW_SOC", codes)

    def test_warning_soc_minimo(self):
        result = adapter.run_plan(config=self.config, soc=0.10, date=HOY, engine=self.engine)
        self.assertTrue(result["warnings"])

    def test_weekly_plan_dias(self):
        result = adapter.run_plan(config=self.config, soc=0.62, date=HOY, engine=self.engine)
        dias = result["weekly_plan"]
        self.assertEqual(len(dias), 2)
        self.assertEqual(dias[0]["weekday"], "lunes")
        self.assertEqual(dias[0]["actions"][0]["title"], "Lavadora")

    def test_validate_no_lanza(self):
        # El contrato promete NUNCA lanzar: devuelve status=error.
        result = adapter.run_plan(config=self.config, soc=2.0, date=HOY, engine=self.engine)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["category"], "CONFIGURATION_ERROR")
        self.assertEqual(result["today_actions"], [])


class TestDemoMode(unittest.TestCase):
    """El modo demo ejecuta el motor con fuentes de datos simuladas."""

    def test_run_plan_demo_marca_resultado(self):
        engine = build_fake_engine()
        result = adapter.run_plan(config={}, soc=0.6, date=HOY, demo=True, engine=engine)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["demo"])
        self.assertTrue(any("demostración" in w.lower() for w in result["warnings"]))
        self.assertEqual(result["sources"]["aemet"]["status"], "demo")

    def test_demo_no_exige_credenciales(self):
        engine = build_fake_engine()
        result = adapter.run_plan(
            config={}, soc=0.6, date=HOY, demo=True, credentials=None, engine=engine
        )
        self.assertEqual(result["status"], "ok")

    def test_demo_acepta_credenciales_vacias(self):
        # La UI envía {aemet_api_key:"", esios_token:""} cuando no hay nada
        # guardado; el modo demo debe seguir funcionando.
        engine = build_fake_engine()
        result = adapter.run_plan(
            config={},
            soc=0.6,
            date=HOY,
            demo=True,
            credentials={"aemet_api_key": "", "esios_token": ""},
            engine=engine,
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["demo"])

    def test_fixtures_diarios_estructura(self):
        dias = adapter._demo_daily_days(HOY, 7)
        self.assertEqual(len(dias), 7)
        for dia in dias:
            self.assertIn("estadoCielo", dia)
            self.assertIn("probPrecipitacion", dia)
            self.assertIn("temperatura", dia)
        self.assertTrue(dias[0]["fecha"].startswith(str(HOY)))
        self.assertTrue(dias[1]["fecha"].startswith(str(HOY + timedelta(days=1))))

    def test_fixtures_horarios_estructura(self):
        dias = adapter._demo_hourly_days(HOY, 2)
        self.assertEqual(len(dias), 2)
        self.assertEqual(len(dias[0]["temperatura"]), 24)
        self.assertEqual(dias[0]["temperatura"][0]["periodo"], "00")
        self.assertEqual(len(dias[0]["estadoCielo"]), 24)
        self.assertIn("descripcion", dias[0]["estadoCielo"][12])

    def test_fixture_precios_estructura(self):
        ind = adapter._demo_esios_indicator(1001, HOY)
        self.assertEqual(len(ind["values"]), 24)
        self.assertEqual(ind["values"][0]["geo_id"], 8741)
        self.assertIn("T", ind["values"][0]["datetime"])
        self.assertEqual(adapter._demo_esios_indicator(600, HOY)["values"][0]["geo_id"], 3)

    def test_install_demo_sources_sustituye_accesos(self):
        engine = build_fake_engine()
        engine.aemet.fetch_forecast = lambda *a, **k: None
        engine.aemet_hourly.fetch_forecast_hourly = lambda *a, **k: None
        engine.esios.obtener_indicador = lambda *a, **k: None
        engine.solar.consultar_pvgis = lambda *a, **k: None

        adapter._install_demo_sources(engine, HOY)

        self.assertEqual(engine.aemet.fetch_forecast(), adapter._demo_daily_days(HOY, 7))
        self.assertIsNotNone(engine.aemet_hourly.fetch_forecast_hourly())
        self.assertEqual(engine.esios.obtener_indicador(600)["values"][0]["geo_id"], 3)
        self.assertIsInstance(engine.solar.consultar_pvgis(), list)


class TestCredentials(unittest.TestCase):
    def test_write_token_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter._write_token_file(tmp, "CLAVE_AEMET", "TOKEN_ESIOS")
            path = os.path.join(tmp, "mytoken.env")
            self.assertTrue(os.path.isfile(path))
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("CLAVE_AEMET", content)
            self.assertIn("TOKEN_ESIOS", content)
            self.assertEqual(len(content.splitlines()), 2)

    def test_write_token_file_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter._write_token_file(tmp, "X", "Y")
            path = os.path.join(tmp, "mytoken.env")
            mtime = os.stat(path).st_mtime_ns
            adapter._write_token_file(tmp, "X", "Y")
            self.assertEqual(os.stat(path).st_mtime_ns, mtime)

    def test_credenciales_no_aparecen_en_resultado(self):
        engine = build_fake_engine()
        result = adapter.run_plan(
            config={},
            credentials={"aemet_api_key": "SECRETO_AEMET", "esios_token": "SECRETO_ESIOS"},
            soc=0.6,
            date=HOY,
            engine=engine,
        )
        text = adapter.dumps(result)
        self.assertNotIn("SECRETO_AEMET", text)
        self.assertNotIn("SECRETO_ESIOS", text)


class TestErrorClassification(unittest.TestCase):
    def test_timeout(self):
        class Timeout(Exception):
            pass

        Timeout.__name__ = "Timeout"
        err = adapter.classify_exception(Timeout("t"))
        self.assertEqual(err.category, "NETWORK_ERROR")

    def test_https_401(self):
        class HTTPError(Exception):
            pass

        HTTPError.__name__ = "HTTPError"
        exc = HTTPError("401")
        exc.response = SimpleNamespace(status_code=401)
        err = adapter.classify_exception(exc)
        self.assertEqual(err.category, "AUTHENTICATION_ERROR")

    def test_credencial(self):
        err = adapter.classify_exception(RuntimeError("No se encontró AEMET_API_KEY en mytoken.env."))
        self.assertEqual(err.category, "AUTHENTICATION_ERROR")


class TestSeleccionPrevision(unittest.TestCase):
    def test_selecciona_hoy(self):
        prevision = [{"fecha": date(2026, 9, 20)}, {"fecha": HOY}]
        self.assertEqual(adapter._seleccionar_prevision_hoy(prevision, HOY)["fecha"], HOY)

    def test_falta_hoy(self):
        with self.assertRaises(adapter.AdapterError):
            adapter._seleccionar_prevision_hoy([{"fecha": date(2026, 9, 20)}], HOY)


# ==========================================================
# Inyección de configuración contra los módulos reales
# ==========================================================

class TestConfigInjection(unittest.TestCase):
    """Usa los módulos reales config.py y demand.py (sin red ni secretos)."""

    @classmethod
    def setUpClass(cls):
        cls.config = _import_real("config")
        cls.demand = _import_real("demand")

    def test_aplica_instalacion(self):
        adapter.apply_installation_config(
            self.config,
            {
                "location": {"municipality": "Motril", "region": "Granada", "latitude": 36.7, "longitude": -3.5},
                "pv": {"panels": 12, "panel_power_w": 500.0, "inclination_deg": 30.0, "azimuth_deg": -10.0},
                "home": {"adults": 3, "children": 1},
            },
        )
        cfg = self.config.obtener_configuracion_sistema()
        self.assertEqual(cfg["localizacion"]["municipio"], "Motril")
        self.assertEqual(cfg["fotovoltaica"]["numero_paneles"], 12)
        self.assertAlmostEqual(cfg["fotovoltaica"]["potencia_total_kwp"], 6.0, places=3)
        self.assertAlmostEqual(cfg["fotovoltaica"]["azimut_grados"], -10.0, places=3)
        self.assertEqual(self.demand.NUM_OCUPANTES, 4)

    def test_recomputa_energia_bateria(self):
        adapter.apply_installation_config(
            self.config,
            {"battery": {"units": 3, "capacity_kwh_unit": 5.0, "min_soc": 0.15, "max_soc": 0.95}},
        )
        cfg = self.config.obtener_configuracion_sistema()
        self.assertEqual(cfg["bateria"]["numero_unidades"], 3)
        self.assertAlmostEqual(cfg["bateria"]["energia_total_kwh"], 15.0, places=3)
        self.assertAlmostEqual(cfg["bateria"]["energia_util_sostenible_kwh"], 15.0 * (0.95 - 0.15), places=3)

    def test_lavadora_flexible(self):
        adapter.apply_demand_config(
            self.demand,
            {"loads": {"lavadora": {"flexible": False, "power_kw": 1.3, "duration_h": 2.0, "window": ["10:00", "16:00"]}}},
        )
        self.assertFalse(self.demand.LAVADORA["flexible"])
        self.assertAlmostEqual(self.demand.LAVADORA["potencia_kw"], 1.3)
        self.assertEqual(self.demand.LAVADORA["ventana_solar_preferida"], ("10:00", "16:00"))


def _import_real(name):
    path = os.path.join(ENGINE_DIR, name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main(verbosity=2)
