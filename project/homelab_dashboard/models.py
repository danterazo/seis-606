from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, Tuple, Union


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


@dataclass(frozen=True, slots=True, kw_only=True)
class Resources:
    """Readings Proxmox did not report stay None rather than becoming zero."""

    cpu_ratio: Union[float, None] = None
    cpu_cores: Union[int, None] = None
    memory_used_bytes: Union[int, None] = None
    memory_total_bytes: Union[int, None] = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Guest:
    vmid: int
    name: str
    node: str
    kind: GuestKind
    state: GuestState
    resources: Resources


@dataclass(frozen=True, slots=True, kw_only=True)
class Node:
    name: str
    state: NodeState
    address: Union[str, None]
    resources: Resources
    guests: Tuple[Guest, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ClusterSnapshot:
    source: str
    fetched_at: datetime
    nodes: Tuple[Node, ...]

    def to_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = asdict(self)
        payload["fetched_at"] = self.fetched_at.isoformat(timespec="seconds")
        return payload
