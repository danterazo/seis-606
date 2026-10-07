import json
import subprocess
import threading
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Sequence
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from homelab_dashboard.config import Settings
from homelab_dashboard.models import ClusterSnapshot, Guest, GuestKind, GuestState, Node, NodeState, Resources
from homelab_dashboard.services.guests import GuestRebooter
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.openwrt_ssh import OpenWrtLeaseSource
from homelab_dashboard.sources.proxmox_ssh import SshTarget
from homelab_dashboard.ui.dashboard import build_dashboard_snapshot
from server import create_server


def test_dashboard_snapshot_includes_label_and_node_counts() -> None:
    snapshot: Dict[str, Any] = build_dashboard_snapshot(
        source_label="Mock data",
        nodes=[
            {
                "node_id": "node-a",
                "name": "Node A",
                "reported_state": "running",
                "workloads": [
                    {"node_id": "node-a", "workload_id": "vm-1", "name": "api", "kind": "virtual_machine", "reported_state": "running"},
                    {"node_id": "node-a", "workload_id": "ct-1", "name": "db", "kind": "container", "reported_state": "running"},
                ],
            },
            {"node_id": "node-b", "name": "Node B", "reported_state": "degraded", "workloads": []},
        ],
    )

    assert snapshot["source_label"] == "Mock data"
    assert snapshot["node_count"] == 2
    assert snapshot["nodes"][0]["name"] == "Node A"
    assert snapshot["nodes"][1]["reported_state"] == "degraded"
    assert snapshot["nodes"][0]["workload_count"] == 2


def test_devices_endpoint_is_independent_of_pve_and_can_force_refresh() -> None:
    calls: List[Sequence[str]] = []

    def runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="0 aa:bb:cc:dd:ee:ff 192.168.10.2 saru *", stderr="")

    class UnavailablePve:
        def fetch(self) -> ClusterSnapshot:
            raise StatusSourceError("PVE unavailable")

        def fetch_fresh(self) -> ClusterSnapshot:
            return self.fetch()

    devices = OpenWrtLeaseSource(target=SshTarget(host="192.168.10.1"), runner=runner)
    server = create_server(settings=Settings.from_env(environ={"PORT": "0"}), source=UnavailablePve(), devices=devices)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(f"{base}/api/devices", timeout=5) as response:
            payload = json.load(response)
            assert payload["leases"][0]["display_name"] == "\u3055\u308b"
            assert payload["error"] is None
        with urlopen(f"{base}/api/devices", timeout=5):
            assert len(calls) == 1
        with urlopen(f"{base}/api/devices?refresh=1", timeout=5):
            assert len(calls) == 2
        try:
            urlopen(f"{base}/api/status", timeout=5)
        except HTTPError as error:
            assert error.code == 503
            assert json.load(error)["error"] == "PVE unavailable"
        else:
            raise AssertionError("Expected PVE to be unavailable")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_reboot_endpoint_checks_origin_and_validates_commands_before_ssh() -> None:
    calls: List[Sequence[str]] = []

    def runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    class FakePve:
        def fetch(self) -> ClusterSnapshot:
            return ClusterSnapshot(source="test", fetched_at=datetime(2026, 10, 7, tzinfo=UTC), nodes=(
                Node(name="cerulean", state=NodeState.ONLINE, address="192.168.20.43", resources=Resources(), guests=(
                    Guest(vmid=112, name="test", node="cerulean", kind=GuestKind.CONTAINER, state=GuestState.RUNNING, resources=Resources()),
                )),
            ))

        def fetch_fresh(self) -> ClusterSnapshot:
            return self.fetch()

    source = FakePve()
    rebooter = GuestRebooter(source=source, runner=runner)
    server = create_server(settings=Settings.from_env(environ={"PORT": "0"}), source=source, rebooter=rebooter)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(*, body: object, origin: str = base, action: str = "reboot", content_type: str = "application/json") -> int:
        request = Request(f"{base}/api/guests/reboot", data=json.dumps(body).encode(), method="POST", headers={
            "Origin": origin, "X-Homelab-Action": action, "Content-Type": content_type,
        })
        try:
            with urlopen(request, timeout=5) as response:
                assert json.load(response)["message"] == "Reboot command submitted."
                return response.status
        except HTTPError as error:
            assert "error" in json.load(error)
            return error.code

    try:
        valid = {"vmid": 112, "node": "cerulean"}
        assert post(body=valid, origin="https://evil.example") == 403
        assert post(body=valid, origin="") == 403
        assert post(body=valid, action="") == 403
        assert post(body=valid, content_type="text/plain") == 415
        assert post(body={**valid, "command": "reboot"}) == 400
        assert post(body={"vmid": "112; reboot", "node": "cerulean"}) == 400
        assert post(body={"vmid": 112, "node": "kex"}) == 400
        assert calls == []
        assert post(body=valid) == 200
        assert calls[0][-2:] == ("root@192.168.20.43", "pct reboot 112")
        assert post(body=valid) == 503
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
