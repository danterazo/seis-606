import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from homelab_dashboard.models import GuestKind, GuestState, NodeState
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import SSH_OPTIONS, ProxmoxSshSource, SshTarget

FIXED_TIME = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)

RESOURCES = [
    {"type": "node", "node": "cerulean", "status": "online", "cpu": 0.25, "mem": 8, "maxmem": 16},
    {"type": "node", "node": "violet", "status": "offline", "cpu": 0.9, "mem": 4, "maxmem": 8},
    {"type": "qemu", "vmid": 101, "node": "cerulean", "name": "web", "status": "running", "cpu": 0.1, "mem": 2, "maxmem": 4},
    {"type": "lxc", "vmid": 201, "node": "cerulean", "name": "dns", "status": "stopped"},
    {"type": "qemu", "vmid": 900, "node": "cerulean", "name": "base", "status": "stopped", "template": 1},
    {"type": "storage", "id": "storage/cerulean/local"},
]
CLUSTER_STATUS = [
    {"type": "cluster", "name": "home"},
    {"type": "node", "name": "cerulean", "ip": "192.168.20.43"},
]


def make_runner(*, stdout: str = "", stderr: str = "", returncode: int = 0, calls: list[Sequence[str]] | None = None):
    def runner(command: Sequence[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
        if calls is not None:
            calls.append(command)
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    return runner


def make_source(**runner_kwargs) -> ProxmoxSshSource:
    return ProxmoxSshSource(target=SshTarget(destination="cerulean"), runner=make_runner(**runner_kwargs), clock=lambda: FIXED_TIME)


def test_fetch_parses_nodes_guests_and_addresses():
    snapshot = make_source(stdout=json.dumps(RESOURCES) + "\n" + json.dumps(CLUSTER_STATUS)).fetch()

    cerulean, violet = snapshot.nodes
    assert (cerulean.name, cerulean.state, cerulean.address) == ("cerulean", NodeState.ONLINE, "192.168.20.43")
    assert cerulean.resources.cpu_ratio == 0.25
    assert [(guest.vmid, guest.kind, guest.state) for guest in cerulean.guests] == [
        (101, GuestKind.VM, GuestState.RUNNING),
        (201, GuestKind.CONTAINER, GuestState.STOPPED),
    ]
    assert snapshot.fetched_at == FIXED_TIME


def test_offline_node_drops_stale_usage_but_keeps_capacity():
    snapshot = make_source(stdout=json.dumps(RESOURCES) + json.dumps(CLUSTER_STATUS)).fetch()

    violet = snapshot.nodes[1]
    assert violet.state is NodeState.OFFLINE
    assert violet.address is None
    assert violet.resources.cpu_ratio is None
    assert violet.resources.memory_used_bytes is None
    assert violet.resources.memory_total_bytes == 8


def test_missing_readings_stay_unknown_instead_of_zero():
    resources = [{"type": "node", "node": "cerulean", "status": "online"}]
    snapshot = make_source(stdout=json.dumps(resources) + "[]").fetch()

    assert snapshot.nodes[0].resources.cpu_ratio is None
    assert snapshot.nodes[0].resources.memory_total_bytes is None


def test_unrecognised_status_is_reported_as_unknown():
    resources = [{"type": "node", "node": "cerulean", "status": "mystery"}]
    snapshot = make_source(stdout=json.dumps(resources) + "[]").fetch()

    assert snapshot.nodes[0].state is NodeState.UNKNOWN


def test_ssh_command_never_prompts_or_relaxes_host_checking():
    calls: list[Sequence[str]] = []
    make_source(stdout="[][]", calls=calls).fetch()

    (command,) = calls
    assert command[0] == "ssh"
    assert set(SSH_OPTIONS) <= set(command)
    assert "-oStrictHostKeyChecking=yes" in command
    assert command[-1].count("pvesh get") == 2


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("Host key verification failed.", "known_hosts"),
        ("root@x: Permission denied (publickey).", "authentication"),
        ("ssh: connect to host x port 22: Connection refused", "refused"),
    ],
)
def test_failures_become_safe_messages(stderr: str, expected: str):
    with pytest.raises(StatusSourceError, match=expected):
        make_source(stderr=stderr, returncode=255).fetch()


def test_malformed_output_is_rejected():
    with pytest.raises(StatusSourceError):
        make_source(stdout="not json").fetch()


def test_target_rejects_option_injection():
    with pytest.raises(ValueError):
        SshTarget(destination="-oProxyCommand=evil")
