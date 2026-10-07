import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Protocol

from homelab_dashboard.models import ClusterSnapshot
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.pve_parser import JsonObject, parse_snapshot

SOURCE_LABEL: Final = "Proxmox VE over SSH"

# Public-key only, never prompts, and never relaxes host-key verification.
SSH_OPTIONS: Final = (
    "-oBatchMode=yes",
    "-oConnectTimeout=6",
    "-oConnectionAttempts=1",
    "-oPreferredAuthentications=publickey",
    "-oPasswordAuthentication=no",
    "-oKbdInteractiveAuthentication=no",
    "-oStrictHostKeyChecking=yes",
)

# Both documents arrive over one connection; their order matters to the decoder.
API_PATHS: Final = ("/cluster/resources", "/cluster/status")
REMOTE_COMMAND: Final = " && ".join(f"pvesh get {path} --output-format json" for path in API_PATHS)

_FAILURE_MESSAGES: Final = (
    ("host key verification failed", "{target}'s SSH host key is not in this user's known_hosts file."),
    ("permission denied", "SSH key authentication to {target} was refused."),
    ("could not resolve", "{target} could not be resolved."),
    ("connection refused", "{target} refused the SSH connection."),
    ("timed out", "Connecting to {target} timed out."),
    ("no route to host", "There is no route to {target}."),
)


class CommandRunner(Protocol):
    def __call__(self, command: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]: ...


def run_command(command: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class SshTarget:
    destination: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", self.destination):
            raise ValueError("SSH target must be a host, alias, or user@host from the SSH configuration.")


def _decode_arrays(*, text: str, count: int) -> list[list[JsonObject]]:
    decoder = json.JSONDecoder()
    arrays: list[list[JsonObject]] = []
    index = 0
    for _ in range(count):
        while index < len(text) and text[index].isspace():
            index += 1
        try:
            value, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError as error:
            raise StatusSourceError("Proxmox returned malformed status data.") from error
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise StatusSourceError("Proxmox returned an unexpected status response.")
        arrays.append(value)
    return arrays


@dataclass(frozen=True, slots=True, kw_only=True)
class ProxmoxSshSource:
    target: SshTarget
    timeout_seconds: float = 15.0
    runner: CommandRunner = run_command
    clock: Callable[[], datetime] = _utc_now

    def fetch(self) -> ClusterSnapshot:
        command = ("ssh", *SSH_OPTIONS, self.target.destination, REMOTE_COMMAND)
        try:
            completed = self.runner(command, timeout=self.timeout_seconds)
        except FileNotFoundError as error:
            raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
        except subprocess.TimeoutExpired as error:
            raise StatusSourceError(f"Reading status from {self.target.destination} timed out.") from error

        if completed.returncode != 0:
            raise StatusSourceError(self._explain_failure(stderr=completed.stderr))

        resources, cluster_status = _decode_arrays(text=completed.stdout, count=len(API_PATHS))
        return parse_snapshot(source=SOURCE_LABEL, fetched_at=self.clock(), resources=resources, cluster_status=cluster_status)

    def _explain_failure(self, *, stderr: str) -> str:
        lowered = stderr.lower()
        for needle, template in _FAILURE_MESSAGES:
            if needle in lowered:
                return template.format(target=self.target.destination)
        detail = stderr.strip().splitlines()[-1][:160] if stderr.strip() else "no error output"
        return f"Querying Proxmox on {self.target.destination} failed ({detail})."
