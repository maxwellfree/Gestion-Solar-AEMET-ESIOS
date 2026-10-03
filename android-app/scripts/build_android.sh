#!/usr/bin/env bash
#
# build_android.sh — genera el proyecto Capacitor y compila el APK
# ================================================================
# Requiere Android SDK + JDK en el HOST (no se instalan en el contenedor).
#
#   make android
#
# PVGIS no envía cabeceras CORS; en la app Android se consulta con el
# plugin nativo CapacitorHttp (ver mvp/js/pvgis.js) llamándolo
# EXPLÍCITAMENTE, sin parchear `window.fetch`/XHR globalmente. Así no se
# altera la carga local de Pyodide (wasm, stdlib, ficheros del motor).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/mvp"
GS="$ROOT/gestion-solar"
WWW="$GS/www"
CONFIG_SRC="$ROOT/capacitor.config.json"

APP_ID="${APP_ID:-com.nonormal.gestionsolarpredictiva}"
APP_NAME="${APP_NAME:-Gestion Solar Predictiva}"

echo "[build_android] Comprobando herramientas del host…"
command -v node >/dev/null 2>&1 || { echo "ERROR: falta node/npm" >&2; exit 1; }
if ! command -v java >/dev/null 2>&1 && [ -z "${JAVA_HOME:-}" ]; then
  echo "ERROR: no se encuentra JDK. Define JAVA_HOME o instala Java 17." >&2
  exit 1
fi
if [ -z "${ANDROID_HOME:-}" ] && [ -z "${ANDROID_SDK_ROOT:-}" ]; then
  echo "AVISO: ANDROID_HOME/ANDROID_SDK_ROOT no definidos. 'cap add android' podría fallar." >&2
fi

# --- Comprobaciones del MVP --------------------------------------------
if [ ! -f "$SOURCE/python/manifest.json" ]; then
  echo "ERROR: falta $SOURCE/python/manifest.json. Ejecuta «make mvp» primero." >&2
  exit 1
fi
if [ ! -d "$SOURCE/vendor/pyodide" ]; then
  echo "AVISO: falta $SOURCE/vendor/pyodide. Ejecuta «make vendor-pyodide» para" >&2
  echo "        que el motor Python arranque sin CDN (recomendado en el APK)." >&2
fi
if [ ! -f "$CONFIG_SRC" ]; then
  echo "ERROR: falta $CONFIG_SRC" >&2
  exit 1
fi

# --- Proyecto Capacitor -------------------------------------------------
if [ ! -f "$GS/package.json" ]; then
  echo "[build_android] Creando proyecto Capacitor en $GS"
  mkdir -p "$GS"
  ( cd "$GS" && npm init -y >/dev/null )
else
  echo "[build_android] Proyecto Capacitor existente"
fi

# Dependencias de Capacitor: se instalan si faltan (idempotente). Sin esto,
# un proyecto preexistente se queda sin `cap` local y `npx cap` falla con
# "could not determine executable to run".
if [ ! -d "$GS/node_modules/@capacitor/cli" ] || [ ! -d "$GS/node_modules/@capacitor/android" ]; then
  echo "[build_android] Instalando dependencias de Capacitor…"
  ( cd "$GS" && npm install @capacitor/core @capacitor/cli @capacitor/android )
fi

CAP="$GS/node_modules/.bin/cap"
if [ ! -x "$CAP" ]; then
  echo "ERROR: no se encuentra el CLI de Capacitor en $CAP" >&2
  echo "       Prueba: (cd \"$GS\" && npm install @capacitor/core @capacitor/cli @capacitor/android)" >&2
  exit 1
fi

# (Re)escribir capacitor.config.json a partir de la fuente del repo,
# permitiendo sobrescribir appId/appName por entorno. Se garantiza que
# CapacitorHttp esté declarado (aunque se llame explícitamente).
python3 - "$CONFIG_SRC" "$GS/capacitor.config.json" "$APP_ID" "$APP_NAME" <<'PY'
import json, sys

src, dst, app_id, app_name = sys.argv[1:5]
with open(src, encoding="utf-8") as fh:
    cfg = json.load(fh)

if app_id:
    cfg["appId"] = app_id
if app_name:
    cfg["appName"] = app_name
cfg.setdefault("plugins", {}).setdefault("CapacitorHttp", {}).setdefault("enabled", False)

with open(dst, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=2, ensure_ascii=False)

print(f"[build_android] capacitor.config.json -> {dst}")
PY

# --- Copiar la aplicación web ------------------------------------------
echo "[build_android] Copiando runtime a $WWW"
rm -rf "$WWW"
mkdir -p "$WWW/vendor"
cp    "$SOURCE/index.html" "$WWW/"
# cp -R (no -a): -a arrastra atributos extendidos que dejan directorios
# ilegibles en algunos sistemas de ficheros.
cp -R "$SOURCE/css"    "$WWW/"
cp -R "$SOURCE/js"     "$WWW/"
cp -R "$SOURCE/python" "$WWW/"
[ -f "$SOURCE/manifest.webmanifest" ] && cp "$SOURCE/manifest.webmanifest" "$WWW/"
[ -d "$SOURCE/vendor/lib" ]     && cp -R "$SOURCE/vendor/lib"     "$WWW/vendor/"
[ -d "$SOURCE/vendor/pyodide" ] && cp -R "$SOURCE/vendor/pyodide" "$WWW/vendor/"

# --- Plataforma Android + compilación ----------------------------------
cd "$GS"
if [ ! -d "$GS/android" ]; then
  echo "[build_android] Añadiendo plataforma Android"
  "$CAP" add android
fi

echo "[build_android] Sincronizando"
"$CAP" sync android

echo "[build_android] Compilando APK (debug)"
( cd "$GS/android" && ./gradlew assembleDebug )

APK="$(find "$GS/android/app/build/outputs/apk" -name '*.apk' 2>/dev/null | head -n1 || true)"
if [ -n "$APK" ]; then
  echo
  echo "========================================================"
  echo " APK generado: $APK"
  echo "========================================================"
else
  echo "No se encontró el APK. Revisa la salida de Gradle." >&2
  exit 1
fi
