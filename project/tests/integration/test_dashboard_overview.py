from typing import Any, Dict

from homelab_dashboard.ui.dashboard import build_dashboard_snapshot


def test_dashboard_snapshot_includes_label_and_node_counts() -> None:
    snapshot: Dict[str, Any] = build_dashboard_snapshot(
        source_label="Mock data",
        nodes=[
            {
                "node_id": "node-a",
                "name": "Node A",
                "reported_state": "running",
                "workloads": [
                    {"node_id": "node-a", "workload_id": "vm-1", "name": "api", "kind": "virtual_machine", "reported_state": "running"},
                    {"node_id": "node-a", "workload_id": "ct-1", "name": "db", "kind": "container", "reported_state": "running"},
                ],
            },
            {"node_id": "node-b", "name": "Node B", "reported_state": "degraded", "workloads": []},
        ],
    )

    assert snapshot["source_label"] == "Mock data"
    assert snapshot["node_count"] == 2
    assert snapshot["nodes"][0]["name"] == "Node A"
    assert snapshot["nodes"][1]["reported_state"] == "degraded"
    assert snapshot["nodes"][0]["workload_count"] == 2
