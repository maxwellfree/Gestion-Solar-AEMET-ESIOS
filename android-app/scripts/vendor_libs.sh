#!/usr/bin/env bash
#
# vendor_libs.sh — descarga jQuery y OnsenUI a mvp/vendor/lib
# ==========================================================
# Permite que la interfaz funcione sin depender de un CDN.
#
# NOTA IMPORTANTE: se usa `cp -R` (NUNCA `cp -a`). `cp -a` conserva
# atributos extendidos/contextos de seguridad del tarball que, en algunos
# entornos, dejan el directorio resultante sin permisos de lectura/borrado.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/mvp/vendor/lib"
JQUERY_VERSION="${JQUERY_VERSION:-3.7.1}"
ONSENUI_VERSION="${ONSENUI_VERSION:-2.12.9}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DEST"

echo "[vendor_libs] Descargando jQuery $JQUERY_VERSION y OnsenUI $ONSENUI_VERSION"
cd "$TMP"
npm pack "jquery@$JQUERY_VERSION" "onsenui@$ONSENUI_VERSION" >/dev/null

# --- jQuery ---------------------------------------------------------
tar xzf jquery-*.tgz
cp package/dist/jquery.min.js "$DEST/jquery.min.js"

# --- OnsenUI --------------------------------------------------------
rm -rf package
tar xzf onsenui-*.tgz

if ! rm -rf "$DEST/onsenui" 2>/dev/null; then
  # Un directorio previo podría no ser borrable: se aparta en lugar de borrar.
  echo "[vendor_libs] aviso: no se pudo borrar $DEST/onsenui; se aparta"
  mv "$DEST/onsenui" "$DEST/onsenui.incomplete.$(date +%s)" 2>/dev/null || true
fi

mkdir -p "$DEST/onsenui/js"
cp -R package/css "$DEST/onsenui/css"
cp package/js/onsenui.min.js "$DEST/onsenui/js/onsenui.min.js"

# Permisos de lectura cómodos (best-effort).
chmod -R u+rwX "$DEST/onsenui" 2>/dev/null || true

echo "[vendor_libs] OK -> $DEST"
ls -1 "$DEST"
