import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol, Tuple

from homelab_dashboard.models import Hardware
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.hardware_parser import parse_hardware
from homelab_dashboard.sources.proxmox_ssh import (
    DEFAULT_USER,
    SSH_OPTIONS,
    CommandRunner,
    SshTarget,
    explain_ssh_failure,
    run_command,
)

PROBE_SCRIPT: Final[str] = Path(__file__).with_name("remote_probe.py").read_text(encoding="utf-8")
# Python reads the program from stdin, so nothing is written to the node's disk.
REMOTE_COMMAND: Final[str] = "python3 -"


class HardwareProbe(Protocol):
    def probe(self, *, node_name: str, address: str) -> Hardware: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class SshHardwareProbe:
    user: str = DEFAULT_USER
    timeout_seconds: float = 15.0
    runner: CommandRunner = run_command

    def probe(self, *, node_name: str, address: str) -> Hardware:
        destination: str = SshTarget(host=address, user=self.user).destination
        command: Tuple[str, ...] = ("ssh", *SSH_OPTIONS, destination, REMOTE_COMMAND)
        try:
            completed: "subprocess.CompletedProcess[str]" = self.runner(
                command, timeout=self.timeout_seconds, stdin=PROBE_SCRIPT
            )
        except FileNotFoundError as error:
            raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
        except subprocess.TimeoutExpired as error:
            raise StatusSourceError(f"Probing {node_name} timed out.") from error

        if completed.returncode != 0:
            raise StatusSourceError(
                explain_ssh_failure(stderr=completed.stderr, destination=destination, action="Probing hardware")
            )
        document: object = self._decode(text=completed.stdout, node_name=node_name)
        return parse_hardware(document=document)

    @staticmethod
    def _decode(*, text: str, node_name: str) -> object:
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise StatusSourceError(f"{node_name} returned malformed hardware data.") from error
