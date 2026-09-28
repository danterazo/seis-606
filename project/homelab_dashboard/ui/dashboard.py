from __future__ import annotations

from typing import Any


def build_dashboard_snapshot(*, source_label: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_nodes = []
    for node in nodes:
        workloads = node.get("workloads") or []
        normalized_nodes.append(
            {
                "node_id": node.get("node_id"),
                "name": node.get("name"),
                "reported_state": node.get("reported_state"),
                "architecture": node.get("architecture"),
                "workloads": workloads,
                "workload_count": len(workloads),
            }
        )

    return {
        "source_label": source_label,
        "node_count": len(normalized_nodes),
        "nodes": normalized_nodes,
    }
