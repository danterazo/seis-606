import json
import subprocess

from homelab_dashboard.sources.operator_report import build_operator_report
from homelab_dashboard.sources.proxmox_ssh import build_ssh_report


def test_operator_report_contains_only_the_supplied_node_facts():
    report = build_operator_report()

    assert report["source_label"] == "OPERATOR REPORT"
    assert report["is_live"] is False
    assert report["known_up_count"] == 1
    assert report["other_nodes_state"] == "down"
    assert report["other_node_identities_known"] is False
    assert report["nodes"] == [
        {
            "node_id": "cerulean",
            "name": "Cerulean",
            "address": "192.168.20.43",
            "role": "PVE HOST",
            "reported_state": "up",
            "architecture": None,
            "cpu_percent": None,
            "memory_percent": None,
            "workloads": None,
        }
    ]


def test_ssh_report_normalizes_live_nodes_and_guest_counts():
    responses = {
        "node": [
            {"node": "cerulean", "status": "online", "cpu": 0.25, "mem": 8, "maxmem": 16},
            {"node": "violet", "status": "offline", "cpu": None, "mem": None, "maxmem": 8},
        ],
        "vm": [
            {"node": "cerulean", "type": "qemu", "vmid": 101},
            {"node": "cerulean", "type": "lxc", "vmid": 201},
        ],
    }

    def runner(command, **kwargs):
        resource_type = command[command.index("--type") + 1]
        return subprocess.CompletedProcess(command, 0, json.dumps(responses[resource_type]), "")

    report = build_ssh_report(target="192.168.20.43", runner=runner)

    assert report["is_live"] is True
    assert report["source_label"] == "LIVE PVE / SSH"
    assert report["known_up_count"] == 1
    assert report["down_count"] == 1
    assert report["primary_node"]["cpu_percent"] == 25
    assert report["primary_node"]["memory_percent"] == 50
    assert report["primary_node"]["workloads"] == {"VM": 1, "LXC": 1}


def test_ssh_report_requires_batch_mode_and_public_key_auth():
    commands = []

    def runner(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "[]", "")

    try:
        build_ssh_report(target="192.168.20.43", runner=runner)
    except RuntimeError:
        pass

    assert len(commands) == 2
    for command, kwargs in commands:
        assert "-oBatchMode=yes" in command
        assert "-oPreferredAuthentications=publickey" in command
        assert "-oPasswordAuthentication=no" in command
        assert "-oStrictHostKeyChecking=yes" in command
        assert kwargs["timeout"] == 12