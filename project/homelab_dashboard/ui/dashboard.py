from collections.abc import Mapping, Sequence
from typing import Any


def build_dashboard_snapshot(*, source_label: str, nodes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized_nodes: list[dict[str, Any]] = []
    for node in nodes:
        workloads: list[Any] = list(node.get("workloads") or [])
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
