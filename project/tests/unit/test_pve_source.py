import json
import subprocess
from datetime import UTC, datetime
from typing import Any, Dict, Final, List, Optional, Sequence, Tuple

import pytest

from homelab_dashboard.config import Settings
from homelab_dashboard.models import GuestKind, GuestState, NodeState
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import SSH_OPTIONS, CommandRunner, ProxmoxSshSource, SshTarget

FIXED_TIME: Final[datetime] = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)

RESOURCES: Final[List[Dict[str, Any]]] = [
    {"type": "node", "node": "cerulean", "status": "online", "cpu": 0.25, "mem": 8, "maxmem": 16},
    {"type": "node", "node": "violet", "status": "offline", "cpu": 0.9, "mem": 4, "maxmem": 8},
    {"type": "qemu", "vmid": 101, "node": "cerulean", "name": "web", "status": "running", "cpu": 0.1, "mem": 2, "maxmem": 4},
    {"type": "lxc", "vmid": 201, "node": "cerulean", "name": "dns", "status": "stopped"},
    {"type": "qemu", "vmid": 900, "node": "cerulean", "name": "base", "status": "stopped", "template": 1},
    {"type": "storage", "id": "storage/cerulean/local"},
]
CLUSTER_STATUS: Final[List[Dict[str, Any]]] = [
    {"type": "cluster", "name": "home"},
    {"type": "node", "name": "cerulean", "ip": "192.168.20.43"},
]


def make_runner(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    calls: Optional[List[Sequence[str]]] = None,
) -> CommandRunner:
    def runner(command: Sequence[str], *, timeout: float, stdin: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        if calls is not None:
            calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=returncode, stdout=stdout, stderr=stderr)

    return runner


def make_source(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    calls: Optional[List[Sequence[str]]] = None,
) -> ProxmoxSshSource:
    return ProxmoxSshSource(
        target=SshTarget(host="cerulean"),
        runner=make_runner(stdout=stdout, stderr=stderr, returncode=returncode, calls=calls),
        clock=lambda: FIXED_TIME,
    )


def documents(*, resources: Sequence[Dict[str, Any]], cluster_status: Sequence[Dict[str, Any]]) -> str:
    return json.dumps(list(resources)) + "\n" + json.dumps(list(cluster_status))


def test_fetch_parses_nodes_guests_and_addresses() -> None:
    snapshot = make_source(stdout=documents(resources=RESOURCES, cluster_status=CLUSTER_STATUS)).fetch()

    cerulean, _violet = snapshot.nodes
    assert (cerulean.name, cerulean.state, cerulean.address) == ("cerulean", NodeState.ONLINE, "192.168.20.43")
    assert cerulean.resources.cpu_ratio == 0.25
    assert [(guest.vmid, guest.kind, guest.state) for guest in cerulean.guests] == [
        (101, GuestKind.VM, GuestState.RUNNING),
        (201, GuestKind.CONTAINER, GuestState.STOPPED),
    ]
    assert snapshot.fetched_at == FIXED_TIME


def test_offline_node_drops_stale_usage_but_keeps_capacity() -> None:
    snapshot = make_source(stdout=documents(resources=RESOURCES, cluster_status=CLUSTER_STATUS)).fetch()

    violet = snapshot.nodes[1]
    assert violet.state is NodeState.OFFLINE
    assert violet.address is None
    assert violet.resources.cpu_ratio is None
    assert violet.resources.memory_used_bytes is None
    assert violet.resources.memory_total_bytes == 8


def test_missing_readings_stay_unknown_instead_of_zero() -> None:
    resources: List[Dict[str, Any]] = [{"type": "node", "node": "cerulean", "status": "online"}]
    snapshot = make_source(stdout=documents(resources=resources, cluster_status=[])).fetch()

    assert snapshot.nodes[0].resources.cpu_ratio is None
    assert snapshot.nodes[0].resources.memory_total_bytes is None


def test_unrecognised_status_is_reported_as_unknown() -> None:
    resources: List[Dict[str, Any]] = [{"type": "node", "node": "cerulean", "status": "mystery"}]
    snapshot = make_source(stdout=documents(resources=resources, cluster_status=[])).fetch()

    assert snapshot.nodes[0].state is NodeState.UNKNOWN


