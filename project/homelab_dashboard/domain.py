from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Union


@dataclass(kw_only=True)
class Workload:
    node_id: str
    workload_id: str
    name: str
    kind: str
    reported_state: str
    architecture: Union[str, None] = None
    restart_count: int = 0
    reason: Union[str, None] = None
    health: Union[str, None] = None
    last_seen: Union[str, None] = None
    tags: List[str] = field(default_factory=list)


@dataclass(kw_only=True)
class Node:
    node_id: str
    name: str
    reported_state: str
    workloads: List[Workload] = field(default_factory=list)
    architecture: Union[str, None] = None
    connection_state: str = "unknown"
    last_successful_update: Union[str, None] = None
    source_label: Union[str, None] = None
    workload_counts: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.workload_counts = workload_counts_for(node=self)


def normalize_workload(*, value: Union[Mapping[str, Any], Workload]) -> Workload:
    if isinstance(value, Workload):
        return value

    return Workload(
        node_id=str(value.get("node_id") or "unknown"),
        workload_id=str(value.get("workload_id") or value.get("id") or "unknown"),
        name=str(value.get("name") or "unknown"),
        kind=str(value.get("kind") or value.get("type") or "unknown"),
        reported_state=str(value.get("reported_state") or value.get("state") or "unknown"),
        architecture=value.get("architecture"),
        restart_count=int(value.get("restart_count") or 0),
        reason=value.get("reason"),
        health=value.get("health"),
        last_seen=value.get("last_seen"),
        tags=list(value.get("tags") or []),
    )


def normalize_node(*, value: Union[Mapping[str, Any], Node]) -> Node:
    if isinstance(value, Node):
        return value

    workloads: List[Workload] = [normalize_workload(value=item) for item in value.get("workloads") or []]
    return Node(
        node_id=str(value.get("node_id") or value.get("id") or "unknown"),
        name=str(value.get("name") or "unknown"),
        reported_state=str(value.get("reported_state") or value.get("state") or "unknown"),
        workloads=workloads,
        architecture=value.get("architecture"),
        connection_state=str(value.get("connection_state") or "unknown"),
        last_successful_update=value.get("last_successful_update"),
        source_label=value.get("source_label"),
    )


def workload_counts_for(*, node: Union[Node, Mapping[str, Any]]) -> Dict[str, int]:
    node_obj: Node = node if isinstance(node, Node) else normalize_node(value=node)

    counts: Dict[str, int] = {}
    for workload in node_obj.workloads:
        kind: str = workload.kind or "unknown"
        counts[kind] = counts.get(kind, 0) + 1

    if isinstance(node, Node):
        node.workload_counts = counts
    return counts
