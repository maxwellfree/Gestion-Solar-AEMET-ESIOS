#!/usr/bin/env bash
#
# Gestión Solar Predictiva — instalador Linux (v3)
#
# Detecta automáticamente:
#   - distribución y versión de Linux
#   - arquitectura
#   - Python y versión
#   - módulo venv
#   - pip
#   - Git / curl / wget (informativos)
#
# Selección automática:
#   Python 3.6–3.7  -> modo LEGACY + requirements-legacy.txt
#   Python >= 3.8   -> modo CURRENT + requirements.txt
#
# No instala paquetes Python globalmente. Todo se instala en .venv.
#

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_DIR="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"

# Permite ejecutar temporalmente el script desde la raíz.
if [[ ! -f "${PROJECT_DIR}/main.py" && -f "${SCRIPT_DIR}/main.py" ]]; then
    PROJECT_DIR="${SCRIPT_DIR}"
fi

TOKEN_FILE="${PROJECT_DIR}/mytoken.env"
VENV_DIR="${PROJECT_DIR}/.venv"
GITIGNORE="${PROJECT_DIR}/.gitignore"
WIZARD="${PROJECT_DIR}/installation/wizard.py"
CURRENT_REQUIREMENTS="${PROJECT_DIR}/requirements.txt"
LEGACY_REQUIREMENTS="${PROJECT_DIR}/installation/requirements-legacy.txt"

bold()   { printf '\033[1m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*" >&2; }

die() {
    red "ERROR: $*"
    exit 1
}

cleanup_on_error() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        printf '\n' >&2
        red "La instalación no se ha completado."
        yellow "Puede corregir el problema y volver a ejecutar este instalador."
    fi
    exit "$exit_code"
}
trap cleanup_on_error EXIT

command_status() {
    local cmd="$1"
    if command -v "$cmd" >/dev/null 2>&1; then
        printf '  ✓ %-12s %s\n' "$cmd" "$(command -v "$cmd")"
    else
        printf '  - %-12s no instalado\n' "$cmd"
    fi
}

ensure_gitignore_entry() {
    local entry="$1"
    touch "${GITIGNORE}"
    if ! grep -Fxq "${entry}" "${GITIGNORE}"; then
        printf '%s\n' "${entry}" >> "${GITIGNORE}"
    fi
}

clear 2>/dev/null || true

cat <<'EOF'
============================================================
              GESTIÓN SOLAR PREDICTIVA
              Instalador Linux v3
============================================================

El instalador detectará automáticamente el software disponible y
seleccionará las dependencias compatibles con la versión de Python.

No se modificarán los paquetes Python del sistema.
Todo se instalará dentro de un entorno virtual .venv.

EOF

# ---------------------------------------------------------------------------
# PASO 1 — Detectar sistema
# ---------------------------------------------------------------------------

bold "PASO 1/6 — Detección del sistema"
printf '\n'

[[ "$(uname -s)" == "Linux" ]] || die \
    "Este instalador está destinado actualmente a Linux."

OS_ID="linux"
OS_VERSION_ID=""
OS_CODENAME=""
DISTRO="Linux"

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS_ID="${ID:-linux}"
    OS_VERSION_ID="${VERSION_ID:-}"
    OS_CODENAME="${VERSION_CODENAME:-}"
    DISTRO="${PRETTY_NAME:-Linux}"
fi

ARCH="$(uname -m)"
KERNEL="$(uname -r)"

printf 'Sistema operativo : %s\n' "${DISTRO}"
printf 'Identificador      : %s\n' "${OS_ID}"
[[ -n "${OS_VERSION_ID}" ]] && printf 'Versión            : %s\n' "${OS_VERSION_ID}"
[[ -n "${OS_CODENAME}" ]] && printf 'Nombre de versión  : %s\n' "${OS_CODENAME}"
printf 'Arquitectura       : %s\n' "${ARCH}"
printf 'Kernel             : %s\n' "${KERNEL}"

