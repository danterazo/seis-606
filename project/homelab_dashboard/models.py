from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class NodeState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class GuestKind(StrEnum):
    VM = "vm"
    CONTAINER = "container"


class GuestState(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    UNKNOWN = "unknown"


class GpuState(StrEnum):
    ACTIVE = "active"
    PASSTHROUGH = "passthrough"
    NO_DRIVER = "no_driver"
    EXPECTED = "expected"


class HardwareSource(StrEnum):
    LIVE = "live"
    EXPECTED = "expected"
    UNKNOWN = "unknown"


class HealthLevel(StrEnum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True, kw_only=True)
class Resources:
    """Readings Proxmox did not report stay None rather than becoming zero."""

    cpu_ratio: float | None = None
    cpu_cores: int | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Guest:
    vmid: int
    name: str
    node: str
    kind: GuestKind
    state: GuestState
    resources: Resources


@dataclass(frozen=True, slots=True, kw_only=True)
class Gpu:
    name: str
    state: GpuState
    utilization_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Disk:
    """`kind` is hdd, ssd or nvme; `findings` lists only what is not normal."""

    device: str
    model: str | None
    serial: str | None
    kind: str
    level: HealthLevel
    standby: bool = False
    temperature_celsius: int | None = None
    power_on_hours: int | None = None
    findings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Pool:
    name: str
    state: str
    level: HealthLevel
    capacity_percent: int | None = None
    size_bytes: int | None = None
    dataset_available_bytes: int | None = None
    allocated_bytes: int | None = None
    free_bytes: int | None = None
    fragmentation_percent: int | None = None
    layout: str | None = None
    scan: str | None = None
    findings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Storage:
    """The availability flags tell "no problems" apart from "smartctl / zpool is not installed"."""

    disks: tuple[Disk, ...] = ()
    pools: tuple[Pool, ...] = ()
    smart_available: bool = False
    zfs_available: bool = False


class ErrorCategory(StrEnum):
    ECC_MEMORY = "ecc_memory"
    CPU_MCE = "cpu_mce"
    PAGE_OFFLINE = "page_offline"
    PCIE = "pcie"
    STORAGE_PATH = "storage_path"


class ErrorClass(StrEnum):
    CORRECTED = "corrected"
    UNCORRECTED = "uncorrected"
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True, slots=True, kw_only=True)
class RawEvent:
    """The original log line, kept verbatim next to whatever was decoded from it."""

    timestamp: str
    boot_id: str
    source: str
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorIncident:
    """Identical repeated events on one boot, folded together; `fields` are the most frequent decoded values."""

    category: ErrorCategory
    classification: ErrorClass
    title: str
    level: HealthLevel
    count: int
    first_seen: str
    last_seen: str
    last_hour: int
    last_day: int
    boot_id: str
    current_boot: bool
    boots_seen: int
    recurrence: tuple[str, ...] = ()
    fields: tuple[tuple[str, str], ...] = ()
    raw: tuple[RawEvent, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class BootRecord:
    boot_id: str
    first_seen: str | None
    last_seen: str | None
    current: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryCounter:
    """EDAC counters; they restart from zero at every boot."""

    controller: str
    label: str | None
    corrected: int
    uncorrected: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HardwareErrors:
    """Hardware error evidence for a node, deliberately separate from utilization.

    `stale` means the figures are the last known ones because the node or the probe did not answer.
    """

    level: HealthLevel
    findings: tuple[str, ...] = ()
    incidents: tuple[ErrorIncident, ...] = ()
    boots: tuple[BootRecord, ...] = ()
    memory_counters: tuple[MemoryCounter, ...] = ()
    edac_available: bool = False
    journal_available: bool = False
    persisted_corrected: int | None = None
    persisted_uncorrected: int | None = None
    persisted_mce: int | None = None
    boot_id: str | None = None
    boot_started: str | None = None
    collected_at: str | None = None
    stale: bool = False
    error: str | None = None
    last_success: str | None = None
    counters_reset: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Hardware:
    """`source` says whether this was read from the node (live) or taken from the configured profile (expected)."""

    cpu_model: str | None = None
    cpu_cores: int | None = None
    cpu_threads: int | None = None
    gpus: tuple[Gpu, ...] = ()
    source: HardwareSource = HardwareSource.UNKNOWN
    ecc_supported: bool | None = None
    zfs_arc_bytes: int | None = None
    zfs_arc_max_bytes: int | None = None
    storage: Storage | None = None
    hardware_errors: HardwareErrors | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    name: str
    state: NodeState
    address: str | None
    resources: Resources
    guests: tuple[Guest, ...]
    hardware: Hardware = Hardware()


@dataclass(frozen=True, slots=True, kw_only=True)
class ClusterSnapshot:
    source: str
    fetched_at: datetime
    nodes: tuple[Node, ...]

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = asdict(self)
        payload["fetched_at"] = self.fetched_at.isoformat(timespec="seconds")
        return payload
