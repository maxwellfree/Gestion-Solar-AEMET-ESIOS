#!/usr/bin/env bash
#
# serve.sh — sirve el MVP en local para desarrollo/pruebas
# ========================================================
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8080}"

cd "$ROOT/mvp"
echo "[serve] http://localhost:$PORT/  (Ctrl+C para detener)"
exec python3 -m http.server "$PORT" --bind 0.0.0.0
