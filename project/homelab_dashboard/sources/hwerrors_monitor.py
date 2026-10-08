import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace

from homelab_dashboard.models import HardwareErrors, HealthLevel
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.hwerrors_ssh import HardwareErrorProbe

UNREACHABLE: str = "Node is unreachable; showing the last known hardware error state."


@dataclass(slots=True, kw_only=True)
class HardwareErrorMonitor:
    """Reads hardware error evidence in the background and never loses the last good reading.

    A failed probe or an unreachable node keeps the previous result, marked stale, so "no new errors"
    can't be confused with "the collector stopped reporting".
    """

    probe: HardwareErrorProbe
    ttl_seconds: float
    clock: Callable[[], float] = time.monotonic
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _good: dict[str, HardwareErrors] = field(default_factory=dict, init=False)
    _failure: dict[str, str] = field(default_factory=dict, init=False)
    _checked: dict[str, float] = field(default_factory=dict, init=False)
    _running: dict[str, "Future[None]"] = field(default_factory=dict, init=False)
    _pool: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(max_workers=4), init=False)

    def refresh(self, *, node_name: str, address: str, force: bool) -> None:
        with self._lock:
            checked: float | None = self._checked.get(node_name)
            fresh: bool = checked is not None and self.clock() - checked < self.ttl_seconds
            if node_name in self._running or (fresh and not force):
                return
            self._running[node_name] = self._pool.submit(self._probe, node_name, address)

    def wait(self) -> None:
        with self._lock:
            running: list[Future[None]] = list(self._running.values())
        for future in running:
            future.result()

    def latest(self, *, node_name: str, reachable: bool) -> HardwareErrors | None:
        with self._lock:
            good: HardwareErrors | None = self._good.get(node_name)
            failure: str | None = self._failure.get(node_name)
        if not reachable:
            failure = UNREACHABLE
        if good is None:
            if failure is None:
                return None
            return HardwareErrors(
                level=HealthLevel.UNKNOWN, findings=("Hardware errors have not been collected from this node",), stale=True, error=failure
            )
        return good if failure is None else replace(good, stale=True, error=failure)

    def _probe(self, node_name: str, address: str) -> None:
        result: HardwareErrors | None = None
        failure: str | None = None
        try:
            result = self.probe.probe(node_name=node_name, address=address)
        except StatusSourceError as error:
            failure = str(error)
        with self._lock:
            if result is not None:
                previous: HardwareErrors | None = self._good.get(node_name)
                rebooted: bool = previous is not None and previous.boot_id != result.boot_id
                carried: bool = previous is not None and previous.counters_reset and not rebooted
                self._good[node_name] = replace(result, counters_reset=rebooted or carried)
                self._failure.pop(node_name, None)
            elif failure is not None:
                self._failure[node_name] = failure
            self._checked[node_name] = self.clock()
            del self._running[node_name]
