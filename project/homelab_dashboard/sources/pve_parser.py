import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Dict, Final, List, Union

from homelab_dashboard.models import ClusterSnapshot, Guest, GuestKind, GuestState, Node, NodeState, Resources

JsonObject = Mapping[str, object]

_NODE_STATES: Final[Dict[str, NodeState]] = {"online": NodeState.ONLINE, "offline": NodeState.OFFLINE}
_GUEST_KINDS: Final[Dict[str, GuestKind]] = {"qemu": GuestKind.VM, "lxc": GuestKind.CONTAINER}
_GUEST_STATES: Final[Dict[str, GuestState]] = {
    "running": GuestState.RUNNING,
    "stopped": GuestState.STOPPED,
    "paused": GuestState.PAUSED,
}
# Proxmox omits names for guests on unreachable nodes.
_FALLBACK_PREFIX: Final[Dict[GuestKind, str]] = {GuestKind.VM: "VM", GuestKind.CONTAINER: "CT"}


def _number(*, value: object) -> Union[float, None]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _integer(*, value: object) -> Union[int, None]:
    number: Union[float, None] = _number(value=value)
    return None if number is None else int(number)


def _text(*, value: object) -> Union[str, None]:
    return value if isinstance(value, str) and value else None


def _resources(*, row: JsonObject) -> Resources:
    return Resources(
        cpu_ratio=_number(value=row.get("cpu")),
        cpu_cores=_integer(value=row.get("maxcpu")),
        memory_used_bytes=_integer(value=row.get("mem")),
        memory_total_bytes=_integer(value=row.get("maxmem")),
    )


def _parse_guest(*, row: JsonObject) -> Union[Guest, None]:
    kind: Union[GuestKind, None] = _GUEST_KINDS.get(str(row.get("type")))
    vmid: Union[int, None] = _integer(value=row.get("vmid"))
    node: Union[str, None] = _text(value=row.get("node"))
    if kind is None or vmid is None or node is None or row.get("template"):
        return None
    return Guest(
        vmid=vmid,
        name=_text(value=row.get("name")) or f"{_FALLBACK_PREFIX[kind]} {vmid}",
        node=node,
        kind=kind,
        state=_GUEST_STATES.get(str(row.get("status")), GuestState.UNKNOWN),
        resources=_resources(row=row),
    )


def _parse_node(*, row: JsonObject, address: Union[str, None], guests: Sequence[Guest]) -> Union[Node, None]:
    name: Union[str, None] = _text(value=row.get("node"))
    if name is None:
        return None
    state: NodeState = _NODE_STATES.get(str(row.get("status")), NodeState.UNKNOWN)
    reported: Resources = _resources(row=row)
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


def _node_addresses(*, cluster_status: Sequence[JsonObject]) -> Dict[str, str]:
    addresses: Dict[str, str] = {}
    for row in cluster_status:
        name: Union[str, None] = _text(value=row.get("name"))
        address: Union[str, None] = _text(value=row.get("ip"))
        if row.get("type") == "node" and name is not None and address is not None:
            addresses[name] = address
    return addresses


def parse_snapshot(
    *,
    source: str,
    fetched_at: datetime,
    resources: Sequence[JsonObject],
    cluster_status: Sequence[JsonObject],
) -> ClusterSnapshot:
    addresses: Dict[str, str] = _node_addresses(cluster_status=cluster_status)

    guests_by_node: defaultdict[str, List[Guest]] = defaultdict(list)
    for row in resources:
        guest: Union[Guest, None] = _parse_guest(row=row)
        if guest is not None:
            guests_by_node[guest.node].append(guest)

    nodes: List[Node] = []
    for row in resources:
        if row.get("type") != "node":
            continue
        node_name: str = str(row.get("node"))
        parsed: Union[Node, None] = _parse_node(row=row, address=addresses.get(node_name), guests=guests_by_node[node_name])
        if parsed is not None:
            nodes.append(parsed)

    return ClusterSnapshot(
        source=source,
        fetched_at=fetched_at,
        nodes=tuple(sorted(nodes, key=lambda node: node.name)),
    )
