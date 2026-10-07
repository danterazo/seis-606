import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Final

from homelab_dashboard.models import ClusterSnapshot, Guest, GuestKind, GuestState, Node, NodeState, Resources

type JsonObject = Mapping[str, object]

_NODE_STATES: Final = {"online": NodeState.ONLINE, "offline": NodeState.OFFLINE}
_GUEST_KINDS: Final = {"qemu": GuestKind.VM, "lxc": GuestKind.CONTAINER}
_GUEST_STATES: Final = {"running": GuestState.RUNNING, "stopped": GuestState.STOPPED, "paused": GuestState.PAUSED}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return float(value)


def _integer(value: object) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _resources(*, row: JsonObject) -> Resources:
    return Resources(
        cpu_ratio=_number(row.get("cpu")),
        memory_used_bytes=_integer(row.get("mem")),
        memory_total_bytes=_integer(row.get("maxmem")),
    )


def _parse_guest(*, row: JsonObject) -> Guest | None:
    kind = _GUEST_KINDS.get(str(row.get("type")))
    vmid = _integer(row.get("vmid"))
    node = _text(row.get("node"))
    if kind is None or vmid is None or node is None or row.get("template"):
        return None
    return Guest(
        vmid=vmid,
        name=_text(row.get("name")) or f"{kind.value}-{vmid}",
        node=node,
        kind=kind,
        state=_GUEST_STATES.get(str(row.get("status")), GuestState.UNKNOWN),
        resources=_resources(row=row),
    )


def _parse_node(*, row: JsonObject, address: str | None, guests: Sequence[Guest]) -> Node | None:
    name = _text(row.get("node"))
    if name is None:
        return None
    state = _NODE_STATES.get(str(row.get("status")), NodeState.UNKNOWN)
    reported = _resources(row=row)
    # An unreachable node's cached usage figures are stale, so only its capacity is kept.
    resources = reported if state is NodeState.ONLINE else Resources(memory_total_bytes=reported.memory_total_bytes)
    return Node(name=name, state=state, address=address, resources=resources, guests=tuple(sorted(guests, key=lambda guest: guest.vmid)))


def parse_snapshot(
    *,
    source: str,
    fetched_at: datetime,
    resources: Sequence[JsonObject],
    cluster_status: Sequence[JsonObject],
) -> ClusterSnapshot:
    addresses = {name: address for row in cluster_status if row.get("type") == "node" and (name := _text(row.get("name"))) and (address := _text(row.get("ip")))}

    guests_by_node: defaultdict[str, list[Guest]] = defaultdict(list)
    for row in resources:
        if (guest := _parse_guest(row=row)) is not None:
            guests_by_node[guest.node].append(guest)

    nodes = [
        node
        for row in resources
        if row.get("type") == "node"
        and (node := _parse_node(row=row, address=addresses.get(str(row.get("node"))), guests=guests_by_node[str(row.get("node"))])) is not None
    ]
    return ClusterSnapshot(source=source, fetched_at=fetched_at, nodes=tuple(sorted(nodes, key=lambda node: node.name)))
