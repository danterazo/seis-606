import subprocess
from datetime import UTC, datetime
from typing import List, Optional, Sequence

import pytest

from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.openwrt_ssh import OpenWrtLeaseSource, parse_leases
from homelab_dashboard.sources.proxmox_ssh import SshTarget

NOW: datetime = datetime(2026, 10, 7, tzinfo=UTC)
LEASES: str = "2000000000 AA:BB:CC:DD:EE:FF 192.168.10.23 ringo-M4 *\n0 11:22:33:44:55:66 192.168.10.24 * *\n"


def test_dnsmasq_leases_preserve_identity_and_use_shared_names() -> None:
    named, unnamed = parse_leases(text=LEASES)
    assert named.mac == "aa:bb:cc:dd:ee:ff"
    assert named.to_payload()["mac"] == "AA:BB:CC:DD:EE:FF"
    assert named.hostname == "ringo-M4"
    assert named.to_payload()["display_name"] == "\u308a\u3093\u3054-M4"
    assert named.expires_at == datetime.fromtimestamp(2000000000, UTC)
    assert unnamed.expires_at is None
    assert unnamed.hostname is None
    assert unnamed.to_payload()["display_name"] == "192.168.10.24"
    assert parse_leases(text="\n") == ()


@pytest.mark.parametrize("text", ["bad row", "x aa:bb:cc:dd:ee:ff 192.168.10.2 suika *", "0 bad 192.168.10.2 suika *", "0 aa:bb:cc:dd:ee:ff bad suika *", "-1 aa:bb:cc:dd:ee:ff 192.168.10.2 suika *"])
def test_malformed_leases_are_not_presented_as_empty_inventory(text: str) -> None:
    with pytest.raises(StatusSourceError):
        parse_leases(text=text)


class FakeRunner:
    def __init__(self) -> None:
        self.calls: List[Sequence[str]] = []
        self.returncode: int = 0
        self.stdout: str = LEASES
        self.stderr: str = ""

    def __call__(self, command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        assert timeout == 8.0
        self.calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=self.returncode, stdout=self.stdout, stderr=self.stderr)


def test_router_source_caches_failures_and_retains_last_good_data() -> None:
    runner = FakeRunner()
    ticks: List[float] = [0.0]
    source = OpenWrtLeaseSource(target=SshTarget(host="192.168.10.1"), runner=runner, now=lambda: NOW, clock=lambda: ticks[0])
    first = source.fetch()
    assert len(first["leases"]) == 2
    assert first["stale"] is False
    assert first["router"] == "192.168.10.1"
    assert first["source"] == "OpenWRT DHCPv4"
    source.fetch()
    assert len(runner.calls) == 1
    command = runner.calls[0]
    assert "-oStrictHostKeyChecking=yes" in command
    assert "-oBatchMode=yes" in command
    assert command[-2:] == ("root@192.168.10.1", "cat /tmp/dhcp.leases")
    ticks[0] = 60.0
    runner.returncode = 255
    runner.stderr = "Host key verification failed."
    failed = source.fetch()
    assert failed["stale"] is True
    assert "host key" in failed["error"]
    assert failed["leases"] == first["leases"]
    assert failed["fetched_at"] == first["fetched_at"]
    source.fetch()
    assert len(runner.calls) == 2
    runner.returncode = 0
    assert source.fetch(force=True)["stale"] is False
    assert len(runner.calls) == 3


def test_first_failure_has_no_fake_leases_or_success_timestamp() -> None:
    runner = FakeRunner()
    runner.returncode = 255
    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner)
    payload = source.fetch()
    assert payload["leases"] == []
    assert payload["fetched_at"] is None
    assert payload["error"] is not None


def test_expired_leases_are_filtered_even_when_the_cache_is_fresh() -> None:
    runner = FakeRunner()
    runner.stdout = "100 aa:bb:cc:dd:ee:ff 192.168.10.2 suika *"
    seconds: List[int] = [99]
    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner, now=lambda: datetime.fromtimestamp(seconds[0], UTC))
    assert len(source.fetch()["leases"]) == 1
    seconds[0] = 100
    assert source.fetch()["leases"] == []
    assert len(runner.calls) == 1


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired(cmd="ssh", timeout=8)])
def test_transport_errors_stay_local_to_the_devices_payload(error: Exception) -> None:
    def runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        raise error

    source = OpenWrtLeaseSource(target=SshTarget(host="router"), runner=runner)
    assert source.fetch()["stale"] is True
