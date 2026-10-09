import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from homelab_dashboard.models import ClusterSnapshot, Hardware, HardwareSource, HealthLevel, Node, NodeState, Resources, Storage
from homelab_dashboard.node_profiles import expected_hardware_for
from homelab_dashboard.sources import storage_probe
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.hardware_source import HardwareEnrichedSource
from homelab_dashboard.sources.storage_parser import parse_storage
from homelab_dashboard.sources.storage_ssh import STORAGE_SCRIPT, SshStorageProbe


def hdd(**overrides: Any) -> dict[str, Any]:
    return {
        "device": "/dev/sda",
        "model": "WDC",
        "serial": "X1",
        "protocol": "ATA",
        "rotation_rate": 7200,
        "smart_passed": True,
        "temperature": 38,
        "attributes": [],
        **overrides,
    }


def test_healthy_hdd_has_no_findings() -> None:
    storage: Storage = parse_storage(document={"disks": [hdd()], "pools": []})
    assert storage.smart_available and storage.zfs_available
    assert storage.disks[0].level is HealthLevel.OK
    assert storage.disks[0].findings == ()


@pytest.mark.parametrize(("celsius", "level"), [(44, HealthLevel.OK), (45, HealthLevel.WARNING), (50, HealthLevel.CRITICAL)])
def test_hdd_temperature_thresholds(celsius: int, level: HealthLevel) -> None:
    assert parse_storage(document={"disks": [hdd(temperature=celsius)]}).disks[0].level is level


def test_ssd_tolerates_temperatures_that_are_hot_for_an_hdd() -> None:
    disk: dict[str, Any] = hdd(rotation_rate=0, temperature=55)
    assert parse_storage(document={"disks": [disk]}).disks[0].level is HealthLevel.OK


def test_failed_smart_and_bad_attributes_are_reported_worst_first() -> None:
    attributes: list[dict[str, Any]] = [
        {"id": 5, "name": "Reallocated_Sector_Ct", "value": 100, "thresh": 10, "raw": 8, "when_failed": ""},
        {"id": 9, "name": "Power_On_Hours", "value": 90, "thresh": 0, "raw": 5000, "when_failed": ""},
        {"id": 3, "name": "Spin_Up_Time", "value": 5, "thresh": 21, "raw": 0, "when_failed": "FAILING_NOW"},
    ]
    disk = parse_storage(document={"disks": [hdd(smart_passed=False, attributes=attributes)]}).disks[0]
    assert disk.level is HealthLevel.CRITICAL
    assert disk.findings[0] == "SMART overall health check failed"
    assert "Reallocated_Sector_Ct: 8" in disk.findings
    assert not any("Power_On_Hours" in finding for finding in disk.findings)


def test_nvme_health_log_is_judged() -> None:
    nvme: dict[str, Any] = {
        "device": "/dev/nvme0",
        "protocol": "NVMe",
        "smart_passed": True,
        "temperature": 40,
        "nvme": {"critical_warning": 0, "available_spare": 4, "available_spare_threshold": 10, "percentage_used": 95, "media_errors": 0},
    }
    disk = parse_storage(document={"disks": [nvme]}).disks[0]
    assert disk.kind == "nvme"
    assert disk.level is HealthLevel.CRITICAL
    assert len(disk.findings) == 2


def test_standby_and_unreadable_disks_are_not_flagged_as_problems_or_hidden() -> None:
    standby, unreadable = parse_storage(document={"disks": [hdd(standby=True, temperature=None), {"device": "/dev/sdb", "read_failed": True}]}).disks
    assert standby.standby and standby.level is HealthLevel.OK
    assert unreadable.level is HealthLevel.UNKNOWN


HEALTHY_STATUS: str = "  pool: rpool\n state: ONLINE\n  scan: scrub repaired 0B in 00:10:00 with 0 errors on Sun\nconfig:\n\n\tNAME        STATE     READ WRITE CKSUM\n\trpool       ONLINE       0     0     0\n\t  sda3      ONLINE       0     0     0\n\nerrors: No known data errors\n"


def test_healthy_pool() -> None:
    pool = parse_storage(
        document={
            "pools": [{"name": "rpool", "health": "ONLINE", "capacity": "12", "size": "1000", "dataset_available": "400", "status": HEALTHY_STATUS}]
        }
    ).pools[0]
    assert (pool.level, pool.capacity_percent, pool.findings) == (HealthLevel.OK, 12, ())
    assert (pool.size_bytes, pool.dataset_available_bytes) == (1000, 400)


