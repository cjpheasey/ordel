"""Local HTTP server: the UI files, plugin pictures and a small JSON API, on 127.0.0.1 only."""
import json
import logging
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .api import Api

log = logging.getLogger(__name__)
_SNAPSHOT = re.compile(r"^/snapshots/([0-9a-f]{12})\.png$")


def make_server(api: Api, ui_dir: Path, snapshots_dir: Path, port: int = 0) -> ThreadingHTTPServer:
    ui_dir = Path(ui_dir).resolve()
    api.snapshots_dir = Path(snapshots_dir)
    posts = {
        "/api/refresh": lambda b: api.refresh(),
        "/api/send": lambda b: api.send(b["id"], b.get("variant")),
        "/api/plugin": lambda b: api.update_plugin(b["id"], **{k: b[k] for k in ("favourite", "category") if k in b}),
        "/api/settings": lambda b: api.update_settings(**b),
        "/api/capture": lambda b: api.capture_action(b["action"], b.get("id")),
        "/api/custom-image": lambda b: api.custom_image(b["id"]),
        "/api/bridge/install": lambda b: api.install_bridge(),
        "/api/window": lambda b: api.window(b["action"]),
        "/api/chain": lambda b: api.chain_action(**b),
        "/api/projects-folder": lambda b: api.choose_projects_folder(),
        "/api/category": lambda b: api.category_action(**b),
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status: int, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data):
            self._send(status, json.dumps(data).encode(), "application/json")

        def _file(self, path: Path):
            self._send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")

        def _foreign(self) -> bool:
            # Block web pages from driving the app: only our own origin may call it.
            # Browsers say where a request comes from: another site may not even look (e.g. probe which
            # plugin pictures exist); only Ordel's own page or a typed-in address may.
            site = self.headers.get("Sec-Fetch-Site")
            if (self.headers.get("Host") != f"127.0.0.1:{self.server.server_address[1]}"
                    or site not in (None, "same-origin", "none")):
                self._json(403, {"error": "forbidden"})
                return True
            return False

        def do_GET(self):
            if self._foreign():
                return
            path = unquote(urlsplit(self.path).path)
            if path == "/api/state":
                return self._json(200, api.state())
            if m := _SNAPSHOT.match(path):
                file = api.snapshots_dir / f"{m.group(1)}.png"
                return self._file(file) if file.is_file() else self._json(404, {"error": "not found"})
            target = (ui_dir / (path.lstrip("/") or "index.html")).resolve()
            if target.is_relative_to(ui_dir) and target.is_file():
                return self._file(target)
            self._json(404, {"error": "not found"})

        def do_POST(self):
            if self._foreign():
                return
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._json(415, {"error": "expected application/json"})  # forces a CORS preflight
            route = posts.get(urlsplit(self.path).path)
            if route is None:
                return self._json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("body must be an object")
                return self._json(200, route(body))
            except (ValueError, KeyError, TypeError) as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:  # one bad request must not take the server down
                log.exception("API error on %s", self.path)
                return self._json(500, {"error": str(e)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
