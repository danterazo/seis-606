import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Optional

from homelab_dashboard.models import ClusterSnapshot, Guest, GuestKind, GuestState, Node, NodeState
from homelab_dashboard.sources.base import RefreshableStatusSource, StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import SSH_EXECUTABLE, SSH_OPTIONS, CommandRunner, SshTarget, explain_ssh_failure, run_command


@dataclass(slots=True, kw_only=True)
class GuestRebooter:
    source: RefreshableStatusSource
    user: str = "root"
    timeout_seconds: float = 30.0
    runner: CommandRunner = run_command
    clock: Callable[[], float] = time.monotonic
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _attempted_at: dict[int, float] = field(default_factory=dict, init=False)

    def reboot(self, *, vmid: object, node_name: object) -> None:
        self._submit(vmid=vmid, node_name=node_name, verb="reboot")

    def start(self, *, vmid: object, node_name: object) -> None:
        self._submit(vmid=vmid, node_name=node_name, verb="start")

    def _submit(self, *, vmid: object, node_name: object, verb: str) -> None:
        if type(vmid) is not int or not 100 <= vmid <= 999999999:
            raise ValueError("Guest ID must be an integer between 100 and 999999999.")
        if not isinstance(node_name, str) or not node_name:
            raise ValueError("A node name is required.")
        if not self._lock.acquire(blocking=False):
            raise StatusSourceError(f"Another guest {verb} is already being submitted.")
        try:
            previous: Optional[float] = self._attempted_at.get(vmid)
            if previous is not None and self.clock() - previous < 30:
                raise StatusSourceError(f"A {verb} was recently attempted for this guest. Check its status before retrying.")
            snapshot: ClusterSnapshot = self.source.fetch_fresh()
            matches: tuple[tuple[Node, Guest], ...] = tuple((node, guest) for node in snapshot.nodes for guest in node.guests if guest.vmid == vmid)
            if len(matches) != 1:
                raise ValueError("The guest could not be uniquely identified in the current cluster.")
            node, guest = matches[0]
            if node.name != node_name or guest.node != node.name:
                raise ValueError("The guest's node has changed. Refresh the dashboard and try again.")
            required_state: GuestState = GuestState.RUNNING if verb == "reboot" else GuestState.STOPPED
            if node.state is not NodeState.ONLINE or guest.state is not required_state:
                raise ValueError(f"Only {required_state.value} guests on online nodes can be {'rebooted' if verb == 'reboot' else 'started'}.")
            if node.address is None:
                raise ValueError("The guest's node has no reported SSH address.")
            target: SshTarget = SshTarget(host=node.address, user=self.user)
            executable: str = "pct" if guest.kind is GuestKind.CONTAINER else "qm"
            command: tuple[str, ...] = (SSH_EXECUTABLE, *SSH_OPTIONS, target.destination, f"{executable} {verb} {vmid}")
            self._attempted_at[vmid] = self.clock()
            try:
                completed: subprocess.CompletedProcess[str] = self.runner(command, timeout=self.timeout_seconds)
            except FileNotFoundError as error:
                raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
            except subprocess.TimeoutExpired as error:
                raise StatusSourceError(f"The {verb} command timed out. It may still be running; check the guest before retrying.") from error
            if completed.returncode != 0:
                raise StatusSourceError(
                    explain_ssh_failure(
                        stderr=completed.stderr, destination=target.destination, action="Rebooting guest" if verb == "reboot" else "Starting guest"
                    )
                )
        finally:
            self._lock.release()
