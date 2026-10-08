import re
from collections.abc import Mapping
from typing import Final, List, Optional, Tuple

from homelab_dashboard.models import Disk, HealthLevel, Pool, Storage
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.json_values import as_integer, as_text

# (warning, critical) in degrees Celsius; spinning disks are rated far lower than flash.
HDD_TEMPERATURE_LIMITS: Final[Tuple[int, int]] = (45, 50)
SOLID_STATE_TEMPERATURE_LIMITS: Final[Tuple[int, int]] = (70, 80)
POOL_CAPACITY_LIMITS: Final[Tuple[int, int]] = (80, 90)
NVME_WEAR_WARNING_PERCENT: Final[int] = 90

# ATA attributes whose raw count should be zero on a healthy disk.
ATA_ZERO_EXPECTED: Final[Tuple[int, ...]] = (5, 10, 184, 187, 196, 197, 198, 199)

_SEVERITY: Final[Tuple[HealthLevel, ...]] = (HealthLevel.OK, HealthLevel.UNKNOWN, HealthLevel.WARNING, HealthLevel.CRITICAL)
_Finding = Tuple[HealthLevel, str]
# AVAIL (idle spare) and INUSE are intentionally excluded; they are not problems.
_DEVICE_STATES: Final[Tuple[str, ...]] = ("ONLINE", "DEGRADED", "FAULTED", "OFFLINE", "UNAVAIL", "REMOVED")


def _worst(*, findings: List[_Finding], base: HealthLevel = HealthLevel.OK) -> HealthLevel:
    return max([base, *(level for level, _ in findings)], key=_SEVERITY.index)


def _disk_kind(*, protocol: Optional[str], rotation_rate: Optional[int]) -> str:
    if protocol is not None and protocol.casefold() == "nvme":
        return "nvme"
    return "ssd" if rotation_rate == 0 else "hdd"


def _temperature_finding(*, kind: str, celsius: int) -> Optional[_Finding]:
    warning, critical = HDD_TEMPERATURE_LIMITS if kind == "hdd" else SOLID_STATE_TEMPERATURE_LIMITS
    if celsius >= critical:
        return HealthLevel.CRITICAL, f"Temperature {celsius} °C (critical at {critical} °C)"
    if celsius >= warning:
        return HealthLevel.WARNING, f"Temperature {celsius} °C (warning at {warning} °C)"
    return None


def _attribute_findings(*, rows: object) -> List[_Finding]:
    findings: List[_Finding] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        name: str = as_text(value=row.get("name")) or f"Attribute {row.get('id')}"
        value: Optional[int] = as_integer(value=row.get("value"))
        threshold: Optional[int] = as_integer(value=row.get("thresh"))
        raw: Optional[int] = as_integer(value=row.get("raw"))
        failed: str = as_text(value=row.get("when_failed")) or ""
        if failed.casefold() == "failing_now" or (value is not None and threshold and value <= threshold):
            detail: str = f"normalized {value} at or below threshold {threshold}" if value is not None else "failing now"
            findings.append((HealthLevel.CRITICAL, f"{name}: {detail}"))
        elif failed:
            findings.append((HealthLevel.WARNING, f"{name} failed in the past"))
        elif as_integer(value=row.get("id")) in ATA_ZERO_EXPECTED and raw:
            findings.append((HealthLevel.WARNING, f"{name}: {raw}"))
    return findings


def _nvme_findings(*, log: object) -> List[_Finding]:
    if not isinstance(log, Mapping):
        return []
    findings: List[_Finding] = []
    warning_flags: Optional[int] = as_integer(value=log.get("critical_warning"))
    spare: Optional[int] = as_integer(value=log.get("available_spare"))
    spare_floor: Optional[int] = as_integer(value=log.get("available_spare_threshold"))
    used: Optional[int] = as_integer(value=log.get("percentage_used"))
    media_errors: Optional[int] = as_integer(value=log.get("media_errors"))
    if warning_flags:
        findings.append((HealthLevel.CRITICAL, f"NVMe critical warning flags 0x{warning_flags:02x}"))
    if spare is not None and spare_floor is not None and spare < spare_floor:
        findings.append((HealthLevel.CRITICAL, f"Available spare {spare}% below threshold {spare_floor}%"))
    if used is not None and used >= NVME_WEAR_WARNING_PERCENT:
        findings.append((HealthLevel.WARNING, f"{used}% of rated endurance used"))
    if media_errors:
        findings.append((HealthLevel.WARNING, f"{media_errors} media errors"))
    return findings


