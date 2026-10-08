import ipaddress
import json
import os
import socket
import socketserver
import sys
import time
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Final, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

from homelab_dashboard.activity_log import ActivityLog
from homelab_dashboard.config import Settings
from homelab_dashboard.node_profiles import expected_hardware_for
from homelab_dashboard.presentation import present_payload
from homelab_dashboard.services.guests import GuestRebooter
from homelab_dashboard.sources.base import RefreshableStatusSource, StatusSource, StatusSourceError
from homelab_dashboard.sources.cache import CachedStatusSource
from homelab_dashboard.sources.hardware_source import HardwareEnrichedSource
from homelab_dashboard.sources.hardware_ssh import SshHardwareProbe
from homelab_dashboard.sources.storage_ssh import SshStorageProbe
from homelab_dashboard.sources.openwrt_ssh import OpenWrtLeaseSource
from homelab_dashboard.sources.proxmox_ssh import ProxmoxSshSource, SshTarget

WEB_ROOT: Final[Path] = Path(__file__).resolve().parent / "web"
NODE_IMAGE_DIR: Final[Path] = WEB_ROOT / "images" / "nodes"
STATUS_PATH: Final[str] = "/api/status"
DEVICES_PATH: Final[str] = "/api/devices"
REBOOT_PATH: Final[str] = "/api/guests/reboot"
LOGS_PATH: Final[str] = "/api/logs"
DEV_VERSION_PATH: Final[str] = "/__dev/version"
BOOT_ID: Final[str] = str(time.time_ns())
CLEAR_LOGS_PATH: Final[str] = "/api/logs/clear"
LOG_PATH: Final[Path] = Path(__file__).resolve().parent / "logs" / "access.jsonl"

