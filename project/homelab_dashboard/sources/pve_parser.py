import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Final, Optional

from homelab_dashboard.models import ClusterSnapshot, Guest, GuestKind, GuestState, GuestTag, Node, NodeState, Resources, TrackedTag
from homelab_dashboard.sources.json_values import as_integer, as_number, as_text

JsonObject = Mapping[str, object]

_NODE_STATES: Final[dict[str, NodeState]] = {"online": NodeState.ONLINE, "offline": NodeState.OFFLINE}
_GUEST_KINDS: Final[dict[str, GuestKind]] = {"qemu": GuestKind.VM, "lxc": GuestKind.CONTAINER}
_GUEST_STATES: Final[dict[str, GuestState]] = {
    "running": GuestState.RUNNING,
    "stopped": GuestState.STOPPED,
    "paused": GuestState.PAUSED,
}
# the Proxmox API omits names for guests on unreachable nodes
_FALLBACK_PREFIX: Final[dict[GuestKind, str]] = {GuestKind.VM: "VM", GuestKind.CONTAINER: "LXC"}


_HEX_COLOR: Final[re.Pattern[str]] = re.compile(r"[0-9a-fA-F]{6}")
# only these tags are shown, in this order; add a row to track another. Colors apply when the Proxmox web UI has none for the tag
TRACKED_TAGS: Final[tuple[TrackedTag, ...]] = (
    TrackedTag(name="docker", letter="K", default_color="#2b7fd6"),
    TrackedTag(name="gpu", letter="G", default_color="#8e55c9"),
    TrackedTag(name="primary", letter="I", default_color="#0f8f94"),
    TrackedTag(name="secondary", letter="II", default_color="#a3174f"),
)
# the environment comes from the guest's resource pool, not from tags: members of these pools are prod, everything else is dev
PROD_POOLS: Final[frozenset[str]] = frozenset({"prod", "dense"})
PROD_TAG: Final[TrackedTag] = TrackedTag(name="prod", letter="P", default_color="#d64545")
DEV_TAG: Final[TrackedTag] = TrackedTag(name="dev", letter="D", default_color="#2e9e4f")
_TRACKED_BY_NAME: Final[dict[str, TrackedTag]] = {tracked.name: tracked for tracked in TRACKED_TAGS}
_TRACKED_ORDER: Final[dict[str, int]] = {tracked.name: position for position, tracked in enumerate(TRACKED_TAGS)}


def _contrast_text(*, color: str) -> str:
    red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
    return "#000000" if (red * 299 + green * 587 + blue * 114) / 1000 > 150 else "#ffffff"


def _tag_style_colors(*, cluster_options: Optional[JsonObject]) -> dict[str, tuple[str, Optional[str]]]:
    """Reads `tag-style` (`color-map=name:bg[:fg];...`), which pvesh may return as a string or an object."""
    style: object = cluster_options.get("tag-style") if cluster_options is not None else None
    color_map: object = None
    if isinstance(style, Mapping):
        color_map = style.get("color-map")
    elif isinstance(style, str):
        color_map = next((part[len("color-map=") :] for part in style.split(",") if part.startswith("color-map=")), None)
    entries: list[str] = [str(item) for item in color_map] if isinstance(color_map, list) else str(color_map or "").split(";")
    colors: dict[str, tuple[str, Optional[str]]] = {}
    for entry in entries:
        name, *shades = entry.strip().split(":")
        if name and shades and _HEX_COLOR.fullmatch(shades[0]):
            foreground: Optional[str] = f"#{shades[1]}" if len(shades) > 1 and _HEX_COLOR.fullmatch(shades[1]) else None
            colors[name.lower()] = (f"#{shades[0].lower()}", foreground.lower() if foreground else None)
    return colors


def _parse_tags(*, row: JsonObject, colors: Mapping[str, tuple[str, Optional[str]]]) -> tuple[GuestTag, ...]:
    is_prod: bool = str(row.get("pool") or "").lower() in PROD_POOLS
    environment: TrackedTag = PROD_TAG if is_prod else DEV_TAG
    names: list[str] = sorted(
        (name for name in re.split(r"[;, ]+", str(row.get("tags") or "")) if name.lower() in _TRACKED_ORDER),
        key=lambda name: _TRACKED_ORDER[name.lower()],
    )
    tracked_tags: list[TrackedTag] = [environment, *(_TRACKED_BY_NAME[name.lower()] for name in names)]
    tags: list[GuestTag] = []
    for tracked in tracked_tags:
        background, foreground = colors.get(tracked.name, (tracked.default_color, None))
        tags.append(GuestTag(name=tracked.name, letter=tracked.letter, color=background, text_color=foreground or _contrast_text(color=background)))
    return tuple(tags)


def _resources(*, row: JsonObject) -> Resources:
    return Resources(
        cpu_ratio=as_number(value=row.get("cpu")),
        cpu_cores=as_integer(value=row.get("maxcpu")),
        memory_used_bytes=as_integer(value=row.get("mem")),
        memory_total_bytes=as_integer(value=row.get("maxmem")),
    )