printf '\nHerramientas detectadas:\n'
command_status git
command_status curl
command_status wget
command_status bash

[[ -f "${PROJECT_DIR}/main.py" ]] || die \
    "No se encuentra main.py en ${PROJECT_DIR}"

# ---------------------------------------------------------------------------
# PASO 2 — Detectar Python y elegir modo
# ---------------------------------------------------------------------------

printf '\n'
bold "PASO 2/6 — Python y compatibilidad"
printf '\n'

command -v python3 >/dev/null 2>&1 || die \
    "No se encuentra python3 en el sistema."

PYTHON_BIN="$(command -v python3)"
PYTHON_VERSION="$("${PYTHON_BIN}" -c \
    'import sys; print(".".join(map(str, sys.version_info[:3])))')"
PYTHON_MAJOR="$("${PYTHON_BIN}" -c 'import sys; print(sys.version_info[0])')"
PYTHON_MINOR="$("${PYTHON_BIN}" -c 'import sys; print(sys.version_info[1])')"

printf 'Python ejecutable   : %s\n' "${PYTHON_BIN}"
printf 'Python versión      : %s\n' "${PYTHON_VERSION}"

if [[ "${PYTHON_MAJOR}" -ne 3 ]]; then
    die "Se requiere Python 3."
fi

INSTALL_MODE=""
REQUIREMENTS=""

if (( PYTHON_MINOR >= 8 )); then
    INSTALL_MODE="current"
    REQUIREMENTS="${CURRENT_REQUIREMENTS}"
    green "✓ Modo CURRENT seleccionado automáticamente (Python >= 3.8)."
elif (( PYTHON_MINOR >= 6 )); then
    INSTALL_MODE="legacy"
    REQUIREMENTS="${LEGACY_REQUIREMENTS}"
    yellow "✓ Modo LEGACY seleccionado automáticamente (Python 3.6–3.7)."
    yellow "  Se utilizarán versiones de dependencias compatibles con Python ${PYTHON_VERSION}."
else
    die "Python ${PYTHON_VERSION} es demasiado antiguo. Se requiere Python 3.6 o superior."
fi

[[ -f "${REQUIREMENTS}" ]] || {
    if [[ "${INSTALL_MODE}" == "legacy" ]]; then
        die "Falta ${LEGACY_REQUIREMENTS}. Copie requirements-legacy.txt dentro de installation/."
    else
        die "Falta ${CURRENT_REQUIREMENTS}."
    fi
}

printf 'Dependencias       : %s\n' "$(basename "${REQUIREMENTS}")"

# Comprobar venv antes de pedir/modificar nada más.
if "${PYTHON_BIN}" -m venv --help >/dev/null 2>&1; then
    green "✓ Módulo venv disponible."
else
    printf '\n'
    red "No está disponible el módulo venv para ${PYTHON_BIN}."
    if [[ "${OS_ID}" == "ubuntu" || "${OS_ID}" == "debian" ]]; then
        cat <<EOF

Instálelo y vuelva a ejecutar el instalador:

    sudo apt update
    sudo apt install python3-venv

Si su distribución requiere el paquete específico de la versión:

    sudo apt install python${PYTHON_MAJOR}.${PYTHON_MINOR}-venv

EOF
    fi
    die "Falta el soporte para entornos virtuales (venv)."
fi

# ---------------------------------------------------------------------------
# PASO 3 — Credenciales
# ---------------------------------------------------------------------------

printf '\n'
bold "PASO 3/6 — Credenciales obligatorias"
cat <<'EOF'

Gestión Solar Predictiva necesita obligatoriamente:

  • una API Key de AEMET OpenData;
  • un token/API Key de ESIOS.

Estas credenciales deben solicitarse previamente a los respectivos
servicios oficiales. El instalador no continuará sin ambas.

EOF

