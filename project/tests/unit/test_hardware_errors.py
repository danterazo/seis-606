import json
import subprocess
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Sequence

from homelab_dashboard.models import (
    ClusterSnapshot,
    ErrorCategory,
    ErrorClass,
    Hardware,
    HardwareErrors,
    HardwareSource,
    HealthLevel,
    Node,
    NodeState,
    Resources,
)
from homelab_dashboard.node_profiles import expected_hardware_for
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.hardware_source import HardwareEnrichedSource
from homelab_dashboard.sources.hwerrors_monitor import UNREACHABLE, HardwareErrorMonitor
from homelab_dashboard.sources.hwerrors_parser import parse_hardware_errors
from homelab_dashboard.sources.hwerrors_ssh import HW_ERRORS_SCRIPT, SshHardwareErrorProbe

BOOT: str = "b" * 32
OLD_BOOT: str = "a" * 32
DIMM: str = "CPU_SrcID#0_Ha#0_Chan#0_DIMM#1"
EDAC_LINE: str = f"EDAC MC0: 1 CE memory read error on {DIMM} (channel:0 slot:1 page:0x17c08ac offset:0xa80 grain:32 syndrome:0x0 - area:DRAM err_code:0001:0090 socket:0 ha:0 channel_mask:1 rank:1)"


def event(message: str, *, minute: int = 0, boot_id: str = BOOT, source: str = "kernel") -> Dict[str, str]:
    return {"timestamp": f"2025-10-08T10:{minute:02d}:00+00:00", "boot_id": boot_id, "source": source, "message": message}


def document(*events: Dict[str, str], **overrides: Any) -> Dict[str, Any]:
    return {"now": "2025-10-08T11:00:00+00:00", "boot_id": BOOT, "uptime_seconds": 3600.0, "edac": [], "events": list(events), "boots": [], "ras_summary": None, **overrides}


def test_clean_node_is_ok_and_distinct_from_unreadable() -> None:
    clean: HardwareErrors = parse_hardware_errors(document=document())
    assert (clean.level, clean.findings, clean.incidents) == (HealthLevel.OK, (), ())
    unreadable: HardwareErrors = parse_hardware_errors(document=document(edac=None, events=None))
    assert unreadable.level is HealthLevel.UNKNOWN
    assert not unreadable.edac_available and not unreadable.journal_available


def test_repeated_corrected_ecc_errors_at_one_address_are_one_escalated_incident_with_raw_evidence() -> None:
    result: HardwareErrors = parse_hardware_errors(document=document(*(event(EDAC_LINE, minute=minute) for minute in range(5))))
    (incident,) = result.incidents
    assert (incident.category, incident.classification) == (ErrorCategory.ECC_MEMORY, ErrorClass.CORRECTED)
    assert incident.count == 5 and incident.level is HealthLevel.CRITICAL and incident.current_boot
    assert dict(incident.fields)["address"] == "0x17c08aca80"
    assert dict(incident.fields)["page_frame"] == "0x17c08ac"
    assert dict(incident.fields)["dimm"] == DIMM
    assert "same address 0x17c08aca80 ×5" in incident.recurrence
    assert incident.title.startswith("Repeated corrected ECC errors at the same memory location")
    assert "bad" not in incident.title.lower()
    assert incident.raw[0].message == EDAC_LINE and incident.raw[0].boot_id == BOOT
    assert incident.last_hour == 5
    assert result.level is HealthLevel.CRITICAL


def test_single_corrected_error_is_a_warning_not_ignored() -> None:
    assert parse_hardware_errors(document=document(event(EDAC_LINE))).level is HealthLevel.WARNING


def test_uncorrected_ecc_is_critical_only_on_the_current_boot() -> None:
    line: str = EDAC_LINE.replace("1 CE", "1 UE")
    assert parse_hardware_errors(document=document(event(line))).level is HealthLevel.CRITICAL
    assert parse_hardware_errors(document=document(event(line, boot_id=OLD_BOOT))).level is HealthLevel.WARNING


