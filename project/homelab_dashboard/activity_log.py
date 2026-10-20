import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ActivityLog:
    def __init__(self, path: Path, *, max_bytes: int = 1024 * 1024) -> None:
        if max_bytes <= 0:
            raise ValueError("Activity log size must be positive.")
        self.path: Path = path
        self.max_bytes: int = max_bytes
        self._lock: threading.Lock = threading.Lock()

    def record(self, *, method: str, path: str, status: int, client: str) -> None:
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "method": method,
            "path": path,
            "status": status,
            "client": client,
        }
        encoded: bytes = (json.dumps(entry, ensure_ascii=True) + "\n").encode("utf-8")
        if len(encoded) > self.max_bytes:
            raise OSError("Activity log entry exceeds the storage limit.")
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with self.path.open("rb") as existing:
                    size: int = existing.seek(0, os.SEEK_END)
                    if size:
                        existing.seek(-1, os.SEEK_END)
                    complete: bool = not size or existing.read(1) == b"\n"
            except FileNotFoundError:
                size = 0
                complete = True
            if complete and size + len(encoded) <= self.max_bytes:
                with self.path.open("ab") as log_file:
                    log_file.write(encoded)
                return
            retained: bytes = self._tail(min(self.max_bytes // 2, self.max_bytes - len(encoded)))
            temporary: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=f".{self.path.name}.", delete=False) as log_file:
                    temporary = Path(log_file.name)
                    log_file.write(retained + encoded)
                os.replace(temporary, self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    def _tail(self, budget: int) -> bytes:
        if budget <= 0:
            return b""
        try:
            with self.path.open("rb") as log_file:
                size: int = log_file.seek(0, os.SEEK_END)
                start: int = max(0, size - budget)
                log_file.seek(max(0, start - 1))
                data: bytes = log_file.read(budget + (1 if start else 0))
        except FileNotFoundError:
            return b""
        if start:
            data = data.partition(b"\n")[2]
        if data and not data.endswith(b"\n"):
            data = data.rpartition(b"\n")[0]
            if data:
                data += b"\n"
        return data

    def read(self, *, limit: int = 500) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        with self._lock:
            lines: list[bytes] = self._tail(self.max_bytes).splitlines()[-limit:]
        entries: list[dict[str, Any]] = []
        for line in lines:
            try:
                entry: object = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(entry, dict):
                entries.append(entry)
        return entries

    def clear(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")
