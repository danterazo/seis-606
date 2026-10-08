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
class Hardware:
    """`source` says whether this was read from the node (live) or taken from the configured profile (expected)."""

    cpu_model: Optional[str] = None
    gpus: Tuple[Gpu, ...] = ()
    source: HardwareSource = HardwareSource.UNKNOWN
    ecc_supported: Optional[bool] = None
    zfs_arc_bytes: Optional[int] = None
    zfs_arc_max_bytes: Optional[int] = None


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
