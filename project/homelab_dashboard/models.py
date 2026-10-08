from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, Optional, Tuple


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

    cpu_ratio: Optional[float] = None
    cpu_cores: Optional[int] = None
    memory_used_bytes: Optional[int] = None
    memory_total_bytes: Optional[int] = None


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
    utilization_percent: Optional[float] = None
    memory_used_bytes: Optional[int] = None
    memory_total_bytes: Optional[int] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Disk:
    """`kind` is hdd, ssd or nvme; `findings` lists only what is not normal."""

    device: str
    model: Optional[str]
    serial: Optional[str]
    kind: str
    level: HealthLevel
    standby: bool = False
    temperature_celsius: Optional[int] = None
    power_on_hours: Optional[int] = None
    findings: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Pool:
    name: str
    state: str
    level: HealthLevel
    capacity_percent: Optional[int] = None
    size_bytes: Optional[int] = None
    allocated_bytes: Optional[int] = None
    free_bytes: Optional[int] = None
    fragmentation_percent: Optional[int] = None
    layout: Optional[str] = None
    scan: Optional[str] = None
    findings: Tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Storage:
    """The availability flags tell "no problems" apart from "smartctl / zpool is not installed"."""

    disks: Tuple[Disk, ...] = ()
    pools: Tuple[Pool, ...] = ()
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
    recurrence: Tuple[str, ...] = ()
    fields: Tuple[Tuple[str, str], ...] = ()
    raw: Tuple[RawEvent, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class BootRecord:
    boot_id: str
    first_seen: Optional[str]
    last_seen: Optional[str]
    current: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryCounter:
    """EDAC counters; they restart from zero at every boot."""

    controller: str
    label: Optional[str]
    corrected: int
    uncorrected: int


@dataclass(frozen=True, slots=True, kw_only=True)
class HardwareErrors:
    """Hardware error evidence for a node, deliberately separate from utilization.

    `stale` means the figures are the last known ones because the node or the probe did not answer.
    """

    level: HealthLevel
    findings: Tuple[str, ...] = ()
    incidents: Tuple[ErrorIncident, ...] = ()
    boots: Tuple[BootRecord, ...] = ()
    memory_counters: Tuple[MemoryCounter, ...] = ()
    edac_available: bool = False
    journal_available: bool = False
    persisted_corrected: Optional[int] = None
    persisted_uncorrected: Optional[int] = None
    persisted_mce: Optional[int] = None
    boot_id: Optional[str] = None
    boot_started: Optional[str] = None
    collected_at: Optional[str] = None
    stale: bool = False
    error: Optional[str] = None
    last_success: Optional[str] = None
    counters_reset: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Hardware:
    """`source` says whether this was read from the node (live) or taken from the configured profile (expected)."""

    cpu_model: Optional[str] = None
    cpu_cores: Optional[int] = None
    cpu_threads: Optional[int] = None
    gpus: Tuple[Gpu, ...] = ()
    source: HardwareSource = HardwareSource.UNKNOWN
    ecc_supported: Optional[bool] = None
    zfs_arc_bytes: Optional[int] = None
    zfs_arc_max_bytes: Optional[int] = None
    storage: Optional[Storage] = None
    hardware_errors: Optional[HardwareErrors] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    name: str
    state: NodeState
    address: Optional[str]
    resources: Resources
    guests: Tuple[Guest, ...]
    hardware: Hardware = Hardware()


@dataclass(frozen=True, slots=True, kw_only=True)
class ClusterSnapshot:
    source: str
    fetched_at: datetime
    nodes: Tuple[Node, ...]

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = asdict(self)
        payload["fetched_at"] = self.fetched_at.isoformat(timespec="seconds")
        return payload
