import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Final, List, Protocol, Sequence, Tuple, Union

from homelab_dashboard.models import ClusterSnapshot
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.pve_parser import JsonObject, parse_snapshot

SOURCE_LABEL: Final[str] = "Proxmox VE via SSH"
DEFAULT_USER: Final[str] = "root"

# Public-key only, never prompts, and never relaxes host-key verification.
SSH_OPTIONS: Final[Tuple[str, ...]] = (
    "-oBatchMode=yes",
    "-oConnectTimeout=6",
    "-oConnectionAttempts=1",
    "-oPreferredAuthentications=publickey",
    "-oPasswordAuthentication=no",
    "-oKbdInteractiveAuthentication=no",
    "-oStrictHostKeyChecking=yes",
)

# Both documents arrive over one connection; their order matters to the decoder.
API_PATHS: Final[Tuple[str, ...]] = ("/cluster/resources", "/cluster/status")
REMOTE_COMMAND: Final[str] = " && ".join(f"pvesh get {path} --output-format json" for path in API_PATHS)

_FAILURE_MESSAGES: Final[Tuple[Tuple[str, str], ...]] = (
    ("host key verification failed", "{target}'s SSH host key is not in this user's known_hosts file."),
    ("permission denied", "SSH key authentication to {target} was refused."),
    ("could not resolve", "{target} could not be resolved."),
    ("connection refused", "{target} refused the SSH connection."),
    ("timed out", "Connecting to {target} timed out."),
    ("no route to host", "There is no route to {target}."),
)

_HOST_PATTERN: Final[str] = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
_USER_PATTERN: Final[str] = r"[A-Za-z_][A-Za-z0-9_-]*"


class CommandRunner(Protocol):
    def __call__(self, command: Sequence[str], *, timeout: float) -> "subprocess.CompletedProcess[str]": ...


def run_command(command: Sequence[str], *, timeout: float) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True, kw_only=True)
class SshTarget:
    host: str
    user: str = DEFAULT_USER

    def __post_init__(self) -> None:
        if not re.fullmatch(_HOST_PATTERN, self.host):
            raise ValueError("SSH host must be a hostname, IP address, or alias without a user prefix.")
        if not re.fullmatch(_USER_PATTERN, self.user):
            raise ValueError("SSH user must be a plain account name.")

    @property
    def destination(self) -> str:
        return f"{self.user}@{self.host}"


def _decode_arrays(*, text: str, count: int) -> List[List[JsonObject]]:
    decoder: json.JSONDecoder = json.JSONDecoder()
    arrays: List[List[JsonObject]] = []
    index: int = 0
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
        command: Tuple[str, ...] = ("ssh", *SSH_OPTIONS, self.target.destination, REMOTE_COMMAND)
        try:
            completed: "subprocess.CompletedProcess[str]" = self.runner(command, timeout=self.timeout_seconds)
        except FileNotFoundError as error:
            raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
        except subprocess.TimeoutExpired as error:
            raise StatusSourceError(f"Reading status from {self.target.destination} timed out.") from error

        if completed.returncode != 0:
            raise StatusSourceError(self._explain_failure(stderr=completed.stderr))

        resources, cluster_status = _decode_arrays(text=completed.stdout, count=len(API_PATHS))
        return parse_snapshot(
            source=SOURCE_LABEL,
            fetched_at=self.clock(),
            resources=resources,
            cluster_status=cluster_status,
        )

    def _explain_failure(self, *, stderr: str) -> str:
        lowered: str = stderr.lower()
        for needle, template in _FAILURE_MESSAGES:
            if needle in lowered:
                return template.format(target=self.target.destination)
        detail: Union[str, None] = stderr.strip().splitlines()[-1][:160] if stderr.strip() else None
        return f"Querying Proxmox on {self.target.destination} failed ({detail or 'no error output'})."
