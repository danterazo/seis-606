from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from homelab_dashboard.sources.operator_report import build_operator_report
from homelab_dashboard.sources.proxmox_ssh import build_ssh_report

WEB_ROOT = Path(__file__).resolve().parent / "web"


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/status":
            source = os.getenv("HOMELAB_STATUS_SOURCE", "ssh").lower()
            if source in {"ssh", "proxmox"}:
                try:
                    self._send_json(200, build_ssh_report())
                except RuntimeError as error:
                    self._send_json(503, {"error": str(error)})
                return
            if source in {"manual", "report"}:
                self._send_json(200, build_operator_report())
                return
            if source not in {"ssh", "proxmox", "manual", "report"}:
                self._send_json(503, {"error": "Unknown status source. Use ssh or manual."})
                return
        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = os.getenv("HOMELAB_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8765"))
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Homelab dashboard running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping homelab dashboard.")
    finally:
        server.server_close()
