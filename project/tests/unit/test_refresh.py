from homelab_dashboard.domain import Node


def test_node_identity_is_preserved_when_offline() -> None:
    node: Node = Node(node_id="node-a", name="Node A", reported_state="offline", connection_state="offline")

    assert node.node_id == "node-a"
    assert node.name == "Node A"
    assert node.connection_state == "offline"
