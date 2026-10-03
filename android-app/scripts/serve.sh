#!/usr/bin/env bash
#
# serve.sh — sirve el MVP en local para desarrollo/pruebas
# ========================================================
# Usa scripts/serve.py (multihilo + sin caché): evita servir módulos JS
# antiguos ya editados y evita el bloqueo de las peticiones paralelas de
# Pyodide.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8080}"

exec python3 "$ROOT/scripts/serve.py" "$PORT" "$ROOT/mvp"
