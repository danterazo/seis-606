import json
import socket
import socketserver
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Final, Tuple, Union
from urllib.parse import urlparse

from homelab_dashboard.config import Settings
from homelab_dashboard.node_images import find_node_image
from homelab_dashboard.sources.base import StatusSource, StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import ProxmoxSshSource, SshTarget

WEB_ROOT: Final[Path] = Path(__file__).resolve().parent / "web"
NODE_IMAGE_DIR: Final[Path] = WEB_ROOT / "images" / "nodes"
STATUS_PATH: Final[str] = "/api/status"

RequestSocket = Union[socket.socket, Tuple[bytes, socket.socket]]


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        request: RequestSocket,
        client_address: Any,
        server: socketserver.BaseServer,
        *,
        source: StatusSource,
    ) -> None:
        self.source: StatusSource = source
        super().__init__(request, client_address, server, directory=str(WEB_ROOT))

    def do_GET(self) -> None:
        if urlparse(self.path).path != STATUS_PATH:
            super().do_GET()
            return
        try:
            self._send_json(status=HTTPStatus.OK, payload=self._status_payload())
        except StatusSourceError as error:
            self._send_json(status=HTTPStatus.SERVICE_UNAVAILABLE, payload={"error": str(error)})

    def _status_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = self.source.fetch().to_payload()
        for node in payload["nodes"]:
            node["image"] = find_node_image(node_name=node["name"], image_dir=NODE_IMAGE_DIR)
        return payload

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, *, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body: bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(*, settings: Settings, source: StatusSource) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((settings.host, settings.port), partial(DashboardHandler, source=source))


def main() -> None:
    settings: Settings = Settings.from_env()
    try:
        target: SshTarget = SshTarget(host=settings.ssh_host, user=settings.ssh_user)
    except ValueError as error:
        sys.exit(str(error))

    source: StatusSource = ProxmoxSshSource(target=target, timeout_seconds=settings.ssh_timeout_seconds)
    server: ThreadingHTTPServer = create_server(settings=settings, source=source)
    print(f"Homelab dashboard running at http://{settings.host}:{settings.port} (source: {target.destination})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping homelab dashboard.")
    finally:
        server.server_close()
