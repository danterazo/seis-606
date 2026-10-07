import json
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from homelab_dashboard.config import Settings
from homelab_dashboard.sources.base import StatusSource, StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import ProxmoxSshSource, SshTarget

WEB_ROOT = Path(__file__).resolve().parent / "web"
STATUS_PATH = "/api/status"


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, source: StatusSource, **kwargs: Any) -> None:
        self.source = source
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        if urlparse(self.path).path != STATUS_PATH:
            super().do_GET()
            return
        try:
            self._send_json(status=HTTPStatus.OK, payload=self.source.fetch().to_payload())
        except StatusSourceError as error:
            self._send_json(status=HTTPStatus.SERVICE_UNAVAILABLE, payload={"error": str(error)})

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, *, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(*, settings: Settings, source: StatusSource) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((settings.host, settings.port), partial(DashboardHandler, source=source))


def main() -> None:
    settings = Settings.from_env()
    try:
        target = SshTarget(destination=settings.ssh_target)
    except ValueError as error:
        sys.exit(str(error))

    source = ProxmoxSshSource(target=target, timeout_seconds=settings.ssh_timeout_seconds)
    server = create_server(settings=settings, source=source)
    print(f"Homelab dashboard running at http://{settings.host}:{settings.port} (source: {target.destination})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping homelab dashboard.")
    finally:
        server.server_close()
