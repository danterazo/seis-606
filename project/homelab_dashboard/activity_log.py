import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List


class ActivityLog:
    def __init__(self, path: Path) -> None:
        self.path: Path = path
        self._lock: threading.Lock = threading.Lock()

    def record(self, *, method: str, path: str, status: int, client: str) -> None:
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "method": method,
            "path": path,
            "status": status,
            "client": client,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def read(self, *, limit: int = 500) -> List[Dict[str, Any]]:
        with self._lock:
            if not self.path.exists():
                return []
            with self.path.open("r", encoding="utf-8") as log_file:
                lines: List[str] = log_file.readlines()[-limit:]
        entries: List[Dict[str, Any]] = []
        for line in lines:
            try:
                entry: object = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
        return entries

    def clear(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")
