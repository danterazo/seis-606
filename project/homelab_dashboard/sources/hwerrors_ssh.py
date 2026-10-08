import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from homelab_dashboard.models import HardwareErrors
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.hwerrors_parser import parse_hardware_errors
from homelab_dashboard.sources.proxmox_ssh import (
    DEFAULT_USER,
    SSH_OPTIONS,
    CommandRunner,
    SshTarget,
    explain_ssh_failure,
    run_command,
)

HW_ERRORS_SCRIPT: Final[str] = Path(__file__).with_name("hwerrors_probe.py").read_text(encoding="utf-8")
REMOTE_COMMAND: Final[str] = "python3 -"


class HardwareErrorProbe(Protocol):
    def probe(self, *, node_name: str, address: str) -> HardwareErrors: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class SshHardwareErrorProbe:
    user: str = DEFAULT_USER
    # Scanning two weeks of journal can take a while on a node that is logging a storm.
    timeout_seconds: float = 60.0
    runner: CommandRunner = run_command

    def probe(self, *, node_name: str, address: str) -> HardwareErrors:
        destination: str = SshTarget(host=address, user=self.user).destination
        command: tuple[str, ...] = ("ssh", *SSH_OPTIONS, destination, REMOTE_COMMAND)
        try:
            completed: subprocess.CompletedProcess[str] = self.runner(command, timeout=self.timeout_seconds, stdin=HW_ERRORS_SCRIPT)
        except FileNotFoundError as error:
            raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
        except subprocess.TimeoutExpired as error:
            raise StatusSourceError(f"Reading hardware errors on {node_name} timed out.") from error
        if completed.returncode != 0:
            raise StatusSourceError(explain_ssh_failure(stderr=completed.stderr, destination=destination, action="Reading hardware errors"))
        try:
            document: object = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise StatusSourceError(f"{node_name} returned malformed hardware error data.") from error
        return parse_hardware_errors(document=document)
