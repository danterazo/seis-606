import ipaddress
import json
import re
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, Optional, Union

from homelab_dashboard.node_profiles import display_name_for
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.mac_manufacturer import MacManufacturerLookup
from homelab_dashboard.sources.proxmox_ssh import SSH_EXECUTABLE, SSH_OPTIONS, CommandRunner, SshTarget, explain_ssh_failure, run_command

LAN_NETWORK: Final[ipaddress.IPv4Network] = ipaddress.IPv4Network("192.168.0.0/16")
ROUTER_LEASES_SEPARATOR: Final[str] = "__HOMELAB_DHCP_LEASES__"
REMOTE_COMMAND: Final[str] = (
    "{ ubus call system board 2>/dev/null || printf '{}'; }; printf '\\n" + ROUTER_LEASES_SEPARATOR + "\\n'; cat /tmp/dhcp.leases"
)


@dataclass(frozen=True, slots=True, kw_only=True)
class DhcpLease:
    address: str
    mac: str
    hostname: Optional[str]
    expires_at: Optional[datetime]

    def to_payload(self, *, manufacturer: Optional[str] = None) -> dict[str, Any]:
        return {
            "address": self.address,
            "mac": self.mac.upper(),
            "manufacturer": manufacturer,
            "hostname": self.hostname,
            "display_name": display_name_for(name=self.hostname) if self.hostname is not None else self.address,
            "network_group": "lan" if ipaddress.IPv4Address(self.address) in LAN_NETWORK else "guest_iot",
            "expires_at": self.expires_at.isoformat(timespec="seconds") if self.expires_at is not None else None,
        }


def parse_leases(*, text: str) -> tuple[DhcpLease, ...]:
    leases: list[DhcpLease] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields: list[str] = line.split()
        if len(fields) != 5:
            raise StatusSourceError("OpenWRT returned an unexpected DHCP lease record.")
        expiry, mac, address, hostname, _client_id = fields
        try:
            seconds: int = int(expiry)
            if seconds < 0 or not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac):
                raise ValueError("Invalid lease")
            parsed_address: ipaddress.IPv4Address = ipaddress.IPv4Address(address)
            expires_at: Optional[datetime] = datetime.fromtimestamp(timestamp=seconds, tz=UTC) if seconds else None
        except (ValueError, OverflowError, OSError) as error:
            raise StatusSourceError("OpenWRT returned an invalid DHCP lease record.") from error
        leases.append(DhcpLease(address=str(parsed_address), mac=mac.lower(), hostname=None if hostname == "*" else hostname, expires_at=expires_at))
    return tuple(leases)


def parse_router_response(*, text: str) -> tuple[Optional[str], tuple[DhcpLease, ...]]:
    board_text, separator, lease_text = text.partition(ROUTER_LEASES_SEPARATOR)
    router_version: Optional[str] = None
    if separator:
        try:
            board: object = json.loads(board_text)
        except json.JSONDecodeError:
            board = None
        if isinstance(board, dict) and isinstance(board.get("release"), dict):
            version: object = board["release"].get("version")
            if isinstance(version, str) and version.strip():
                router_version = version.strip()
    return router_version, parse_leases(text=lease_text if separator else text)


@dataclass(frozen=True, slots=True, kw_only=True)
class Ipv6Record:
    address: str
    interface: str
    identity: str
    mac: Optional[str] = None
    hostname: Optional[str] = None
    expires_at: Optional[datetime] = None


def _mac_address(value: object) -> Optional[str]:
    return value.lower() if isinstance(value, str) and re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", value) else None