have_existing_credentials=false
if [[ -f "${TOKEN_FILE}" ]]; then
    if grep -Eq '^[[:space:]]*AEMET_API_KEY=.+$' "${TOKEN_FILE}" \
       && grep -Eq '^[[:space:]]*ESIOS_API_KEY=.+$' "${TOKEN_FILE}"; then
        have_existing_credentials=true
    fi
fi

if [[ "${have_existing_credentials}" == true ]]; then
    green "Se ha encontrado mytoken.env con ambas credenciales."
    printf 'Las claves no se mostrarán.\n\n'
    read -r -p "¿Desea conservar y utilizar estas credenciales? [S/n]: " reuse
    reuse="${reuse:-S}"
    if [[ "${reuse}" =~ ^[Nn]$ ]]; then
        have_existing_credentials=false
    fi
fi

if [[ "${have_existing_credentials}" == false ]]; then
    read -r -p "¿Dispone ya de las dos credenciales? [s/N]: " has_keys
    has_keys="${has_keys:-N}"

    if [[ ! "${has_keys}" =~ ^[SsYy]$ ]]; then
        cat <<'EOF'

Instalación detenida.

Solicite primero las credenciales de AEMET OpenData y ESIOS.
Cuando disponga de ambas, vuelva a ejecutar:

    ./installation/install.sh

EOF
        exit 2
    fi

    printf '\nPegue las claves cuando se soliciten.\n'
    printf 'La entrada permanecerá oculta por seguridad.\n\n'

    read -r -s -p "API Key de AEMET OpenData (entrada oculta): " AEMET_KEY
    printf '\n'
    if [[ -n "${AEMET_KEY}" ]]; then
        printf '  ✓ Clave AEMET recibida (%s caracteres).\n' "${#AEMET_KEY}"
    else
        die "La clave AEMET está vacía."
    fi

    read -r -s -p "Token/API Key de ESIOS (entrada oculta): " ESIOS_KEY
    printf '\n'
    if [[ -n "${ESIOS_KEY}" ]]; then
        printf '  ✓ Clave ESIOS recibida (%s caracteres).\n' "${#ESIOS_KEY}"
    else
        die "La clave ESIOS está vacía."
    fi
    printf '\n'

    if [[ -f "${TOKEN_FILE}" ]]; then
        backup="${TOKEN_FILE}.bak.$(date +%Y%m%d_%H%M%S)"
        cp -p "${TOKEN_FILE}" "${backup}"
        yellow "Copia de seguridad creada: $(basename "${backup}")"
    fi

    umask 077
    {
        printf 'AEMET_API_KEY=%s\n' "${AEMET_KEY}"
        printf 'ESIOS_API_KEY=%s\n' "${ESIOS_KEY}"
    } > "${TOKEN_FILE}"
    chmod 600 "${TOKEN_FILE}"
    unset AEMET_KEY ESIOS_KEY

    green "✓ mytoken.env creado con permisos 600."
fi

ensure_gitignore_entry "mytoken.env"
ensure_gitignore_entry "config.yaml"
ensure_gitignore_entry ".venv/"
ensure_gitignore_entry "__pycache__/"
ensure_gitignore_entry "*.pyc"
green "✓ .gitignore comprobado."

# ---------------------------------------------------------------------------
# PASO 4 — Crear/recrear venv si cambió Python
# ---------------------------------------------------------------------------

printf '\n'
bold "PASO 4/6 — Entorno virtual"
printf '\n'

RECREATE_VENV=false

if [[ -d "${VENV_DIR}" ]]; then
    if [[ -x "${VENV_DIR}/bin/python" ]]; then
        VENV_VERSION="$("${VENV_DIR}/bin/python" -c \
            'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || true)"
        SYSTEM_MM="${PYTHON_MAJOR}.${PYTHON_MINOR}"

        if [[ "${VENV_VERSION}" != "${SYSTEM_MM}" ]]; then
            yellow "El .venv existente usa Python ${VENV_VERSION:-desconocido}."
            yellow "El sistema actual usa Python ${SYSTEM_MM}."
            read -r -p "¿Desea recrear .venv con el Python detectado? [S/n]: " recreate
            recreate="${recreate:-S}"
            if [[ ! "${recreate}" =~ ^[Nn]$ ]]; then
                RECREATE_VENV=true
            else
                die "No se puede garantizar la compatibilidad usando un .venv de otra versión."
            fi
        else
            green "✓ .venv existente compatible con Python ${VENV_VERSION}."
        fi
    else
        yellow "Existe .venv pero parece incompleto."
        RECREATE_VENV=true
    fi
