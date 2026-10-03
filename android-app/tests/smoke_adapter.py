#!/usr/bin/env python3
"""
smoke_adapter.py
================

Prueba de humo de la integración sin red:

    config + soc  ->  android_adapter.run_plan(engine=fake)  ->  contrato JSON

Además escribe ``tests/fixtures/plan_result.json`` con el contrato real
generado por el adaptador; las pruebas JavaScript validan el mapper
contra ese mismo fixture (evita duplicar la forma del contrato a mano).

Uso:

    python3 tests/smoke_adapter.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import android_adapter as adapter  # noqa: E402
from test_adapter import build_fake_engine, HOY  # noqa: E402

CONFIG = {
    "location": {"municipality": "Maracena", "region": "Granada"},
    "pv": {"panels": 10, "panel_power_w": 605.0, "inclination_deg": 33.0, "azimuth_deg": 0.0},
    "battery": {"units": 2, "capacity_kwh_unit": 5.12, "min_soc": 0.2, "max_soc": 0.85},
    "home": {"adults": 2, "children": 3},
    "loads": {"lavadora": {"flexible": True, "power_kw": 1.0, "duration_h": 1.5, "window": ["12:00", "15:00"]}},
    "strategy": "sostenible_predictiva",
}


def main() -> int:
    engine = build_fake_engine()
    result = adapter.run_plan(config=CONFIG, soc=0.62, refresh=False, date=HOY, engine=engine)

    assert isinstance(result, dict), "run_plan debe devolver un dict"
    assert result["status"] == "ok", f"estado inesperado: {result.get('status')}"
    assert result["schema_version"] == adapter.SCHEMA_VERSION
    assert result["today_actions"], "debe haber acciones para hoy"
    assert result["weekly_plan"], "debe haber plan semanal"

    text = adapter.dumps(result)
    json.loads(text)  # JSON válido

    fixtures = os.path.join(HERE, "fixtures")
    os.makedirs(fixtures, exist_ok=True)
    with open(os.path.join(fixtures, "plan_result.json"), "w", encoding="utf-8") as fh:
        fh.write(text)

    print("status            :", result["status"])
    print("acciones hoy      :", len(result["today_actions"]))
    print("días de la semana :", len(result["weekly_plan"]))
    print("calidad solar     :", result["forecast"]["quality"])
    print("PV diaria (kWh)   :", result["pv"]["energia_kwh"])
    print("fixture           :", os.path.join("tests", "fixtures", "plan_result.json"))
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