RequestSocket = Union[socket.socket, Tuple[bytes, socket.socket]]


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        request: RequestSocket,
        client_address: Any,
        server: socketserver.BaseServer,
        *,
        source: RefreshableStatusSource,
        activity_log: ActivityLog,
        devices: Optional[OpenWrtLeaseSource] = None,
        rebooter: Optional[GuestRebooter] = None,
    ) -> None:
        self.source: RefreshableStatusSource = source
        self.activity_log: ActivityLog = activity_log
        self.devices: Optional[OpenWrtLeaseSource] = devices
        self.rebooter: Optional[GuestRebooter] = rebooter
        super().__init__(request, client_address, server, directory=str(WEB_ROOT))

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == DEV_VERSION_PATH and os.environ.get("DASHBOARD_DEV") == "1":
            newest: int = max((path.stat().st_mtime_ns for path in WEB_ROOT.glob("*") if path.is_file()), default=0)
            self._send_json(status=HTTPStatus.OK, payload={"version": f"{BOOT_ID}:{newest}"})
            return
        if url.path == LOGS_PATH:
            self._send_json(status=HTTPStatus.OK, payload={"entries": self.activity_log.read()})
            return
        if url.path == DEVICES_PATH:
            if self.devices is None:
                self._send_json(status=HTTPStatus.SERVICE_UNAVAILABLE, payload={"error": "OpenWRT lease source is not configured."})
            else:
                self._send_json(status=HTTPStatus.OK, payload=self.devices.fetch(force="refresh" in parse_qs(url.query)))
            return
        if url.path != STATUS_PATH:
            super().do_GET()
            return
        force_refresh: bool = "refresh" in parse_qs(url.query)
        try:
            self._send_json(status=HTTPStatus.OK, payload=self._status_payload(force_refresh=force_refresh))
        except StatusSourceError as error:
            self._send_json(status=HTTPStatus.SERVICE_UNAVAILABLE, payload={"error": str(error)})

    def do_POST(self) -> None:
        request_path: str = urlparse(self.path).path
        if request_path == CLEAR_LOGS_PATH:
            if not self._is_local_same_origin_request(action="clear-logs"):
                self._send_json(status=HTTPStatus.FORBIDDEN, payload={"error": "Log controls require a same-origin localhost request."})
                return
            self.activity_log.clear()
            self._send_json(status=HTTPStatus.OK, payload={"message": "Activity log cleared."})
            return
        if request_path != REBOOT_PATH:
            self._send_json(status=HTTPStatus.NOT_FOUND, payload={"error": "Unknown action."})
            return
        if not self._is_local_same_origin_request(action="reboot"):
            self._send_json(status=HTTPStatus.FORBIDDEN, payload={"error": "Guest controls require a same-origin localhost request."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self._send_json(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE, payload={"error": "A JSON request is required."})
            return
        if self.rebooter is None:
            self._send_json(status=HTTPStatus.SERVICE_UNAVAILABLE, payload={"error": "Guest controls are not configured."})
            return
        try:
            length: int = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError("Guest action requests must be between 1 and 1024 bytes.")
            self.connection.settimeout(5.0)
            document: object = json.loads(self.rfile.read(length))
            if not isinstance(document, dict) or set(document) != {"vmid", "node"}:
                raise ValueError("A guest ID and node name are required; no other fields are accepted.")
            self.rebooter.reboot(vmid=document["vmid"], node_name=document["node"])
        except (ValueError, UnicodeDecodeError) as error:
            self._send_json(status=HTTPStatus.BAD_REQUEST, payload={"error": str(error)})
        except TimeoutError:
            self._send_json(status=HTTPStatus.REQUEST_TIMEOUT, payload={"error": "Reading the guest action request timed out."})
        except StatusSourceError as error:
            self._send_json(status=HTTPStatus.SERVICE_UNAVAILABLE, payload={"error": str(error)})
        else:
            self._send_json(status=HTTPStatus.OK, payload={"message": "Reboot command submitted."})

    def _is_local_same_origin_request(self, *, action: str) -> bool:
        host: str = self.headers.get("Host", "")
        origin = urlparse(self.headers.get("Origin", ""))
        return not (
            not ipaddress.ip_address(self.client_address[0]).is_loopback
            or urlparse(f"//{host}").hostname not in ("localhost", "127.0.0.1", "::1")
            or origin.scheme not in ("http", "https")
            or origin.netloc != host
            or self.headers.get("X-Homelab-Action") != action
        )

    def log_request(self, code: Union[int, str] = "-", size: Union[int, str] = "-") -> None:
        request_path: str = urlparse(self.path).path[:512]
        try:
            self.activity_log.record(
                method=self.command,
                path=request_path,
                status=int(code),
                client=self.client_address[0],
            )
        except OSError as error:
            self.log_message("Could not write activity log: %s", error)

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


def create_server(
    *, settings: Settings, source: RefreshableStatusSource, activity_log: Optional[ActivityLog] = None, devices: Optional[OpenWrtLeaseSource] = None,
    rebooter: Optional[GuestRebooter] = None,
) -> ThreadingHTTPServer:
    log_store: ActivityLog = activity_log if activity_log is not None else ActivityLog(LOG_PATH)
    return ThreadingHTTPServer(
        (settings.host, settings.port),
        partial(
            DashboardHandler,
            source=source,
            activity_log=log_store,
            devices=devices,
            rebooter=rebooter,
        ),
    )


def main() -> None:
    settings: Settings = Settings.from_env()
    try:
        target: SshTarget = SshTarget(host=settings.ssh_host, user=settings.ssh_user)
        router_target: SshTarget = SshTarget(host=settings.router_ssh_host, user=settings.router_ssh_user)
    except ValueError as error:
        sys.exit(str(error))

    source: StatusSource = ProxmoxSshSource(target=target, timeout_seconds=settings.ssh_timeout_seconds)
    cached: CachedStatusSource = CachedStatusSource(inner=source, ttl_seconds=settings.cache_seconds)
    enriched: RefreshableStatusSource = HardwareEnrichedSource(
        cluster=cached,
        probe=SshHardwareProbe(user=settings.ssh_user, timeout_seconds=settings.ssh_timeout_seconds),
        expected_hardware=expected_hardware_for,
        ttl_seconds=settings.hardware_cache_seconds,
        storage_probe=SshStorageProbe(user=settings.ssh_user),
        storage_ttl_seconds=settings.storage_cache_seconds,
    )
    devices: OpenWrtLeaseSource = OpenWrtLeaseSource(target=router_target, ttl_seconds=settings.router_cache_seconds)
    rebooter: GuestRebooter = GuestRebooter(source=enriched, user=settings.ssh_user)
    server: ThreadingHTTPServer = create_server(settings=settings, source=enriched, devices=devices, rebooter=rebooter)
    print(f"Homelab dashboard running at http://{settings.host}:{settings.port} (source: {target.destination})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping homelab dashboard.")
    finally:
        server.server_close()