fi

if [[ "${RECREATE_VENV}" == true ]]; then
    stamp="$(date +%Y%m%d_%H%M%S)"
    mv "${VENV_DIR}" "${VENV_DIR}.bak.${stamp}"
    yellow "Entorno anterior conservado como .venv.bak.${stamp}"
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    printf 'Creando .venv con %s...\n' "${PYTHON_BIN}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
    green "✓ Entorno virtual creado."
fi

VENV_PYTHON="${VENV_DIR}/bin/python"

# ---------------------------------------------------------------------------
# PASO 5 — pip y dependencias
# ---------------------------------------------------------------------------

printf '\n'
bold "PASO 5/6 — Dependencias Python"
printf '\n'

# Verificar que el entorno virtual contiene pip.
# Un .venv antiguo/incompleto puede existir y usar la versión correcta de
# Python pero carecer de pip. En ese caso se recrea automáticamente.
if ! "${VENV_PYTHON}" -m pip --version >/dev/null 2>&1; then
    yellow "El .venv existente no contiene pip."
    yellow "Se intentará reparar recreando el entorno virtual."

    stamp="$(date +%Y%m%d_%H%M%S)"
    if [[ -d "${VENV_DIR}" ]]; then
        mv "${VENV_DIR}" "${VENV_DIR}.incompleto.${stamp}"
        yellow "Entorno incompleto conservado como .venv.incompleto.${stamp}"
    fi

    if "${PYTHON_BIN}" -m venv "${VENV_DIR}" >/tmp/gestion_solar_venv.log 2>&1; then
        VENV_PYTHON="${VENV_DIR}/bin/python"
    else
        cat /tmp/gestion_solar_venv.log >&2 || true
        rm -rf "${VENV_DIR}" 2>/dev/null || true

        printf '\n'
        yellow "Python puede crear la estructura venv, pero no dispone de los"
        yellow "componentes necesarios para incorporar pip automáticamente."

        if [[ "${OS_ID}" == "ubuntu" || "${OS_ID}" == "debian" ]]; then
            VENV_PACKAGE="python${PYTHON_MAJOR}.${PYTHON_MINOR}-venv"

            printf '\nPaquete de reparación recomendado: %s\n' "${VENV_PACKAGE}"

            if command -v dpkg >/dev/null 2>&1 && dpkg -s "${VENV_PACKAGE}" >/dev/null 2>&1; then
                yellow "El paquete ${VENV_PACKAGE} figura como instalado."
                yellow "Intentaremos reinstalarlo para reparar ensurepip/venv."
                APT_ACTION="reinstalar"
            else
                APT_ACTION="instalar"
            fi

            read -r -p "¿Desea que el instalador intente ${APT_ACTION} ${VENV_PACKAGE} con sudo? [S/n]: " fix_venv
            fix_venv="${fix_venv:-S}"

            if [[ ! "${fix_venv}" =~ ^[Nn]$ ]]; then
                command -v sudo >/dev/null 2>&1 || die \
                    "No se encuentra sudo. Instale manualmente ${VENV_PACKAGE}."

                command -v apt-get >/dev/null 2>&1 || die \
                    "No se encuentra apt-get. Instale manualmente ${VENV_PACKAGE}."

                printf '\nActualizando índices de paquetes...\n'
                sudo apt-get update

                if [[ "${APT_ACTION}" == "reinstalar" ]]; then
                    sudo apt-get install --reinstall -y "${VENV_PACKAGE}"
                else
                    sudo apt-get install -y "${VENV_PACKAGE}"
                fi

                printf '\nCreando de nuevo .venv...\n'
                "${PYTHON_BIN}" -m venv "${VENV_DIR}"
                VENV_PYTHON="${VENV_DIR}/bin/python"
            else
                cat <<EOF