def test_guests_without_names_get_a_short_fallback() -> None:
    resources: List[Dict[str, Any]] = [
        {"type": "node", "node": "violet", "status": "offline"},
        {"type": "lxc", "vmid": 7, "node": "violet", "status": "unknown"},
    ]
    snapshot = make_source(stdout=documents(resources=resources, cluster_status=[])).fetch()

    assert snapshot.nodes[0].guests[0].name == "LXC 7"


def test_ssh_command_never_prompts_or_relaxes_host_checking() -> None:
    calls: List[Sequence[str]] = []
    make_source(stdout="[][]", calls=calls).fetch()

    (command,) = calls
    assert command[0] == "ssh"
    assert set(SSH_OPTIONS) <= set(command)
    assert "-oStrictHostKeyChecking=yes" in command
    assert command[-1].count("pvesh get") == 3


def test_reachable_node_stays_online_and_keeps_its_figures_without_quorum() -> None:
    resources: List[Dict[str, Any]] = [{"type": "node", "node": "cerulean", "status": "unknown"}, {"type": "node", "node": "kex", "status": "unknown"}]
    cluster_status: List[Dict[str, Any]] = [
        {"type": "node", "name": "cerulean", "ip": "10.0.0.2", "online": 1, "local": 1},
        {"type": "node", "name": "kex", "ip": "10.0.0.1", "online": 0, "local": 0},
    ]
    local_status: Dict[str, Any] = {"cpu": 0.25, "cpuinfo": {"cpus": 4}, "memory": {"used": 1, "total": 4}}
    stdout: str = documents(resources=resources, cluster_status=cluster_status) + "\n" + json.dumps(local_status)

    cerulean, kex = make_source(stdout=stdout).fetch().nodes

    assert (cerulean.state, cerulean.resources.cpu_cores, cerulean.resources.memory_used_bytes) == (NodeState.ONLINE, 4, 1)
    assert kex.state is not NodeState.ONLINE and kex.resources.memory_used_bytes is None


def test_core_counts_are_kept_for_guests_and_for_offline_nodes() -> None:
    resources: List[Dict[str, Any]] = [
        {"type": "node", "node": "cerulean", "status": "online", "maxcpu": 4, "cpu": 0.5},
        {"type": "node", "node": "violet", "status": "offline", "maxcpu": 8, "cpu": 0.9},
        {"type": "lxc", "vmid": 100, "node": "cerulean", "name": "pocket-id", "status": "running", "maxcpu": 2, "cpu": 0.25},
        {"type": "lxc", "vmid": 101, "node": "cerulean", "name": "no-cores", "status": "running"},
    ]
    snapshot = make_source(stdout=documents(resources=resources, cluster_status=[])).fetch()

    cerulean, violet = snapshot.nodes
    assert cerulean.resources.cpu_cores == 4
    assert violet.resources.cpu_cores == 8
    assert violet.resources.cpu_ratio is None
    assert [guest.resources.cpu_cores for guest in cerulean.guests] == [2, None]


def test_connections_use_root_by_default() -> None:
    calls: List[Sequence[str]] = []
    make_source(stdout="[][]", calls=calls).fetch()

    assert "root@cerulean" in calls[0]
    assert SshTarget(host="192.168.20.43").destination == "root@192.168.20.43"


def test_settings_default_to_root_on_cerulean() -> None:
    settings: Settings = Settings.from_env(environ={})

    assert (settings.ssh_user, settings.ssh_host) == ("root", "192.168.20.43")


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("Host key verification failed.", "known_hosts"),
        ("root@x: Permission denied (publickey).", "authentication"),
        ("ssh: connect to host x port 22: Connection refused", "refused"),
    ],
)
def test_failures_become_safe_messages(*, stderr: str, expected: str) -> None:
    with pytest.raises(StatusSourceError, match=expected):
        make_source(stderr=stderr, returncode=255).fetch()


def test_malformed_output_is_rejected() -> None:
    with pytest.raises(StatusSourceError):
        make_source(stdout="not json").fetch()


@pytest.mark.parametrize(
    ("host", "user"),
    [("-oProxyCommand=evil", "root"), ("admin@cerulean", "root"), ("cerulean", "-oBad"), ("cerulean", "a b")],
)
def test_target_rejects_option_injection(*, host: str, user: str) -> None:
    with pytest.raises(ValueError):
        SshTarget(host=host, user=user)
