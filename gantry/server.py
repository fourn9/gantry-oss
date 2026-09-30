"""Loopback HTTP API. Deploy behind an authenticated TLS reverse proxy off-host."""
import json
import sys
import re
import threading
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from pathlib import Path

from . import __version__
from .model import Fault, canonical
from .service import Service


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, service):
        self.service = service
        self.failures = defaultdict(deque)
        self.failure_lock = threading.Lock()
        super().__init__(address, Handler)

    def resolve(self, path):
        return self.service, path


class CloudServer(Server):
    """Provisioned workspaces only. Separate databases, blobs and credentials.

    Bind behind TLS/edge request limits. No execution takes place on this host.
    The operator provisions each directory; HTTP never creates a workspace.
    """
    def __init__(self, address, root):
        self.root = Path(root).resolve()
        self.services = {}; self.services_lock = threading.Lock()
        super().__init__(address, None)

    def resolve(self, path):
        match = re.fullmatch(r'/w/([a-z0-9][a-z0-9-]{0,47})(/.*)?', path)
        if not match:
            return None, path
        name, suffix = match.group(1), match.group(2) or '/'
        folder = self.root / name
        if folder.is_symlink() or not (folder / 'ledger.sqlite3').is_file():
            return None, suffix
        with self.services_lock:
            if name not in self.services:
                self.services[name] = Service(folder)
                self.services[name].credential_prefix = 'GANTRY_CONNECTOR_' + name.upper().replace('-', '_') + '_'
            return self.services[name], suffix


class Handler(BaseHTTPRequestHandler):
    server_version = "Gantry/" + __version__
    def log_message(self, fmt, *args):
        # Never log Authorization headers or request bodies.
        sys.stderr.write("gantry-http: " + fmt % args + "\n")

    def respond(self, code, body):
        raw = canonical(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def valid_host(self):
        # Protect a local service from DNS rebinding. Cloud proxy deployments
        # must enforce their own external Host allowlist at the TLS edge.
        if isinstance(self.server, CloudServer) or self.server.server_address[0] not in {'127.0.0.1', '::1'}:
            return True
        try:
            value = urlparse('http://' + self.headers.get('Host', ''))
            return (value.hostname in {'127.0.0.1', 'localhost', '::1'} and
                    (value.port or 80) == self.server.server_port and not value.username and not value.password)
        except ValueError:
            return False

    def do_GET(self):
        if not self.valid_host():
            self.respond(403, {'error': {'code': 'unauthorized', 'message': 'Untrusted Host'}}); return
        if isinstance(self.server, CloudServer) and re.fullmatch(r'/w/[a-z0-9][a-z0-9-]{0,47}', self.path):
            self.send_response(308); self.send_header('Location', self.path + '/')
            self.send_header('Content-Length', '0'); self.end_headers(); return
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/review_views.js": ("review_views.js", "text/javascript; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/ui.js": ("ui.js", "text/javascript; charset=utf-8"),
                  "/views.js": ("views.js", "text/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        _, path = self.server.resolve(urlparse(self.path).path)
        if path in assets:
            name, mime = assets[path]
            raw = (Path(__file__).parent / "web" / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers(); self.wfile.write(raw)
        elif self.path == "/health": self.respond(200, {"service": "gantry", "status": "ok"})
        else: self.respond(404, {"error": {"code": "not_found", "message": "Use POST /v1/commands/{command}"}})

    def do_POST(self):
        try:
            if not self.valid_host(): raise Fault('unauthorized', 'Untrusted Host')
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                raise Fault('invalid_input', 'Require exactly one Content-Length and no Transfer-Encoding')
            now = time.monotonic(); address = self.client_address[0]
            with self.server.failure_lock:
                attempts = self.server.failures[address]
                while attempts and attempts[0] < now - 60: attempts.popleft()
                if len(attempts) >= 30:
                    self.respond(429, {"error": {"code": "rate_limited", "message": "Too many authentication failures; wait one minute"}}); return
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                raise Fault("unauthorized", "Cross-origin requests denied")
            service, path = self.server.resolve(urlparse(self.path).path)
            if not path.startswith("/v1/commands/"):
                self.respond(404, {"error": {"code": "not_found"}}); return
            if service is None:
                raise Fault('unauthorized', 'Workspace or credential unavailable')
            command = path.removeprefix("/v1/commands/")
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 90 * 1024 * 1024:
                raise Fault("invalid_input", "Invalid body size")
            if "application/json" not in self.headers.get("Content-Type", ""):
                raise Fault("invalid_input", "Content-Type must be application/json")
            self.connection.settimeout(30)
            args = json.loads(self.rfile.read(length))
            auth = self.headers.get("Authorization", "")
            token = auth[7:] if auth.startswith("Bearer ") else ""
            result = service.call(token, command, args, self.headers.get("Idempotency-Key"))
            self.respond(200, {"result": result})
        except Fault as exc:
            if exc.code == 'unauthorized':
                with self.server.failure_lock:
                    self.server.failures[self.client_address[0]].append(time.monotonic())
                    if len(self.server.failures) > 10000:
                        self.server.failures = defaultdict(deque, {k: v for k, v in self.server.failures.items() if v and v[-1] > time.monotonic()-60})
            code = 401 if exc.code == "unauthorized" else 404 if exc.code == "not_found" else 409 if exc.code in {
                "conflict", "stale_basis", "idempotency_mismatch", "human_approval_required", "review_pending"} else 400
            self.respond(code, {"error": exc.as_dict()})
        except (ValueError, TypeError, KeyError) as exc:
            self.respond(400, {"error": {"code": "invalid_input", "message": str(exc)}})
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)
            self.respond(500, {"error": {"code": "internal_error", "message": "Request failed; inspect server log"}})


def serve(directory, host="127.0.0.1", port=8765):
    server = Server((host, port), Service(directory))
    print("Gantry API: http://%s:%s" % server.server_address, file=sys.stderr)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


def serve_cloud(root, host='127.0.0.1', port=8765):
    server = CloudServer((host, port), root)
    print('Gantry cloud gateway: http://%s:%s (TLS proxy required)' % server.server_address, file=sys.stderr)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
