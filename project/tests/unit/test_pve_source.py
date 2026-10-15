import json
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Final, Optional

import pytest
from homelab_dashboard.config import Settings
from homelab_dashboard.models import ClusterSnapshot, GuestKind, GuestState, GuestTag, Node, NodeState
from homelab_dashboard.sources.base import StatusSourceError
from homelab_dashboard.sources.proxmox_ssh import QUORUM_STATUS_MARKER, SSH_EXECUTABLE, SSH_OPTIONS, CommandRunner, ProxmoxSshSource, SshTarget

FIXED_TIME: Final[datetime] = datetime(year=2026, month=10, day=6, hour=12, minute=0, tzinfo=UTC)

RESOURCES: Final[list[dict[str, Any]]] = [
    {"type": "node", "node": "cerulean", "status": "online", "cpu": 0.25, "mem": 8, "maxmem": 16},
    {"type": "node", "node": "violet", "status": "offline", "cpu": 0.9, "mem": 4, "maxmem": 8},
    {"type": "qemu", "vmid": 101, "node": "cerulean", "name": "web", "status": "running", "cpu": 0.1, "mem": 2, "maxmem": 4},
    {"type": "lxc", "vmid": 201, "node": "cerulean", "name": "caddy", "status": "stopped"},
    {"type": "qemu", "vmid": 900, "node": "cerulean", "name": "base", "status": "stopped", "template": 1},
    {"type": "storage", "id": "storage/cerulean/local"},
]
CLUSTER_STATUS: Final[list[dict[str, Any]]] = [
    {"type": "cluster", "name": "home", "quorate": 1},
    {"type": "node", "name": "cerulean", "ip": "192.168.20.43"},
]


def make_runner(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    calls: Optional[list[Sequence[str]]] = None,
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
    calls: Optional[list[Sequence[str]]] = None,
) -> ProxmoxSshSource:
    return ProxmoxSshSource(
        target=SshTarget(host="cerulean"),
        runner=make_runner(stdout=stdout, stderr=stderr, returncode=returncode, calls=calls),
        clock=lambda: FIXED_TIME,
    )


def documents(*, resources: Sequence[dict[str, Any]], cluster_status: Sequence[dict[str, Any]]) -> str:
    return json.dumps(list(resources)) + "\n" + json.dumps(list(cluster_status))


def test_fetch_parses_nodes_guests_and_addresses() -> None:
    snapshot: ClusterSnapshot = make_source(stdout=documents(resources=RESOURCES, cluster_status=CLUSTER_STATUS)).fetch()

    cerulean: Node = snapshot.nodes[0]
    _violet: Node = snapshot.nodes[1]
    assert (cerulean.name, cerulean.state, cerulean.address) == ("cerulean", NodeState.ONLINE, "100.100.20.43")
    assert cerulean.resources.cpu_ratio == 0.25
    assert [(guest.vmid, guest.kind, guest.state) for guest in cerulean.guests] == [
        (101, GuestKind.VM, GuestState.RUNNING),
        (201, GuestKind.CONTAINER, GuestState.STOPPED),
    ]
    assert snapshot.fetched_at == FIXED_TIME
    assert snapshot.quorate is True


def test_cluster_quorum_is_false_when_proxmox_reports_no_quorum() -> None:
    cluster_status: list[dict[str, Any]] = [{"type": "cluster", "name": "home", "quorate": 0}]

    snapshot: ClusterSnapshot = make_source(stdout=documents(resources=RESOURCES, cluster_status=cluster_status)).fetch()

    assert snapshot.quorate is False


def test_cluster_quorum_is_unknown_when_proxmox_does_not_report_it() -> None:
    snapshot: ClusterSnapshot = make_source(stdout=documents(resources=RESOURCES, cluster_status=[])).fetch()

    assert snapshot.quorate is None


def test_fetch_parses_pvecm_vote_and_qdevice_details() -> None:
    pvecm_status: str = """Cluster information
Name: home
Config Version: 3
Transport: knet
Secure auth: on

Quorum information
Quorum provider: corosync_votequorum
Nodes: 3
Node ID: 0x00000001
Quorate: Yes

Votequorum information
Expected votes: 3
Highest expected: 3
Total votes: 3
Quorum: 2
Flags: Quorate Qdevice

Membership information
Nodeid Votes Qdevice Name
0x00000001 1 A,V,NMW 192.168.1.10 (local)
0x00000000 1 Qdevice
"""
    stdout: str = documents(resources=RESOURCES, cluster_status=CLUSTER_STATUS) + f"\nnull\nnull\n{QUORUM_STATUS_MARKER}\n{pvecm_status}"

    snapshot: ClusterSnapshot = make_source(stdout=stdout).fetch()

    assert snapshot.quorum_details is not None
    assert "Expected votes: 3" in snapshot.quorum_details
    assert "Total votes: 3" in snapshot.quorum_details
    assert "Quorum: 2" in snapshot.quorum_details
    assert "Flags: Quorate QDevice" in snapshot.quorum_details
    assert "NodeID Votes QDevice Name" in snapshot.quorum_details
    assert "0x00000000 1 QDevice" in snapshot.quorum_details


