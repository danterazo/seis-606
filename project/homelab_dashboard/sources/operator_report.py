from __future__ import annotations


def build_operator_report() -> dict[str, object]:
    return {
        "source_label": "OPERATOR REPORT",
        "is_live": False,
        "nodes": [
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
        ],
        "known_up_count": 1,
        "other_nodes_state": "down",
        "other_node_identities_known": False,
    }