import ipaddress
import re
import zlib
from dataclasses import dataclass
from typing import Final, Optional, Union

from homelab_dashboard.models import Hardware, HardwareSource

ICELANDIC_NAME_MAP: Final[dict[str, str]] = {
    "ovedur": "óveður",
    "vardeldur": "varðeldur",
    "saeglopur": "sæglópur",
    "hoppipolla": "hoppípolla",
    "hafid": "hafið",
}
JAPANESE_NAME_MAP: Final[dict[str, str]] = {
    "ringo": "りんご",
    "suika": "すいか",
    "ichigo": "いちご",
    "saru": "さる",
}


def display_name_for(*, name: str) -> str:
    display_name: str = name
    if display_name.casefold().startswith("kp125m-"):
        display_name = "kp125m_" + display_name[len("kp125m-") :]
    for name_map in (ICELANDIC_NAME_MAP, JAPANESE_NAME_MAP):
        for source_name, replacement in name_map.items():
            display_name = re.sub(rf"(?<![A-Za-z]){re.escape(source_name)}", replacement, display_name, flags=re.IGNORECASE)
    return display_name


@dataclass(frozen=True, slots=True, kw_only=True)
class NodeProfile:
    display_name: str
    # one letter for the guest badge; set by hand because Kex and Kveikur both start with K
    initial: str
    color: str
    # shown, marked as expected, while the node can't be probed (e.g. it is offline)
    expected_cpu: Optional[str] = None
    memory_description: Optional[str] = None
    memory_ecc: Optional[bool] = None


NODE_PROFILES: Final[dict[str, NodeProfile]] = {
    "kex": NodeProfile(
        display_name="Kex",
        initial="K",
        color="#c62839",
        expected_cpu="Intel Xeon E5-1650 v4",
        memory_description="DDR4 RDIMM",
        memory_ecc=True,
    ),
    "cerulean": NodeProfile(
        display_name="Cerulean",
        initial="C",
        color="#0b7fc7",
        expected_cpu="Intel N150",
        memory_description="DDR4 SODIMM",
        memory_ecc=False,
    ),
    "kveikur": NodeProfile(
        display_name="Kveikur",
        initial="V",
        color="#f28c1b",
        expected_cpu="AMD Ryzen Threadripper PRO 3945WX",
        memory_description="DDR4 RDIMM",
        memory_ecc=True,
    ),
}

# avoids the green and purple already used for LXC and VM
FALLBACK_PALETTE: Final[tuple[str, ...]] = ("#d6457f", "#c9a100", "#5b6b7a", "#8a5a2b")


def profile_for_node(*, node_name: str) -> NodeProfile:
    """Configured profile, else a stable one so a new node keeps its color across restarts."""
    key: str = node_name.casefold()
    known: Optional[NodeProfile] = NODE_PROFILES.get(key)
    if known is not None:
        return known
    return NodeProfile(
        display_name=display_name_for(name=node_name),
        initial=node_name[:1].upper(),
        color=FALLBACK_PALETTE[zlib.crc32(key.encode("utf-8")) % len(FALLBACK_PALETTE)],
    )


def node_sort_key(*, node_name: str, address: Optional[str] = None) -> tuple[bool, int, int, str]:
    if address is None:
        return (True, 0, 0, node_name.casefold())
    try:
        parsed_address: Union[ipaddress.IPv4Address, ipaddress.IPv6Address] = ipaddress.ip_address(address)
    except ValueError:
        return (True, 0, 0, node_name.casefold())
    return (False, parsed_address.version, int(parsed_address), node_name.casefold())


def expected_hardware_for(*, node_name: str) -> Hardware:
    """What the profile says the node contains; unknown nodes report nothing rather than a guess."""
    profile: NodeProfile = profile_for_node(node_name=node_name)
    if profile.expected_cpu is None:
        return Hardware()
    return Hardware(
        cpu_model=profile.expected_cpu,
        source=HardwareSource.EXPECTED,
    )
