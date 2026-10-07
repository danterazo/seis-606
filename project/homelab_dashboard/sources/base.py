from typing import Protocol

from homelab_dashboard.models import ClusterSnapshot


class StatusSourceError(Exception):
    """Raised when no snapshot could be produced; the message is safe to show in the UI."""


class StatusSource(Protocol):
    def fetch(self) -> ClusterSnapshot: ...
