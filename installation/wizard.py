#!/usr/bin/env python3
"""
wizard.py

Asistente interactivo de configuración para Gestion-Solar-AEMET-ESIOS.

Este asistente genera:

    config.yaml
    config.py
    demand.py

config.yaml es la fuente de verdad de la configuración del usuario.
config.py y demand.py se regeneran automáticamente manteniendo la
interfaz pública esperada por el resto del programa.

Si config.yaml ya existe, el asistente pregunta si se desea conservar.
Si se conserva, no vuelve a preguntar todos los datos: utiliza el YAML
existente y regenera directamente config.py y demand.py.

El asistente presupone que install.sh ya ha creado mytoken.env con:

    AEMET_API_KEY=...
    ESIOS_API_KEY=...

Las claves nunca se copian a config.yaml.

Uso:
    python installation/wizard.py
    python installation/wizard.py --output /ruta/config.yaml
    python installation/wizard.py --force

Autor del proyecto: Enrique M. Moreno Pérez
"""

import argparse
import datetime as _dt
import importlib.util
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


APP_NAME = "Gestión Solar Predictiva"
CONFIG_VERSION = 1

KNOWN_INVERTERS = {
    "1": {
        "fabricante": "Deye",
        "modelo": "SUN-6K-SG05LP1-EU-AM2-P",
        "potencia_nominal_w": 6000.0,
        "bateria_v_min": 40.0,
        "bateria_v_max": 60.0,
        "corriente_carga_max_a": 135.0,
        "corriente_descarga_max_a": 135.0,
        "pv_voltage_max_v": 500.0,
        "pv_start_v": 125.0,
        "mppt_v_min": 150.0,
        "mppt_v_max": 425.0,
        "num_mppt": 2,
    },
}

KNOWN_BATTERIES = {
    "1": {
        "fabricante": "Deye",
        "modelo": "SE-G5.1 Pro-B",
        "tension_nominal_v": 51.2,
        "capacidad_ah_unidad": 100.0,
        "energia_kwh_unidad": 5.12,
        "corriente_recomendada_a_unidad": 50.0,
        "corriente_max_a_unidad": 100.0,
        "ciclos_referencia": 6000,
        "dod_referencia": 0.90,
        "eol_soh": 0.80,
    },
}

KNOWN_PANELS = {
    "1": {
        "fabricante": "JA Solar",
        "modelo": "605 W (perfil de referencia del proyecto)",
        "potencia_w": 605.0,
        "vmp_v": 45.05,
        "voc_v": 53.00,
        "imp_a": 13.43,
        "isc_a": 14.09,
        "coef_temp_pmax": -0.0029,
    },
}



def show_runtime_environment(project_dir):
    """Muestra el software detectado sin requerir dependencias externas."""
    print("Entorno detectado:")
    print("  Python:      {}".format(sys.version.split()[0]))
    print("  Ejecutable:  {}".format(sys.executable))
    print("  Plataforma:  {}".format(sys.platform))
    print("  Proyecto:    {}".format(project_dir))

    version = sys.version_info[:2]
    if version >= (3, 8):
        print("  Modo:        CURRENT")
    elif version >= (3, 6):
        print("  Modo:        LEGACY")
    else:
        print("  Modo:        NO COMPATIBLE")
    print()


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def hr(char: str = "=", width: int = 68) -> None:
    print(char * width)


def title(text: str) -> None:
    print()
    hr()
    print(text.center(68))
    hr()
    print()


def section(step: int, total: int, text: str) -> None:
    print()
    hr("-")
    print(f"PASO {step}/{total} — {text}")
    hr("-")
    print()


def info(text: str) -> None:
    print(text)


def warn(text: str) -> None:
    print(f"ADVERTENCIA: {text}")


