import ipaddress
import re
import zlib
from dataclasses import dataclass
from typing import Final, Optional

from homelab_dashboard.models import Hardware, HardwareSource

JAPANESE_NAME_PARTS: Final[dict[str, str]] = {
    "ringo": "りんご",
    "suika": "すいか",
    "ichigo": "いちご",
    "saru": "さる",
}
ICELANDIC_NAME_PARTS: Final[dict[str, str]] = {
    "ovedur": "óveður",
    "vardeldur": "varðeldur",
    "saeglopur": "sæglópur",
    "hoppipolla": "hoppípolla",
}
PRODUCT_NAME_PREFIXES: Final[tuple[tuple[str, str], ...]] = (
    ("ecoflow-delta3-plus", "EcoFlow DELTA 3 Plus"),
    ("ecoflow", "EcoFlow DELTA 3 Plus"),
    ("delta3-plus", "EcoFlow DELTA 3 Plus"),
    ("delta3", "EcoFlow DELTA 3 Plus"),
    ("kp125m", "Kasa KP125M"),
)
PRODUCT_DEFAULT_PURPOSES: Final[dict[str, str]] = {"ecoflow": "Server Rack"}
CONNECTION_TYPES: Final[dict[str, str]] = {"wifi": "WiFi", "eth": "Eth"}


def display_name_for(*, name: str) -> str:
    hostname: str = name.strip()
    for prefix, product_name in PRODUCT_NAME_PREFIXES:
        product_prefix: Optional[re.Match[str]] = re.match(rf"^{re.escape(prefix)}(?:-|$)", hostname, flags=re.IGNORECASE)
        if product_prefix is None:
            continue
        remainder: str = hostname[product_prefix.end() :].strip("- ")
        if remainder:
            purpose: str = _format_hostname_words(name=remainder, parenthesize_codes=False)
            return f"{product_name} ({purpose})"
        default_purpose: Optional[str] = PRODUCT_DEFAULT_PURPOSES.get(prefix)
        if default_purpose is not None:
            return f"{product_name} ({default_purpose})"
        return product_name
    return _format_hostname_words(name=hostname, parenthesize_codes=True)


def _format_hostname_words(*, name: str, parenthesize_codes: bool) -> str:
    words: list[str] = []
    separated_name: str = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).replace("-", " ")
    for word in separated_name.split():
        if word.casefold() == "delta3":
            words.append("Delta3")
            continue
        model_suffix: Optional[re.Match[str]] = re.fullmatch(r"([A-Za-z]+?)([A-Za-z]\d+)", word)
        words.extend(model_suffix.groups() if model_suffix is not None else (word,))
    formatted_words: list[str] = []
    word_index: int = 0
    while word_index < len(words):
        word: str = words[word_index]
        if word.casefold() == "nerd" and word_index + 1 < len(words) and words[word_index + 1].casefold() == "qaxe":
            formatted_words.append("NerdQAxe++")
            word_index += 2
            continue
        if word.casefold() == "nerdqaxe":
            formatted_words.append("NerdQAxe++")
            word_index += 1
            continue
        japanese_name: Optional[str] = JAPANESE_NAME_PARTS.get(word.casefold())
        if japanese_name is not None:
            formatted_words.append(japanese_name)
        elif word == "Delta3":
            formatted_words.append(word)
        elif word.casefold() == "qaxe":
            formatted_words.append("QAxe")
        else:
            icelandic_name: Optional[str] = ICELANDIC_NAME_PARTS.get(word.casefold())
            if icelandic_name is not None:
                formatted_words.append(icelandic_name.title())
            elif word.casefold() in CONNECTION_TYPES:
                connection: str = CONNECTION_TYPES[word.casefold()]
                formatted_words.append(f"({connection})" if parenthesize_codes else connection)
            elif re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9]+", word):
                formatted_words.append(f"({word.upper()})" if parenthesize_codes else word.upper())
            elif word.isalpha() and len(word) == 2:
                formatted_words.append(word.upper())
            else:
                formatted_words.append(word.title())
        word_index += 1
    return " ".join(formatted_words)


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
        display_name=display_name_for(name="Kex"),
        initial="K",
        color="#c62839",
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
        display_name=display_name_for(name=node_name[:1].upper() + node_name[1:]),
        initial=node_name[:1].upper(),
        color=FALLBACK_PALETTE[zlib.crc32(key.encode("utf-8")) % len(FALLBACK_PALETTE)],
    )


def node_sort_key(*, node_name: str, address: Optional[str] = None) -> tuple[bool, int, int, str]:
    if address is None:
        return (True, 0, 0, node_name.casefold())
    try:
        parsed_address = ipaddress.ip_address(address)
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