def test_only_tracked_guest_tags_are_kept_and_use_pve_colors() -> None:
    resources: list[dict[str, Any]] = [
        {"type": "node", "node": "cerulean", "status": "online"},
        {
            "type": "lxc",
            "vmid": 201,
            "node": "cerulean",
            "name": "caddy",
            "status": "running",
            "pool": "prod",
            "tags": "secondary;dev;gpu;docker;lab;alt-arch",
        },
    ]
    options: dict[str, Any] = {"tag-style": "color-map=dev:FFFF00;lab:112233:EEEEEE,shape=full"}
    stdout: str = documents(resources=resources, cluster_status=[]) + "\nnull\n" + json.dumps(options)

    tags: tuple[GuestTag, ...] = make_source(stdout=stdout).fetch().nodes[0].guests[0].tags

    assert [(tag.name, tag.letter, tag.color, tag.text_color) for tag in tags] == [
        ("prod", "P", "#d64545", "#ffffff"),
        ("docker", "K", "#2b7fd6", "#ffffff"),
        ("gpu", "G", "#8e55c9", "#ffffff"),
        ("secondary", "II", "#a3174f", "#ffffff"),
    ]


def test_dense_pool_guest_is_prod() -> None:
    resources: list[dict[str, Any]] = [
        {"type": "node", "node": "cerulean", "status": "online"},
        {"type": "qemu", "vmid": 170, "node": "cerulean", "name": "win", "status": "running", "pool": "dense"},
    ]
    stdout: str = documents(resources=resources, cluster_status=[])

    tags: tuple[GuestTag, ...] = make_source(stdout=stdout).fetch().nodes[0].guests[0].tags

    assert [tag.name for tag in tags] == ["prod"]


def test_guest_outside_prod_pools_is_dev_with_pve_color() -> None:
    resources: list[dict[str, Any]] = [
        {"type": "node", "node": "cerulean", "status": "online"},
        {"type": "lxc", "vmid": 201, "node": "cerulean", "name": "caddy", "status": "running", "pool": "other", "tags": "prod"},
    ]
    options: dict[str, Any] = {"tag-style": "color-map=dev:FFFF00"}
    stdout: str = documents(resources=resources, cluster_status=[]) + "\nnull\n" + json.dumps(options)

    tags: tuple[GuestTag, ...] = make_source(stdout=stdout).fetch().nodes[0].guests[0].tags

    assert [(tag.name, tag.color) for tag in tags] == [("dev", "#ffff00")]


def test_offline_node_drops_stale_usage_but_keeps_capacity() -> None:
    snapshot: ClusterSnapshot = make_source(stdout=documents(resources=RESOURCES, cluster_status=CLUSTER_STATUS)).fetch()

    violet: Node = snapshot.nodes[1]
    assert violet.state is NodeState.OFFLINE
    assert violet.address is None
    assert violet.resources.cpu_ratio is None
    assert violet.resources.memory_used_bytes is None
    assert violet.resources.memory_total_bytes == 8


def test_missing_readings_stay_unknown_instead_of_zero() -> None:
    resources: list[dict[str, Any]] = [{"type": "node", "node": "cerulean", "status": "online"}]
    snapshot: ClusterSnapshot = make_source(stdout=documents(resources=resources, cluster_status=[])).fetch()

    assert snapshot.nodes[0].resources.cpu_ratio is None
    assert snapshot.nodes[0].resources.memory_total_bytes is None


def test_unrecognised_status_is_reported_as_unknown() -> None:
    resources: list[dict[str, Any]] = [{"type": "node", "node": "cerulean", "status": "mystery"}]
    snapshot: ClusterSnapshot = make_source(stdout=documents(resources=resources, cluster_status=[])).fetch()

    assert snapshot.nodes[0].state is NodeState.UNKNOWN


def test_guests_without_names_get_a_short_fallback() -> None:
    resources: list[dict[str, Any]] = [
        {"type": "node", "node": "violet", "status": "offline"},
        {"type": "lxc", "vmid": 7, "node": "violet", "status": "unknown"},
    ]
    snapshot: ClusterSnapshot = make_source(stdout=documents(resources=resources, cluster_status=[])).fetch()

    assert snapshot.nodes[0].guests[0].name == "LXC 7"