def test_pool_problems() -> None:
    status: str = HEALTHY_STATUS.replace("rpool       ONLINE       0     0     0", "rpool       ONLINE       0     0     3").replace(
        "No known data errors", "Permanent errors have been detected"
    )
    pool = parse_storage(document={"pools": [{"name": "rpool", "health": "DEGRADED", "capacity": "93", "status": status}]}).pools[0]
    assert pool.level is HealthLevel.CRITICAL
    assert any("checksum 3" in finding for finding in pool.findings)
    assert "93% full" in pool.findings and "Pool is DEGRADED" in pool.findings


def test_missing_tools_are_distinguished_from_clean_results() -> None:
    storage: Storage = parse_storage(document={"disks": None, "pools": []})
    assert (storage.smart_available, storage.zfs_available) == (False, True)
    with pytest.raises(StatusSourceError):
        parse_storage(document=[])


def test_ssh_probe_sends_script_and_parses() -> None:
    sent: list[str | None] = []

    def runner(command: Sequence[str], *, timeout: float, stdin: str | None = None) -> "subprocess.CompletedProcess[str]":
        sent.append(stdin)
        return subprocess.CompletedProcess(args=list(command), returncode=0, stdout=json.dumps({"disks": [hdd()], "pools": []}), stderr="")

    assert len(SshStorageProbe(runner=runner).probe(node_name="kex", address="10.0.0.1").disks) == 1
    assert sent == [STORAGE_SCRIPT]


def test_pool_probe_reads_available_from_only_the_root_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []

    def fake_run(*, command: list[str], timeout: float) -> str:
        commands.append(command)
        if command[:2] == ["zpool", "list"]:
            return "rpool\tONLINE\t40\t1000\t400\t600\t1\n"
        if command[:2] == ["zpool", "status"]:
            return HEALTHY_STATUS
        if command[0] == "zfs":
            return "rpool\t600\n"
        raise AssertionError(command)

    monkeypatch.setattr(storage_probe.shutil, "which", lambda name: "/sbin/zpool" if name == "zpool" else None)
    monkeypatch.setattr(storage_probe, "run", fake_run)

    pools = storage_probe.collect_pools()

    assert pools is not None
    assert pools[0]["dataset_available"] == 600
    assert ["zfs", "get", "-Hp", "-d", "0", "-o", "name,value", "available", "rpool"] in commands


class OneNode:
    def fetch(self) -> ClusterSnapshot:
        node: Node = Node(name="kex", state=NodeState.ONLINE, address="10.0.0.5", resources=Resources(), guests=())
        return ClusterSnapshot(source="fake", fetched_at=datetime(2025, 1, 1, tzinfo=UTC), nodes=(node,))

    fetch_fresh = fetch


class HardwareStub:
    def probe(self, *, node_name: str, address: str) -> Hardware:
        return Hardware(source=HardwareSource.LIVE)


class StorageStub:
    def __init__(self) -> None:
        self.calls: int = 0
        self.fail: bool = False

    def probe(self, *, node_name: str, address: str) -> Storage:
        self.calls += 1
        if self.fail:
            raise StatusSourceError("down")
        return Storage(smart_available=True, zfs_available=True)


def test_storage_is_probed_in_the_background_cached_and_kept_when_a_probe_fails() -> None:
    now: list[float] = [0.0]
    stub: StorageStub = StorageStub()
    source: HardwareEnrichedSource = HardwareEnrichedSource(
        cluster=OneNode(),
        probe=HardwareStub(),
        expected_hardware=expected_hardware_for,
        ttl_seconds=3,
        storage_probe=stub,
        storage_ttl_seconds=300,
        clock=lambda: now[0],
    )
    source.fetch()
    source.wait_for_storage_probes()
    assert source.fetch().nodes[0].hardware.storage == Storage(smart_available=True, zfs_available=True)
    source.wait_for_storage_probes()
    assert stub.calls == 1
    now[0] = 301.0
    stub.fail = True
    source.fetch()
    source.wait_for_storage_probes()
    assert stub.calls == 2
    assert source.fetch().nodes[0].hardware.storage is not None
