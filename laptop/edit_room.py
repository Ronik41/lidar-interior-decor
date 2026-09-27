#!/usr/bin/env python3
"""Open a verified scan or saved design-input revision in a local Mac browser."""

import argparse
import json
import secrets
import sys
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from design_input import DesignStore
from import_scan import import_scan, read_object

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).with_name("editor")


def make_server(store, initial_document, initial_filename, port=0):
    token = secrets.token_urlsafe(32)
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, status, data, content_type="application/json"):
            body = json.dumps(data, allow_nan=False).encode() if content_type == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != host:
                self.respond(403, {"error": "Use the localhost URL printed by the launcher"})
                return False
            if self.command == "POST" and (self.headers.get("X-Editor-Token") != token
                    or self.headers.get("Origin") not in (None, f"http://{host}")):
                self.respond(403, {"error": "Invalid local editor session; reload this page"})
                return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            route = urlparse(self.path)
            try:
                if route.path == "/api/state":
                    store.verify()
                    data = store.payload(initial_document, initial_filename)
                    data["token"] = token
                    self.respond(200, data)
                elif route.path == "/api/open":
                    name = parse_qs(route.query).get("file", [""])[0]
                    self.respond(200, store.payload(store.load(store.version_path(name)), name))
                elif route.path == "/api/new":
                    store.verify()
                    self.respond(200, store.payload(store.new()))
                elif route.path == "/reference.jpg" and store.manifest["rgb_reference_available"]:
                    store.verify()
                    self.respond(200, (store.scan / "Reference.jpg").read_bytes(), "image/jpeg")
                elif route.path in ("/", "/app.js", "/style.css", "/scene.js", "/reference.js", "/vendor/three.module.js", "/vendor/three.core.js", "/vendor/OrbitControls.js"):
                    name = "index.html" if route.path == "/" else route.path[1:]
                    mime = "text/javascript; charset=utf-8" if name.endswith(".js") else "text/css; charset=utf-8" if name.endswith(".css") else "text/html; charset=utf-8"
                    self.respond(200, (ASSETS / name).read_bytes(), mime)
                else:
                    self.respond(404, {"error": "Not found"})
            except (ValueError, OSError) as error:
                self.respond(400, {"error": str(error)})

        def do_POST(self):
            if not self.allowed():
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 2_000_000:
                    raise ValueError("Invalid request size")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or "document" not in body:
                    raise ValueError("Missing design document")
                if self.path == "/api/preview":
                    data = store.payload(body["document"], body.get("filename"))
                elif self.path == "/api/save":
                    with lock:
                        doc, name = store.save(body["document"], body.get("filename"))
                    data = store.payload(doc, name)
                else:
                    self.respond(404, {"error": "Not found"})
                    return
                self.respond(200, data)
            except (ValueError, OSError, TypeError, KeyError) as error:
                self.respond(400, {"error": str(error)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, help="Imported scan folder, original ZIP, or saved .design.json")
    parser.add_argument("--port", type=int, default=0, help="Local port (default: any free port)")
    parser.add_argument("--no-open", action="store_true", help="Print the URL without opening a browser")
    args = parser.parse_args()
    try:
        source = args.source.expanduser().resolve() if args.source else None
        initial = None
        if source and source.name.endswith(".design.json"):
            saved = read_object(source)
            source_info = saved.get("source")
            if not isinstance(source_info, dict) or not isinstance(source_info.get("scan_id"), str):
                raise ValueError("Saved file is missing its source scan ID")
            scan_id = source_info["scan_id"]
            # Require the canonical local scan, never accept a path from JSON.
            import uuid
            if str(uuid.UUID(scan_id)) != scan_id:
                raise ValueError("Invalid saved scan ID")
            scan = ROOT / "scans" / scan_id
            store = DesignStore(scan, ROOT / "design-inputs")
            initial = store.load(source)
            if source.parent != store.output or source != store.version_path(source.name):
                raise ValueError(f"Open revisions from their saved location: {store.output}")
            filename = source.name
        else:
            if source is None:
                candidates = sorted((ROOT / "scans").glob("*/manifest.json"))
                if len(candidates) != 1:
                    raise ValueError("Pass the scan folder or ZIP to open (expected one local scan)")
                scan = candidates[0].parent
            else:
                scan = import_scan(source, ROOT / "scans")
            store = DesignStore(scan, ROOT / "design-inputs")
            filename = None
        server = make_server(store, initial or store.new(), filename, args.port)
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"Verified scan: {store.source['scan_id']}\nEditor: {url}\nSaves: {store.output}\nKeep this Terminal running. Ctrl-C stops the editor.", flush=True)
        if not args.no_open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"Cannot open editor: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