def _duid_mac(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        duid: bytes = bytes.fromhex(value.replace(":", ""))
    except ValueError:
        return None
    if (len(duid) == 14 and duid[:4] == b"\x00\x01\x00\x01") or (len(duid) == 10 and duid[:4] == b"\x00\x03\x00\x01"):
        return ":".join(f"{part:02x}" for part in duid[-6:])
    return None


def parse_ipv6_records(*, leases: object, neighbors: object, now: datetime) -> tuple[Ipv6Record, ...]:
    if not isinstance(leases, dict) or not isinstance(leases.get("device"), dict) or not isinstance(neighbors, list):
        raise StatusSourceError("OpenWRT returned an unexpected IPv6 discovery response.")
    records: list[Ipv6Record] = []
    neighbor_macs: dict[tuple[str, str], str] = {}
    for row in neighbors:
        if not isinstance(row, dict) or not isinstance(row.get("dev"), str) or not row["dev"].startswith("br-"):
            continue
        mac: Optional[str] = _mac_address(value=row.get("lladdr"))
        states: object = row.get("state", [])
        if mac is None or not isinstance(states, list) or any(state in ("FAILED", "INCOMPLETE") for state in states):
            continue
        try:
            address: ipaddress.IPv6Address = ipaddress.IPv6Address(row.get("dst", ""))
        except (ValueError, TypeError):
            continue
        if address.is_multicast or address.is_unspecified:
            continue
        neighbor_macs[(row["dev"], str(address))] = mac
        records.append(Ipv6Record(address=str(address), interface=row["dev"], identity=f"mac:{mac}", mac=mac))
    for interface, device in leases["device"].items():
        if not isinstance(interface, str) or not isinstance(device, dict) or not isinstance(device.get("leases"), list):
            continue
        for lease in device["leases"]:
            if not isinstance(lease, dict) or not isinstance(lease.get("ipv6-addr"), list):
                continue
            duid_value: object = lease.get("duid")
            duid_text: Optional[str] = duid_value.casefold() if isinstance(duid_value, str) and duid_value else None
            hostname_value: object = lease.get("hostname")
            hostname: Optional[str] = hostname_value if isinstance(hostname_value, str) and hostname_value not in ("", "*") else None
            for reading in lease["ipv6-addr"]:
                if not isinstance(reading, dict):
                    continue
                lifetime: object = reading.get("valid-lifetime", lease.get("valid"))
                if type(lifetime) is not int or not 0 < lifetime <= 4294967295:
                    continue
                try:
                    parsed_address: ipaddress.IPv6Address = ipaddress.IPv6Address(reading.get("address", ""))
                except (ValueError, TypeError):
                    continue
                if parsed_address.is_multicast or parsed_address.is_unspecified:
                    continue
                lease_mac: Optional[str] = neighbor_macs.get((interface, str(parsed_address))) or _duid_mac(value=duid_value)
                identity: str = (
                    f"mac:{lease_mac}" if lease_mac is not None else f"duid:{duid_text}" if duid_text is not None else f"address:{parsed_address}"
                )
                records.append(
                    Ipv6Record(
                        address=str(parsed_address),
                        interface=interface,
                        identity=identity,
                        mac=lease_mac,
                        hostname=hostname,
                        expires_at=datetime.fromtimestamp(timestamp=now.timestamp() + lifetime, tz=UTC),
                    )
                )
    return tuple(records)


def _device_sort_key(device: dict[str, Any]) -> tuple[bool, bool, int, int, str]:
    hostname: Optional[str] = device["hostname"]
    unnamed: bool = hostname is None
    if hostname is not None:
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            unnamed = True
    address: Union[ipaddress.IPv4Address, ipaddress.IPv6Address] = ipaddress.ip_address(device["address"] or device["ipv6_addresses"][0])
    outside_lan: bool = device["network_group"] != "lan"
    return (outside_lan, unnamed, address.version, int(address), device["mac"] or "")


def build_device_payloads(*, leases: tuple[DhcpLease, ...], ipv6: tuple[Ipv6Record, ...], now: datetime) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = [lease.to_payload() for lease in leases if lease.expires_at is None or lease.expires_at > now]
    by_mac: dict[str, list[dict[str, Any]]] = {}
    for device in devices:
        device["ipv6_addresses"] = []
        by_mac.setdefault(device["mac"].lower(), []).append(device)
    ipv6_only: dict[tuple[str, str], dict[str, Any]] = {}
    for record in ipv6:
        if record.expires_at is not None and record.expires_at <= now:
            continue
        targets: list[dict[str, Any]] = by_mac.get(record.mac, []) if record.mac is not None else []
        if not targets:
            key: tuple[str, str] = (record.interface, record.identity)
            if key not in ipv6_only:
                ipv6_only[key] = {
                    "address": None,
                    "mac": record.mac.upper() if record.mac is not None else None,
                    "hostname": record.hostname,
                    "display_name": display_name_for(name=record.hostname) if record.hostname else record.address,
                    "network_group": "lan" if record.interface == "br-lan" else "guest_iot",
                    "expires_at": None,
                    "ipv6_addresses": [],
                }
            targets = [ipv6_only[key]]
        for target in targets:
            if record.address not in target["ipv6_addresses"]:
                target["ipv6_addresses"].append(record.address)
            if target["hostname"] is None and record.hostname is not None:
                target["hostname"] = record.hostname
                target["display_name"] = display_name_for(name=record.hostname)
    devices.extend(ipv6_only.values())
    for device in devices:
        device["ipv6_addresses"].sort(key=lambda address: (ipaddress.IPv6Address(address).is_link_local, int(ipaddress.IPv6Address(address))))
    return sorted(devices, key=_device_sort_key)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True, kw_only=True)