def _parse_disk(*, row: object) -> Optional[Disk]:
    if not isinstance(row, Mapping):
        return None
    device: Optional[str] = as_text(value=row.get("device"))
    if device is None:
        return None
    model: Optional[str] = as_text(value=row.get("model"))
    serial: Optional[str] = as_text(value=row.get("serial"))
    if row.get("read_failed") is True:
        return Disk(device=device, model=model, serial=serial, kind="hdd", level=HealthLevel.UNKNOWN, findings=("SMART data could not be read",))
    kind: str = _disk_kind(protocol=as_text(value=row.get("protocol")), rotation_rate=as_integer(value=row.get("rotation_rate")))
    if row.get("standby") is True:
        return Disk(device=device, model=model, serial=serial, kind=kind, level=HealthLevel.OK, standby=True)
    findings: List[_Finding] = []
    if row.get("smart_passed") is False:
        findings.append((HealthLevel.CRITICAL, "SMART overall health check failed"))
    temperature: Optional[int] = as_integer(value=row.get("temperature"))
    hot: Optional[_Finding] = None if temperature is None else _temperature_finding(kind=kind, celsius=temperature)
    if hot is not None:
        findings.append(hot)
    findings.extend(_attribute_findings(rows=row.get("attributes")))
    findings.extend(_nvme_findings(log=row.get("nvme")))
    return Disk(
        device=device,
        model=model,
        serial=serial,
        kind=kind,
        level=_worst(findings=findings),
        temperature_celsius=temperature,
        power_on_hours=as_integer(value=row.get("power_on_hours")),
        findings=tuple(text for _, text in sorted(findings, key=lambda finding: _SEVERITY.index(finding[0]), reverse=True)),
    )


def _pool_status_findings(*, name: str, status: str) -> List[_Finding]:
    findings: List[_Finding] = []
    for line in status.splitlines():
        fields: List[str] = line.split()
        # The pool's own row in the config table: NAME STATE READ WRITE CKSUM.
        if len(fields) == 5 and fields[0] == name and fields[2:] != ["0", "0", "0"]:
            findings.append((HealthLevel.WARNING, f"Device errors on pool: read {fields[2]}, write {fields[3]}, checksum {fields[4]}"))
        if len(fields) >= 5 and fields[0] != name and fields[1] in _DEVICE_STATES:
            detail: str = " ".join(fields[5:])
            suffix: str = f" ({detail})" if detail else ""
            if fields[1] != "ONLINE":
                level: HealthLevel = HealthLevel.WARNING if fields[1] == "DEGRADED" else HealthLevel.CRITICAL
                findings.append((level, f"Device {fields[0]} is {fields[1]}{suffix}"))
            elif fields[2:5] != ["0", "0", "0"]:
                findings.append((HealthLevel.WARNING, f"Device {fields[0]} errors: read {fields[2]}, write {fields[3]}, checksum {fields[4]}"))
        if line.strip().startswith("errors:") and "No known data errors" not in line:
            findings.append((HealthLevel.CRITICAL, line.strip().removeprefix("errors:").strip().capitalize()))
        if "resilver in progress" in line:
            findings.append((HealthLevel.WARNING, "Resilver in progress"))
        scrub: Optional["re.Match[str]"] = re.search(r"with (\d+) errors", line)
        if line.strip().startswith("scan:") and scrub is not None and int(scrub.group(1)) > 0:
            findings.append((HealthLevel.WARNING, f"Last scrub found {scrub.group(1)} errors"))
    return findings