def test_ssh_command_never_prompts_or_relaxes_host_checking() -> None:
    calls: list[Sequence[str]] = []
    make_source(stdout="[][]", calls=calls).fetch()

    command: Sequence[str] = calls[0]
    assert command[0] == SSH_EXECUTABLE
    assert set(SSH_OPTIONS) <= set(command)
    assert "-oStrictHostKeyChecking=yes" in command
    assert command[-1].count("pvesh get") == 4
    assert "pvecm status" in command[-1]


def test_reachable_node_stays_online_and_keeps_its_figures_without_quorum() -> None:
    resources: list[dict[str, Any]] = [
        {"type": "node", "node": "cerulean", "status": "unknown"},
        {"type": "node", "node": "kex", "status": "unknown"},
    ]
    cluster_status: list[dict[str, Any]] = [
        {"type": "node", "name": "cerulean", "ip": "10.0.0.2", "online": 1, "local": 1},
        {"type": "node", "name": "kex", "ip": "10.0.0.1", "online": 0, "local": 0},
    ]
    local_status: dict[str, Any] = {"cpu": 0.25, "cpuinfo": {"cpus": 4}, "memory": {"used": 1, "total": 4}}
    stdout: str = documents(resources=resources, cluster_status=cluster_status) + "\n" + json.dumps(local_status)

    snapshot: ClusterSnapshot = make_source(stdout=stdout).fetch()
    cerulean: Node = snapshot.nodes[0]
    kex: Node = snapshot.nodes[1]

    assert (cerulean.state, cerulean.resources.cpu_cores, cerulean.resources.memory_used_bytes) == (NodeState.ONLINE, 4, 1)
    assert kex.state is not NodeState.ONLINE and kex.resources.memory_used_bytes is None


def test_core_counts_are_kept_for_guests_and_for_offline_nodes() -> None:
    resources: list[dict[str, Any]] = [
        {"type": "node", "node": "cerulean", "status": "online", "maxcpu": 4, "cpu": 0.5},
        {"type": "node", "node": "violet", "status": "offline", "maxcpu": 8, "cpu": 0.9},
        {"type": "lxc", "vmid": 100, "node": "cerulean", "name": "pocket-id", "status": "running", "maxcpu": 2, "cpu": 0.25},
        {"type": "lxc", "vmid": 101, "node": "cerulean", "name": "no-cores", "status": "running"},
    ]
    snapshot: ClusterSnapshot = make_source(stdout=documents(resources=resources, cluster_status=[])).fetch()

    cerulean: Node = snapshot.nodes[0]
    violet: Node = snapshot.nodes[1]
    assert cerulean.resources.cpu_cores == 4
    assert violet.resources.cpu_cores == 8
    assert violet.resources.cpu_ratio is None
    assert [guest.resources.cpu_cores for guest in cerulean.guests] == [2, None]


def test_connections_use_root_by_default() -> None:
    calls: list[Sequence[str]] = []
    make_source(stdout="[][]", calls=calls).fetch()

    assert "root@cerulean" in calls[0]
    assert SshTarget(host="100.100.20.43").destination == "root@100.100.20.43"


def test_settings_default_to_root_on_cerulean_tailscale_ip() -> None:
    settings: Settings = Settings.from_env(environ={})

    assert (settings.ssh_user, settings.ssh_host) == ("root", "100.100.20.43")


@pytest.mark.parametrize(
    argnames=("stderr", "expected"),
    argvalues=[
        ("Host key verification failed.", "known_hosts"),
        ("root@x: Permission denied (publickey).", "authentication"),
        ("ssh: connect to host x port 22: Connection refused", "refused"),
    ],
)
def test_failures_become_safe_messages(*, stderr: str, expected: str) -> None:
    with pytest.raises(expected_exception=StatusSourceError, match=expected):
        make_source(stderr=stderr, returncode=255).fetch()


def test_malformed_output_is_rejected() -> None:
    with pytest.raises(expected_exception=StatusSourceError):
        make_source(stdout="not json").fetch()


@pytest.mark.parametrize(
    argnames=("host", "user"),
    argvalues=[("-oProxyCommand=evil", "root"), ("admin@cerulean", "root"), ("cerulean", "-oBad"), ("cerulean", "a b")],
)
def test_target_rejects_option_injection(*, host: str, user: str) -> None:
    with pytest.raises(expected_exception=ValueError):
        SshTarget(host=host, user=user)
