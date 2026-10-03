#!/usr/bin/env python3
"""
serve.py — servidor de desarrollo del MVP
=========================================
Sirve `mvp/` SIN caché y **multi-hilo**.

Dos motivos concretos (vistos en pruebas reales):

* Sin `Cache-Control: no-store`, el navegador reutiliza módulos JS ya
  editados y se depura código viejo (p. ej. un onboarding que mostraba
  mal las credenciales que ya estaba corregido en disco).
* Debe ser multi-hilo: Pyodide lanza varias peticiones en paralelo
  (wasm + stdlib + lockfile) y un servidor mono-hilo se bloquea.

    python3 scripts/serve.py [puerto] [directorio]
"""

import functools
import http.server
import os
import socketserver
import sys

NO_CACHE = "no-store, no-cache, must-revalidate, max-age=0"


class Handler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self):  # noqa: D102
        self.send_header("Cache-Control", NO_CACHE)
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):  # noqa: A002 - firma de la clase base
        pass


class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8080"))
    directory = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "mvp")

    handler = functools.partial(Handler, directory=directory)
    with ThreadingHTTPServer(("0.0.0.0", port), handler) as httpd:
        print(f"[serve] http://localhost:{port}/  (sin caché, multihilo · Ctrl+C para detener)")
        print(f"[serve] sirviendo: {directory}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