def _pool_layout(*, name: str, status: str) -> Optional[str]:
    """Summarises the top-level vdevs, e.g. "2 × raidz1 (6 disks)"."""
    groups: List[Tuple[str, int]] = []
    pool_indent: Optional[int] = None
    for line in status.splitlines():
        fields: List[str] = line.split()
        indent: int = len(line) - len(line.lstrip())
        if len(fields) >= 2 and fields[0] == name and fields[1] in _DEVICE_STATES:
            pool_indent = indent
        elif pool_indent is None:
            continue
        elif not fields or fields[0] in {"errors:", "logs", "cache", "spares", "special", "dedup"}:
            break
        elif indent == pool_indent + 2:
            groups.append((re.sub(r"-\d+$", "", fields[0]), 0))
        elif indent > pool_indent + 2 and groups:
            groups[-1] = (groups[-1][0], groups[-1][1] + 1)
    if not groups:
        return None
    kinds: dict[str, List[int]] = {}
    for kind, disks in groups:
        kinds.setdefault(kind, []).append(disks)
    parts: List[str] = []
    for kind, counts in kinds.items():
        is_group: bool = counts[0] > 0
        parts.append(f"{len(counts)} × {kind} ({counts[0]} disks)" if is_group else f"{len(counts)} × disk (stripe)")
    return ", ".join(parts)


def _pool_scan(*, status: str) -> Optional[str]:
    """Shortens the scan line to e.g. "resilver Oct 8"."""
    for line in status.splitlines():
        if not line.strip().startswith("scan:"):
            continue
        kind: Optional["re.Match[str]"] = re.search(r"\b(scrub|resilver)", line)
        if kind is None:
            return None
        label: str = kind.group(1).capitalize()
        if "in progress" in line:
            return f"{label} running"
        when: Optional["re.Match[str]"] = re.search(r"\b(?:on|since) \w{3} (\w{3})\s+(\d+)", line)
        return label if when is None else f"{label} {when.group(1)} {when.group(2)}"
    return None


def _as_count(*, value: object) -> Optional[int]:
    text: Optional[str] = as_text(value=value)
    return int(text) if text is not None and text.isdigit() else as_integer(value=value)


def _parse_pool(*, row: object) -> Optional[Pool]:
    if not isinstance(row, Mapping):
        return None
    name: Optional[str] = as_text(value=row.get("name"))
    health: Optional[str] = as_text(value=row.get("health"))
    if name is None or health is None:
        return None
    capacity_text: str = (as_text(value=row.get("capacity")) or "").rstrip("%")
    capacity: Optional[int] = int(capacity_text) if capacity_text.isdigit() else None
    findings: List[_Finding] = []
    if health != "ONLINE":
        findings.append((HealthLevel.WARNING if health == "DEGRADED" else HealthLevel.CRITICAL, f"Pool is {health}"))
    if capacity is not None and capacity >= POOL_CAPACITY_LIMITS[0]:
        level: HealthLevel = HealthLevel.CRITICAL if capacity >= POOL_CAPACITY_LIMITS[1] else HealthLevel.WARNING
        findings.append((level, f"{capacity}% full"))
    findings.extend(_pool_status_findings(name=name, status=as_text(value=row.get("status")) or ""))
    status_text: str = as_text(value=row.get("status")) or ""
    fragmentation_text: str = (as_text(value=row.get("fragmentation")) or "").rstrip("%")
    return Pool(
        name=name,
        state=health,
        level=_worst(findings=findings),
        capacity_percent=capacity,
        size_bytes=_as_count(value=row.get("size")),
        allocated_bytes=_as_count(value=row.get("allocated")),
        free_bytes=_as_count(value=row.get("free")),
        fragmentation_percent=int(fragmentation_text) if fragmentation_text.isdigit() else None,
        layout=_pool_layout(name=name, status=status_text),
        scan=_pool_scan(status=status_text),
        findings=tuple(text for _, text in sorted(findings, key=lambda finding: _SEVERITY.index(finding[0]), reverse=True)),
    )


def parse_storage(*, document: object) -> Storage:
    if not isinstance(document, Mapping):
        raise StatusSourceError("The storage probe returned an unexpected response.")
    disk_rows: object = document.get("disks")
    pool_rows: object = document.get("pools")
    disks: Tuple[Disk, ...] = tuple(
        disk for disk in (_parse_disk(row=row) for row in (disk_rows if isinstance(disk_rows, list) else [])) if disk is not None
    )
    pools: Tuple[Pool, ...] = tuple(
        pool for pool in (_parse_pool(row=row) for row in (pool_rows if isinstance(pool_rows, list) else [])) if pool is not None
    )
    return Storage(disks=disks, pools=pools, smart_available=isinstance(disk_rows, list), zfs_available=isinstance(pool_rows, list))
