from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Final

from homelab_dashboard.models import ClusterSnapshot, Guest, GuestKind, GuestState, Node, NodeState, Resources
from homelab_dashboard.sources.json_values import as_integer, as_number, as_text

JsonObject = Mapping[str, object]

_NODE_STATES: Final[dict[str, NodeState]] = {"online": NodeState.ONLINE, "offline": NodeState.OFFLINE}
_GUEST_KINDS: Final[dict[str, GuestKind]] = {"qemu": GuestKind.VM, "lxc": GuestKind.CONTAINER}
_GUEST_STATES: Final[dict[str, GuestState]] = {
    "running": GuestState.RUNNING,
    "stopped": GuestState.STOPPED,
    "paused": GuestState.PAUSED,
}
# Proxmox omits names for guests on unreachable nodes.
_FALLBACK_PREFIX: Final[dict[GuestKind, str]] = {GuestKind.VM: "VM", GuestKind.CONTAINER: "LXC"}


def _resources(*, row: JsonObject) -> Resources:
    return Resources(
        cpu_ratio=as_number(value=row.get("cpu")),
        cpu_cores=as_integer(value=row.get("maxcpu")),
        memory_used_bytes=as_integer(value=row.get("mem")),
        memory_total_bytes=as_integer(value=row.get("maxmem")),
    )


def _parse_guest(*, row: JsonObject) -> Guest | None:
    kind: GuestKind | None = _GUEST_KINDS.get(str(row.get("type")))
    vmid: int | None = as_integer(value=row.get("vmid"))
    node: str | None = as_text(value=row.get("node"))
    if kind is None or vmid is None or node is None or row.get("template"):
        return None
    return Guest(
        vmid=vmid,
        name=as_text(value=row.get("name")) or f"{_FALLBACK_PREFIX[kind]} {vmid}",
        node=node,
        kind=kind,
        state=_GUEST_STATES.get(str(row.get("status")), GuestState.UNKNOWN),
        resources=_resources(row=row),
    )


def _parse_node(
    *, row: JsonObject, address: str | None, guests: Sequence[Guest], online: bool, local_resources: Resources | None
) -> Node | None:
    name: str | None = as_text(value=row.get("node"))
    if name is None:
        return None
    state: NodeState = NodeState.ONLINE if online else _NODE_STATES.get(str(row.get("status")), NodeState.UNKNOWN)
    reported: Resources = _resources(row=row)
    if local_resources is not None and reported.memory_used_bytes is None:
        reported = local_resources
    # An unreachable node's cached usage figures are stale, so only its capacity is kept.
    resources: Resources = (
        reported
        if state is NodeState.ONLINE
        else Resources(cpu_cores=reported.cpu_cores, memory_total_bytes=reported.memory_total_bytes)
    )
    return Node(
        name=name,
        state=state,
        address=address,
        resources=resources,
        guests=tuple(sorted(guests, key=lambda guest: guest.vmid)),
    )


def _node_addresses(*, cluster_status: Sequence[JsonObject]) -> dict[str, str]:
    addresses: dict[str, str] = {}
    for row in cluster_status:
        name: str | None = as_text(value=row.get("name"))
        address: str | None = as_text(value=row.get("ip"))
        if row.get("type") == "node" and name is not None and address is not None:
            addresses[name] = address
    return addresses


def _local_resources(*, status: JsonObject | None) -> Resources | None:
    if status is None:
        return None
    memory: object = status.get("memory")
    cpuinfo: object = status.get("cpuinfo")
    return Resources(
        cpu_ratio=as_number(value=status.get("cpu")),
        cpu_cores=as_integer(value=cpuinfo.get("cpus")) if isinstance(cpuinfo, Mapping) else None,
        memory_used_bytes=as_integer(value=memory.get("used")) if isinstance(memory, Mapping) else None,
        memory_total_bytes=as_integer(value=memory.get("total")) if isinstance(memory, Mapping) else None,
    )


def parse_snapshot(
    *,
    source: str,
    fetched_at: datetime,
    resources: Sequence[JsonObject],
    cluster_status: Sequence[JsonObject],
    local_status: JsonObject | None = None,
) -> ClusterSnapshot:
    addresses: dict[str, str] = _node_addresses(cluster_status=cluster_status)
    # Without quorum the resources list marks even the reachable node "unknown"; the cluster status still knows it is up.
    online_names: set[str] = {str(row.get("name")) for row in cluster_status if row.get("type") == "node" and row.get("online") == 1}
    local_names: set[str] = {str(row.get("name")) for row in cluster_status if row.get("type") == "node" and row.get("local") == 1}
    local_resources: Resources | None = _local_resources(status=local_status)

    guests_by_node: defaultdict[str, list[Guest]] = defaultdict(list)
    for row in resources:
        guest: Guest | None = _parse_guest(row=row)
        if guest is not None:
            guests_by_node[guest.node].append(guest)

    nodes: list[Node] = []
    for row in resources:
        if row.get("type") != "node":
            continue
        node_name: str = str(row.get("node"))
        parsed: Node | None = _parse_node(
            row=row,
            address=addresses.get(node_name),
            guests=guests_by_node[node_name],
            online=node_name in online_names,
            local_resources=local_resources if node_name in local_names else None,
        )
        if parsed is not None:
            nodes.append(parsed)

    return ClusterSnapshot(
        source=source,
        fetched_at=fetched_at,
        nodes=tuple(sorted(nodes, key=lambda node: node.name)),
    )
