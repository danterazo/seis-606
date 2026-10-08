import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from homelab_dashboard.models import ClusterSnapshot
from homelab_dashboard.sources.base import StatusSource, StatusSourceError


@dataclass(slots=True, kw_only=True)
class CachedStatusSource:
    """Shares one query between all callers within `ttl_seconds`, failures included, so a down node isn't retried per request."""

    inner: StatusSource
    ttl_seconds: float
    clock: Callable[[], float] = time.monotonic
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _stored_at: float | None = field(default=None, init=False)
    _snapshot: ClusterSnapshot | None = field(default=None, init=False)
    _error: StatusSourceError | None = field(default=None, init=False)

    def fetch(self) -> ClusterSnapshot:
        with self._lock:
            if not self._is_fresh():
                self._refill()
            return self._result()

    def fetch_fresh(self) -> ClusterSnapshot:
        """Ignore the cache; used by the manual Refresh button."""
        with self._lock:
            self._refill()
            return self._result()

    def _is_fresh(self) -> bool:
        return self._stored_at is not None and self.clock() - self._stored_at < self.ttl_seconds

    def _refill(self) -> None:
        try:
            self._snapshot, self._error = self.inner.fetch(), None
        except StatusSourceError as error:
            self._snapshot, self._error = None, error
        self._stored_at = self.clock()

    def _result(self) -> ClusterSnapshot:
        if self._error is not None:
            raise self._error
        if self._snapshot is None:
            raise StatusSourceError("No status has been read yet.")
        return self._snapshot
