import zlib
from dataclasses import dataclass
from typing import Dict, Final, Optional, Tuple


@dataclass(frozen=True, slots=True, kw_only=True)
class NodeProfile:
    display_name: str
    # One letter for the guest badge; set by hand because Kex and Kveikur both start with K.
    initial: str
    color: str
    rank: int
    # When set, shown instead of whatever Proxmox reports (offline nodes report none).
    address: Optional[str] = None


NODE_PROFILES: Final[Dict[str, NodeProfile]] = {
    "kex": NodeProfile(display_name="Kex", initial="K", color="#c62839", rank=0, address="192.168.20.42"),
    "cerulean": NodeProfile(display_name="Cerulean", initial="C", color="#0b7fc7", rank=1),
    "kveikur": NodeProfile(display_name="Kveikur", initial="V", color="#f28c1b", rank=2, address="192.168.20.46"),
}

# Avoids the green and purple already used for LXC and VM.
FALLBACK_PALETTE: Final[Tuple[str, ...]] = ("#d6457f", "#c9a100", "#5b6b7a", "#8a5a2b")


def profile_for_node(*, node_name: str) -> NodeProfile:
    """Configured profile, else a stable one so a new node keeps its color across restarts."""
    key: str = node_name.casefold()
    known: Optional[NodeProfile] = NODE_PROFILES.get(key)
    if known is not None:
        return known
    return NodeProfile(
        display_name=node_name[:1].upper() + node_name[1:],
        initial=node_name[:1].upper(),
        color=FALLBACK_PALETTE[zlib.crc32(key.encode("utf-8")) % len(FALLBACK_PALETTE)],
        rank=len(NODE_PROFILES),
    )


def node_sort_key(*, node_name: str) -> Tuple[int, str]:
    return (profile_for_node(node_name=node_name).rank, node_name.casefold())
