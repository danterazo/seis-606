from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Workload:
    node_id: str
    workload_id: str
    name: str
    kind: str
    reported_state: str
    architecture: str | None = None
    restart_count: int = 0
    reason: str | None = None
    health: str | None = None
    last_seen: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class Node:
    node_id: str
    name: str
    reported_state: str
    workloads: list[Workload] = field(default_factory=list)
    architecture: str | None = None
    connection_state: str = "unknown"
    last_successful_update: str | None = None
    source_label: str | None = None
    workload_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.workload_counts = workload_counts_for(self)


def normalize_workload(value: dict[str, Any] | Workload) -> Workload:
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


def normalize_node(value: dict[str, Any] | Node) -> Node:
    if isinstance(value, Node):
        return value

    workloads = [normalize_workload(item) for item in value.get("workloads") or []]
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


def workload_counts_for(node: Node | dict[str, Any]) -> dict[str, int]:
    if isinstance(node, dict):
        node_obj = normalize_node(node)
    else:
        node_obj = node

    counts: dict[str, int] = {}
    for workload in node_obj.workloads:
        kind = workload.kind or "unknown"
        counts[kind] = counts.get(kind, 0) + 1

    if isinstance(node, Node):
        node.workload_counts = counts
    return counts
