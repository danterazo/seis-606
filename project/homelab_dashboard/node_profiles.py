import ipaddress
import zlib
from dataclasses import dataclass
from typing import Final

from homelab_dashboard.models import Hardware, HardwareSource

# hardcode standardizations & display names
DISPLAY_NAMES: Final[dict[str, str]] = {
    "ovedur-10G": "óveður-10g",
    "creality-k1c-wifi": "varðeldur",
    "ringom4-wifi": "りんご-m4",
    "ringoa20": "りんご-a20",
    "suika": "すいか",
    "ichigo": "いちご",
    "saru": "さる",
}


def display_name_for(*, name: str) -> str:
    key: str = name.casefold()
    return next((display_name for hostname, display_name in DISPLAY_NAMES.items() if hostname.casefold() == key), name)


@dataclass(frozen=True, slots=True, kw_only=True)
class NodeProfile:
    display_name: str
    # One letter for the guest badge; set by hand because Kex and Kveikur both start with K.
    initial: str
    color: str
    # When set, shown instead of whatever Proxmox reports (offline nodes report none).
    address: str | None = None
    # Shown, marked as expected, while the node can't be probed (e.g. it is offline).
    expected_cpu: str | None = None
    memory_description: str | None = None
    memory_ecc: bool | None = None


NODE_PROFILES: Final[dict[str, NodeProfile]] = {
    "kex": NodeProfile(
        display_name=display_name_for(name="Kex"),
        initial="K",
        color="#c62839",
        address="192.168.20.42",
        expected_cpu="Intel Xeon E5-1650 v4",
        memory_description="DDR4 RDIMM",
        memory_ecc=True,
    ),
    "cerulean": NodeProfile(
        display_name=display_name_for(name="Cerulean"),
        initial="C",
        color="#0b7fc7",
        expected_cpu="Intel N150",
        memory_description="DDR4 SODIMM",
        memory_ecc=False,
    ),
    "kveikur": NodeProfile(
        display_name=display_name_for(name="Kveikur"),
        initial="V",
        color="#f28c1b",
        address="192.168.20.46",
        expected_cpu="AMD Ryzen Threadripper PRO 3945WX",
        memory_description="DDR4 RDIMM",
        memory_ecc=True,
    ),
}

# Avoids the green and purple already used for LXC and VM.
FALLBACK_PALETTE: Final[tuple[str, ...]] = ("#d6457f", "#c9a100", "#5b6b7a", "#8a5a2b")


def profile_for_node(*, node_name: str) -> NodeProfile:
    """Configured profile, else a stable one so a new node keeps its color across restarts."""
    key: str = node_name.casefold()
    known: NodeProfile | None = NODE_PROFILES.get(key)
    if known is not None:
        return known
    return NodeProfile(
        display_name=display_name_for(name=node_name[:1].upper() + node_name[1:]),
        initial=node_name[:1].upper(),
        color=FALLBACK_PALETTE[zlib.crc32(key.encode("utf-8")) % len(FALLBACK_PALETTE)],
    )


def node_sort_key(*, node_name: str, address: str | None = None) -> tuple[bool, int, int, str]:
    effective_address: str | None = profile_for_node(node_name=node_name).address or address
    if effective_address is None:
        return (True, 0, 0, node_name.casefold())
    try:
        parsed_address = ipaddress.ip_address(effective_address)
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
