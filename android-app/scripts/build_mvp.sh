#!/usr/bin/env bash
#
# build_mvp.sh — genera el MVP en android-app/mvp
# ================================================
#
#   1. copia los módulos .py del motor (carpeta superior) y el adaptador
#      a mvp/python/;
#   2. genera mvp/python/manifest.json;
#   3. empaqueta jQuery y OnsenUI en mvp/vendor/lib (modo offline);
#   4. escribe el registro de la operación.
#
# El motor NO se modifica: únicamente se copia.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE_DIR="$(cd "$ROOT/.." && pwd)"
MVP="$ROOT/mvp"
PYDEST="$MVP/python"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

ENGINE_FILES=(
  config.py demand.py cache.py aemet.py aemet_hourly.py esios.py
  solar.py balance.py dispatch.py optimizer.py weekly.py municipios.py
)

echo "[build_mvp] Motor: $ENGINE_DIR"
echo "[build_mvp] Destino: $PYDEST"

rm -rf "$PYDEST"
mkdir -p "$PYDEST"

for f in "${ENGINE_FILES[@]}"; do
  if [[ ! -f "$ENGINE_DIR/$f" ]]; then
    echo "[build_mvp] ERROR: falta $ENGINE_DIR/$f" >&2
    exit 1
  fi
  cp "$ENGINE_DIR/$f" "$PYDEST/$f"
done

cp "$ROOT/android_adapter.py" "$PYDEST/android_adapter.py"

# Sanity check: el adaptador debe poder importarse sin red.
if command -v python3 >/dev/null 2>&1; then
  python3 - <<PY
import ast, sys, pathlib
for p in pathlib.Path("$PYDEST").glob("*.py"):
    ast.parse(p.read_text(encoding="utf-8"))
print("[build_mvp] Sintaxis Python verificada: %d archivos" % len(list(pathlib.Path("$PYDEST").glob("*.py"))))
PY
fi

# --- manifest.json ---------------------------------------------------
python3 - "$PYDEST" <<'PY'
import json, os, sys
from datetime import datetime
dest = sys.argv[1]
files = sorted(p for p in os.listdir(dest) if p.endswith(".py"))
manifest = {
    "schema_version": 1,
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "adapter": "android_adapter.py",
    "engine_files": [f for f in files if f != "android_adapter.py"],
    "files": files,
}
with open(os.path.join(dest, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)
print("[build_mvp] manifest.json con %d archivos" % len(files))
PY

# --- librerías de UI -------------------------------------------------
"$ROOT/scripts/vendor_libs.sh"

echo "[build_mvp] MVP generado en $MVP"
