import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from homelab_dashboard.models import Storage
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import (
    DEFAULT_USER,
    SSH_OPTIONS,
    CommandRunner,
    SshTarget,
    explain_ssh_failure,
    run_command,
)
from homelab_dashboard.sources.storage_parser import parse_storage

STORAGE_SCRIPT: Final[str] = Path(__file__).with_name("storage_probe.py").read_text(encoding="utf-8")
REMOTE_COMMAND: Final[str] = "python3 -"


class StorageProbe(Protocol):
    def probe(self, *, node_name: str, address: str) -> Storage: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class SshStorageProbe:
    user: str = DEFAULT_USER
    # Reading every disk's SMART data takes a few seconds, well beyond the hardware probe.
    timeout_seconds: float = 60.0
    runner: CommandRunner = run_command

    def probe(self, *, node_name: str, address: str) -> Storage:
        destination: str = SshTarget(host=address, user=self.user).destination
        command: tuple[str, ...] = ("ssh", *SSH_OPTIONS, destination, REMOTE_COMMAND)
        try:
            completed: subprocess.CompletedProcess[str] = self.runner(command, timeout=self.timeout_seconds, stdin=STORAGE_SCRIPT)
        except FileNotFoundError as error:
            raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
        except subprocess.TimeoutExpired as error:
            raise StatusSourceError(f"Reading storage health on {node_name} timed out.") from error
        if completed.returncode != 0:
            raise StatusSourceError(explain_ssh_failure(stderr=completed.stderr, destination=destination, action="Reading storage health"))
        try:
            document: object = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise StatusSourceError(f"{node_name} returned malformed storage data.") from error
        return parse_storage(document=document)
