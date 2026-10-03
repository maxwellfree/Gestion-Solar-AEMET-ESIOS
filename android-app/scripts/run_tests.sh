#!/usr/bin/env bash
#
# run_tests.sh — pruebas Python + JavaScript
# ===========================================
# Se ejecuta en el host (mvn/jdk no son necesarios). Escribe en stdout;
# el Makefile se encarga de volcar a logs/.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "================ PRUEBAS PYTHON (adaptador) ================"
python3 -m unittest discover -s tests -p "test_*.py" -v

echo
echo "================ PRUEBA DE HUMO (contrato sin red) ========="
python3 tests/smoke_adapter.py

echo
echo "================ PRUEBAS JAVASCRIPT (UI) ==================="
if command -v node >/dev/null 2>&1; then
  node tests/js/run.mjs
else
  echo "node no disponible: se omiten las pruebas JS." >&2
fi

echo
echo "Todas las pruebas han finalizado."