def error(text: str) -> None:
    print(f"ERROR: {text}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Entrada y validación
# ---------------------------------------------------------------------------

def ask_text(
    prompt: str,
    default: Optional[str] = None,
    required: bool = True,
) -> str:
    while True:
        suffix = f" [{default}]" if default not in (None, "") else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default is not None:
            value = default
        if value or not required:
            return value
        print("Este valor es obligatorio.")


def ask_int(
    prompt: str,
    default: Optional[int] = None,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
    while True:
        raw = ask_text(
            prompt,
            str(default) if default is not None else None,
            required=True,
        )
        try:
            value = int(raw)
        except ValueError:
            print("Introduzca un número entero.")
            continue
        if minimum is not None and value < minimum:
            print(f"El valor mínimo permitido es {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"El valor máximo permitido es {maximum}.")
            continue
        return value


def ask_float(
    prompt: str,
    default: Optional[float] = None,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    while True:
        default_s = None if default is None else str(default)
        raw = ask_text(prompt, default_s, required=True).replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            print("Introduzca un número válido.")
            continue
        if minimum is not None and value < minimum:
            print(f"El valor mínimo permitido es {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"El valor máximo permitido es {maximum}.")
            continue
        return value


def ask_optional_float(
    prompt: str,
    default: Optional[float] = None,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> Optional[float]:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"{prompt}{suffix} (Enter = desconocido): ").strip()
        if not raw:
            return default
        raw = raw.replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            print("Introduzca un número válido o pulse Enter.")
            continue
        if minimum is not None and value < minimum:
            print(f"El valor mínimo permitido es {minimum}.")
            continue
        if maximum is not None and value > maximum:
            print(f"El valor máximo permitido es {maximum}.")
            continue
        return value


def ask_bool(prompt: str, default: bool = True) -> bool:
    marker = "S/n" if default else "s/N"
    while True:
        raw = input(f"{prompt} [{marker}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"s", "si", "sí", "y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Responda s o n.")


def ask_choice(prompt: str, choices: Dict[str, str], default: Optional[str] = None) -> str:
    while True:
        print(prompt)
        for key, label in choices.items():
            print(f"  {key}. {label}")
        suffix = f" [{default}]" if default else ""
        raw = input(f"Seleccione una opción{suffix}: ").strip()
        if not raw and default:
            raw = default
        if raw in choices:
            return raw
        print("Opción no válida.")


def ask_soc(prompt: str, default_percent: float) -> float:
    percent = ask_float(prompt, default_percent, 0.0, 100.0)
    return percent / 100.0


def normalize_name(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


# ---------------------------------------------------------------------------
# Proyecto, credenciales y municipios
# ---------------------------------------------------------------------------

def detect_project_dir() -> Path:
    script_dir = Path(__file__).resolve().parent
    parent = script_dir.parent
    if (parent / "main.py").exists():
        return parent
    if (script_dir / "main.py").exists():
        return script_dir
    return parent


def credentials_present(project_dir: Path) -> Tuple[bool, List[str]]:
    env_path = project_dir / "mytoken.env"
    if not env_path.exists():
        return False, ["mytoken.env"]

    values: Dict[str, str] = {}
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    except OSError:
        return False, ["mytoken.env ilegible"]

    missing = [
        key for key in ("AEMET_API_KEY", "ESIOS_API_KEY")
        if not values.get(key)
    ]
    return not missing, missing


def load_municipios(project_dir: Path) -> Dict[str, str]:
    path = project_dir / "municipios.py"
    if not path.exists():
        return {}

    try:
        spec = importlib.util.spec_from_file_location("_gsp_municipios", str(path))
        if spec is None or spec.loader is None:
            return {}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        data = getattr(module, "MUNICIPIOS", {})
        return dict(data) if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_municipio(
    municipios: Dict[str, str],
    municipio: str,
) -> Tuple[Optional[str], List[str]]:
    """
    Devuelve (codigo, sugerencias).

    municipios.py normaliza nombres sin provincia, por lo que esta primera
    versión valida el nombre pero guarda también la provincia introducida
    por el usuario para resolver ambigüedades en una fase posterior.
    """
    if not municipios:
        return None, []

    key = normalize_name(municipio)
    normalized_map = {normalize_name(k): v for k, v in municipios.items()}

    if key in normalized_map:
        return normalized_map[key], []

    suggestions = [
        original
        for original in municipios.keys()
        if key in normalize_name(original) or normalize_name(original) in key
    ][:8]
    return None, suggestions


# ---------------------------------------------------------------------------
# Equipos
# ---------------------------------------------------------------------------

def choose_panel() -> Dict[str, Any]:
    info("Puede usar el perfil de panel ya documentado en el proyecto o introducir otro.")
    choice = ask_choice(
        "Tipo de panel:",
        {
            "1": "JA Solar 605 W — perfil de referencia",
            "2": "Otro / configuración manual",
        },
        default="1",
    )

    if choice == "1":
        panel = dict(KNOWN_PANELS["1"])
        info(
            f"Perfil seleccionado: {panel['fabricante']} "
            f"{panel['modelo']}."
        )
        return panel

    return {
        "fabricante": ask_text("Fabricante del panel", required=False),
        "modelo": ask_text("Modelo del panel", required=False),
        "potencia_w": ask_float("Potencia nominal de cada panel [W]", 450.0, 1.0),
        "vmp_v": ask_optional_float("Vmp del panel [V]", minimum=0.0),
        "voc_v": ask_optional_float("Voc del panel [V]", minimum=0.0),
        "imp_a": ask_optional_float("Imp del panel [A]", minimum=0.0),
        "isc_a": ask_optional_float("Isc del panel [A]", minimum=0.0),
        "coef_temp_pmax": ask_optional_float(
            "Coeficiente térmico Pmax [fracción/°C; ej. -0.0034]"
        ),
    }


def choose_inverter() -> Dict[str, Any]:
    choice = ask_choice(
        "Inversor:",
        {
            "1": "Deye SUN-6K-SG05LP1-EU-AM2-P — perfil conocido",
            "2": "Otro / configuración manual",
        },
        default="1",
    )

    if choice == "1":
        inv = dict(KNOWN_INVERTERS["1"])
        info(f"Perfil seleccionado: {inv['fabricante']} {inv['modelo']}.")
        return inv

    potencia_kw = ask_float("Potencia nominal del inversor [kW]", 5.0, 0.1)
    return {
        "fabricante": ask_text("Fabricante del inversor"),
        "modelo": ask_text("Modelo del inversor"),
        "potencia_nominal_w": potencia_kw * 1000.0,
        "bateria_v_min": ask_optional_float("Tensión mínima de batería admitida [V]", minimum=0.0),
        "bateria_v_max": ask_optional_float("Tensión máxima de batería admitida [V]", minimum=0.0),
        "corriente_carga_max_a": ask_optional_float("Corriente máxima de carga [A]", minimum=0.0),
        "corriente_descarga_max_a": ask_optional_float("Corriente máxima de descarga [A]", minimum=0.0),
        "pv_voltage_max_v": ask_optional_float("Tensión FV máxima [V]", minimum=0.0),
        "pv_start_v": ask_optional_float("Tensión FV de arranque [V]", minimum=0.0),
        "mppt_v_min": ask_optional_float("Tensión MPPT mínima [V]", minimum=0.0),
        "mppt_v_max": ask_optional_float("Tensión MPPT máxima [V]", minimum=0.0),
        "num_mppt": ask_int("Número de MPPT", 2, 1),
    }


def choose_battery() -> Dict[str, Any]:
    has_battery = ask_bool("¿La instalación dispone de batería?", True)
    if not has_battery:
        return {
            "presente": False,
            "numero_unidades": 0,
        }

    choice = ask_choice(
        "Batería:",
        {
            "1": "Deye SE-G5.1 Pro-B — perfil conocido",
            "2": "Otra / configuración manual",
        },
        default="1",
    )

    if choice == "1":
        battery = dict(KNOWN_BATTERIES["1"])
    else:
        battery = {
            "fabricante": ask_text("Fabricante de la batería"),
            "modelo": ask_text("Modelo de la batería"),
            "tension_nominal_v": ask_float("Tensión nominal [V]", 51.2, 1.0),
            "capacidad_ah_unidad": ask_optional_float("Capacidad por unidad [Ah]", minimum=0.0),
            "energia_kwh_unidad": ask_float("Energía nominal por unidad [kWh]", 5.0, 0.01),
            "corriente_recomendada_a_unidad": ask_optional_float(
                "Corriente recomendada de carga/descarga por unidad [A]", minimum=0.0
            ),
            "corriente_max_a_unidad": ask_optional_float(
                "Corriente máxima por unidad [A]", minimum=0.0
            ),
            "ciclos_referencia": ask_int("Ciclos de referencia del fabricante", 6000, 1),
            "dod_referencia": ask_float(
                "DoD de referencia [%]", 90.0, 0.0, 100.0
            ) / 100.0,
            "eol_soh": ask_float(
                "SOH considerado fin de vida [%]", 80.0, 0.0, 100.0
            ) / 100.0,
        }

    battery["presente"] = True
    battery["numero_unidades"] = ask_int("Número de baterías", 2, 1)

    soc_min = ask_soc("SOC mínimo normal [%]", 20.0)
    soc_max = ask_soc("SOC máximo normal [%]", 85.0)
    while soc_max <= soc_min:
        print("El SOC máximo debe ser mayor que el SOC mínimo.")
        soc_min = ask_soc("SOC mínimo normal [%]", 20.0)
        soc_max = ask_soc("SOC máximo normal [%]", 85.0)

    soc_em_min = ask_soc("SOC mínimo de emergencia [%]", 10.0)
    soc_em_max = ask_soc("SOC máximo de emergencia [%]", 95.0)

    battery["soc_min_normal"] = soc_min
    battery["soc_max_normal"] = soc_max
    battery["soc_min_emergencia"] = soc_em_min
    battery["soc_max_emergencia"] = soc_em_max
    battery["eficiencia_carga"] = ask_float(
        "Eficiencia de carga [%]", 95.0, 1.0, 100.0
    ) / 100.0
    battery["eficiencia_descarga"] = ask_float(
        "Eficiencia de descarga [%]", 95.0, 1.0, 100.0
    ) / 100.0

    return battery


# ---------------------------------------------------------------------------
# Cargas y vivienda
# ---------------------------------------------------------------------------

def ask_time(prompt: str, default: str) -> str:
    while True:
        raw = ask_text(prompt, default)
        if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", raw):
            return raw
        print("Formato horario no válido. Use HH:MM, por ejemplo 12:30.")


def add_custom_loads() -> List[Dict[str, Any]]:
    loads: List[Dict[str, Any]] = []

    info(
        "Las cargas que registre se incorporarán a demand.py al finalizar."
    )
    info(
        "Si una carga coincide con una carga conocida (por ejemplo lavadora, "
        "termo_electrico o bomba_de_calor), sustituirá su equivalente del "
        "modelo de referencia para evitar duplicidades."
    )
    print()

    while ask_bool("¿Desea añadir/configurar una carga?", False):
        nombre = ask_text("Nombre corto de la carga")
        descripcion = ask_text("Descripción", nombre)
        potencia_kw = ask_float("Potencia aproximada [kW]", 1.0, 0.0)
        flexible = ask_bool("¿Puede desplazarse en el tiempo?", True)
        automatizable = ask_bool("¿Puede automatizarse?", False)
        requiere_presencia = ask_bool("¿Requiere presencia en la vivienda?", True)
        prioridad = ask_int("Prioridad (1 = alta)", 2, 1, 10)

        load: Dict[str, Any] = {
            "nombre": normalize_name(nombre).replace(" ", "_"),
            "descripcion": descripcion,
            "potencia_kw": potencia_kw,
            "flexible": flexible,
            "automatizable": automatizable,
            "requiere_presencia": requiere_presencia,
            "prioridad": prioridad,
        }

        if flexible:
            load["hora_inicio_permitida"] = ask_time(
                "Inicio de la ventana permitida", "10:00"
            )
            load["hora_fin_permitida"] = ask_time(
                "Fin de la ventana permitida", "18:00"
            )
            load["duracion_h"] = ask_float(
                "Duración aproximada [h]", 1.0, 0.05, 24.0
            )

        loads.append(load)
        print(f"✓ Carga '{descripcion}' registrada.\n")

    return loads


# ---------------------------------------------------------------------------
# Escritura YAML (sin dependencia externa)
# ---------------------------------------------------------------------------

_SIMPLE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    # JSON produce cadenas entrecomilladas compatibles con YAML 1.2.
    return json.dumps(str(value), ensure_ascii=False)


def yaml_key(key: Any) -> str:
    key_s = str(key)
    if _SIMPLE_KEY.fullmatch(key_s):
        return key_s
    return json.dumps(key_s, ensure_ascii=False)


def dump_yaml(data: Any, indent: int = 0) -> List[str]:
    sp = " " * indent
    lines: List[str] = []

    if isinstance(data, dict):
        for key, value in data.items():
            k = yaml_key(key)
            if isinstance(value, dict):
                if value:
                    lines.append(f"{sp}{k}:")
                    lines.extend(dump_yaml(value, indent + 2))
                else:
                    lines.append(f"{sp}{k}: {{}}")
            elif isinstance(value, list):
                if value:
                    lines.append(f"{sp}{k}:")
                    lines.extend(dump_yaml(value, indent + 2))
                else:
                    lines.append(f"{sp}{k}: []")
            else:
                lines.append(f"{sp}{k}: {yaml_scalar(value)}")
        return lines

    if isinstance(data, list):
        for value in data:
            if isinstance(value, dict):
                if not value:
                    lines.append(f"{sp}- {{}}")
                    continue
                first = True
                for key, item in value.items():
                    k = yaml_key(key)
                    prefix = f"{sp}- " if first else f"{sp}  "
                    if isinstance(item, dict):
                        lines.append(f"{prefix}{k}:")
                        lines.extend(dump_yaml(item, indent + 4))
                    elif isinstance(item, list):
                        if item:
                            lines.append(f"{prefix}{k}:")
                            lines.extend(dump_yaml(item, indent + 4))
                        else:
                            lines.append(f"{prefix}{k}: []")
                    else:
                        lines.append(f"{prefix}{k}: {yaml_scalar(item)}")
                    first = False
            elif isinstance(value, list):
                lines.append(f"{sp}-")
                lines.extend(dump_yaml(value, indent + 2))
            else:
                lines.append(f"{sp}- {yaml_scalar(value)}")
        return lines

    lines.append(f"{sp}{yaml_scalar(data)}")
    return lines


def write_config(path: Path, config: Dict[str, Any], force: bool) -> Optional[Path]:
    backup = None

    if path.exists():
        if not force:
            if not ask_bool(
                f"Ya existe {path.name}. ¿Desea sustituirlo?", False
            ):
                raise RuntimeError("El usuario decidió conservar la configuración existente.")

        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = path.with_name(f"{path.name}.bak.{stamp}")
        shutil.copy2(path, backup)

    path.parent.mkdir(parents=True, exist_ok=True)

    header = [
        "# ================================================================",
        "# Gestión Solar Predictiva — configuración de usuario",
        "# Generado automáticamente por installation/wizard.py",
        "#",
        "# No contiene las claves AEMET/ESIOS. Esas credenciales se guardan",
        "# exclusivamente en mytoken.env.",
        "# ================================================================",
        "",
    ]
    content = "\n".join(header + dump_yaml(config)) + "\n"

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)

    return backup


# ---------------------------------------------------------------------------
# Lectura del YAML generado por este asistente
# ---------------------------------------------------------------------------

def _parse_yaml_scalar(raw):
    raw = raw.strip()
    if raw == "null":
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw in ("{}", "[]"):
        return {} if raw == "{}" else []
    if raw.startswith('"'):
        return json.loads(raw)
    try:
        if re.fullmatch(r"[-+]?\d+", raw):
            return int(raw)
        if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", raw):
            return float(raw)
    except Exception:
        pass
    return raw


def load_generated_yaml(path):
    """
    Lee el subconjunto de YAML que escribe dump_yaml(), sin PyYAML.

    No pretende ser un parser YAML general. Su objetivo es poder reutilizar
    de forma segura config.yaml en sistemas legacy como Ubuntu 18.04 /
    Python 3.6 sin añadir dependencias externas.
    """
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    items = []
    for lineno, raw in enumerate(raw_lines, 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if "\t" in raw[:indent]:
            raise ValueError("config.yaml contiene tabuladores en la línea {}".format(lineno))
        items.append((indent, raw.strip(), lineno))

    if not items:
        raise ValueError("config.yaml está vacío.")

    def parse_mapping(start, indent):
        result = {}
        i = start
        while i < len(items):
            ind, content, lineno = items[i]
            if ind < indent:
                break
            if ind > indent:
                raise ValueError(
                    "Indentación inesperada en config.yaml, línea {}".format(lineno)
                )
            if content.startswith("-"):
                break
            if ":" not in content:
                raise ValueError("Línea YAML no válida: {}".format(lineno))
            key_raw, rest = content.split(":", 1)
            key = _parse_yaml_scalar(key_raw.strip()) if key_raw.strip().startswith('"') else key_raw.strip()
            rest = rest.strip()
            if rest:
                result[key] = _parse_yaml_scalar(rest)
                i += 1
                continue

            # Bloque anidado.
            if i + 1 >= len(items) or items[i + 1][0] <= indent:
                result[key] = {}
                i += 1
                continue

            next_indent, next_content, _ = items[i + 1]
            if next_content.startswith("-"):
                value, i = parse_list(i + 1, next_indent)
            else:
                value, i = parse_mapping(i + 1, next_indent)
            result[key] = value
        return result, i

    def parse_list(start, indent):
        result = []
        i = start
        while i < len(items):
            ind, content, lineno = items[i]
            if ind < indent:
                break
            if ind > indent:
                raise ValueError(
                    "Indentación inesperada en lista YAML, línea {}".format(lineno)
                )
            if not content.startswith("-"):
                break

            payload = content[1:].strip()
            if not payload:
                if i + 1 >= len(items) or items[i + 1][0] <= indent:
                    result.append(None)
                    i += 1
                    continue
                next_indent, next_content, _ = items[i + 1]
                if next_content.startswith("-"):
                    value, i = parse_list(i + 1, next_indent)
                else:
                    value, i = parse_mapping(i + 1, next_indent)
                result.append(value)
                continue

            # Elemento escalar.
            if ":" not in payload:
                result.append(_parse_yaml_scalar(payload))
                i += 1
                continue

            # Primer campo de un diccionario de lista: "- nombre: ..."
            key_raw, rest = payload.split(":", 1)
            key = _parse_yaml_scalar(key_raw.strip()) if key_raw.strip().startswith('"') else key_raw.strip()
            obj = {}
            rest = rest.strip()
            if rest:
                obj[key] = _parse_yaml_scalar(rest)
            else:
                obj[key] = {}

            i += 1

            # Campos siguientes del mismo objeto, al nivel indent+2.
            while i < len(items):
                ind2, content2, lineno2 = items[i]
                if ind2 <= indent:
                    break
                if ind2 != indent + 2:
                    raise ValueError(
                        "Indentación inesperada en objeto YAML, línea {}".format(lineno2)
                    )
                if content2.startswith("-") or ":" not in content2:
                    raise ValueError("Objeto YAML no válido, línea {}".format(lineno2))
                kraw, r2 = content2.split(":", 1)
                k2 = _parse_yaml_scalar(kraw.strip()) if kraw.strip().startswith('"') else kraw.strip()
                r2 = r2.strip()
                if r2:
                    obj[k2] = _parse_yaml_scalar(r2)
                    i += 1
                else:
                    if i + 1 >= len(items) or items[i + 1][0] <= ind2:
                        obj[k2] = {}
                        i += 1
                    else:
                        nind, ncontent, _ = items[i + 1]
                        if ncontent.startswith("-"):
                            nested, i = parse_list(i + 1, nind)
                        else:
                            nested, i = parse_mapping(i + 1, nind)
                        obj[k2] = nested

            result.append(obj)
        return result, i

    if items[0][1].startswith("-"):
        data, end = parse_list(0, items[0][0])
    else:
        data, end = parse_mapping(0, items[0][0])

    if end != len(items):
        raise ValueError("No se pudo interpretar config.yaml completamente.")
    if not isinstance(data, dict):
        raise ValueError("La raíz de config.yaml debe ser un diccionario.")
    return data


# ---------------------------------------------------------------------------
# Generación de config.py y demand.py
# ---------------------------------------------------------------------------

def _py(value):
    return repr(value)


def _template_path(project_dir, name):
    path = project_dir / "installation" / "templates" / name
    if not path.exists():
        raise RuntimeError(
            "Falta la plantilla {}. Debe existir en installation/templates/.".format(name)
        )
    return path


def _atomic_write(path, content):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(path))


def _generated_header(config_path):
    return (
        "\n\n# ==========================================================\n"
        "# BLOQUE GENERADO AUTOMÁTICAMENTE\n"
        "# ==========================================================\n"
        "# Fuente: {}\n"
        "# No editar manualmente este bloque: vuelva a ejecutar\n"
        "# installation/wizard.py para regenerarlo.\n"
        "# ==========================================================\n\n"
    ).format(config_path.name)


def generate_config_py(project_dir, config, config_path):
    template = _template_path(project_dir, "config.py.tpl")
    source = template.read_text(encoding="utf-8")
    marker = "\ndef obtener_configuracion_sistema():"
    if marker not in source:
        raise RuntimeError("La plantilla config.py.tpl no contiene obtener_configuracion_sistema().")

    sistema = config.get("sistema", {})
    ubicacion = config.get("ubicacion", {})
    fv = config.get("fotovoltaica", {})
    panel = fv.get("panel", {})
    inv = config.get("inversor", {})
    bat = config.get("bateria", {})
    ctl = config.get("control", {})

    presente = bool(bat.get("presente", True))
    num_bat = int(bat.get("numero_unidades", 0 if not presente else 1) or 0)

    overrides = []
    add = overrides.append

    add("SISTEMA_NOMBRE = {}".format(_py(sistema.get("nombre", "Instalación fotovoltaica residencial"))))
    add("SISTEMA_DESCRIPCION = {}".format(_py(sistema.get("descripcion", ""))))
    add("MUNICIPIO = {}".format(_py(ubicacion.get("municipio"))))
    add("PROVINCIA = {}".format(_py(ubicacion.get("provincia"))))
    add("LATITUD = {}".format(_py(ubicacion.get("latitud"))))
    add("LONGITUD = {}".format(_py(ubicacion.get("longitud"))))
    add("CODIGO_AEMET = {}".format(_py(ubicacion.get("codigo_aemet"))))
    add("")
    add("NUM_PANELES = {}".format(int(fv.get("numero_paneles", 0) or 0)))
    add("PANEL_POTENCIA_W = {}".format(float(panel.get("potencia_w", 0.0) or 0.0)))
    add("POTENCIA_FV_WP = NUM_PANELES * PANEL_POTENCIA_W")
    add("POTENCIA_FV_KWP = POTENCIA_FV_WP / 1000.0")
    add("PANEL_INCLINACION_GRADOS = {}".format(float(fv.get("inclinacion_grados", 0.0) or 0.0)))
    add("PANEL_AZIMUT_GRADOS = {}".format(float(fv.get("azimut_grados_pvgis", 0.0) or 0.0)))
    add("PANEL_VMP_V = {}".format(_py(panel.get("vmp_v"))))
    add("PANEL_VOC_V = {}".format(_py(panel.get("voc_v"))))
    add("PANEL_IMP_A = {}".format(_py(panel.get("imp_a"))))
    add("PANEL_ISC_A = {}".format(_py(panel.get("isc_a"))))
    add("PANEL_COEF_TEMP_PMAX = {}".format(_py(panel.get("coef_temp_pmax"))))
    add("")
    add("INVERSOR_FABRICANTE = {}".format(_py(inv.get("fabricante", ""))))
    add("INVERSOR_MODELO = {}".format(_py(inv.get("modelo", ""))))
    add("INVERSOR_POTENCIA_NOMINAL_W = {}".format(float(inv.get("potencia_nominal_w", 0.0) or 0.0)))
    add("INVERSOR_POTENCIA_NOMINAL_KW = INVERSOR_POTENCIA_NOMINAL_W / 1000.0")
    add("INVERSOR_BATERIA_V_MIN = {}".format(_py(inv.get("bateria_v_min"))))
    add("INVERSOR_BATERIA_V_MAX = {}".format(_py(inv.get("bateria_v_max"))))
    add("INVERSOR_CORRIENTE_CARGA_MAX_A = {}".format(float(inv.get("corriente_carga_max_a", 0.0) or 0.0)))
    add("INVERSOR_CORRIENTE_DESCARGA_MAX_A = {}".format(float(inv.get("corriente_descarga_max_a", 0.0) or 0.0)))
    add("INVERSOR_PV_VOLTAGE_MAX_V = {}".format(_py(inv.get("pv_voltage_max_v"))))
    add("INVERSOR_PV_START_V = {}".format(_py(inv.get("pv_start_v"))))
    add("INVERSOR_MPPT_V_MIN = {}".format(_py(inv.get("mppt_v_min"))))
    add("INVERSOR_MPPT_V_MAX = {}".format(_py(inv.get("mppt_v_max"))))
    add("INVERSOR_NUM_MPPT = {}".format(int(inv.get("num_mppt", 0) or 0)))
    add("")
    add("BATERIA_FABRICANTE = {}".format(_py(bat.get("fabricante", ""))))
    add("BATERIA_MODELO = {}".format(_py(bat.get("modelo", ""))))
    add("NUM_BATERIAS = {}".format(num_bat))
    add("BATERIA_TENSION_NOMINAL_V = {}".format(float(bat.get("tension_nominal_v", 0.0) or 0.0)))
    add("BATERIA_CAPACIDAD_AH_UNIDAD = {}".format(float(bat.get("capacidad_ah_unidad", 0.0) or 0.0)))
    add("BATERIA_ENERGIA_KWH_UNIDAD = {}".format(float(bat.get("energia_kwh_unidad", 0.0) or 0.0)))
    add("BATERIA_CAPACIDAD_AH_TOTAL = NUM_BATERIAS * BATERIA_CAPACIDAD_AH_UNIDAD")
    add("BATERIA_ENERGIA_KWH_TOTAL = NUM_BATERIAS * BATERIA_ENERGIA_KWH_UNIDAD")
    add("BATERIA_CORRIENTE_RECOMENDADA_A_UNIDAD = {}".format(float(bat.get("corriente_recomendada_a_unidad", 0.0) or 0.0)))
    add("BATERIA_CORRIENTE_MAX_A_UNIDAD = {}".format(float(bat.get("corriente_max_a_unidad", 0.0) or 0.0)))
    add("BATERIA_CORRIENTE_RECOMENDADA_A_TOTAL = NUM_BATERIAS * BATERIA_CORRIENTE_RECOMENDADA_A_UNIDAD")
    add("BATERIA_CORRIENTE_MAX_A_TOTAL = NUM_BATERIAS * BATERIA_CORRIENTE_MAX_A_UNIDAD")
    add("CORRIENTE_CARGA_MAX_FISICA_A = min(BATERIA_CORRIENTE_MAX_A_TOTAL, INVERSOR_CORRIENTE_CARGA_MAX_A)")
    add("CORRIENTE_DESCARGA_MAX_FISICA_A = min(BATERIA_CORRIENTE_MAX_A_TOTAL, INVERSOR_CORRIENTE_DESCARGA_MAX_A)")
    add("BATERIA_CICLOS_REFERENCIA = {}".format(int(bat.get("ciclos_referencia", 0) or 0)))
    add("BATERIA_DOD_REFERENCIA = {}".format(float(bat.get("dod_referencia", 0.0) or 0.0)))
    add("BATERIA_EOL_SOH = {}".format(float(bat.get("eol_soh", 0.0) or 0.0)))
    add("EFICIENCIA_CARGA_BATERIA = {}".format(float(bat.get("eficiencia_carga", 1.0) or 1.0)))
    add("EFICIENCIA_DESCARGA_BATERIA = {}".format(float(bat.get("eficiencia_descarga", 1.0) or 1.0)))
    add("EFICIENCIA_CICLO_BATERIA = EFICIENCIA_CARGA_BATERIA * EFICIENCIA_DESCARGA_BATERIA")
    add("SOC_MIN_NORMAL = {}".format(float(bat.get("soc_min_normal", 0.0) or 0.0)))
    add("SOC_MAX_NORMAL = {}".format(float(bat.get("soc_max_normal", 1.0) or 1.0)))
    add("SOC_MIN_EMERGENCIA = {}".format(float(bat.get("soc_min_emergencia", 0.0) or 0.0)))
    add("SOC_MAX_EMERGENCIA = {}".format(float(bat.get("soc_max_emergencia", 1.0) or 1.0)))
    add("BATERIA_ENERGIA_UTIL_SOSTENIBLE_KWH = BATERIA_ENERGIA_KWH_TOTAL * (SOC_MAX_NORMAL - SOC_MIN_NORMAL)")
    add("CORRIENTE_CARGA_PREFERIDA_A = min(BATERIA_CORRIENTE_RECOMENDADA_A_TOTAL, INVERSOR_CORRIENTE_CARGA_MAX_A)")
    add("CORRIENTE_DESCARGA_PREFERIDA_A = min(BATERIA_CORRIENTE_RECOMENDADA_A_TOTAL, INVERSOR_CORRIENTE_DESCARGA_MAX_A)")
    add("BATERIA_POTENCIA_CARGA_PREFERIDA_KW = BATERIA_TENSION_NOMINAL_V * CORRIENTE_CARGA_PREFERIDA_A / 1000.0")
    add("BATERIA_POTENCIA_DESCARGA_PREFERIDA_KW = BATERIA_TENSION_NOMINAL_V * CORRIENTE_DESCARGA_PREFERIDA_A / 1000.0")
    add("")
    add("MARGEN_ECONOMICO_MINIMO_EUR_KWH = {}".format(float(ctl.get("margen_economico_minimo_eur_kwh", 0.02) or 0.0)))
    add("SOSTENIBILIDAD_PRIORITARIA = {}".format(bool(ctl.get("sostenibilidad_prioritaria", True))))
    add("ESTRATEGIA_DEFAULT = {}".format(_py(ctl.get("estrategia_default", "sostenible_predictiva"))))
    add("HORIZONTE_OPTIMIZACION_HORAS = {}".format(int(ctl.get("horizonte_optimizacion_horas", 24) or 24)))
    add("PASO_TEMPORAL_HORAS = {}".format(float(ctl.get("paso_temporal_horas", 1.0) or 1.0)))
    add("")

    block = _generated_header(config_path) + "\n".join(overrides) + "\n"
    generated = source.replace(marker, block + marker, 1)
    target = project_dir / "config.py"
    _atomic_write(target, generated)
    return target


def _normalize_load_name(name):
    return normalize_name(str(name or "")).replace(" ", "_")


def generate_demand_py(project_dir, config, config_path):
    template = _template_path(project_dir, "demand.py.tpl")
    source = template.read_text(encoding="utf-8")

    vivienda = config.get("vivienda", {})
    demanda = config.get("demanda", {})
    custom = list(demanda.get("cargas_personalizadas", []) or [])

    # Normalizar y completar campos para que sean compatibles con las cargas
    # históricas de demand.py.
    clean_loads = []
    for item in custom:
        if not isinstance(item, dict):
            continue
        load = dict(item)
        load["nombre"] = _normalize_load_name(load.get("nombre"))
        load.setdefault("descripcion", load["nombre"])
        load.setdefault("potencia_kw", 0.0)
        load.setdefault("flexible", False)
        load.setdefault("automatizable", False)
        load.setdefault("requiere_presencia", False)
        load.setdefault("prioridad", 3)
        load.setdefault("estacional", "todo")
        load.setdefault("duracion_h", None)
        clean_loads.append(load)

    overrides = []
    add = overrides.append
    add("NUM_ADULTOS = {}".format(int(vivienda.get("adultos", 0) or 0)))
    add("NUM_NINOS = {}".format(int(vivienda.get("ninos", 0) or 0)))
    add("NUM_OCUPANTES = NUM_ADULTOS + NUM_NINOS")
    add("PRIORIDAD_RED_SOBRE_BATERIA = {}".format(bool(demanda.get("prioridad_red_sobre_bateria", True))))
    add("HORA_CIERRE_VENTANAS_VERANO = {}".format(_py(vivienda.get("hora_cierre_ventanas_verano", "11:00"))))
    add("VENTILACION_NOCTURNA_VERANO = {}".format(bool(vivienda.get("ventilacion_nocturna_verano", True))))
    add("CARGAS_PERSONALIZADAS = {}".format(repr(clean_loads)))
    add("")
    add("def _normalizar_nombre_carga(valor):")
    add("    texto = str(valor or '').strip().lower()")
    add("    import unicodedata as _unicodedata")
    add("    texto = _unicodedata.normalize('NFD', texto)")
    add("    texto = ''.join(c for c in texto if _unicodedata.category(c) != 'Mn')")
    add("    return '_'.join(texto.split())")
    add("")
    add("# Alias usados para evitar duplicar cargas del modelo de referencia.")
    add("_ALIAS_CARGAS = {")
    add("    'lavadora': {'lavadora'},")
    add("    'termo_electrico': {'termo_electrico'},")
    add("    'bomba_de_calor': {'bomba_calor_superior', 'bomba_calor_inferior'},")
    add("    'bomba_calor': {'bomba_calor_superior', 'bomba_calor_inferior'},")
    add("    'climatizacion': {'bomba_calor_superior', 'bomba_calor_inferior'},")
    add("}")
    add("")
    add("def _cargas_base_modelo():")
    add("    cargas = []")
    add("    cargas.extend(CARGAS_BASE)")
    add("    cargas.extend(CARGAS_COCINA)")
    add("    cargas.append(ACS['termo_electrico'])")
    add("    cargas.append(LAVADORA)")
    add("    cargas.append(CLIMATIZACION['planta_superior'])")
    add("    cargas.append(CLIMATIZACION['planta_inferior'])")
    add("    cargas.append(DESPENSA)")
    add("    cargas.append(RIEGO)")
    add("    cargas.append(UV_COCINA)")
    add("    return cargas")
    add("")
    add("def obtener_cargas():")
    add("    \"\"\"Devuelve cargas del modelo base con sustituciones de config.yaml.\"\"\"")
    add("    cargas = _cargas_base_modelo()")
    add("    for nueva in CARGAS_PERSONALIZADAS:")
    add("        nombre = _normalizar_nombre_carga(nueva.get('nombre'))")
    add("        retirar = set([nombre])")
    add("        retirar.update(_ALIAS_CARGAS.get(nombre, set()))")
    add("        cargas = [c for c in cargas if _normalizar_nombre_carga(c.get('nombre')) not in retirar]")
    add("        cargas.append(dict(nueva))")
    add("    return cargas")
    add("")

    block = _generated_header(config_path) + "\n".join(overrides) + "\n"

    # El bloque se añade al final para que sus asignaciones y la nueva
    # obtener_cargas() prevalezcan sobre la plantilla original.
    generated = source.rstrip() + block + "\n"
    target = project_dir / "demand.py"
    _atomic_write(target, generated)
    return target


def validate_generated_modules(project_dir):
    """
    Comprueba sintaxis e interfaz pública sin importar módulos externos.
    """
    import py_compile
    targets = [project_dir / "config.py", project_dir / "demand.py"]
    for target in targets:
        py_compile.compile(str(target), doraise=True)

    # Comprobación ligera de interfaz mediante importación directa.
    old_path = list(sys.path)
    try:
        sys.path.insert(0, str(project_dir))
        for name in ("config", "demand"):
            if name in sys.modules:
                del sys.modules[name]
        import config as _config
        import demand as _demand
        if not callable(getattr(_config, "obtener_configuracion_sistema", None)):
            raise RuntimeError("config.py no ofrece obtener_configuracion_sistema().")
        if not callable(getattr(_demand, "obtener_configuracion_demanda", None)):
            raise RuntimeError("demand.py no ofrece obtener_configuracion_demanda().")
        if not callable(getattr(_demand, "obtener_cargas", None)):
            raise RuntimeError("demand.py no ofrece obtener_cargas().")
        # Ejecutar las interfaces principales para detectar errores de
        # referencias globales en el código generado.
        _config.obtener_configuracion_sistema()
        _demand.obtener_cargas()
        _demand.obtener_configuracion_demanda()
    finally:
        sys.path[:] = old_path


def generate_python_modules(project_dir, config, config_path):
    config_target = generate_config_py(project_dir, config, config_path)
    demand_target = generate_demand_py(project_dir, config, config_path)
    validate_generated_modules(project_dir)
    return config_target, demand_target


def ensure_gitignore(project_dir: Path) -> None:
    path = project_dir / ".gitignore"
    entries = ["config.yaml", "mytoken.env", ".venv/", "__pycache__/", "*.pyc"]
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing_lines = set(existing.splitlines())
    with path.open("a", encoding="utf-8") as f:
        for entry in entries:
            if entry not in existing_lines:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                    existing += "\n"
                f.write(entry + "\n")
                existing_lines.add(entry)


# ---------------------------------------------------------------------------
# Construcción de la configuración
# ---------------------------------------------------------------------------

def run_wizard(project_dir: Path) -> Dict[str, Any]:
    total_steps = 7

    title(f"{APP_NAME} — Asistente de configuración")

    ok, missing = credentials_present(project_dir)
    if not ok:
        error(
            "No se han encontrado las credenciales obligatorias: "
            + ", ".join(missing)
        )
        print()
        print("Ejecute primero:")
        print()
        print("    ./installation/install.sh")
        print()
        print(
            "El instalador solicitará las claves de AEMET OpenData y ESIOS "
            "y creará mytoken.env."
        )
        raise SystemExit(2)

    print("✓ Credenciales AEMET/ESIOS detectadas (no se mostrarán).")
    print("✓ Este asistente NO copiará las claves a config.yaml.")

    # 1 — Identificación
    section(1, total_steps, "Identificación de la instalación")
    sistema_nombre = ask_text(
        "Nombre de la instalación",
        "Instalación fotovoltaica residencial",
    )
    sistema_descripcion = ask_text(
        "Descripción breve",
        "Sistema fotovoltaico gestionado por Gestión Solar Predictiva",
    )

    # 2 — Localización
    section(2, total_steps, "Localización")
    provincia = ask_text("Provincia")
    municipios = load_municipios(project_dir)

    while True:
        municipio = ask_text("Municipio")
        codigo_aemet, suggestions = resolve_municipio(municipios, municipio)

        if not municipios:
            warn(
                "No se pudo cargar municipios.py. Se guardará el municipio "
                "sin validar su código AEMET."
            )
            codigo_aemet = None
            break

        if codigo_aemet:
            print(f"✓ Municipio reconocido. Código municipal AEMET: {codigo_aemet}")
            break

        print("No se ha encontrado una coincidencia exacta en municipios.py.")
        if suggestions:
            print("Posibles coincidencias:")
            for s in suggestions:
                print(f"  - {s}")
        if ask_bool("¿Desea guardar este municipio de todas formas?", False):
            codigo_aemet = None
            break

    latitud = ask_optional_float(
        "Latitud [grados; normalmente puede dejarse sin indicar]",
        minimum=-90.0,
        maximum=90.0,
    )
    longitud = ask_optional_float(
        "Longitud [grados; normalmente puede dejarse sin indicar]",
        minimum=-180.0,
        maximum=180.0,
    )

    # 3 — FV
    section(3, total_steps, "Campo fotovoltaico")
    panel = choose_panel()
    num_paneles = ask_int("Número total de paneles", 10, 1)
    inclinacion = ask_float(
        "Inclinación respecto de la horizontal [°]", 30.0, 0.0, 90.0
    )
    print(
        "Convención de azimut PVGIS: 0°=Sur, -90°=Este, +90°=Oeste, ±180°=Norte."
    )
    azimut = ask_float("Azimut de los paneles [°]", 0.0, -180.0, 180.0)

    potencia_total_wp = num_paneles * float(panel["potencia_w"])

    # 4 — Inversor
    section(4, total_steps, "Inversor")
    inverter = choose_inverter()

    # 5 — Batería
    section(5, total_steps, "Batería")
    battery = choose_battery()

    # 6 — Vivienda y cargas
    section(6, total_steps, "Vivienda y cargas")
    adultos = ask_int("Número de adultos", 2, 0, 30)
    ninos = ask_int("Número de niños", 0, 0, 30)
    prioridad_red = ask_bool(
        "¿Priorizar la red frente a ciclos de batería de escaso valor?",
        True,
    )
    ventilacion_nocturna = ask_bool(
        "¿Se utiliza ventilación natural nocturna en verano?",
        True,
    )
    hora_cierre_ventanas = ask_time(
        "Hora habitual de cierre de ventanas en verano",
        "11:00",
    )

    custom_loads = add_custom_loads()

    # 7 — Política y resumen
    section(7, total_steps, "Política de gestión y resumen")
    estrategia = ask_choice(
        "Estrategia por defecto:",
        {
            "1": "sostenible_predictiva — preservar batería y desplazar consumos",
            "2": "autoconsumo — maximizar autoconsumo",
        },
        default="1",
    )
    estrategia_nombre = (
        "sostenible_predictiva" if estrategia == "1" else "autoconsumo"
    )

    margen = ask_float(
        "Margen económico mínimo para justificar uso de batería [€/kWh]",
        0.02,
        0.0,
    )

    config: Dict[str, Any] = {
        "config_version": CONFIG_VERSION,
        "generado_por": "installation/wizard.py",
        "generado_en": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sistema": {
            "nombre": sistema_nombre,
            "descripcion": sistema_descripcion,
        },
        "ubicacion": {
            "provincia": provincia,
            "municipio": municipio,
            "codigo_aemet": codigo_aemet,
            "latitud": latitud,
            "longitud": longitud,
        },
        "fotovoltaica": {
            "numero_paneles": num_paneles,
            "panel": panel,
            "potencia_total_wp": round(potencia_total_wp, 3),
            "potencia_total_kwp": round(potencia_total_wp / 1000.0, 6),
            "inclinacion_grados": inclinacion,
            "azimut_grados_pvgis": azimut,
        },
        "inversor": inverter,
        "bateria": battery,
        "vivienda": {
            "adultos": adultos,
            "ninos": ninos,
            "ocupantes_totales": adultos + ninos,
            "ventilacion_nocturna_verano": ventilacion_nocturna,
            "hora_cierre_ventanas_verano": hora_cierre_ventanas,
        },
        "demanda": {
            "prioridad_red_sobre_bateria": prioridad_red,
            "cargas_personalizadas": custom_loads,
            "nota": (
                "config.yaml es la fuente de verdad; wizard.py regenera "
                "config.py y demand.py a partir de esta configuración."
            ),
        },
        "control": {
            "estrategia_default": estrategia_nombre,
            "sostenibilidad_prioritaria": estrategia_nombre == "sostenible_predictiva",
            "margen_economico_minimo_eur_kwh": margen,
            "horizonte_optimizacion_horas": 24,
            "paso_temporal_horas": 1.0,
        },
        "seguridad": {
            "credenciales_en": "mytoken.env",
            "credenciales_incluidas_en_config": False,
        },
    }

    print()
    print("Resumen:")
    print(f"  Instalación: {sistema_nombre}")
    print(f"  Ubicación:   {municipio} ({provincia})")
    if codigo_aemet:
        print(f"  AEMET:       {codigo_aemet}")
    print(
        f"  FV:          {num_paneles} × {panel['potencia_w']} W "
        f"= {potencia_total_wp/1000.0:.3f} kWp"
    )
    print(
        f"  Inversor:    {inverter.get('fabricante', '')} "
        f"{inverter.get('modelo', '')}"
    )
    if battery.get("presente"):
        energy = (
            float(battery.get("energia_kwh_unidad") or 0.0)
            * int(battery.get("numero_unidades") or 0)
        )
        print(
            f"  Batería:     {battery.get('numero_unidades')} × "
            f"{battery.get('energia_kwh_unidad')} kWh "
            f"= {energy:.2f} kWh nominales"
        )
        print(
            f"  SOC normal:  "
            f"{battery.get('soc_min_normal', 0)*100:.0f}–"
            f"{battery.get('soc_max_normal', 0)*100:.0f} %"
        )
    else:
        print("  Batería:     no instalada")
    print(f"  Ocupantes:   {adultos + ninos}")
    print(f"  Estrategia:  {estrategia_nombre}")
    print(f"  Cargas nuevas registradas: {len(custom_loads)}")
    print()

    if not ask_bool("¿Es correcta esta configuración?", True):
        print(
            "Configuración no guardada. Vuelva a ejecutar el asistente "
            "para introducir los datos de nuevo."
        )
        raise SystemExit(3)

    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Asistente interactivo de configuración de Gestión Solar Predictiva."
        )
    )
    parser.add_argument(
        "--output",
        help="Ruta de salida. Por defecto: <proyecto>/config.yaml",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Crear una configuración nueva sin preguntar si se conserva config.yaml.",
    )
    parser.add_argument(
        "--project-dir",
        help="Directorio raíz del proyecto; normalmente se detecta automáticamente.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    project_dir = (
        Path(args.project_dir).expanduser().resolve()
        if args.project_dir
        else detect_project_dir()
    )

    if not (project_dir / "main.py").exists():
        error("No se encuentra main.py en {}".format(project_dir))
        return 1

    show_runtime_environment(project_dir)

    if sys.version_info < (3, 6):
        error("wizard.py requiere Python 3.6 o superior.")
        return 1

    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else project_dir / "config.yaml"
    )

    backup = None
    preserved = False

    try:
        if output.exists() and not args.force:
            title("{} — Configuración existente".format(APP_NAME))
            print("Se ha encontrado:")
            print()
            print("    {}".format(output))
            print()
            print(
                "Puede conservar esta configuración y regenerar directamente "
                "config.py y demand.py, o introducir una configuración nueva."
            )
            print()

            if ask_bool("¿Desea conservar la configuración existente?", True):
                config = load_generated_yaml(output)
                preserved = True
                print()
                print("✓ config.yaml conservado.")
            else:
                print()
                print("Se iniciará nuevamente el asistente de configuración.")
                config = run_wizard(project_dir)
                backup = write_config(output, config, force=True)
        else:
            config = run_wizard(project_dir)
            backup = write_config(output, config, force=args.force)

        ensure_gitignore(project_dir)

        print()
        print("Generando módulos Python compatibles con el programa actual...")
        config_target, demand_target = generate_python_modules(
            project_dir, config, output
        )

    except KeyboardInterrupt:
        print("\n\nConfiguración cancelada por el usuario.")
        return 130
    except EOFError:
        error("La entrada interactiva se cerró inesperadamente.")
        return 1
    except (RuntimeError, ValueError) as exc:
        error(str(exc))
        return 3
    except OSError as exc:
        error("No se pudo escribir la configuración: {}".format(exc))
        return 1
    except Exception as exc:
        error("No se pudieron generar los módulos Python: {}".format(exc))
        return 1

    print()
    hr()
    print("CONFIGURACIÓN PREPARADA".center(68))
    hr()
    print()
    if preserved:
        print("config.yaml conservado: {}".format(output))
    else:
        print("config.yaml escrito:   {}".format(output))
    if backup:
        print("Copia del YAML anterior: {}".format(backup))
    print("config.py generado:    {}".format(config_target))
    print("demand.py generado:    {}".format(demand_target))
    print()
    print("✓ Sintaxis de config.py y demand.py comprobada.")
    print("✓ Interfaz pública de ambos módulos comprobada.")
    print("✓ Las claves AEMET/ESIOS permanecen únicamente en mytoken.env.")
    print()
    print("Puede probar inmediatamente:")
    print()
    print("    python main.py --soc 0.60")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
