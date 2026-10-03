#!/usr/bin/env bash
#
# vendor_pyodide.sh — copia local del runtime Pyodide (opcional)
# ==============================================================
# Permite que el motor arranque SIN depender del CDN.
#
# Estructura (importante):
#   Pyodide resuelve los paquetes desde el lockfile como
#   `indexURL + file_name`, así que los .whl deben quedar EN EL MISMO
#   directorio que pyodide.js. El CDN tampoco usa `full/packages/`:
#   sirve los .whl en `full/<archivo>`.
#
# Se vendorizan:
#   * el núcleo del runtime (pyodide.js, wasm, stdlib, lockfile);
#   * los paquetes de la distribución de Pyodide que usa el motor
#     (micropip, pytz, packaging, requests y sus dependencias,
#      pyodide-http), resueltos de forma transitiva desde el lockfile;
#   * python-dotenv, que NO está en la distribución de Pyodide y se
#     descarga de PyPI.
#   Se genera `local-packages.json` (nombre -> wheel) para que el
#   runtime instale las wheels locales antes de recurrir a la red.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/mvp/vendor/pyodide"
VERSION="${PYODIDE_VERSION:-0.27.8}"
BASE="${PYODIDE_BASE:-https://cdn.jsdelivr.net/pyodide/v${VERSION}/full}"

mkdir -p "$DEST"

echo "[vendor_pyodide] Descargando runtime Pyodide $VERSION -> $DEST"

# --- Núcleo del runtime --------------------------------------------
for f in pyodide.js pyodide.asm.js pyodide.asm.wasm python_stdlib.zip pyodide-lock.json; do
  echo "  - $f"
  curl -fsSL --retry 3 --max-time 300 "$BASE/$f" -o "$DEST/$f"
done

# --- Paquetes (distribución Pyodide + PyPI) ------------------------
python3 - "$DEST" "$BASE" <<'PY'
import json, os, sys, urllib.request

dest, base = sys.argv[1], sys.argv[2]
lock = json.load(open(os.path.join(dest, "pyodide-lock.json"), encoding="utf-8"))
pkgs = lock["packages"]

# Paquetes de la distribución de Pyodide que necesita el motor.
# Las dependencias se resuelven de forma transitiva desde el lockfile.
semilla = ["micropip", "pytz", "packaging", "requests", "pyodide-http"]

vistos = set()
pila = list(semilla)
while pila:
    nombre = pila.pop()
    if nombre in vistos:
        continue
    vistos.add(nombre)
    entrada = pkgs.get(nombre)
    if not entrada:
        continue
    for dep in entrada.get("depends", []):
        pila.append(dep)

wheels = {}          # nombre -> file_name  (distribución Pyodide)
faltan = []

def descargar(url, out, etiqueta):
    if os.path.exists(out) and os.path.getsize(out) > 0:
        print(f"[vendor_pyodide]   = {etiqueta} (ya presente)")
        return True
    try:
        urllib.request.urlretrieve(url, out)
        print(f"[vendor_pyodide]   + {etiqueta} ({os.path.getsize(out)} bytes)")
        return True
    except Exception as exc:
        faltan.append(etiqueta)
        print(f"[vendor_pyodide] aviso: no se pudo descargar {etiqueta}: {exc}")
        return False

for nombre in sorted(vistos):
    entrada = pkgs.get(nombre)
    if not entrada:
        print(f"[vendor_pyodide] aviso: {nombre} no está en el lockfile")
        continue
    fn = entrada["file_name"]
    if descargar(f"{base}/{fn}", os.path.join(dest, fn), fn):
        wheels[nombre] = fn

# python-dotenv: no está en la distribución de Pyodide -> PyPI.
dotenv_fn = None
try:
    meta = json.load(urllib.request.urlopen("https://pypi.org/pypi/python-dotenv/json", timeout=30))
    candidatos = [u for u in meta["urls"] if u["filename"].endswith("py3-none-any.whl")]
    candidatos.sort(key=lambda u: "py2.py3" in u["filename"])  # preferir py3
    u = candidatos[0]
    dotenv_fn = u["filename"]
    descargar(u["url"], os.path.join(dest, dotenv_fn), dotenv_fn)
except Exception as exc:
    print(f"[vendor_pyodide] aviso: python-dotenv no se pudo obtener de PyPI: {exc}")

# Mapa que usará el runtime: nombre del paquete -> wheel local.
local = {
    "requests": wheels.get("requests"),
    "pyodide-http": wheels.get("pyodide-http"),
    "python-dotenv": dotenv_fn,
}
local = {k: v for k, v in local.items() if v}
with open(os.path.join(dest, "local-packages.json"), "w", encoding="utf-8") as fh:
    json.dump(local, fh, indent=2, ensure_ascii=False)
print(f"[vendor_pyodide] local-packages.json -> {local}")

if "requests" not in wheels:
    print("[vendor_pyodide] AVISO: falta 'requests'; el motor no podrá importarse offline.")
PY

# --- Comprobación final --------------------------------------------
ok=1
for f in pyodide.js pyodide.asm.wasm pyodide-lock.json local-packages.json; do
  [ -s "$DEST/$f" ] || { echo "[vendor_pyodide] FALTA $f"; ok=0; }
done
whl_count=$(find "$DEST" -maxdepth 1 -name '*.whl' | wc -l | tr -d ' ')
echo "[vendor_pyodide] .whl presentes: $whl_count"

if [ "$ok" -ne 1 ]; then
  echo "[vendor_pyodide] ERROR: el runtime local está incompleto." >&2
  exit 1
fi
echo "[vendor_pyodide] Listo -> $DEST"
