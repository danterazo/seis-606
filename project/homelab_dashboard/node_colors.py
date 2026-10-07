import zlib
from typing import Dict, Final, Tuple, Union

NODE_COLORS: Final[Dict[str, str]] = {
    "cerulean": "#0b7fc7",
    "kex": "#800000",
    "kveikur": "#f28c1b",
}

# Avoids the green and purple already used for LXC and VM.
FALLBACK_PALETTE: Final[Tuple[str, ...]] = ("#d6457f", "#c9a100", "#5b6b7a", "#8a5a2b")


def color_for_node(*, node_name: str) -> str:
    """Configured color for the node, else a stable pick so a new node keeps its color across restarts."""
    key: str = node_name.casefold()
    configured: Union[str, None] = NODE_COLORS.get(key)
    if configured is not None:
        return configured
    return FALLBACK_PALETTE[zlib.crc32(key.encode("utf-8")) % len(FALLBACK_PALETTE)]
