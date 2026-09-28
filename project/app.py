from __future__ import annotations

import os
from typing import Any

from homelab_dashboard.ui.dashboard import build_dashboard_snapshot


def main() -> None:
    source_label = os.getenv("HOMELAB_STATUS_SOURCE", "mock").lower()
    if source_label == "mock":
        source_label = "Mock data"
    else:
        source_label = "Live Proxmox"

    snapshot = build_dashboard_snapshot(
        source_label=source_label,
        nodes=[
            {
                "node_id": "node-a",
                "name": "Node A",
                "reported_state": "running",
                "workloads": [
                    {"node_id": "node-a", "workload_id": "vm-1", "name": "api", "kind": "virtual_machine", "reported_state": "running"},
                    {"node_id": "node-a", "workload_id": "ct-1", "name": "db", "kind": "container", "reported_state": "running"},
                ],
            }
        ],
    )
    return snapshot


if __name__ == "__main__":
    main()