class OpenWrtLeaseSource:
    target: SshTarget
    timeout_seconds: float = 8.0
    ttl_seconds: float = 60.0
    runner: CommandRunner = run_command
    resolver: Callable[[str], str] = socket.gethostbyname
    clock: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = _utc_now
    manufacturer_lookup: MacManufacturerLookup = field(default_factory=MacManufacturerLookup)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _stored_at: Optional[float] = field(default=None, init=False)
    _fetched_at: Optional[datetime] = field(default=None, init=False)
    _leases: tuple[DhcpLease, ...] = field(default=(), init=False)
    _router_version: Optional[str] = field(default=None, init=False)
    _router_address: Optional[str] = field(default=None, init=False)
    _router_address_resolved: bool = field(default=False, init=False)
    _error: Optional[str] = field(default=None, init=False)

    def _read(self) -> tuple[Optional[str], tuple[DhcpLease, ...]]:
        command: tuple[str, ...] = (SSH_EXECUTABLE, *SSH_OPTIONS, self.target.destination, REMOTE_COMMAND)
        try:
            completed: subprocess.CompletedProcess[str] = self.runner(command, timeout=self.timeout_seconds)
        except FileNotFoundError as error:
            raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
        except subprocess.TimeoutExpired as error:
            raise StatusSourceError("Reading OpenWRT DHCP leases timed out.") from error
        if completed.returncode != 0:
            raise StatusSourceError(explain_ssh_failure(stderr=completed.stderr, destination=self.target.destination, action="Reading DHCP leases"))
        return parse_router_response(text=completed.stdout)

    def _resolve_router_address(self) -> Optional[str]:
        if not self._router_address_resolved:
            self._router_address_resolved = True
            try:
                self._router_address = self.resolver(self.target.host)
            except (OSError, ValueError):
                self._router_address = None
        return self._router_address

    def fetch(self, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            if force or self._stored_at is None or self.clock() - self._stored_at >= self.ttl_seconds:
                try:
                    router_version, leases = self._read()
                    self._leases = leases
                    if router_version is not None:
                        self._router_version = router_version
                    self._fetched_at = self.now()
                    self._error = None
                except StatusSourceError as error:
                    self._error = str(error)
                self._stored_at = self.clock()
            now: datetime = self.now()
            lease_payloads: list[dict[str, Any]] = [
                lease.to_payload(manufacturer=self.manufacturer_lookup.lookup(mac=lease.mac))
                for lease in self._leases
                if lease.expires_at is None or lease.expires_at > now
            ]
            return {
                "source": "OpenWRT",
                "router": self.target.host,
                "router_address": self._resolve_router_address(),
                "router_version": self._router_version,
                "fetched_at": self._fetched_at.isoformat(timespec="seconds") if self._fetched_at is not None else None,
                "stale": self._error is not None,
                "error": self._error,
                "leases": sorted(lease_payloads, key=_device_sort_key),
            }
