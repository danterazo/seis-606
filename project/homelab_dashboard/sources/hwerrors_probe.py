"""Runs on a Proxmox node (python3, standard library only) and prints raw hardware-error evidence as JSON.

The dashboard sends this file over SSH on stdin, so it must not import anything from this project.
It only reads: EDAC counters, the kernel and rasdaemon journal, and `ras-mc-ctl --summary`.
Decoding and judging what is abnormal happens on the dashboard side.
"""

import collections
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOOKBACK = "14 days ago"
MAX_EVENTS = 3000
MAX_MESSAGE_CHARS = 400
JOURNAL_DEADLINE_SECONDS = 25.0
COMMAND_TIMEOUT_SECONDS = 15.0
EDAC_ROOT = Path("/sys/devices/system/edac/mc")

# Deliberately broad; the dashboard decides which lines are real events.
INTERESTING = re.compile(
    r"mce|machine check|hardware error|edac|soft[- ]offlin|hwpoison|memory failure|pcie bus error|\baer\b"
    r"|nvme\d+|blk_update_request|i/o error|synchronize cache|rejecting i/o|detached scsi|\bata\d+(\.\d+)?:"
    r"|mpt3sas|megaraid|cmci|rasdaemon|\bsd [\d:]+: \[sd",
    re.IGNORECASE,
)


def run(*, command: list[str]) -> str | None:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def read_text(*, path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_count(*, path: Path) -> int | None:
    text = read_text(path=path)
    return int(text) if text is not None and text.isdigit() else None


def iso(*, microseconds: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(microseconds) / 1_000_000, timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def collect_edac() -> list[dict[str, Any]] | None:
    if not EDAC_ROOT.is_dir():
        return None
    controllers: list[dict[str, Any]] = []
    for controller in sorted(EDAC_ROOT.glob("mc[0-9]*")):
        dimms = []
        for dimm in sorted(controller.glob("dimm[0-9]*")):
            dimms.append(
                {
                    "label": read_text(path=dimm / "dimm_label"),
                    "corrected": read_count(path=dimm / "dimm_ce_count"),
                    "uncorrected": read_count(path=dimm / "dimm_ue_count"),
                }
            )
        controllers.append(
            {
                "controller": controller.name,
                "corrected": read_count(path=controller / "ce_count"),
                "uncorrected": read_count(path=controller / "ue_count"),
                "dimms": dimms,
            }
        )
    return controllers


def stream_journal(*, matches: list[str], source: str) -> list[dict[str, Any]] | None:
    if shutil.which("journalctl") is None:
        return None
    command = ["journalctl", "--no-pager", "-o", "json", "--output-fields=MESSAGE,_BOOT_ID", "--since", LOOKBACK, *matches]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, text=True, errors="replace")
    except OSError:
        return None
    assert process.stdout is not None
    kept: collections.deque[dict[str, Any]] = collections.deque(maxlen=MAX_EVENTS)
    deadline = time.monotonic() + JOURNAL_DEADLINE_SECONDS
    for line in process.stdout:
        if time.monotonic() > deadline:
            process.kill()
            break
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("MESSAGE")
        if not isinstance(message, str) or not INTERESTING.search(message):
            continue
        timestamp = iso(microseconds=entry.get("__REALTIME_TIMESTAMP"))
        if timestamp is None:
            continue
        kept.append({"timestamp": timestamp, "boot_id": str(entry.get("_BOOT_ID", "")), "source": source, "message": message[:MAX_MESSAGE_CHARS]})
    process.stdout.close()
    return list(kept) if process.wait() == 0 or kept else None


def collect_events() -> list[dict[str, Any]] | None:
    kernel = stream_journal(matches=["_TRANSPORT=kernel"], source="kernel")
    rasdaemon = stream_journal(matches=["SYSLOG_IDENTIFIER=rasdaemon"], source="rasdaemon")
    if kernel is None and rasdaemon is None:
        return None
    return sorted([*(kernel or []), *(rasdaemon or [])], key=lambda event: event["timestamp"])[-MAX_EVENTS:]


def collect_boots() -> list[dict[str, Any]]:
    output = run(command=["journalctl", "--list-boots", "--no-pager", "-o", "json"]) if shutil.which("journalctl") else None
    try:
        rows = json.loads(output) if output else []
    except ValueError:
        return []
    return [
        {
            "boot_id": str(row.get("boot_id", "")),
            "first_seen": iso(microseconds=row.get("first_entry")),
            "last_seen": iso(microseconds=row.get("last_entry")),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def collect_ras_summary() -> str | None:
    return run(command=["ras-mc-ctl", "--summary"]) if shutil.which("ras-mc-ctl") else None


def main() -> None:
    uptime_text = (read_text(path=Path("/proc/uptime")) or "").split()
    document = {
        "now": datetime.now(timezone.utc).isoformat(),
        "boot_id": (read_text(path=Path("/proc/sys/kernel/random/boot_id")) or "").replace("-", ""),
        "uptime_seconds": float(uptime_text[0]) if uptime_text else None,
        "edac": collect_edac(),
        "events": collect_events(),
        "boots": collect_boots(),
        "ras_summary": collect_ras_summary(),
    }
    print(json.dumps(document))


if __name__ == "__main__":
    main()