def test_earlier_boot_incidents_are_marked_historical_and_recurrence_spans_boots() -> None:
    result: HardwareErrors = parse_hardware_errors(document=document(event(EDAC_LINE, boot_id=OLD_BOOT, minute=1), event(EDAC_LINE, minute=2)))
    old, new = sorted(result.incidents, key=lambda incident: incident.current_boot)
    assert not old.current_boot and new.current_boot
    assert old.level is HealthLevel.WARNING and new.level is HealthLevel.CRITICAL
    assert old.boots_seen == new.boots_seen == 2
    assert any("historical" in finding for finding in result.findings)


def test_cpu_internal_parity_reports_keep_cpu_bank_and_raw_status() -> None:
    message: str = "bank=0 status=90000040000f0005 Internal parity error Corrected_error cpu=5 socketid=0"
    result: HardwareErrors = parse_hardware_errors(document=document(*(event(message, minute=minute, source="rasdaemon") for minute in range(3))))
    (incident,) = result.incidents
    assert incident.category is ErrorCategory.CPU_MCE and incident.classification is ErrorClass.CORRECTED
    assert dict(incident.fields).items() >= {"cpu": "5", "bank": "0", "status": "0x90000040000f0005", "socket": "0"}.items()
    assert incident.title == "Repeated corrected internal parity errors reported on CPU 5 (bank 0)"
    assert incident.level is HealthLevel.CRITICAL


def test_kernel_mce_lines_cmci_storms_and_soft_offlining_are_separate_categories() -> None:
    result: HardwareErrors = parse_hardware_errors(
        document=document(
            event("mce: [Hardware Error]: Machine check events logged", minute=1),
            event("mce: CMCI storm detected: switching to poll mode", minute=2),
            event("RAS: Soft-offlining pfn: 0x17c08ac", minute=3),
            event("mce: [Hardware Error]: CPU 5: Machine Check: 0 Bank 0: 90000040000f0005", minute=4),
        )
    )
    categories = {incident.category for incident in result.incidents}
    assert categories == {ErrorCategory.CPU_MCE, ErrorCategory.PAGE_OFFLINE}
    offline = next(incident for incident in result.incidents if incident.category is ErrorCategory.PAGE_OFFLINE)
    assert dict(offline.fields)["page_frame"] == "0x17c08ac"
    assert "containment" in offline.title
    assert any(dict(incident.fields).get("note") == "CMCI storm" for incident in result.incidents)


def test_pcie_and_storage_path_errors_are_tracked_without_double_counting_continuation_lines() -> None:
    result: HardwareErrors = parse_hardware_errors(
        document=document(
            event("pcieport 0000:00:1c.0: PCIe Bus Error: severity=Uncorrected (Fatal), type=Transaction Layer", minute=1),
            event("pcieport 0000:00:1c.0:   device [8086:1234] error status/mask=00004000/00000000", minute=1),
            event("nvme nvme0: controller is down; will reset: CSTS=0x3", minute=2),
            event("blk_update_request: I/O error, dev sdb, sector 0", minute=3),
        )
    )
    by_category = {incident.category: incident for incident in result.incidents}
    assert by_category[ErrorCategory.PCIE].count == 1
    assert by_category[ErrorCategory.PCIE].classification is ErrorClass.UNCORRECTED
    assert dict(by_category[ErrorCategory.PCIE].fields)["device"] == "0000:00:1c.0"
    assert ErrorCategory.STORAGE_PATH in by_category
    assert len([incident for incident in result.incidents if incident.category is ErrorCategory.STORAGE_PATH]) == 2


def test_perf_sample_rate_message_is_not_a_hardware_error() -> None:
    message: str = "perf: interrupt took too long (2503 > 2500), lowering kernel.perf_event_max_sample_rate to 79000"
    assert parse_hardware_errors(document=document(event(message))).incidents == ()


def test_edac_counters_and_persisted_rasdaemon_totals() -> None:
    edac: List[Dict[str, Any]] = [{"controller": "mc0", "corrected": 15, "uncorrected": 0, "dimms": [{"label": DIMM, "corrected": 15, "uncorrected": 0}]}]
    summary: str = f"Memory controller events summary:\n\tCorrected on DIMM Label(s): '{DIMM}' location: 0:0:0:1 errors: 20\nNo PCIe AER errors.\nMCE records summary:\n\t3 Internal parity errors\n"
    result: HardwareErrors = parse_hardware_errors(document=document(edac=edac, ras_summary=summary))
    assert (result.memory_counters[0].label, result.memory_counters[0].corrected) == (DIMM, 15)
    assert (result.persisted_corrected, result.persisted_uncorrected, result.persisted_mce) == (20, 0, 3)
    assert result.level is HealthLevel.WARNING
    assert "15 corrected ECC errors since boot" in result.findings