def _parse_guest(*, row: JsonObject, tag_colors: Mapping[str, tuple[str, Optional[str]]]) -> Optional[Guest]:
    kind: Optional[GuestKind] = _GUEST_KINDS.get(str(row.get("type")))
    vmid: Optional[int] = as_integer(value=row.get("vmid"))
    node: Optional[str] = as_text(value=row.get("node"))
    if kind is None or vmid is None or node is None or row.get("template"):
        return None
    return Guest(
        vmid=vmid,
        name=as_text(value=row.get("name")) or f"{_FALLBACK_PREFIX[kind]} {vmid}",
        node=node,
        kind=kind,
        state=_GUEST_STATES.get(str(row.get("status")), GuestState.UNKNOWN),
        resources=_resources(row=row),
        tags=_parse_tags(row=row, colors=tag_colors),
    )


def _parse_node(
    *, row: JsonObject, address: Optional[str], guests: Sequence[Guest], online: bool, local_resources: Optional[Resources]
) -> Optional[Node]:
    name: Optional[str] = as_text(value=row.get("node"))
    if name is None:
        return None
    state: NodeState = NodeState.ONLINE if online else _NODE_STATES.get(str(row.get("status")), NodeState.UNKNOWN)
    reported: Resources = _resources(row=row)
    if local_resources is not None and reported.memory_used_bytes is None:
        reported = local_resources
    # an unreachable node's cached usage figures are stale, so only its capacity is kept
    resources: Resources = (
        reported if state is NodeState.ONLINE else Resources(cpu_cores=reported.cpu_cores, memory_total_bytes=reported.memory_total_bytes)
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
        name: Optional[str] = as_text(value=row.get("name"))
        address: Optional[str] = as_text(value=row.get("ip"))
        if row.get("type") == "node" and name is not None and address is not None:
            addresses[name] = address
    return addresses


def _cluster_quorum(*, cluster_status: Sequence[JsonObject]) -> Optional[bool]:
    for row in cluster_status:
        if row.get("type") != "cluster":
            continue
        quorate: object = row.get("quorate")
        if isinstance(quorate, bool):
            return quorate
        if isinstance(quorate, int) and quorate in (0, 1):
            return quorate == 1
    return None


def parse_quorum_details(*, status_output: str) -> Optional[str]:
    summary_fields: Final[frozenset[str]] = frozenset(
        {
            "Name",
            "Config Version",
            "Transport",
            "Secure auth",
            "Quorum provider",
            "Nodes",
            "Node ID",
            "Ring ID",
            "Quorate",
            "Expected votes",
            "Highest expected",
            "Total votes",
            "Quorum",
            "Flags",
        }
    )
    details: list[str] = []
    membership_header: Optional[str] = None
    qdevice_rows: list[str] = []
    in_membership: bool = False

    for raw_line in status_output.splitlines():
        line: str = raw_line.strip()
        if not line:
            continue
        if in_membership:
            if membership_header is not None and "qdevice" in membership_header.lower() and "qdevice" in line.lower():
                qdevice_rows.append(re.sub("qdevice", "QDevice", line, flags=re.IGNORECASE))
            continue
        if line.lower().startswith("nodeid") and "votes" in line.lower():
            membership_header = re.sub(r"\bnodeid\b", "NodeID", line, flags=re.IGNORECASE)
            in_membership = True
            continue
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", maxsplit=1))
        if key in summary_fields and value:
            normalized_value: str = re.sub("qdevice", "QDevice", value, flags=re.IGNORECASE)
            details.append(f"{key}: {normalized_value}")

    if not details:
        return None
    if membership_header is None or "qdevice" not in membership_header.lower():
        details.append("QDevice: Not configured")
    else:
        details.extend(("QDevice membership:", re.sub("qdevice", "QDevice", membership_header, flags=re.IGNORECASE)))
        details.extend(qdevice_rows or ["No QDevice membership row reported"])
    return "\n".join(details)


def _local_resources(*, status: Optional[JsonObject]) -> Optional[Resources]:
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
    local_status: Optional[JsonObject] = None,
    cluster_options: Optional[JsonObject] = None,
    quorum_details: Optional[str] = None,
) -> ClusterSnapshot:
    addresses: dict[str, str] = _node_addresses(cluster_status=cluster_status)
    # without quorum the resources list marks even the reachable node "unknown"; the cluster status still knows it is up
    online_names: set[str] = {str(row.get("name")) for row in cluster_status if row.get("type") == "node" and row.get("online") == 1}
    local_names: set[str] = {str(row.get("name")) for row in cluster_status if row.get("type") == "node" and row.get("local") == 1}
    local_resources: Optional[Resources] = _local_resources(status=local_status)

    tag_colors: dict[str, tuple[str, Optional[str]]] = _tag_style_colors(cluster_options=cluster_options)
    guests_by_node: defaultdict[str, list[Guest]] = defaultdict(list)
    for row in resources:
        guest: Optional[Guest] = _parse_guest(row=row, tag_colors=tag_colors)
        if guest is not None:
            guests_by_node[guest.node].append(guest)

    nodes: list[Node] = []
    for row in resources:
        if row.get("type") != "node":
            continue
        node_name: str = str(row.get("node"))
        parsed: Optional[Node] = _parse_node(
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
        quorate=_cluster_quorum(cluster_status=cluster_status),
        quorum_details=quorum_details,
    )
