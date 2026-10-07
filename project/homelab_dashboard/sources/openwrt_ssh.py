import ipaddress
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from homelab_dashboard.node_profiles import display_name_for
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import SSH_OPTIONS, CommandRunner, SshTarget, explain_ssh_failure, run_command


@dataclass(frozen=True, slots=True, kw_only=True)
class DhcpLease:
    address: str
    mac: str
    hostname: Optional[str]
    expires_at: Optional[datetime]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "mac": self.mac,
            "hostname": self.hostname,
            "display_name": display_name_for(name=self.hostname) if self.hostname is not None else self.address,
            "expires_at": self.expires_at.isoformat(timespec="seconds") if self.expires_at is not None else None,
        }


def parse_leases(*, text: str) -> Tuple[DhcpLease, ...]:
    leases: List[DhcpLease] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields: List[str] = line.split()
        if len(fields) != 5:
            raise StatusSourceError("OpenWrt returned an unexpected DHCP lease record.")
        expiry, mac, address, hostname, _client_id = fields
        try:
            seconds: int = int(expiry)
            if seconds < 0 or not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac):
                raise ValueError("Invalid lease")
            parsed_address: ipaddress.IPv4Address = ipaddress.IPv4Address(address)
            expires_at: Optional[datetime] = datetime.fromtimestamp(seconds, UTC) if seconds else None
        except (ValueError, OverflowError, OSError) as error:
            raise StatusSourceError("OpenWrt returned an invalid DHCP lease record.") from error
        leases.append(DhcpLease(address=str(parsed_address), mac=mac.lower(), hostname=None if hostname == "*" else hostname, expires_at=expires_at))
    return tuple(leases)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True, kw_only=True)
class OpenWrtLeaseSource:
    target: SshTarget
    timeout_seconds: float = 8.0
    ttl_seconds: float = 60.0
    runner: CommandRunner = run_command
    clock: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = _utc_now
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _stored_at: Optional[float] = field(default=None, init=False)
    _fetched_at: Optional[datetime] = field(default=None, init=False)
    _leases: Tuple[DhcpLease, ...] = field(default=(), init=False)
    _error: Optional[str] = field(default=None, init=False)

    def _read(self) -> Tuple[DhcpLease, ...]:
        command: Tuple[str, ...] = ("ssh", *SSH_OPTIONS, self.target.destination, "cat /tmp/dhcp.leases")
        try:
            completed: "subprocess.CompletedProcess[str]" = self.runner(command, timeout=self.timeout_seconds)
        except FileNotFoundError as error:
            raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
        except subprocess.TimeoutExpired as error:
            raise StatusSourceError("Reading OpenWrt DHCP leases timed out.") from error
        if completed.returncode != 0:
            raise StatusSourceError(explain_ssh_failure(stderr=completed.stderr, destination=self.target.destination, action="Reading DHCP leases"))
        return parse_leases(text=completed.stdout)

    def fetch(self, *, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            if force or self._stored_at is None or self.clock() - self._stored_at >= self.ttl_seconds:
                try:
                    self._leases = self._read()
                    self._fetched_at = self.now()
                    self._error = None
                except StatusSourceError as error:
                    self._error = str(error)
                self._stored_at = self.clock()
            now: datetime = self.now()
            return {
                "source": "OpenWrt DHCPv4",
                "router": self.target.host,
                "fetched_at": self._fetched_at.isoformat(timespec="seconds") if self._fetched_at is not None else None,
                "stale": self._error is not None,
                "error": self._error,
                "leases": [lease.to_payload() for lease in self._leases if lease.expires_at is None or lease.expires_at > now],
            }