def test_boot_and_uptime_are_recorded() -> None:
    result: HardwareErrors = parse_hardware_errors(document=document())
    assert result.boot_started == "2025-10-08T10:00:00+00:00"
    assert [(boot.boot_id, boot.current) for boot in result.boots] == [(BOOT, True)]


def test_probe_sends_script_and_parses() -> None:
    sent: List[Optional[str]] = []

    def runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        sent.append(stdin)
        return subprocess.CompletedProcess(args=list(command), returncode=0, stdout=json.dumps(document(event(EDAC_LINE))), stderr="")

    assert len(SshHardwareErrorProbe(runner=runner).probe(node_name="kex", address="10.0.0.1").incidents) == 1
    assert sent == [HW_ERRORS_SCRIPT]


class ErrorStub:
    def __init__(self) -> None:
        self.fail: bool = False
        self.boot: str = BOOT

    def probe(self, *, node_name: str, address: str) -> HardwareErrors:
        if self.fail:
            raise StatusSourceError("ssh down")
        return parse_hardware_errors(document=document(event(EDAC_LINE), boot_id=self.boot))


def test_monitor_keeps_last_known_state_marked_stale_and_flags_counter_resets() -> None:
    now: List[float] = [0.0]
    stub: ErrorStub = ErrorStub()
    monitor: HardwareErrorMonitor = HardwareErrorMonitor(probe=stub, ttl_seconds=60, clock=lambda: now[0])
    assert monitor.latest(node_name="kex", reachable=True) is None
    monitor.refresh(node_name="kex", address="10.0.0.1", force=False)
    monitor.wait()
    first: Optional[HardwareErrors] = monitor.latest(node_name="kex", reachable=True)
    assert first is not None and not first.stale and not first.counters_reset

    stub.fail = True
    now[0] = 61.0
    monitor.refresh(node_name="kex", address="10.0.0.1", force=False)
    monitor.wait()
    kept: Optional[HardwareErrors] = monitor.latest(node_name="kex", reachable=True)
    assert kept is not None and kept.stale and kept.error == "ssh down" and kept.incidents == first.incidents

    down: Optional[HardwareErrors] = monitor.latest(node_name="kex", reachable=False)
    assert down is not None and down.stale and down.error == UNREACHABLE and down.incidents == first.incidents

    stub.fail, stub.boot = False, OLD_BOOT
    now[0] = 200.0
    monitor.refresh(node_name="kex", address="10.0.0.1", force=False)
    monitor.wait()
    after: Optional[HardwareErrors] = monitor.latest(node_name="kex", reachable=True)
    assert after is not None and not after.stale and after.counters_reset


class OfflineAfterwards:
    def __init__(self) -> None:
        self.state: NodeState = NodeState.ONLINE

    def fetch(self) -> ClusterSnapshot:
        node: Node = Node(name="kex", state=self.state, address="10.0.0.5", resources=Resources(), guests=())
        return ClusterSnapshot(source="fake", fetched_at=datetime(2025, 1, 1, tzinfo=UTC), nodes=(node,))

    fetch_fresh = fetch


class HardwareStub:
    def probe(self, *, node_name: str, address: str) -> Hardware:
        return Hardware(source=HardwareSource.LIVE)


def test_hardware_errors_survive_a_node_going_offline() -> None:
    cluster: OfflineAfterwards = OfflineAfterwards()
    source: HardwareEnrichedSource = HardwareEnrichedSource(
        cluster=cluster,
        probe=HardwareStub(),
        expected_hardware=expected_hardware_for,
        ttl_seconds=3,
        errors=HardwareErrorMonitor(probe=ErrorStub(), ttl_seconds=60),
    )
    source.fetch()
    source.wait_for_storage_probes()
    online: Optional[HardwareErrors] = source.fetch().nodes[0].hardware.hardware_errors
    assert online is not None and online.incidents and not online.stale
    cluster.state = NodeState.OFFLINE
    offline: Optional[HardwareErrors] = source.fetch().nodes[0].hardware.hardware_errors
    assert offline is not None and offline.stale and offline.incidents == online.incidents