Para continuar manualmente:

    sudo apt update
    sudo apt install ${VENV_PACKAGE}

Después vuelva a ejecutar:

    ./installation/install.sh

EOF
                die "No se puede continuar sin pip dentro del entorno virtual."
            fi
        else
            die "El entorno virtual no puede crear pip. Instale el paquete venv/ensurepip de su distribución."
        fi
    fi
fi

# Comprobación final: no seguir jamás con un .venv sin pip.
"${VENV_PYTHON}" -m pip --version >/dev/null 2>&1 || \
    die "pip sigue sin estar disponible dentro de .venv después del intento de reparación."

green "✓ pip disponible dentro de .venv: $("${VENV_PYTHON}" -m pip --version)"

if [[ "${INSTALL_MODE}" == "legacy" ]]; then
    # pip 21.3.1 es la última rama de pip compatible con Python 3.6.
    printf 'Preparando herramientas compatibles con Python legacy...\n'
    "${VENV_PYTHON}" -m pip install --upgrade \
        "pip<22" "setuptools<60" "wheel<0.38"
else
    printf 'Actualizando pip dentro del entorno virtual...\n'
    "${VENV_PYTHON}" -m pip install --upgrade pip
fi

printf '\nInstalando %s...\n' "$(basename "${REQUIREMENTS}")"
"${VENV_PYTHON}" -m pip install -r "${REQUIREMENTS}"

printf '\nComprobando módulos principales...\n'
"${VENV_PYTHON}" - <<'PY'
import sys
import requests
import pytz
from dotenv import load_dotenv

print("✓ Python       {}".format(sys.version.split()[0]))
print("✓ requests     {}".format(getattr(requests, "__version__", "?")))
print("✓ pytz         {}".format(getattr(pytz, "__version__", "?")))
print("✓ python-dotenv importado correctamente")
PY

# ---------------------------------------------------------------------------
# PASO 6 — Wizard
# ---------------------------------------------------------------------------

printf '\n'
bold "PASO 6/6 — Configuración de la instalación"
printf '\n'

if [[ -f "${WIZARD}" ]]; then
    if "${VENV_PYTHON}" -m py_compile "${WIZARD}"; then
        green "✓ wizard.py es compatible con Python ${PYTHON_VERSION}."
    else
        die "wizard.py no es compatible con Python ${PYTHON_VERSION}."
    fi

    read -r -p "¿Desea ejecutar ahora el asistente de configuración? [S/n]: " run_wizard
    run_wizard="${run_wizard:-S}"

    if [[ ! "${run_wizard}" =~ ^[Nn]$ ]]; then
        "${VENV_PYTHON}" "${WIZARD}"
    else
        yellow "Asistente omitido. Puede ejecutarlo después con:"
        printf '  %s %s\n' "${VENV_PYTHON}" "${WIZARD}"
    fi
else
    yellow "No se encuentra installation/wizard.py; se omite la configuración."
fi

# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

trap - EXIT

cat <<EOF

============================================================
                INSTALACIÓN COMPLETADA
============================================================

Sistema             : ${DISTRO}
Arquitectura        : ${ARCH}
Python              : ${PYTHON_VERSION}
Modo                : ${INSTALL_MODE^^}
Dependencias        : $(basename "${REQUIREMENTS}")
Entorno virtual     : ${VENV_DIR}
Credenciales        : ${TOKEN_FILE}

Para ejecutar el programa:

    cd "${PROJECT_DIR}"
    source .venv/bin/activate
    python main.py --soc 0.60

Para volver a configurar la instalación:

    source .venv/bin/activate
    python installation/wizard.py

============================================================
EOF
