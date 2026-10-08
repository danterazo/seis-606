import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from homelab_dashboard.models import ClusterSnapshot, Guest, GuestKind, GuestState, Node, NodeState
from homelab_dashboard.sources.base import RefreshableStatusSource, StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import SSH_OPTIONS, CommandRunner, SshTarget, explain_ssh_failure, run_command


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
        if type(vmid) is not int or not 100 <= vmid <= 999999999:
            raise ValueError("Guest ID must be an integer between 100 and 999999999.")
        if not isinstance(node_name, str) or not node_name:
            raise ValueError("A node name is required.")
        if not self._lock.acquire(blocking=False):
            raise StatusSourceError("Another guest reboot is already being submitted.")
        try:
            previous: float | None = self._attempted_at.get(vmid)
            if previous is not None and self.clock() - previous < 30:
                raise StatusSourceError("A reboot was recently attempted for this guest. Check its status before retrying.")
            snapshot: ClusterSnapshot = self.source.fetch_fresh()
            matches: tuple[tuple[Node, Guest], ...] = tuple(
                (node, guest) for node in snapshot.nodes for guest in node.guests if guest.vmid == vmid
            )
            if len(matches) != 1:
                raise ValueError("The guest could not be uniquely identified in the current cluster.")
            node, guest = matches[0]
            if node.name != node_name or guest.node != node.name:
                raise ValueError("The guest's node has changed. Refresh the dashboard and try again.")
            if node.state is not NodeState.ONLINE or guest.state is not GuestState.RUNNING:
                raise ValueError("Only running guests on online nodes can be rebooted.")
            if node.address is None:
                raise ValueError("The guest's node has no reported SSH address.")
            target: SshTarget = SshTarget(host=node.address, user=self.user)
            executable: str = "pct" if guest.kind is GuestKind.CONTAINER else "qm"
            command: tuple[str, ...] = ("ssh", *SSH_OPTIONS, target.destination, f"{executable} reboot {vmid}")
            self._attempted_at[vmid] = self.clock()
            try:
                completed: subprocess.CompletedProcess[str] = self.runner(command, timeout=self.timeout_seconds)
            except FileNotFoundError as error:
                raise StatusSourceError("The OpenSSH client is not installed in this environment.") from error
            except subprocess.TimeoutExpired as error:
                raise StatusSourceError("The reboot command timed out. It may still be running; check the guest before retrying.") from error
            if completed.returncode != 0:
                raise StatusSourceError(explain_ssh_failure(stderr=completed.stderr, destination=target.destination, action="Rebooting guest"))
        finally:
            self._lock.release()
