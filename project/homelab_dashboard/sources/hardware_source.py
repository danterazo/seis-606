import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Callable, Dict, List, Optional, Protocol, Tuple

from homelab_dashboard.models import ClusterSnapshot, Hardware, Node, NodeState
from homelab_dashboard.sources.base import RefreshableStatusSource, StatusSourceError
from homelab_dashboard.sources.hardware_ssh import HardwareProbe


class ExpectedHardware(Protocol):
    def __call__(self, *, node_name: str) -> Hardware: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class _Entry:
    hardware: Hardware
    stored_at: float
    checked_at: datetime


@dataclass(slots=True, kw_only=True)
class HardwareEnrichedSource:
    """Adds CPU/GPU details to each node of the cluster snapshot.

    Only online nodes are probed, in parallel and on their own short cache so GPU
    load stays lively without repeating the heavier cluster query. A node that
    can't be probed never fails the snapshot; it shows the profile's expected
    hardware instead.
    """

    cluster: RefreshableStatusSource
    probe: HardwareProbe
    expected_hardware: ExpectedHardware
    ttl_seconds: float
    clock: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = _utc_now
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _entries: Dict[str, _Entry] = field(default_factory=dict, init=False)

    def fetch(self) -> ClusterSnapshot:
        return self._enrich(snapshot=self.cluster.fetch(), force=False)

    def fetch_fresh(self) -> ClusterSnapshot:
        return self._enrich(snapshot=self.cluster.fetch_fresh(), force=True)

    def _enrich(self, *, snapshot: ClusterSnapshot, force: bool) -> ClusterSnapshot:
        with self._lock:
            stale: List[Node] = [node for node in snapshot.nodes if self._is_probeable(node=node) and (force or self._is_stale(node=node))]
            if stale:
                with ThreadPoolExecutor(max_workers=len(stale)) as pool:
                    for node, entry in zip(stale, pool.map(self._probe_one, stale)):
                        self._entries[node.name] = entry
            nodes: Tuple[Node, ...] = tuple(self._with_hardware(node=node) for node in snapshot.nodes)
            checked: List[datetime] = [self._entries[node.name].checked_at for node in snapshot.nodes if self._is_probeable(node=node)]
        return replace(snapshot, nodes=nodes, fetched_at=max([snapshot.fetched_at, *checked]))

    @staticmethod
    def _is_probeable(*, node: Node) -> bool:
        return node.state is NodeState.ONLINE and node.address is not None

    def _is_stale(self, *, node: Node) -> bool:
        entry: Optional[_Entry] = self._entries.get(node.name)
        return entry is None or self.clock() - entry.stored_at >= self.ttl_seconds

    def _probe_one(self, node: Node) -> _Entry:
        try:
            hardware: Hardware = self.probe.probe(node_name=node.name, address=str(node.address))
        except StatusSourceError:
            hardware = self.expected_hardware(node_name=node.name)
        return _Entry(hardware=hardware, stored_at=self.clock(), checked_at=self.now())

    def _with_hardware(self, *, node: Node) -> Node:
        if self._is_probeable(node=node) and node.name in self._entries:
            return replace(node, hardware=self._entries[node.name].hardware)
        return replace(node, hardware=self.expected_hardware(node_name=node.name))
