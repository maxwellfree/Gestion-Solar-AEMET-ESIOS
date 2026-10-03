# ==========================================================================
# android-app/Makefile
# ==========================================================================
#
#  make mvp             genera el MVP en android-app/mvp (y su log)
#  make android         genera el proyecto Capacitor y compila el APK
#  make test            ejecuta las pruebas (python + js) y guarda el log
#  make serve           sirve el MVP en http://localhost:8080
#  make vendor-pyodide  copia local del runtime Pyodide (opcional)
#  make clean           elimina artefactos generados
#
# Todos los comandos guardan un registro en logs/.
# El motor Python de la carpeta superior NUNCA se modifica: sólo se copia.
#
# NOTA: la ruta puede contener espacios; todas las variables van entre
# comillas en las recetas y no se usan rutas como objetivos de make.
# ==========================================================================

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c

# ROOT: directorio de este Makefile. Se usa $(CURDIR) (no $(abspath ...))
# porque la ruta contiene espacios y abspath los altera en algunas
# versiones de make. Ejecutar «make» desde android-app/.
ROOT := $(CURDIR)
TS := $(shell date +%Y%m%d-%H%M%S)
LOGDIR := $(ROOT)/logs

LOG_MVP := $(LOGDIR)/mvp-$(TS).log
LOG_ANDROID := $(LOGDIR)/android-$(TS).log
LOG_TEST := $(LOGDIR)/test-$(TS).log
LOG_SERVE := $(LOGDIR)/serve-$(TS).log
LOG_VENDOR := $(LOGDIR)/vendor-pyodide-$(TS).log

.PHONY: all mvp android test serve vendor-pyodide clean logs help

all: mvp

## Genera el MVP (copia motor + adaptador, manifest y librerías UI)
mvp:
	@echo "== make mvp ==  (log: $(LOG_MVP))"
	@mkdir -p "$(LOGDIR)"
	@bash "$(ROOT)/scripts/build_mvp.sh" 2>&1 | tee "$(LOG_MVP)"
	@echo "== OK =="

## Genera el proyecto Capacitor y compila el APK (requiere Android SDK/JDK en el host)
android: mvp
	@echo "== make android ==  (log: $(LOG_ANDROID))"
	@mkdir -p "$(LOGDIR)"
	@bash "$(ROOT)/scripts/build_android.sh" 2>&1 | tee "$(LOG_ANDROID)"
	@echo "== OK =="

## Ejecuta las pruebas (python + javascript) y guarda el log
test:
	@echo "== make test ==  (log: $(LOG_TEST))"
	@mkdir -p "$(LOGDIR)"
	@bash "$(ROOT)/scripts/run_tests.sh" 2>&1 | tee "$(LOG_TEST)"
	@echo "== OK =="

## Sirve el MVP en local para desarrollo
serve: mvp
	@echo "== make serve ==  (log: $(LOG_SERVE))"
	@mkdir -p "$(LOGDIR)"
	@bash "$(ROOT)/scripts/serve.sh" 2>&1 | tee "$(LOG_SERVE)"

## Copia local del runtime Pyodide (funcionamiento sin CDN)
vendor-pyodide:
	@echo "== make vendor-pyodide ==  (log: $(LOG_VENDOR))"
	@mkdir -p "$(LOGDIR)"
	@bash "$(ROOT)/scripts/vendor_pyodide.sh" 2>&1 | tee "$(LOG_VENDOR)"

## Elimina artefactos generados (no toca el código fuente)
clean:
	@rm -rf "$(ROOT)/mvp/python" "$(ROOT)/mvp/vendor" "$(ROOT)/logs" 2>/dev/null || true
	@rm -rf "$(ROOT)/gestion-solar/www" "$(ROOT)/gestion-solar/node_modules" 2>/dev/null || true
	@rm -rf "$(ROOT)/tests/fixtures" 2>/dev/null || true
	@find "$(ROOT)" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "Limpieza completada."

logs:
	@mkdir -p "$(LOGDIR)"
	@echo "Logs en $(LOGDIR):"
	@ls -1 "$(LOGDIR)" 2>/dev/null || true

help:
	@grep -E '^##' $(MAKEFILE_LIST) | sed 's/^## //'
