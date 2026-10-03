#!/usr/bin/env bash
#
# build_android.sh — genera el proyecto Capacitor y compila el APK
# ================================================================
# Requiere Android SDK + JDK en el HOST (no se instalan en el contenedor).
#
#   make android
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT/mvp"
GS="$ROOT/gestion-solar"
WWW="$GS/www"

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

# --- Proyecto Capacitor -------------------------------------------------
if [ ! -f "$GS/package.json" ]; then
  echo "[build_android] Creando proyecto Capacitor en $GS"
  mkdir -p "$GS"
  ( cd "$GS" && npm init -y >/dev/null )

  cat > "$GS/capacitor.config.json" <<JSON
{
  "appId": "$APP_ID",
  "appName": "$APP_NAME",
  "webDir": "www",
  "bundledWebRuntime": false,
  "server": { "androidScheme": "https" }
}
JSON

  ( cd "$GS" && npm install @capacitor/core @capacitor/cli @capacitor/android )
else
  echo "[build_android] Proyecto Capacitor existente"
fi

# --- Copiar la aplicación web ------------------------------------------
echo "[build_android] Copiando runtime a $WWW"
rm -rf "$WWW"
mkdir -p "$WWW/vendor"
cp    "$SOURCE/index.html"         "$WWW/"
cp -a "$SOURCE/css"                "$WWW/"
cp -a "$SOURCE/js"                 "$WWW/"
cp -a "$SOURCE/python"             "$WWW/"
[ -f "$SOURCE/manifest.webmanifest" ] && cp "$SOURCE/manifest.webmanifest" "$WWW/"
[ -d "$SOURCE/vendor/lib" ]   && cp -a "$SOURCE/vendor/lib"   "$WWW/vendor/"
[ -d "$SOURCE/vendor/pyodide" ] && cp -a "$SOURCE/vendor/pyodide" "$WWW/vendor/"

# --- Plataforma Android + compilación ----------------------------------
cd "$GS"
if [ ! -d "$GS/android" ]; then
  echo "[build_android] Añadiendo plataforma Android"
  npx cap add android
fi

echo "[build_android] Sincronizando"
npx cap sync android

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
