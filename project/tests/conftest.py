from typing import Any

import pytest


@pytest.fixture
def sample_node_payload() -> dict[str, Any]:
    return {
        "node_id": "node-a",
        "name": "Node A",
        "reported_state": "running",
        "workloads": [
            {"node_id": "node-a", "workload_id": "vm-1", "name": "api", "kind": "virtual_machine", "reported_state": "running"},
            {"node_id": "node-a", "workload_id": "ct-1", "name": "db", "kind": "container", "reported_state": "running"},
        ],
    }
