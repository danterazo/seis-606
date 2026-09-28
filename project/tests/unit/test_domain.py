from homelab_dashboard.domain import Node, Workload, workload_counts_for


def test_workload_counts_are_derived_from_returned_workloads():
    node = Node(
        node_id="node-a",
        name="Node A",
        reported_state="running",
        workloads=[
            Workload(node_id="node-a", workload_id="vm-1", name="web", kind="virtual_machine", reported_state="running"),
            Workload(node_id="node-a", workload_id="vm-2", name="web", kind="virtual_machine", reported_state="stopped"),
            Workload(node_id="node-a", workload_id="ct-1", name="db", kind="container", reported_state="running"),
        ],
    )

    counts = workload_counts_for(node)

    assert counts == {"virtual_machine": 2, "container": 1}
    assert node.workload_counts == counts


def test_duplicate_names_are_kept_distinct_by_node():
    nodes = [
        Node(node_id="node-a", name="Node A", reported_state="running", workloads=[Workload(node_id="node-a", workload_id="vm-a", name="api", kind="virtual_machine", reported_state="running")]),
        Node(node_id="node-b", name="Node B", reported_state="running", workloads=[Workload(node_id="node-b", workload_id="vm-b", name="api", kind="virtual_machine", reported_state="running")]),
    ]

    names = {workload.name for node in nodes for workload in node.workloads}
    assert len(names) == 1
    assert [node.node_id for node in nodes] == ["node-a", "node-b"]
