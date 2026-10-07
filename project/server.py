import json
import socket
import socketserver
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Final, Tuple, Union
from urllib.parse import parse_qs, urlparse

from homelab_dashboard.config import Settings
from homelab_dashboard.presentation import present_payload
from homelab_dashboard.node_profiles import expected_hardware_for
from homelab_dashboard.sources.base import RefreshableStatusSource, StatusSource, StatusSourceError
from homelab_dashboard.sources.cache import CachedStatusSource
from homelab_dashboard.sources.hardware_source import HardwareEnrichedSource
from homelab_dashboard.sources.hardware_ssh import SshHardwareProbe
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
        source: RefreshableStatusSource,
    ) -> None:
        self.source: RefreshableStatusSource = source
        super().__init__(request, client_address, server, directory=str(WEB_ROOT))

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path != STATUS_PATH:
            super().do_GET()
            return
        force_refresh: bool = "refresh" in parse_qs(url.query)
        try:
            self._send_json(status=HTTPStatus.OK, payload=self._status_payload(force_refresh=force_refresh))
        except StatusSourceError as error:
            self._send_json(status=HTTPStatus.SERVICE_UNAVAILABLE, payload={"error": str(error)})

    def _status_payload(self, *, force_refresh: bool) -> Dict[str, Any]:
        snapshot = self.source.fetch_fresh() if force_refresh else self.source.fetch()
        return present_payload(payload=snapshot.to_payload(), image_dir=NODE_IMAGE_DIR)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, *, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body: bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The browser navigated away or reloaded before the response finished.
            return


def create_server(*, settings: Settings, source: RefreshableStatusSource) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((settings.host, settings.port), partial(DashboardHandler, source=source))


def main() -> None:
    settings: Settings = Settings.from_env()
    try:
        target: SshTarget = SshTarget(host=settings.ssh_host, user=settings.ssh_user)
    except ValueError as error:
        sys.exit(str(error))

    source: StatusSource = ProxmoxSshSource(target=target, timeout_seconds=settings.ssh_timeout_seconds)
    cached: CachedStatusSource = CachedStatusSource(inner=source, ttl_seconds=settings.cache_seconds)
    enriched: RefreshableStatusSource = HardwareEnrichedSource(
        cluster=cached,
        probe=SshHardwareProbe(user=settings.ssh_user, timeout_seconds=settings.ssh_timeout_seconds),
        expected_hardware=expected_hardware_for,
        ttl_seconds=settings.hardware_cache_seconds,
    )
    server: ThreadingHTTPServer = create_server(settings=settings, source=enriched)
    print(f"Homelab dashboard running at http://{settings.host}:{settings.port} (source: {target.destination})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping homelab dashboard.")
    finally:
        server.server_close()
