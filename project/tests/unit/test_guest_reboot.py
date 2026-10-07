import subprocess
from datetime import UTC, datetime
from typing import List, Optional, Sequence

import pytest

from homelab_dashboard.models import ClusterSnapshot, Guest, GuestKind, GuestState, Node, NodeState, Resources
from homelab_dashboard.services.guests import GuestRebooter
from homelab_dashboard.sources.base import StatusSourceError


class FakeSource:
    def __init__(self, *, kind: GuestKind = GuestKind.CONTAINER, guest_state: GuestState = GuestState.RUNNING, node_state: NodeState = NodeState.ONLINE) -> None:
        self.calls: int = 0
        self.snapshot: ClusterSnapshot = ClusterSnapshot(
            source="test", fetched_at=datetime(2026, 10, 7, tzinfo=UTC),
            nodes=(Node(name="cerulean", state=node_state, address="192.168.20.43", resources=Resources(), guests=(
                Guest(vmid=112, name="test", node="cerulean", kind=kind, state=guest_state, resources=Resources()),
            )),),
        )

    def fetch(self) -> ClusterSnapshot:
        return self.snapshot

    def fetch_fresh(self) -> ClusterSnapshot:
        self.calls += 1
        return self.snapshot


@pytest.mark.parametrize(("kind", "expected"), [(GuestKind.CONTAINER, "pct reboot 112"), (GuestKind.VM, "qm reboot 112")])
def test_reboot_uses_the_current_node_address_and_server_derived_kind(kind: GuestKind, expected: str) -> None:
    calls: List[Sequence[str]] = []

    def runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    source = FakeSource(kind=kind)
    service = GuestRebooter(source=source, runner=runner)
    service.reboot(vmid=112, node_name="cerulean")
    assert source.calls == 1
    assert calls[0][-2:] == ("root@192.168.20.43", expected)
    assert "-oStrictHostKeyChecking=yes" in calls[0]
    with pytest.raises(StatusSourceError, match="recently attempted"):
        service.reboot(vmid=112, node_name="cerulean")
    assert len(calls) == 1


def forbidden_runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
    pytest.fail("An invalid request must not run SSH")


@pytest.mark.parametrize("vmid", [True, "112", "112; reboot", 99, 1000000000, None])
def test_invalid_ids_never_run_ssh(vmid: object) -> None:
    service = GuestRebooter(source=FakeSource(), runner=forbidden_runner)
    with pytest.raises(ValueError, match="Guest ID"):
        service.reboot(vmid=vmid, node_name="cerulean")


@pytest.mark.parametrize(("vmid", "node"), [(113, "cerulean"), (112, "kex"), (112, "cerulean; reboot"), (112, "")])
def test_missing_or_moved_guests_never_run_ssh(vmid: int, node: str) -> None:
    service = GuestRebooter(source=FakeSource(), runner=forbidden_runner)
    with pytest.raises(ValueError):
        service.reboot(vmid=vmid, node_name=node)


@pytest.mark.parametrize(("guest_state", "node_state"), [(GuestState.STOPPED, NodeState.ONLINE), (GuestState.RUNNING, NodeState.OFFLINE)])
def test_unavailable_guests_never_run_ssh(guest_state: GuestState, node_state: NodeState) -> None:
    service = GuestRebooter(source=FakeSource(guest_state=guest_state, node_state=node_state), runner=forbidden_runner)
    with pytest.raises(ValueError, match="Only running"):
        service.reboot(vmid=112, node_name="cerulean")


def test_command_failure_does_not_claim_a_successful_reboot() -> None:
    def runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        return subprocess.CompletedProcess(args=command, returncode=255, stdout="", stderr="Permission denied")

    service = GuestRebooter(source=FakeSource(), runner=runner)
    with pytest.raises(StatusSourceError, match="refused"):
        service.reboot(vmid=112, node_name="cerulean")


def test_command_timeout_warns_against_blind_retries() -> None:
    def runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)

    service = GuestRebooter(source=FakeSource(), runner=runner)
    with pytest.raises(StatusSourceError, match="may still be running"):
        service.reboot(vmid=112, node_name="cerulean")
