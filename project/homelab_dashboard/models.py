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


@dataclass(frozen=True, slots=True, kw_only=True)
class Resources:
    """Readings Proxmox did not report stay None rather than becoming zero."""

    cpu_ratio: float | None = None
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
class Node:
    name: str
    state: NodeState
    address: str | None
    resources: Resources
    guests: tuple[Guest, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ClusterSnapshot:
    source: str
    fetched_at: datetime
    nodes: tuple[Node, ...]

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["fetched_at"] = self.fetched_at.isoformat(timespec="seconds")
        return payload
