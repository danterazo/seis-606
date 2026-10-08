import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol

from homelab_dashboard.models import ClusterSnapshot, Hardware, HardwareErrors, Node, NodeState, Storage
from homelab_dashboard.sources.base import RefreshableStatusSource, StatusSourceError
from homelab_dashboard.sources.hardware_ssh import HardwareProbe
from homelab_dashboard.sources.hwerrors_monitor import HardwareErrorMonitor
from homelab_dashboard.sources.storage_ssh import StorageProbe


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
    storage_probe: StorageProbe | None = None
    storage_ttl_seconds: float = 300.0
    errors: HardwareErrorMonitor | None = None
    clock: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = _utc_now
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _entries: dict[str, _Entry] = field(default_factory=dict, init=False)
    _storage_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _storage: dict[str, Storage] = field(default_factory=dict, init=False)
    _storage_checked: dict[str, float] = field(default_factory=dict, init=False)
    _storage_running: dict[str, "Future[None]"] = field(default_factory=dict, init=False)
    _storage_pool: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(max_workers=4), init=False)

    def fetch(self) -> ClusterSnapshot:
        return self._enrich(snapshot=self.cluster.fetch(), force=False)

    def fetch_fresh(self) -> ClusterSnapshot:
        return self._enrich(snapshot=self.cluster.fetch_fresh(), force=True)

    def _enrich(self, *, snapshot: ClusterSnapshot, force: bool) -> ClusterSnapshot:
        with self._lock:
            stale: list[Node] = [node for node in snapshot.nodes if self._is_probeable(node=node) and (force or self._is_stale(node=node))]
            if stale:
                with ThreadPoolExecutor(max_workers=len(stale)) as pool:
                    for node, entry in zip(stale, pool.map(self._probe_one, stale)):
                        self._entries[node.name] = entry
            for node in snapshot.nodes:
                if self._is_probeable(node=node):
                    self._refresh_storage(node=node, force=force)
                    if self.errors is not None:
                        self.errors.refresh(node_name=node.name, address=str(node.address), force=force)
            nodes: tuple[Node, ...] = tuple(self._with_hardware(node=node) for node in snapshot.nodes)
            checked: list[datetime] = [self._entries[node.name].checked_at for node in snapshot.nodes if self._is_probeable(node=node)]
        return replace(snapshot, nodes=nodes, fetched_at=max([snapshot.fetched_at, *checked]))

    def wait_for_storage_probes(self) -> None:
        with self._storage_lock:
            running: list[Future[None]] = list(self._storage_running.values())
        for future in running:
            future.result()
        if self.errors is not None:
            self.errors.wait()

    def _refresh_storage(self, *, node: Node, force: bool) -> None:
        """SMART reads take seconds, so they run in the background and the page keeps the last result meanwhile."""
        if self.storage_probe is None:
            return
        with self._storage_lock:
            checked: float | None = self._storage_checked.get(node.name)
            fresh: bool = checked is not None and self.clock() - checked < self.storage_ttl_seconds
            if node.name in self._storage_running or (fresh and not force):
                return
            self._storage_running[node.name] = self._storage_pool.submit(self._probe_storage, node.name, str(node.address))

    def _probe_storage(self, node_name: str, address: str) -> None:
        assert self.storage_probe is not None
        result: Storage | None = None
        try:
            result = self.storage_probe.probe(node_name=node_name, address=address)
        except StatusSourceError:
            pass  # keep the previous reading rather than hiding a known problem
        with self._storage_lock:
            if result is not None:
                self._storage[node_name] = result
            self._storage_checked[node_name] = self.clock()
            del self._storage_running[node_name]

    @staticmethod
    def _is_probeable(*, node: Node) -> bool:
        return node.state is NodeState.ONLINE and node.address is not None

    def _is_stale(self, *, node: Node) -> bool:
        entry: _Entry | None = self._entries.get(node.name)
        return entry is None or self.clock() - entry.stored_at >= self.ttl_seconds

    def _probe_one(self, node: Node) -> _Entry:
        try:
            hardware: Hardware = self.probe.probe(node_name=node.name, address=str(node.address))
        except StatusSourceError:
            hardware = self.expected_hardware(node_name=node.name)
        return _Entry(hardware=hardware, stored_at=self.clock(), checked_at=self.now())

    def _with_hardware(self, *, node: Node) -> Node:
        # Hardware error history is kept even while the node is down; that is when it matters most.
        hardware_errors: HardwareErrors | None = None
        if self.errors is not None:
            hardware_errors = self.errors.latest(node_name=node.name, reachable=self._is_probeable(node=node))
        if self._is_probeable(node=node) and node.name in self._entries:
            with self._storage_lock:
                storage: Storage | None = self._storage.get(node.name)
            return replace(node, hardware=replace(self._entries[node.name].hardware, storage=storage, hardware_errors=hardware_errors))
        return replace(node, hardware=replace(self.expected_hardware(node_name=node.name), hardware_errors=hardware_errors))
