import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Dict, Final, List, Optional, Tuple

from homelab_dashboard.models import (
    BootRecord,
    ErrorCategory,
    ErrorClass,
    ErrorIncident,
    HardwareErrors,
    HealthLevel,
    MemoryCounter,
    RawEvent,
)
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.json_values import as_integer, as_number, as_text

# Events at one location this many times, or on more than one boot, count as recurring rather than isolated.
RECURRENCE_THRESHOLD: Final[int] = 3
RAW_EVENTS_PER_INCIDENT: Final[int] = 10
PAGE_SHIFT: Final[int] = 12

_SEVERITY: Final[Tuple[HealthLevel, ...]] = (HealthLevel.OK, HealthLevel.UNKNOWN, HealthLevel.WARNING, HealthLevel.CRITICAL)
_RECURRENCE_FIELDS: Final[Tuple[Tuple[str, str], ...]] = (
    ("dimm", "DIMM"),
    ("address", "address"),
    ("page_frame", "page frame"),
    ("cpu", "CPU"),
    ("bank", "bank"),
    ("status", "status"),
    ("device", "device"),
)

_HEX: Final[str] = r"(0x[0-9a-fA-F]+)"
_EDAC: Final["re.Pattern[str]"] = re.compile(r"EDAC MC(?P<mc>\d+): (?P<n>\d+) (?P<kind>CE|UE) .*?(?: on (?P<label>\S+))? \((?P<detail>[^)]*)\)")
_DIMM_LABEL: Final["re.Pattern[str]"] = re.compile(r"(CPU_SrcID#\d+_Ha#\d+_Chan#\d+_DIMM#\d+)")
_ADDRESS: Final["re.Pattern[str]"] = re.compile(r"(?:location:|\baddr(?:ess)?[ :=])\s*" + _HEX, re.IGNORECASE)
_PAGE: Final["re.Pattern[str]"] = re.compile(r"\bpage:" + _HEX)
_OFFSET: Final["re.Pattern[str]"] = re.compile(r"\boffset:" + _HEX)
_SOFT_OFFLINE: Final["re.Pattern[str]"] = re.compile(r"soft[- ]offlin\w*.*?pfn:?\s*" + _HEX, re.IGNORECASE)
_HWPOISON: Final["re.Pattern[str]"] = re.compile(r"Memory failure:\s*" + _HEX + ":", re.IGNORECASE)
_KERNEL_MCE: Final["re.Pattern[str]"] = re.compile(r"CPU (\d+): Machine Check(?: Exception)?: \w+ Bank (\d+): ([0-9a-fA-F]+)")
_CPU: Final["re.Pattern[str]"] = re.compile(r"\bcpu[= ](\d+)", re.IGNORECASE)
_SOCKET: Final["re.Pattern[str]"] = re.compile(r"\bsocket(?:id)?[=:](\d+)", re.IGNORECASE)
_BANK: Final["re.Pattern[str]"] = re.compile(r"\bbank[= ](\d+)", re.IGNORECASE)
_STATUS: Final["re.Pattern[str]"] = re.compile(r"\bstatus=(?:0x)?([0-9a-fA-F]{8,16})\b")
_PCIE: Final["re.Pattern[str]"] = re.compile(r"PCIe Bus Error: severity=(?P<severity>\w+(?: \([\w-]+\))?)")
_BDF: Final["re.Pattern[str]"] = re.compile(r"\b([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.\d)\b")
_STORAGE: Final[Tuple["re.Pattern[str]", ...]] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"nvme\d+.*(?:I/O \d+ .*timeout|controller is down|Removing after probe failure|reset controller|disabling device|device not ready)",
        r"blk_update_request: I/O error, dev \w+",
        r"\[sd\w+\].*(?:Synchronize Cache.*failed|FAILED Result|rejecting I/O)",
        r"\bata\d+(?:\.\d+)?: .*(?:failed command|exception|hard resetting link|SError|device offline|disabled)",
        r"(?:mpt3sas|megaraid).*(?:fault|removing|reset)",
    )
)
_STORAGE_DEVICE: Final["re.Pattern[str]"] = re.compile(r"\b(nvme\d+(?:n\d+)?|sd[a-z]+|ata\d+)\b")
_RAS_SUMMARY_ROW: Final["re.Pattern[str]"] = re.compile(r"(Corrected|Uncorrected) on .*?errors:\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True, kw_only=True)
class _Event:
    timestamp: datetime
    raw: RawEvent
    category: ErrorCategory
    classification: ErrorClass
    key: str
    attrs: Dict[str, str]


def _classification(*, text: str) -> ErrorClass:
    lowered: str = text.casefold()
    if re.search(r"uncorrect|\bue\b|fatal", lowered):
        return ErrorClass.UNCORRECTED
    if re.search(r"corrected|\bce\b", lowered):
        return ErrorClass.CORRECTED
    return ErrorClass.UNSPECIFIED


def _hex(*, text: str) -> str:
    return hex(int(text, 16))


def _first(*, pattern: "re.Pattern[str]", text: str) -> Optional[str]:
    found: Optional["re.Match[str]"] = pattern.search(text)
    return None if found is None else found.group(1)


def _memory_attrs(*, text: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    edac: Optional["re.Match[str]"] = _EDAC.search(text)
    label: Optional[str] = None if edac is None else edac.group("label")
    label = label or _first(pattern=_DIMM_LABEL, text=text)
    if label is not None:
        attrs["dimm"] = label
    if edac is not None:
        attrs["controller"] = f"mc{edac.group('mc')}"
    address: Optional[str] = _first(pattern=_ADDRESS, text=text)
    page: Optional[str] = _first(pattern=_PAGE, text=text)
    offset: Optional[str] = _first(pattern=_OFFSET, text=text)
    if address is None and page is not None and offset is not None:
        address = hex((int(page, 16) << PAGE_SHIFT) | int(offset, 16))
    if address is not None:
        attrs["address"] = _hex(text=address)
        page = hex(int(address, 16) >> PAGE_SHIFT)
    if page is not None:
        attrs["page_frame"] = _hex(text=page)
    return attrs


def _cpu_attrs(*, text: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    kernel: Optional["re.Match[str]"] = _KERNEL_MCE.search(text)
    if kernel is not None:
        attrs.update(cpu=kernel.group(1), bank=kernel.group(2), status="0x" + kernel.group(3).lower())
    for name, pattern in (("cpu", _CPU), ("socket", _SOCKET), ("bank", _BANK)):
        value: Optional[str] = _first(pattern=pattern, text=text)
        if value is not None:
            attrs.setdefault(name, value)
    status: Optional[str] = _first(pattern=_STATUS, text=text)
    if status is not None:
        attrs.setdefault("status", "0x" + status.lower())
    if "parity" in text.casefold():
        attrs["type"] = "internal parity error" if "internal parity" in text.casefold() else "parity error"
    return attrs


def _interpret(*, text: str, source: str) -> Optional[Tuple[ErrorCategory, ErrorClass, str, Dict[str, str]]]:
    """Maps one log line to (category, classification, grouping key, decoded fields); None for unrelated lines."""
    lowered: str = text.casefold()
    soft: Optional["re.Match[str]"] = _SOFT_OFFLINE.search(text) or _HWPOISON.search(text)
    if soft is not None:
        frame: str = _hex(text=soft.group(1))
        return ErrorCategory.PAGE_OFFLINE, ErrorClass.UNSPECIFIED, frame, {"page_frame": frame}
    if _EDAC.search(text) or (source == "rasdaemon" and ("dimm" in lowered or "memory" in lowered)):
        attrs: Dict[str, str] = _memory_attrs(text=text)
        classification: ErrorClass = _classification(text=text)
        return ErrorCategory.ECC_MEMORY, classification, attrs.get("dimm", "unattributed"), attrs
    mce_event: bool = bool(_KERNEL_MCE.search(text)) or "machine check events logged" in lowered or "cmci" in lowered
    if mce_event or (source == "rasdaemon" and ("bank" in lowered or "mce" in lowered)):
        attrs = _cpu_attrs(text=text)
        if "cmci" in lowered:
            attrs["note"] = "CMCI storm"
        classification = ErrorClass.UNCORRECTED if "machine check exception" in lowered else _classification(text=text)
        location: str = f"cpu {attrs['cpu']} bank {attrs['bank']}" if "cpu" in attrs and "bank" in attrs else "unattributed"
        return ErrorCategory.CPU_MCE, classification, location, attrs
    pcie: Optional["re.Match[str]"] = _PCIE.search(text)
    if pcie is not None:
        attrs = {}
        device: Optional[str] = _first(pattern=_BDF, text=text)
        if device is not None:
            attrs["device"] = device
        attrs["severity"] = pcie.group("severity")
        return ErrorCategory.PCIE, _classification(text=pcie.group("severity")), attrs.get("device", "unattributed"), attrs
    if any(pattern.search(text) for pattern in _STORAGE):
        found: Optional[str] = _first(pattern=_STORAGE_DEVICE, text=text)
        return ErrorCategory.STORAGE_PATH, ErrorClass.UNSPECIFIED, found or "unattributed", ({"device": found} if found else {})
    return None


def _parse_time(*, value: object) -> Optional[datetime]:
    text: Optional[str] = as_text(value=value)
    if text is None:
        return None
    try:
        parsed: datetime = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _parse_event(*, row: object) -> Optional[_Event]:
    if not isinstance(row, Mapping):
        return None
    timestamp: Optional[datetime] = _parse_time(value=row.get("timestamp"))
    message: Optional[str] = as_text(value=row.get("message"))
    if timestamp is None or message is None:
        return None
    source: str = as_text(value=row.get("source")) or "kernel"
    interpreted: Optional[Tuple[ErrorCategory, ErrorClass, str, Dict[str, str]]] = _interpret(text=message, source=source)
    if interpreted is None:
        return None
    category, classification, key, attrs = interpreted
    raw: RawEvent = RawEvent(timestamp=timestamp.isoformat(), boot_id=as_text(value=row.get("boot_id")) or "", source=source, message=message)
    return _Event(timestamp=timestamp, raw=raw, category=category, classification=classification, key=key, attrs=attrs)


def _top(*, events: List[_Event], name: str) -> Optional[Tuple[str, int]]:
    values: Counter[str] = Counter(event.attrs[name] for event in events if name in event.attrs)
    common: List[Tuple[str, int]] = values.most_common(1)
    return common[0] if common else None


def _title(*, category: ErrorCategory, classification: ErrorClass, events: List[_Event]) -> str:
    count: int = len(events)
    lead: str = "repeated " if count >= RECURRENCE_THRESHOLD else ""
    kind: str = "" if classification is ErrorClass.UNSPECIFIED else f"{classification.value} "
    noun: str = "errors" if count > 1 else "error"

    def top(name: str) -> Optional[Tuple[str, int]]:
        return _top(events=events, name=name)

    text: str
    if category is ErrorCategory.ECC_MEMORY:
        address, page, dimm = top("address"), top("page_frame"), top("dimm")
        where: str = f" ({dimm[0]})" if dimm else ""
        if address and address[1] >= 2:
            text = f"{lead}{kind}ECC {noun} at the same memory location{where}, address {address[0]}"
        elif page and page[1] >= 2:
            text = f"{lead}{kind}ECC {noun} in the same memory page {page[0]}{where}"
        else:
            text = f"{lead}{kind}ECC memory {noun}{' on ' + dimm[0] if dimm else ''}"
    elif category is ErrorCategory.CPU_MCE:
        cpu, bank, type_ = top("cpu"), top("bank"), top("type")
        subject: str = f"{type_[0]}s" if type_ else "machine-check events"
        if type_ and count == 1:
            subject = type_[0]
        where = f" reported on CPU {cpu[0]}" if cpu else ""
        where += f" (bank {bank[0]})" if bank else ""
        note: Optional[Tuple[str, int]] = top("note")
        text = f"{lead}{kind}{subject}{where}" if cpu or not note else f"{note[0]} reported by the CPU machine-check subsystem"
    elif category is ErrorCategory.PAGE_OFFLINE:
        frame: Optional[Tuple[str, int]] = top("page_frame")
        text = f"Kernel soft-offlined memory page {frame[0] if frame else ''} (page retirement is containment, not a repair)".replace("  ", " ")
    elif category is ErrorCategory.PCIE:
        device: Optional[Tuple[str, int]] = top("device")
        text = f"{lead}{kind}PCIe bus {noun}{' on ' + device[0] if device else ''}"
    else:
        device = top("device")
        text = f"{lead}storage-path {noun}{' involving ' + device[0] if device else ''}"
    return text[:1].upper() + text[1:]


def _incident_level(*, classification: ErrorClass, count: int, boots_seen: int, current: bool) -> HealthLevel:
    recurring: bool = count >= RECURRENCE_THRESHOLD or boots_seen >= 2
    level: HealthLevel = HealthLevel.CRITICAL if classification is ErrorClass.UNCORRECTED or recurring else HealthLevel.WARNING
    # An earlier boot is history; it should be visible but must not mark the node as failing now.
    return level if current else min(level, HealthLevel.WARNING, key=_SEVERITY.index)


def _build_incident(*, events: List[_Event], boots_seen: int, current_boot: str, now: datetime) -> ErrorIncident:
    first: _Event = events[0]
    boot_id: str = first.raw.boot_id
    current: bool = boot_id == current_boot
    recurrence: List[str] = []
    fields: List[Tuple[str, str]] = []
    for name, label in _RECURRENCE_FIELDS:
        common: Optional[Tuple[str, int]] = _top(events=events, name=name)
        if common is not None:
            fields.append((name, common[0]))
            if common[1] >= 2:
                recurrence.append(f"same {label} {common[0]} ×{common[1]}")
    for name in ("controller", "socket", "severity", "type", "note"):
        extra: Optional[Tuple[str, int]] = _top(events=events, name=name)
        if extra is not None:
            fields.append((name, extra[0]))
    if boots_seen >= 2:
        recurrence.append(f"seen on {boots_seen} boots")
    return ErrorIncident(
        category=first.category,
        classification=first.classification,
        title=_title(category=first.category, classification=first.classification, events=events),
        level=_incident_level(classification=first.classification, count=len(events), boots_seen=boots_seen, current=current),
        count=len(events),
        first_seen=events[0].timestamp.isoformat(),
        last_seen=events[-1].timestamp.isoformat(),
        last_hour=sum(1 for event in events if event.timestamp >= now - timedelta(hours=1)),
        last_day=sum(1 for event in events if event.timestamp >= now - timedelta(days=1)),
        boot_id=boot_id,
        current_boot=current,
        boots_seen=boots_seen,
        recurrence=tuple(recurrence),
        fields=tuple(fields),
        raw=tuple(event.raw for event in events[-RAW_EVENTS_PER_INCIDENT:]),
    )


def _build_incidents(*, events: List[_Event], current_boot: str, now: datetime) -> Tuple[ErrorIncident, ...]:
    by_location: Dict[Tuple[ErrorCategory, ErrorClass, str], List[_Event]] = {}
    for event in events:
        by_location.setdefault((event.category, event.classification, event.key), []).append(event)
    incidents: List[ErrorIncident] = []
    for group in by_location.values():
        boots: Dict[str, List[_Event]] = {}
        for event in group:
            boots.setdefault(event.raw.boot_id, []).append(event)
        for boot_events in boots.values():
            incidents.append(_build_incident(events=boot_events, boots_seen=len(boots), current_boot=current_boot, now=now))
    return tuple(sorted(incidents, key=lambda incident: incident.last_seen, reverse=True))


def _counter_rows(*, rows: object) -> Optional[Tuple[MemoryCounter, ...]]:
    if not isinstance(rows, list):
        return None
    counters: List[MemoryCounter] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        controller: str = as_text(value=row.get("controller")) or "mc?"
        dimms: object = row.get("dimms")
        dimm_rows: List[object] = dimms if isinstance(dimms, list) else []
        for dimm in dimm_rows:
            if isinstance(dimm, Mapping):
                counters.append(
                    MemoryCounter(
                        controller=controller,
                        label=as_text(value=dimm.get("label")),
                        corrected=as_integer(value=dimm.get("corrected")) or 0,
                        uncorrected=as_integer(value=dimm.get("uncorrected")) or 0,
                    )
                )
        if not dimm_rows:
            counters.append(MemoryCounter(controller=controller, label=None, corrected=as_integer(value=row.get("corrected")) or 0, uncorrected=as_integer(value=row.get("uncorrected")) or 0))
    return tuple(counters)


def _ras_summary(*, text: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """(corrected, uncorrected, MCE records) persisted by rasdaemon across reboots; all None if it is not installed."""
    if text is None:
        return None, None, None
    totals: Dict[str, int] = {"corrected": 0, "uncorrected": 0}
    for found in _RAS_SUMMARY_ROW.finditer(text):
        totals[found.group(1).casefold()] += int(found.group(2))
    mce: int = 0
    in_mce: bool = False
    for line in text.splitlines():
        if line.strip().casefold().startswith("mce records summary"):
            in_mce = True
        elif in_mce and (row := re.match(r"\s*(\d+)\s+\S", line)):
            mce += int(row.group(1))
    return totals["corrected"], totals["uncorrected"], mce


def _boot_records(*, rows: object, current_boot: str, boot_started: Optional[datetime], now: datetime) -> Tuple[BootRecord, ...]:
    records: List[BootRecord] = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, Mapping) and (boot_id := as_text(value=row.get("boot_id"))):
            records.append(BootRecord(boot_id=boot_id, first_seen=as_text(value=row.get("first_seen")), last_seen=as_text(value=row.get("last_seen")), current=boot_id == current_boot))
    if current_boot and not any(record.current for record in records):
        started: Optional[str] = None if boot_started is None else boot_started.isoformat()
        records.append(BootRecord(boot_id=current_boot, first_seen=started, last_seen=now.isoformat(), current=True))
    return tuple(records)


def _summarize(*, incidents: Tuple[ErrorIncident, ...], counters: Optional[Tuple[MemoryCounter, ...]], persisted_uncorrected: Optional[int], persisted_corrected: Optional[int]) -> Tuple[HealthLevel, Tuple[str, ...]]:
    findings: List[Tuple[HealthLevel, str]] = []
    corrected: int = sum(counter.corrected for counter in counters or ())
    uncorrected: int = sum(counter.uncorrected for counter in counters or ())
    if uncorrected:
        findings.append((HealthLevel.CRITICAL, f"{uncorrected} uncorrected ECC errors since boot"))
    if corrected:
        findings.append((HealthLevel.WARNING, f"{corrected} corrected ECC errors since boot"))
    if persisted_uncorrected:
        findings.append((HealthLevel.WARNING, f"rasdaemon has recorded {persisted_uncorrected} uncorrected memory errors in total"))
    elif persisted_corrected:
        findings.append((HealthLevel.WARNING, f"rasdaemon has recorded {persisted_corrected} corrected memory errors in total"))
    for incident in incidents:
        if incident.current_boot and incident.level is not HealthLevel.OK:
            suffix: str = f", {incident.last_hour} in the last hour" if incident.last_hour else ""
            findings.append((incident.level, f"{incident.title} ({incident.count} this boot{suffix})"))
    earlier: int = sum(1 for incident in incidents if not incident.current_boot)
    if earlier:
        findings.append((HealthLevel.WARNING, f"{earlier} incident{'s' if earlier != 1 else ''} on earlier boots (historical)"))
    ordered: List[Tuple[HealthLevel, str]] = sorted(findings, key=lambda finding: _SEVERITY.index(finding[0]), reverse=True)
    level: HealthLevel = max([HealthLevel.OK, *(level for level, _ in ordered)], key=_SEVERITY.index)
    return level, tuple(text for _, text in ordered)


def parse_hardware_errors(*, document: object) -> HardwareErrors:
    if not isinstance(document, Mapping):
        raise StatusSourceError("The hardware error probe returned an unexpected response.")
    now: datetime = _parse_time(value=document.get("now")) or datetime.now(UTC)
    current_boot: str = as_text(value=document.get("boot_id")) or ""
    uptime: Optional[float] = as_number(value=document.get("uptime_seconds"))
    boot_started: Optional[datetime] = None if uptime is None else now - timedelta(seconds=uptime)
    event_rows: object = document.get("events")
    events: List[_Event] = sorted(
        (event for event in (_parse_event(row=row) for row in (event_rows if isinstance(event_rows, list) else [])) if event is not None),
        key=lambda event: event.timestamp,
    )
    incidents: Tuple[ErrorIncident, ...] = _build_incidents(events=events, current_boot=current_boot, now=now)
    counters: Optional[Tuple[MemoryCounter, ...]] = _counter_rows(rows=document.get("edac"))
    persisted_corrected, persisted_uncorrected, persisted_mce = _ras_summary(text=as_text(value=document.get("ras_summary")))
    level, findings = _summarize(incidents=incidents, counters=counters, persisted_uncorrected=persisted_uncorrected, persisted_corrected=persisted_corrected)
    journal_available: bool = isinstance(event_rows, list)
    if counters is None and not journal_available and persisted_corrected is None:
        level, findings = HealthLevel.UNKNOWN, ("No hardware error source could be read on this node",)
    return HardwareErrors(
        level=level,
        findings=findings,
        incidents=incidents,
        boots=_boot_records(rows=document.get("boots"), current_boot=current_boot, boot_started=boot_started, now=now),
        memory_counters=counters or (),
        edac_available=counters is not None,
        journal_available=journal_available,
        persisted_corrected=persisted_corrected,
        persisted_uncorrected=persisted_uncorrected,
        persisted_mce=persisted_mce,
        boot_id=current_boot or None,
        boot_started=None if boot_started is None else boot_started.isoformat(),
        collected_at=now.isoformat(),
        last_success=now.isoformat(),
    )
