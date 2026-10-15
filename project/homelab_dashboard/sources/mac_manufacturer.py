import csv
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from io import StringIO
from typing import Final, Optional, cast
from urllib.request import Request, urlopen

IEEE_OUI_REGISTRY_URL: Final[str] = "https://standards-oui.ieee.org/oui/oui.csv"
_PREFIX_LENGTHS: Final[tuple[int, ...]] = (9, 7, 6)


def _download_registry() -> str:
    request: Request = Request(IEEE_OUI_REGISTRY_URL, headers={"User-Agent": "HomelabDashboard/1.0"})
    with urlopen(request, timeout=3.0) as response:
        registry_bytes: bytes = cast(bytes, response.read())
        return registry_bytes.decode("utf-8")


def _parse_registry(*, text: str) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for row in csv.DictReader(StringIO(text)):
        prefix: str = row.get("Assignment", "").strip().upper()
        manufacturer: str = row.get("Organization Name", "").strip()
        if len(prefix) in _PREFIX_LENGTHS and re.fullmatch(r"[0-9A-F]+", prefix) and manufacturer:
            prefixes[prefix] = manufacturer
    if not prefixes:
        raise ValueError("The IEEE MAC prefix registry contained no assignments.")
    return prefixes


@dataclass(slots=True, kw_only=True)
class MacManufacturerLookup:
    fetch_registry: Callable[[], str] = _download_registry
    clock: Callable[[], float] = time.monotonic
    refresh_seconds: float = 86_400.0
    retry_seconds: float = 300.0
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _prefixes: dict[str, str] = field(default_factory=dict, init=False)
    _refresh_at: Optional[float] = field(default=None, init=False)

    def lookup(self, *, mac: str) -> Optional[str]:
        compact: str = mac.replace(":", "").upper()
        if not re.fullmatch(r"[0-9A-F]{12}", compact) or int(compact[:2], 16) & 3:
            return None

        with self._lock:
            now: float = self.clock()
            if self._refresh_at is None or now >= self._refresh_at:
                try:
                    self._prefixes = _parse_registry(text=self.fetch_registry())
                    self._refresh_at = now + self.refresh_seconds
                except (OSError, UnicodeError, csv.Error, ValueError):
                    self._refresh_at = now + self.retry_seconds

            for length in _PREFIX_LENGTHS:
                manufacturer: Optional[str] = self._prefixes.get(compact[:length])
                if manufacturer is not None:
                    return manufacturer
        return None
