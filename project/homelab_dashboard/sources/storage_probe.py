"""Runs on a Proxmox node (python3, standard library only) and prints raw SMART and zpool readings as JSON.

The dashboard sends this file over SSH on stdin, so it must not import anything from this project.
Judging what is abnormal happens on the dashboard side; this script only reports.
"""

import json
import shutil
import subprocess
from typing import Any

# `-n standby` makes smartctl skip a spun-down disk instead of waking it.
SMARTCTL_TIMEOUT_SECONDS = 20.0
ZPOOL_TIMEOUT_SECONDS = 15.0
NVME_FIELDS = ("critical_warning", "available_spare", "available_spare_threshold", "percentage_used", "media_errors")


def run(*, command: list[str], timeout: float) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return completed.stdout


def run_json(*, command: list[str]) -> dict[str, Any] | None:
    # smartctl exits non-zero to flag SMART findings while still printing valid JSON, so ignore the exit status.
    try:
        document = json.loads(run(command=command, timeout=SMARTCTL_TIMEOUT_SECONDS))
    except ValueError:
        return None
    return document if isinstance(document, dict) else None


def describe_disk(*, name: str, report: dict[str, Any] | None) -> dict[str, Any]:
    if report is None:
        return {"device": name, "read_failed": True}
    messages = " ".join(str(message.get("string", "")) for message in report.get("smartctl", {}).get("messages", []))
    nvme = report.get("nvme_smart_health_information_log", {})
    attributes = [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "value": row.get("value"),
            "thresh": row.get("thresh"),
            "raw": row.get("raw", {}).get("value"),
            "when_failed": row.get("when_failed"),
        }
        for row in report.get("ata_smart_attributes", {}).get("table", [])
    ]
    temperature = report.get("temperature", {}).get("current")
    return {
        "device": name,
        "model": report.get("model_name"),
        "serial": report.get("serial_number"),
        "protocol": report.get("device", {}).get("protocol"),
        "rotation_rate": report.get("rotation_rate"),
        "standby": "STANDBY" in messages.upper(),
        "read_failed": "model_name" not in report and "STANDBY" not in messages.upper(),
        "smart_passed": report.get("smart_status", {}).get("passed"),
        "temperature": temperature if temperature is not None else nvme.get("temperature"),
        "power_on_hours": report.get("power_on_time", {}).get("hours"),
        "attributes": attributes,
        "nvme": {field: nvme.get(field) for field in NVME_FIELDS},
    }


def collect_disks() -> list[dict[str, Any]] | None:
    if shutil.which("smartctl") is None:
        return None
    scan = run_json(command=["smartctl", "--scan", "-j"]) or {}
    disks: list[dict[str, Any]] = []
    for entry in scan.get("devices", []):
        name = entry.get("name")
        if not isinstance(name, str):
            continue
        command = ["smartctl", "-a", "-j", "-n", "standby", name]
        # Forcing `-d scsi` on a SATA disk behind an HBA hides its ATA data; auto-detection handles it.
        if isinstance(entry.get("type"), str) and entry["type"] != "scsi":
            command[1:1] = ["-d", entry["type"]]
        disks.append(describe_disk(name=name, report=run_json(command=command)))
    return disks


def collect_pools() -> list[dict[str, Any]] | None:
    if shutil.which("zpool") is None:
        return None
    listing = run(command=["zpool", "list", "-Hp", "-o", "name,health,capacity,size,allocated,free,fragmentation"], timeout=ZPOOL_TIMEOUT_SECONDS)
    pools: list[dict[str, Any]] = []
    for line in listing.splitlines():
        fields = line.split("\t")
        if len(fields) != 7:
            continue
        name, health, capacity, size, allocated, free, fragmentation = fields
        status = run(command=["zpool", "status", "-p", name], timeout=ZPOOL_TIMEOUT_SECONDS)
        dataset = run(command=["zfs", "get", "-Hp", "-d", "0", "-o", "name,value", "available", name], timeout=ZPOOL_TIMEOUT_SECONDS)
        dataset_available = next(
            (int(value) for line in dataset.splitlines() if len((row := line.split("\t"))) == 2 and row[0] == name and (value := row[1]).isdigit()),
            None,
        )
        pools.append(
            {
                "name": name,
                "health": health,
                "capacity": capacity,
                "size": size,
                "dataset_available": dataset_available,
                "allocated": allocated,
                "free": free,
                "fragmentation": fragmentation,
                "status": status,
            }
        )
    return pools


def main() -> None:
    print(json.dumps({"disks": collect_disks(), "pools": collect_pools()}))


if __name__ == "__main__":
    main()
